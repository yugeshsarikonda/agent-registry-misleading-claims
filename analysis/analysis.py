"""Rebuild every number reported in the paper from the released files.

Usage:  python analysis/analysis.py            (run from the release root)
Writes: results/*.csv and results/summary.json

Uncertainty: all intervals are central 95% percentile intervals from 10,000 bootstrap resamples of
TASKS (numpy default_rng, seed 0). All rotations of a task move together. In each resample, task
success is (total successes) / (total readable trials) over the resampled tasks. Paired differences
against a reference rate evaluate the reference on the same resampled tasks. Intervals are conditional
on the single calibration/evaluation split and on the claimed rates fitted to it.
"""
import json, os
from itertools import combinations
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RD = os.path.join(ROOT, "router_decisions")
OUT = os.path.join(ROOT, "results")
os.makedirs(OUT, exist_ok=True)
NB, SEED = 10_000, 0
PROV = ["P1", "P2", "P3", "P4"]


def rd(name):
    return pd.read_csv(os.path.join(RD, name))


def cluster_ci(df, ok="parsed", y="realised_correct", task="task_id"):
    """Task-clustered ratio bootstrap. Tasks with no readable trial stay in as 0/0 clusters."""
    d = df[df[ok] == 1]
    g = d.groupby(task)[y].agg(["sum", "count"]).reindex(df[task].unique()).fillna(0)
    s, n = g["sum"].to_numpy(), g["count"].to_numpy()
    idx = np.random.default_rng(SEED).integers(0, len(s), (NB, len(s)))
    est = 100 * s[idx].sum(1) / n[idx].sum(1)
    return dict(success=round(100 * s.sum() / n.sum(), 2), lo=round(float(np.percentile(est, 2.5)), 2),
                hi=round(float(np.percentile(est, 97.5)), 2), n_readable=int(n.sum()), n_attempted=len(df))


def paired_ci(df, ref_by_task, ok="parsed", y="realised_correct"):
    d = df[df[ok] == 1]
    g = d.groupby("task_id")[y].agg(["sum", "count"]).reindex(df.task_id.unique()).fillna(0)
    r = ref_by_task.reindex(g.index).to_numpy()
    s, n = g["sum"].to_numpy(), g["count"].to_numpy()
    idx = np.random.default_rng(SEED).integers(0, len(s), (NB, len(s)))
    diff = 100 * (s[idx].sum(1) / n[idx].sum(1) - r[idx].mean(1))
    return dict(diff=round(100 * (s.sum() / n.sum() - r.mean()), 2),
                lo=round(float(np.percentile(diff, 2.5)), 2), hi=round(float(np.percentile(diff, 97.5)), 2))


def share(df, provider, ok="parsed", col="chosen_provider"):
    d = df[df[ok] == 1]
    return int((d[col] == provider).sum()), len(d)


# ---------------------------------------------------------------- providers and split
comp = pd.read_csv(os.path.join(ROOT, "provider_outputs", "pop2_competence.csv"))
split = json.load(open(os.path.join(ROOT, "tasks", "heldout_split.json")))
TH = comp.pivot(index="task_id", columns="provider", values="correct").astype(float)
CAL, EVAL = split["calibration"], split["evaluation"]
summary = {
    "measured_all59": {p: round(100 * TH[p].mean(), 2) for p in PROV},
    "measured_heldout": {p: round(100 * TH.loc[EVAL, p].mean(), 2) for p in PROV},
    "claimed_heldout_jeffreys": {p: round(100 * (TH.loc[CAL, p].sum() + 0.5) / (len(CAL) + 1), 1) for p in PROV},
}
UNIF_TASK = TH.mean(1)
summary["uniform_all59"] = round(100 * UNIF_TASK.mean(), 2)
summary["uniform_heldout"] = round(100 * UNIF_TASK.loc[EVAL].mean(), 2)

# ---------------------------------------------------------------- Table 1 and Figure 1a,b
pop, ho, gp = rd("pop2_arms.csv"), rd("heldout_trials.csv"), rd("heldout_router_gpt4o.csv")
rep = rd("router_replication.csv")
T1 = []
for cond, a59, aho, exag in [("all honest", "honest", "honest-J", None),
                             ("strongest exaggerates", "deviation-best", "deviation-best-J", "P1"),
                             ("all exaggerate", "pooling", "pooling", None),
                             ("weakest exaggerates", "deviation-weakest", "deviation-weakest-J", "P4")]:
    for setting, df in [("all59 sonnet", pop[pop.arm == a59]), ("heldout sonnet", ho[ho.arm == aho]),
                        ("heldout gpt-4o", gp[gp.arm == aho])]:
        row = dict(condition=cond, setting=setting, **cluster_ci(df))
        if exag:
            k, n = share(df, exag); row["exaggerator_assignments"] = f"{k}/{n}"
        T1.append(row)
T1 = pd.DataFrame(T1); T1.to_csv(os.path.join(OUT, "table1_market.csv"), index=False)

pairs = {
    "heldout sonnet weakest vs uniform": paired_ci(ho[ho.arm == "deviation-weakest-J"], UNIF_TASK),
    "heldout gpt-4o weakest vs uniform": paired_ci(gp[gp.arm == "deviation-weakest-J"], UNIF_TASK),
    "all59 sonnet weakest vs uniform": paired_ci(pop[pop.arm == "deviation-weakest"], UNIF_TASK),
    "all59 opus weakest vs uniform": paired_ci(rep[(rep.router == "opus-5") & (rep.arm == "deviation-weakest")],
                                               UNIF_TASK, ok="parsed_ok", y="correct"),
    "all59 opus weakest vs best-provider": paired_ci(rep[(rep.router == "opus-5") & (rep.arm == "deviation-weakest")],
                                                     TH["P1"], ok="parsed_ok", y="correct"),
}
summary["paired_differences"] = pairs

fig1b = []
for p, arm in [("P1", "deviation-best-J"), ("P2", "deviation-P2-J"), ("P3", "deviation-P3-J"), ("P4", "deviation-weakest-J")]:
    df = ho[ho.arm == arm]; k, n = share(df, p)
    fig1b.append(dict(provider=p, theta_heldout=summary["measured_heldout"][p], assignments=f"{k}/{n}",
                      share_pct=round(100 * k / n, 2), **cluster_ci(df)))
pd.DataFrame(fig1b).to_csv(os.path.join(OUT, "fig1b_single_exaggerator.csv"), index=False)

# all-59 P2/P3 alone (30-task subsets)
summary["all59_single"] = {a: cluster_ci(pop[pop.arm == a]) for a in ["deviation-P2", "deviation-P3"]}
summary["boundary_raw_calibration"] = dict(**cluster_ci(ho[ho.arm == "deviation-weakest"]),
                                           P4_assignments="%d/%d" % share(ho[ho.arm == "deviation-weakest"], "P4"))

# ---------------------------------------------------------------- RQ3 deposit: all 16 listing profiles
prof = pd.concat([ho, rd("heldout_deposit_profiles.csv"), rd("heldout_deposit_profiles_extra.csv")], ignore_index=True)
ARM = {frozenset(): "honest-J", frozenset({"P1"}): "deviation-best-J", frozenset({"P2"}): "deviation-P2-J",
       frozenset({"P3"}): "deviation-P3-J", frozenset({"P4"}): "deviation-weakest-J", frozenset(PROV): "pooling"}
for k in range(2, 4):
    for S in combinations(PROV, k):
        ARM[frozenset(S)] = "deposit-" + "".join(S) + "-J"
EV = sorted(EVAL); TIX = {t: i for i, t in enumerate(EV)}


def profile_counts(fs):
    d = prof[(prof.arm == ARM[fs]) & (prof.parsed == 1)]
    K = np.zeros((len(EV), 4)); F = np.zeros((len(EV), 4)); N = np.zeros(len(EV))
    for r in d.itertuples():
        j = PROV.index(r.chosen_provider)
        K[TIX[r.task_id], j] += 1; F[TIX[r.task_id], j] += (r.realised_correct == 0); N[TIX[r.task_id]] += 1
    return K, F, N


C = {fs: profile_counts(fs) for fs in ARM}
rows = []
for fs in sorted(ARM, key=lambda s: (len(s), sorted(s))):
    K, F, N = C[fs]
    row = dict(exaggerating="+".join(sorted(fs)) or "none", condition=ARM[fs], **cluster_ci(prof[prof.arm == ARM[fs]]))
    for j, p in enumerate(PROV):
        row[f"{p}_assignments"] = int(K[:, j].sum()); row[f"{p}_failures"] = int(F[:, j].sum())
    rows.append(row)
pd.DataFrame(rows).to_csv(os.path.join(OUT, "deposit_profiles.csv"), index=False)


def earnings(p, fs, B, rule, idx):
    """Earnings per readable trial, fee = 1. 'claim': only exaggerated listings forfeit B on a failed
    assignment. 'all': every provider forfeits B on a failed assignment."""
    K, F, N = C[frozenset(fs)]; j = PROV.index(p)
    pays = (p in fs) if rule == "claim" else True
    return (K[idx, j].sum() - (B * F[idx, j].sum() if pays else 0)) / N[idx].sum()


def stable(fs, B, rule, idx):
    """No provider gains by switching its own listing, and no provider earns less than the outside
    option of leaving (0). The market after a provider leaves is not observed and not modelled."""
    for p in PROV:
        here = earnings(p, fs, B, rule, idx)
        if earnings(p, set(fs) ^ {p}, B, rule, idx) > here + 1e-12 or here < -1e-12:
            return False
    return True


ALLIDX = np.arange(len(EV))
grid = np.round(np.arange(0, 6.0001, 0.01), 2)
eq_rows = []
for rule in ["claim", "all"]:
    prev, start = None, 0.0
    for b in grid:
        e = tuple(sorted("+".join(sorted(fs)) or "none" for fs in ARM if stable(fs, b, rule, ALLIDX)))
        if e != prev:
            if prev is not None:
                eq_rows.append(dict(rule=rule, B_from=start, B_to=b, stable_profiles=" | ".join(prev) or "(none)"))
            prev, start = e, b
    eq_rows.append(dict(rule=rule, B_from=start, B_to=6.0, stable_profiles=" | ".join(prev) or "(none)"))
pd.DataFrame(eq_rows).to_csv(os.path.join(OUT, "deposit_equilibria.csv"), index=False)


def boundaries(idx):
    def kfn(fs, p):
        K, F, N = C[frozenset(fs)]; j = PROV.index(p); return K[idx, j].sum(), F[idx, j].sum(), N[idx].sum()
    out = {}
    k, f, _ = kfn(PROV, "P4"); out["P4 stops exaggerating (from all exaggerate)"] = k / f if f else np.inf
    k, f, _ = kfn({"P1", "P2", "P3"}, "P3"); out["P3 stops exaggerating"] = k / f if f else np.inf
    k, f, n = kfn({"P1", "P2"}, "P2"); kh, _, nh = kfn({"P1"}, "P2")
    out["P2 stops exaggerating (claim rule)"] = (k / n - kh / nh) / (f / n) if f else np.inf
    k, f, _ = kfn({"P2"}, "P2"); out["all-honest listings stable from"] = k / f if f else np.inf
    return out


pt = boundaries(ALLIDX)
rng = np.random.default_rng(SEED)
bs = [boundaries(rng.integers(0, len(EV), len(EV))) for _ in range(NB)]
summary["deposit_boundaries"] = {k: dict(B=round(v, 2), lo=round(float(np.percentile([b[k] for b in bs], 2.5)), 2),
                                         hi=round(float(np.percentile([b[k] for b in bs], 97.5)), 2)) for k, v in pt.items()}
uni = {}
for p in ["P2", "P3", "P4"]:
    K, F, N = C[frozenset({p})]; j = PROV.index(p)
    uni[p] = dict(assignments=int(K[:, j].sum()), failures=int(F[:, j].sum()), threshold=round(K[:, j].sum() / F[:, j].sum(), 2),
                  formula_1_over_1_minus_theta=round(1 / (1 - summary["measured_heldout"][p] / 100), 2))
summary["unilateral_thresholds"] = uni

# displayed (uncollected) deposit: P4 share on the same 20 tasks, task-clustered
base = pop[pop.arm == "deviation-weakest"]
disp = {}
for arm in ["deviation-weakest+bond1", "deviation-weakest+bond4"]:
    x = pop[pop.arm == arm]; tasks = sorted(set(x.task_id))

    def agg(df):
        d = df[(df.parsed == 1) & (df.task_id.isin(tasks))]
        g = d.assign(k=(d.chosen_provider == "P4").astype(int)).groupby("task_id").k.agg(["sum", "count"])
        return g.reindex(tasks).fillna(0)
    gx, gz = agg(x), agg(base)
    idx = np.random.default_rng(SEED).integers(0, len(tasks), (NB, len(tasks)))
    dd = 100 * (gx["sum"].to_numpy()[idx].sum(1) / gx["count"].to_numpy()[idx].sum(1)
                - gz["sum"].to_numpy()[idx].sum(1) / gz["count"].to_numpy()[idx].sum(1))
    disp[arm] = dict(tasks=len(tasks), displayed=f"{int(gx['sum'].sum())}/{int(gx['count'].sum())}",
                     not_displayed_same_tasks=f"{int(gz['sum'].sum())}/{int(gz['count'].sum())}",
                     diff=round(100 * (gx['sum'].sum() / gx['count'].sum() - gz['sum'].sum() / gz['count'].sum()), 2),
                     lo=round(float(np.percentile(dd, 2.5)), 2), hi=round(float(np.percentile(dd, 97.5)), 2))
summary["displayed_deposit"] = disp

# ---------------------------------------------------------------- RQ4 checking
hs = rd("heldout_screening.csv")
T2 = []
for pol in ["check_best_observed", "check_random", "check_worst_observed"]:
    g = hs[hs.policy == pol]; r = g[g.parsed == 1]; n = len(r)
    T2.append(dict(policy=pol, **cluster_ci(g), chose_checked=f"{int(r.chose_checked.sum())}/{n}",
                   chose_P1=f"{int((r.chosen_provider == 'P1').sum())}/{n}", first_position=f"{int((r.chosen_slot == 'A').sum())}/{n}"))
pd.DataFrame(T2).to_csv(os.path.join(OUT, "table2_checking.csv"), index=False)
burn = rd("burnin_trials.csv")
summary["observation_period"] = {p: dict(assignments=int((burn.chosen_provider == p).sum()),
                                         observed_pct=round(100 * burn[burn.chosen_provider == p].correct.mean(), 1)) for p in PROV}
scr = rd("pop2_screening.csv"); scr = scr[scr.run == "primary"]
summary["checking_all59"] = {a: cluster_ci(scr[scr.arm == a]) for a in ["attest_best_v25", "attest_random_v25", "attest_loudest_v25"]}
summary["paired_differences"]["heldout check worst observed vs uniform"] = paired_ci(hs[hs.policy == "check_worst_observed"], UNIF_TASK)
summary["paired_differences"]["all59 check largest claim vs uniform"] = paired_ci(scr[scr.arm == "attest_loudest_v25"], UNIF_TASK)

cov = []
for (N_, v), g in rd("scale_results.csv").groupby(["N", "v"]):
    cov.append(dict(N=N_, v=v, **cluster_ci(g, ok="parse_ok", y="realised_success")))
pd.DataFrame(cov).to_csv(os.path.join(OUT, "coverage_sweep.csv"), index=False)

# ---------------------------------------------------------------- RQ5 routers
ro = rep[rep.router == "opus-5"]
summary["opus"] = {a: cluster_ci(ro[ro.arm == a], ok="parsed_ok", y="correct") for a in ["honest", "pooling", "deviation-weakest"]}
dw = ro[(ro.arm == "deviation-weakest") & (ro.parsed_ok == 1)]
summary["opus_position"] = {f"P4 listed {s}": f"{int((g.chosen_provider == 'P4').sum())}/{len(g)}" for s, g in dw.groupby("p4_slot")}
summary["opus_P4_assignments"] = f"{int((dw.chosen_provider == 'P4').sum())}/{len(dw)}"

json.dump(summary, open(os.path.join(OUT, "summary.json"), "w"), indent=1, default=str)
if __name__ == "__main__":
    print(T1.to_string(index=False))
    print(json.dumps(summary["paired_differences"], indent=1))
    print(pd.DataFrame(eq_rows).to_string(index=False))
