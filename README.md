# Misleading Claims in Agent Registries: data and analysis (release v1.1-camera-ready)

Everything behind the reported numbers: the generated tasks, the exact prompts, every provider
answer with its correctness label, the routing trials, and one script that rebuilds every table,
interval and figure in the paper.

    tasks/              generated table problems with correct answers; calibration/evaluation split
    prompts/            prompt templates, verbatim, as executed
    provider_outputs/   provider configuration (row limits) and each provider's answer on every task
    router_decisions/   routing trials: condition, task, rotation, displayed order, chosen position,
                        chosen provider, whether the reply was readable, whether the choice was correct
    rq1/                aggregate counts for the RQ1 listing comparisons
    analysis/           analysis.py (tables, intervals, deposit analysis), make_figures.py (figures)
    results/            outputs of analysis.py
    figures/            outputs of make_figures.py

## Reproducing the paper's numbers

    pip install -r requirements.txt
    python analysis/analysis.py
    python analysis/make_figures.py

Both scripts run in about a second on a laptop. Re-running the hosted models will not reproduce
individual trials exactly; the files here are the record of what was run.

## Uncertainty and denominators

Every interval is a central 95% percentile interval from 10,000 bootstrap resamples of tasks (seed 0).
All rotations of a task move together, and each resample's task success is total successes over total
readable trials. Comparisons with the uniform or best-provider rate are paired on the same resampled
tasks. Held-out intervals are conditional on the single split in `tasks/heldout_split.json`.

Every share and every rate is over trials with a readable answer line; the attempted count is reported
beside it (`n_attempted` in the results files). A condition with 116 attempted trials and 114 readable
reports, for example, 112/114.

## Map from paper to files

| Paper item | Source trials | Output |
|---|---|---|
| Table 1, Figure 2a | `router_decisions/pop2_arms.csv`, `heldout_trials.csv`, `heldout_router_gpt4o.csv` | `results/table1_market.csv` |
| Paired differences (RQ2, RQ5) | as above, `router_replication.csv` | `results/summary.json` → `paired_differences` |
| Figure 2b | `heldout_trials.csv` (single-exaggerator conditions) | `results/fig1b_single_exaggerator.csv` |
| Table 2, Figure 2c, Table 4 (all 16 listing combinations) | `heldout_trials.csv`, `heldout_deposit_profiles.csv`, `heldout_deposit_profiles_extra.csv` | `results/deposit_profiles.csv`, `results/deposit_equilibria.csv`, `summary.json` → `deposit_boundaries` |
| Displayed deposit | `pop2_arms.csv` (`deviation-weakest+bond1`, `+bond4`) | `summary.json` → `displayed_deposit` |
| Table 3 (checking), observation period | `heldout_screening.csv`, `burnin_trials.csv` | `results/table2_checking.csv`, `summary.json` → `observation_period` |
| Earlier checking rules (appendix) | `pop2_screening.csv` (`run == primary`) | `summary.json` → `checking_all59` |
| Checking sweep, Figure 3 | `scale_results.csv` | `results/coverage_sweep.csv` |
| Opus comparison | `router_replication.csv` | `summary.json` → `opus`, `opus_position` |
| Figure 1 (RQ1) | `rq1/rq1_counts.json` | `figures/fig2_claims.png` |
| Turn-taking game (appendix) | `dynamics_results.csv` | assignments as recorded |
| Provider row limits and measured rates | `provider_outputs/pop2_ladder.csv`, `pop2_competence.csv` | `summary.json` → `measured_*` |

The RQ1 comparisons asked the router for a single letter; their per-trial records were not retained,
and `rq1/rq1_counts.json` gives the counts by listing and by position recovered from the run log.
`router_decisions/pop2_bond_summary.csv` and `pop2_arms_summary.csv` are summaries written during the
original runs and are kept for reference; the paper's numbers come from `analysis.py`.

## Deposit analysis

Deposits are settled on recorded outcomes. No provider chose its listing in response to a deposit.
`deposit_equilibria.csv` lists, for each deposit level and each settlement rule, the combinations of
listings from which no provider gains by switching its own listing and in which no provider earns less
than zero. The market after a provider leaves was not run.

## Configuration

Providers: `claude-sonnet-5`, 900 output tokens, API-default temperature, one system prompt (see
`prompts/prompts_core.py`); P1 reads all rows, P2, P3 and P4 read the first 11, 9 and 8.
Routers: `claude-sonnet-5` (600 output tokens), `claude-opus-5` (1000), `gpt-4o` via the Azure OpenAI
Responses API (600), all at the API's default temperature.

Licence: CC BY 4.0.
