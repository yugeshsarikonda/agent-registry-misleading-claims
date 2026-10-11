# Misleading Claims in Agent Registries — data release

Everything behind the reported numbers: the task set, the exact prompts, every provider
answer with its correctness label, and every router decision.

    tasks/              the generated table problems with their correct answers,
                        and the calibration/evaluation split used in the held-out test
    prompts/            the prompt templates, verbatim, as executed
    provider_outputs/   each provider's answer and correctness label on every task
    router_decisions/   every routing trial: condition, task, rotation, displayed order,
                        chosen slot, chosen provider, whether the reply was readable,
                        and whether the chosen provider solved that task

## Task set

60 generated table problems are in `tasks/market_ground_truth.json`. The paper uses 59 of
them; task_id 10 is excluded. Each entry holds the question text and the correct integer answer.
A provider is a fixed agent configuration that may read only the first K rows of the table, so
competence differs without the task, the prompt or the answer format changing.

## Prompts

`prompts/prompts_core.py` holds the provider prompt, the router prompt, the listing template and
the answer rule used in the main conditions. `prompts/prompts_screening.py` holds the variants
used in the checking experiments, including the [verified] tag and the two notes shown to the
router. These are the templates as executed, not reconstructions.

## Reading the router files

A listing is one provider's advertised text. A trial is one task shown to the router under one
rotation of listing positions. `chosen_provider` is the routing decision; `realised_correct` is
whether that provider's recorded answer for that task was right. Shares are reported over
readable trials, and the attempted count is given alongside, so unreadable replies are visible
rather than silently dropped.

`heldout_*` files are the held-out test: advertised rates estimated on 30 calibration tasks,
routing scored on 29 disjoint evaluation tasks. `burnin_trials.csv` is the observation block that
lets a registry identify its best provider from its own routing outcomes.

`heldout_router_gpt4o.csv` repeats the four held-out market conditions with gpt-4o (Azure OpenAI
Responses API, 600 output tokens, default sampling) as router; `heldout_router_comparison.csv`
sets it beside the claude-sonnet-5 held-out results.

## Reproducing

Provider answers and router decisions were produced by calls to hosted language models. Re-running
will not reproduce the trial-level rows exactly. The files here are the record of what was run.

## License

Released under **CC BY 4.0** (`LICENSE`). Retain attribution to Yugesh Sarikonda when reusing
these materials.
