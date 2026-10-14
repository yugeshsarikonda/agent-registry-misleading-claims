"""Rebuild the paper's three figures from results/ (run analysis.py first) and rq1/rq1_counts.json.

Usage:  python analysis/make_figures.py        (run from the release root)
Writes: figures/fig_heldout.png, figures/fig2_claims.png, figures/fig4_checking.png
"""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results"); FIG = os.path.join(ROOT, "figures"); os.makedirs(FIG, exist_ok=True)
BLUE, ORANGE, GREY, DARK = "#1b6ca8", "#c9781e", "#808080", "#444444"
plt.rcParams.update({"font.size": 8.0, "axes.titlesize": 8.0, "axes.labelsize": 8.0, "xtick.labelsize": 7.2,
                     "ytick.labelsize": 7.2, "legend.fontsize": 7.2, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.linewidth": 0.7, "savefig.dpi": 400, "font.family": "DejaVu Sans"})
ANN = 6.8
S = json.load(open(os.path.join(RES, "summary.json")))
T1 = pd.read_csv(os.path.join(RES, "table1_market.csv"))
B1 = pd.read_csv(os.path.join(RES, "fig1b_single_exaggerator.csv"))
DPF = pd.read_csv(os.path.join(RES, "deposit_profiles.csv")).set_index("exaggerating")
BEST, UNIF = S["measured_heldout"]["P1"], S["uniform_heldout"]


def letter(ax, s):
    ax.text(-0.16, 1.10, s, transform=ax.transAxes, fontsize=10, fontweight="bold", va="bottom")


# ------------------------------------------------------------------ paper Figure 2 (fig_heldout.png)
fig, ax = plt.subplots(1, 3, figsize=(6.4, 2.9))
a = ax[0]; conds = ["all honest", "strongest exaggerates", "all exaggerate", "weakest exaggerates"]
labels = ["all honest", "strongest\nexaggerates", "all\nexaggerate", "weakest\nexaggerates"]
for i, c in enumerate(conds):
    y = len(conds) - 1 - i
    for setting, col, dy, lab in [("heldout sonnet", BLUE, 0.13, "claude-sonnet-5"), ("heldout gpt-4o", ORANGE, -0.13, "gpt-4o")]:
        r = T1[(T1.condition == c) & (T1.setting == setting)].iloc[0]
        a.plot([r.lo, r.hi], [y + dy] * 2, color=col, lw=1.6, alpha=0.55)
        a.plot(r.success, y + dy, "o", color=col, ms=4.5, label=lab if i == 0 else None)
a.axvline(UNIF, ls=(0, (1, 2)), color=GREY, lw=1); a.axvline(BEST, ls=(0, (4, 3)), color=GREY, lw=1)
a.text(UNIF - 1.5, -0.78, "uniform", fontsize=ANN, color=GREY, ha="right", va="center")
a.text(BEST - 1.5, -0.78, "best", fontsize=ANN, color=GREY, ha="right", va="center")
a.set_yticks(range(4)); a.set_yticklabels(labels[::-1]); a.set_xlim(10, 104); a.set_ylim(-1.0, 4.15)
a.set_xlabel("task success (%)"); a.legend(frameon=False, loc="upper left", handletextpad=0.2, borderaxespad=0.1)
a.set_title("A weak provider exaggerating\npulls routers below uniform", loc="left"); letter(a, "a")

b = ax[1]
for r in B1.itertuples():
    b.plot([r.theta_heldout] * 2, [r.lo, r.hi], color=BLUE, lw=1.6, alpha=0.55)
    b.plot(r.theta_heldout, r.success, "o", color=BLUE, ms=4.5)
    b.text(r.theta_heldout + 2.5, r.success - 6.5, r.provider, fontsize=ANN, color=DARK)
b.plot([25, 100], [25, 100], ls=(0, (4, 3)), color=GREY, lw=1)
b.text(98, 24, "dashed line: equal", fontsize=ANN, color=GREY, ha="right", va="bottom")
b.set_xlim(25, 102); b.set_ylim(20, 102)
b.set_xlabel("measured success rate of the\nprovider that exaggerates (%)"); b.set_ylabel("task success (%)")
b.set_title("Task success follows the\nprovider that exaggerates", loc="left"); letter(b, "b")

c = ax[2]
eq = [(0.00, 1.45, "P1+P2+P3+P4"), (1.45, 1.93, "P1+P2+P3"), (1.93, 3.37, "P1+P2"), (3.56, 4.6, "none")]
for i, (lo, hi, key) in enumerate(eq):
    r = DPF.loc[key]
    c.fill_between([lo, hi], r.lo, r.hi, color=BLUE, alpha=0.13, lw=0)
    c.plot([lo, hi], [r.success] * 2, color=BLUE, lw=2.2, label="stable listings" if i == 0 else None)
c.axvspan(3.37, 3.56, color=GREY, alpha=0.18, lw=0)
c.text(3.465, 30, "none stable", fontsize=6.3, color=DARK, rotation=90, ha="center", va="bottom")
imp = [(0, 1.48, "P2+P3+P4"), (1.48, 1.88, "P2+P3"), (1.88, 3.56, "P2"), (3.56, 4.6, "none")]
for i, (lo, hi, key) in enumerate(imp):
    c.plot([lo, hi], [DPF.loc[key].success] * 2, color=GREY, lw=1.0, ls=(0, (3, 2)),
           label="if P1 stayed honest" if i == 0 else None)
c.axhline(UNIF, ls=(0, (1, 2)), color=GREY, lw=0.9)
c.text(4.55, UNIF + 1.2, "uniform rate", fontsize=ANN, color=GREY, ha="right")
c.set_xlim(0, 4.6); c.set_ylim(28, 112); c.set_xlabel("deposit $B$ (task fees)"); c.set_ylabel("task success (%)")
c.legend(frameon=False, loc="upper left", handlelength=1.6, borderaxespad=0.1)
c.set_title("Task success rises with the\ndeposit when providers respond", loc="left"); letter(c, "c")
fig.tight_layout(w_pad=2.2); fig.savefig(os.path.join(FIG, "fig_heldout.png"), bbox_inches="tight")

# ------------------------------------------------------------------ paper Figure 1 (fig2_claims.png, RQ1 counts)
R = json.load(open(os.path.join(ROOT, "rq1", "rq1_counts.json")))
pct = lambda d: [100 * d["selected_by_level"][str(l)] / d["n"] for l in range(4)]
f2, a2 = plt.subplots(1, 2, figsize=(7.0, 2.6))
x = range(4); sup, num, ext = pct(R["superlatives_equal_length"]), pct(R["numerical_claims"]), pct(R["extreme_claim"])
a2[0].plot(x, sup, "o-", color=BLUE, ms=4.5, lw=1.7); a2[0].plot(x, num, "o-", color=ORANGE, ms=4.5, lw=1.7)
a2[0].text(2.7, num[3] - 6, "numerical claims", color=ORANGE, fontsize=ANN, ha="right")
a2[0].text(2.95, sup[3] + 7, "superlatives", color=BLUE, fontsize=ANN, ha="right")
a2[0].axhline(25, ls=(0, (4, 3)), color=GREY, lw=1); a2[0].text(0.05, 27.5, "equal shares", fontsize=ANN, color=GREY)
a2[0].set_xticks(list(x)); a2[0].set_xlabel("exaggeration level (0 = plain)"); a2[0].set_ylabel("share of assignments (%)")
a2[0].set_ylim(-5, 100); a2[0].set_title("Numerical claims gain assignments;\nsuperlatives lose them", loc="left"); letter(a2[0], "a")
a2[1].plot(x, ext, "o-", color=ORANGE, ms=4.5, lw=1.7); a2[1].axhline(25, ls=(0, (4, 3)), color=GREY, lw=1)
a2[1].set_xticks(list(x)); a2[1].set_xticklabels([R["extreme_claim"]["levels"][str(l)].replace(" / ", "\n") for l in range(4)])
a2[1].set_xlabel("claimed success rate and response time"); a2[1].set_ylabel("share of assignments (%)")
a2[1].set_ylim(-5, 100); a2[1].set_title("The most extreme claim falls back\nto an equal share", loc="left"); letter(a2[1], "b")
f2.tight_layout(w_pad=2.0); f2.savefig(os.path.join(FIG, "fig2_claims.png"), bbox_inches="tight")

# ------------------------------------------------------------------ paper Figure 3 (fig4_checking.png, checking sweep)
CV = pd.read_csv(os.path.join(RES, "coverage_sweep.csv"))
f4, a4 = plt.subplots(figsize=(3.6, 2.7)); COL = {4: BLUE, 8: ORANGE, 16: DARK}
for N_, g in CV.groupby("N"):
    g = g.sort_values("v")
    a4.fill_between(g.v, g.lo, g.hi, color=COL[N_], alpha=0.10, lw=0)
    a4.plot(g.v, g.success, "o-", color=COL[N_], ms=3.8, lw=1.5, label=f"$N={N_}$")
a4.axhline(100, ls=(0, (4, 3)), color=GREY, lw=1); a4.text(0.02, 101.3, "best-provider rate", fontsize=ANN, color=GREY)
a4.axvline(0.5, ls=(0, (1, 2)), color=GREY, lw=1)
a4.set_xlabel("fraction of listings checked, $v$"); a4.set_ylabel("task success (%)"); a4.set_ylim(40, 106)
a4.legend(frameon=False, loc="lower right"); a4.set_title("Checking half the listings stays below\nthe best-provider rate", loc="left")
f4.tight_layout(); f4.savefig(os.path.join(FIG, "fig4_checking.png"), bbox_inches="tight")
print("figures written to", FIG)
