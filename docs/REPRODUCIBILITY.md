# Verifying the released analysis

The release records a fixed experiment on generated table tasks. Its data support
offline numerical reproduction. They do not support an exact replay of hosted
model requests or claims about trading performance or a deployed marketplace.

## One verification command

From the repository root, after installing `requirements.txt` in a Python 3.11
environment:

```sh
python analysis/verify_release.py --regenerate
```

The command first validates the original snapshot, then runs `analysis.py` in a
temporary directory. The temporary copy is removed on success or failure. The
reference `results/` files remain unchanged. A mismatch reports its file and
field and returns a nonzero exit status. The analysis subprocess has a 180-second
timeout. No API keys, model requests, GPU or network access are used by the
verification command. Dependency installation requires package access first.

`python analysis/verify_release.py` omits regeneration and uses only Python's
standard library. It verifies the bytes and recorded relationships, not a fresh
execution of the statistical analysis.

## Checks and expected counts

| Check | Current release |
| --- | --- |
| SHA-256 snapshot | 30 frozen analysis, prompt, data and numerical result files |
| Provider measurements | 59 tasks with one record per provider, P1 through P4 |
| Calibration and evaluation | 30 calibration tasks and 29 evaluation tasks, disjoint and covering all measured tasks |
| Held-out routing | 5 CSV files restricted to evaluation task IDs |
| Observation period | `burnin_trials.csv` restricted to calibration task IDs |
| Readable choices | Chosen slot, displayed provider order and provider identity agree |
| Recorded outcomes | Provider answers agree with recorded ground truth, and readable router outcomes agree with those provider measurements |
| Unreadable trials | Retained in attempted counts, separately reported from readable counts |
| Regenerated outputs | 6 CSV tables and `results/summary.json` |

The ground-truth bank contains 60 tasks. Task 10 has no measurements in
`pop2_competence.csv` and is outside both split groups. The verifier reports this
explicitly. The released records do not establish why it was omitted, so no
reason is inferred here. This discrepancy should be resolved from experiment
notes before describing all 60 generated tasks as evaluated.

The held-out screening file has 348 attempted trials and 337 readable trials.
Reported success rates condition on readability, as documented in the root
README. They should not be described as success rates over every attempted
trial. The checker reports both denominators rather than changing the estimand.

## Provenance and integrity

`SHA256SUMS.json` records the SHA-256 digest of each frozen analysis input,
analysis script and saved numerical output present at baseline commit
`db19f2317f3020ca418c0d1dc02070fdc49b6dc7`. The manifest does not include itself,
the new verifier, tests, CI configuration, README, license or figure images.
It detects drift relative to this repository snapshot. It does not independently
authenticate how the original experiment was collected.

The older `MANIFEST.json` is preserved as an archive-ID index. Its values are
UUIDs rather than content hashes, and some entries reference files absent from
this release. It is not used as the integrity manifest. New results or changed
analysis methods need a reviewed, explicitly documented baseline update. The
verifier never rewrites reference outputs or regenerates the checksum manifest.

Trials, prompt templates and measured provider answers come from the recorded
experiment. The RQ1 per-trial records were not retained. Its aggregate counts
cannot receive the same trial-level checks as the released routing CSVs.

## Statistical and design limits

- The analysis retains its existing 10,000 task-clustered bootstrap resamples,
  NumPy seed 0, percentile intervals and one fixed calibration/evaluation split.
- Split validation detects overlapping task IDs and unexpected recorded tasks.
  It cannot establish that the split was fixed before analysis, that no model
  saw another task's contents, or that task templates are independent.
- Recorded ground-truth values are checked for consistency with answers. The
  mathematical correctness of each generated problem is not independently
  recomputed by this verifier.
- Deposit equilibria are calculated from recorded allocations and settlement
  rules. Providers did not adapt their listing choices to deposits. This is not
  evidence of strategic adaptation in a live market.
- Regeneration compares numerical values with relative tolerance `1e-10` and
  absolute tolerance `1e-9`. Counts, table structures and text labels must agree.
  Figures are outside this check. The original figure script remains available.

## Tests and CI

```sh
python -m unittest discover -s tests -v
```

The tests exercise corrupted snapshots, missing files, an escaping manifest
path, split leakage, duplicate or missing measurements, mis-scored outcomes,
invalid slot mappings, unreadable-trial denominators and changed results. One
test checks the actual release records. The CI configuration runs these checks
and a fresh temporary-directory numerical reproduction with Python 3.11.

Local verification on macOS used Python 3.11.15, NumPy 2.4.6, pandas 2.3.3 and
Matplotlib 3.11.0. A Linux CI result is pending publication and execution of the
workflow.
