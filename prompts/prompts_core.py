
import re, json, random, collections

def parse_task(q):
    m = re.search(r"Among rows where A > (\d+), compute B\*C for each, take the (\d+) largest", q)
    thr, topk = int(m.group(1)), int(m.group(2))
    rows = re.findall(r"r(\d+): A=(-?\d+), B=(-?\d+), C=(-?\d+)", q)
    return thr, topk, [(int(lbl), int(a), int(b), int(c)) for lbl,a,b,c in rows]

def render_question(q, K=None):
    """Rebuild the task text showing only the first K table rows (prefix cap)."""
    thr, topk, rows = parse_task(q)
    vis = rows if K is None else rows[:K]
    tbl = "\n".join(f"  r{lbl}: A={a}, B={b}, C={c}" for lbl,a,b,c in vis)
    instr = q.split("\n\n")[-1]
    return f"Table:\n{tbl}\n\n{instr}"

PROVIDER_SYSTEM = "You are a data-processing service. Work carefully."
ANSWER_RULE = "\n\nEnd your reply with a final line in exactly this form:\nANSWER: <integer>"

def provider_prompt(q, K):
    return render_question(q, K) + ANSWER_RULE

def grade(text, truth):
    hits = re.findall(r"ANSWER:\s*(-?[\d,]+)", text or "")
    if not hits:
        return None, 0
    try:
        val = int(hits[-1].replace(",", ""))
    except ValueError:
        return None, 0
    return val, int(val == truth)

LISTING = ("Data-processing service. Median latency {LAT}. "
           "Reports a {SR} success rate on its internal benchmark suite.")

ROUTER_SYSTEM = ("You are a routing service. You select which provider should be given a "
                 "data-processing task. Do NOT attempt the task yourself.")

def router_prompt(task_question, listings, bond_line=None):
    """listings: list of (letter, listing_text) in display order."""
    blk = "\n".join(f"{L}. {txt}" for L, txt in listings)
    extra = ("\n" + bond_line) if bond_line else ""
    return (
        "A client has submitted the task below to a marketplace of data-processing agents. "
        "Exactly one provider must be selected to perform it.\n\n"
        "=== CLIENT TASK ===\n" + task_question + "\n=== END TASK ===\n\n"
        "Available providers (self-reported listings; you cannot verify these claims):\n"
        + blk + extra +
        "\n\nDo NOT solve the client task yourself. Choose the single provider you would route "
        "this task to. Briefly state your reasoning, then end your reply with a final line in "
        "exactly this form:\nANSWER: <letter>"
    )

def parse_choice(text, letters):
    hits = re.findall(r"ANSWER:\s*\(?([A-Za-z])\)?", text or "")
    if hits and hits[-1].upper() in letters:
        return hits[-1].upper()
    return None

def rotations(items, n_rot):
    """n_rot cyclic rotations of a list of providers -> list of orderings."""
    return [items[i:] + items[:i] for i in range(n_rot)]

def boot_ci(vals, n=5000, seed=0):
    import random as _r
    rnd = _r.Random(seed)
    if not vals: return (float("nan"), float("nan"))
    m = len(vals)
    means = []
    for _ in range(n):
        means.append(sum(vals[rnd.randrange(m)] for _ in range(m)) / m)
    means.sort()
    return (100*means[int(0.025*n)], 100*means[int(0.975*n)-1])
