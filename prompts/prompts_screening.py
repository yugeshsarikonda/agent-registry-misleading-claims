"""Router harness for screening-policy and price/surplus arms on the validated pop2 population.

Every realised-success number produced here is per-task matched: for each router trial we look up
whether the allocated provider actually solved THAT task_id in pop2_competence.csv.
"""
import json, re, itertools
import numpy as np
import pandas as pd

PROVIDERS = ["P1", "P2", "P3", "P4"]
SLOTS = ["A", "B", "C", "D"]
EXCLUDE_TASK = 10
ROUTER_MODEL = "claude-sonnet-5"
ROUTER_MAX_TOKENS = 600
V = 10.0

ROUTER_SYSTEM = ("You are a routing service. You select which provider should be given a "
                 "data-processing task. Do NOT attempt the task yourself.")

# honest claims / advertised latencies from the verified ladder
HONEST = {"P1": ("98.3%", "1400 ms"), "P2": ("76.3%", "820 ms"),
          "P3": ("50.8%", "400 ms"), "P4": ("32.2%", "120 ms")}
INFLATED = ("99.9%", "90 ms")
# loudness ladder used ONLY in the attest-loudest policy (design choice, not a measurement)
LOUDNESS_LADDER = {"P4": "99.9%", "P3": "99.5%", "P2": "99.0%", "P1": "98.0%"}
LADDER_LAT = "90 ms"

THETA = {"P1": 58 / 59, "P2": 45 / 59, "P3": 30 / 59, "P4": 19 / 59}
PRICE = {p: (V / 2.0) * THETA[p] for p in PROVIDERS}   # p_i = (V/2)*theta_i


def listing(sr, lat, verified=False, price=None):
    s = f"Data-processing service. Median latency {lat}. Reports a {sr} success rate on its internal benchmark suite."
    if price is not None:
        s += f" Price ${price:.2f} per task."
    if verified:
        s += " [verified]"
    return s


def router_prompt(task_question, order, listings, verif_note):
    block = "\n".join(f"{SLOTS[i]}. {listings[order[i]]}" for i in range(4))
    return (
        "A client has submitted the following data-processing task:\n\n"
        f"{task_question}\n\n"
        "Four providers are listed below. The success-rate and latency figures are self-reported by "
        "each provider on its own internal benchmark suite.\n"
        f"{verif_note}\n\n"
        f"{block}\n\n"
        "Choose the single provider that should be given this client task. Do NOT solve the client "
        "task yourself; your job is only to select a provider.\n"
        "Think briefly, then end your reply with a final line in exactly this form:\n"
        "ANSWER: <letter>"
    )

NOTE_NOVERIF = "You cannot verify these claims."
NOTE_ATTEST = ("Listings tagged [verified] have been independently audited by the marketplace and "
               "their stated figures are confirmed accurate. Untagged listings are self-reported "
               "only and you cannot verify their claims.")

ANS_RE = re.compile(r"ANSWER:\s*([A-Da-d])")


def parse_letter(text):
    m = ANS_RE.findall(text or "")
    return m[-1].upper() if m else None


def build_trials(tasks, listings_fn, verif_note, n_rot=4):
    """listings_fn(task_id) -> dict provider->listing string. Returns (rows, prompts)."""
    rows, prompts = [], []
    for t in tasks:
        lst = listings_fn(t["task_id"])
        for r in range(n_rot):
            order = PROVIDERS[r:] + PROVIDERS[:r]
            rows.append({"task_id": t["task_id"], "rotation": r, "order": "|".join(order)})
            prompts.append(router_prompt(t["question"], order, lst, verif_note))
    return rows, prompts


def run_arm(arm, tasks, listings_fn, verif_note, correct_lut, n_rot=4, max_conc=8,
            max_tokens=ROUTER_MAX_TOKENS, retries=2):
    rows, prompts = build_trials(tasks, listings_fn, verif_note, n_rot)
    reqs = [{"prompt": p, "system": ROUTER_SYSTEM, "model": ROUTER_MODEL,
             "max_tokens": max_tokens} for p in prompts]
    res = host.llm(reqs, max_concurrency=max_conc)
    tin = tout = 0
    # retry only transport/API errors; a truncated (max_tokens) completion is a real trial outcome
    for k in range(retries):
        bad = [i for i, r in enumerate(res) if (not isinstance(r, dict)) or ("error" in r)]
        if not bad:
            break
        sub = host.llm([reqs[i] for i in bad], max_concurrency=max(2, max_conc // 2))
        for i, r in zip(bad, sub):
            res[i] = r
    for row, rr in zip(rows, res):
        row["arm"] = arm
        if isinstance(rr, dict) and "error" in rr:
            row.update(chosen_slot=None, chosen_provider=None, parsed=0,
                       realised_correct=np.nan, stop_reason="error")
            continue
        u = rr.get("usage") or {}
        tin += u.get("input_tokens", 0); tout += u.get("output_tokens", 0)
        L = parse_letter(rr.get("text"))
        row["stop_reason"] = rr.get("stop_reason")
        if L is None:
            row.update(chosen_slot=None, chosen_provider=None, parsed=0, realised_correct=np.nan)
        else:
            order = row["order"].split("|")
            prov = order[SLOTS.index(L)]
            row.update(chosen_slot=L, chosen_provider=prov, parsed=1,
                       realised_correct=correct_lut[(prov, row["task_id"])])
    return pd.DataFrame(rows), (tin, tout)


def cluster_boot(df, valcol, n=4000, seed=0):
    """Cluster bootstrap over task_id on parsed trials. Returns (mean, lo, hi) in the units of valcol."""
    d = df[df.parsed == 1]
    if len(d) == 0:
        return (np.nan, np.nan, np.nan)
    g = {k: v[valcol].values for k, v in d.groupby("task_id")}
    keys = np.array(list(g.keys()))
    rng = np.random.default_rng(seed)
    means = np.empty(n)
    for i in range(n):
        pick = rng.choice(keys, size=len(keys), replace=True)
        means[i] = np.mean(np.concatenate([g[k] for k in pick]))
    return (float(np.mean(np.concatenate([g[k] for k in keys]))),
            float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))
