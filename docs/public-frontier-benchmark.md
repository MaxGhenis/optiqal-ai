# Public Frontier Benchmark

This benchmark is the safety and plausibility harness for the public `/analyze` frontier.

It exists to support:

- public-product regression testing
- policy-tuning work on lanes, conditions, and item metadata
- future AutoAgent optimization over a narrow, safe edit surface
- future LLM-judge comparisons between candidate frontier outputs

## What it covers

The harness scores the same public frontier path used by the app:

- [`build_frontier_response`](../python/optiqal/web_api.py)

It evaluates:

- deterministic public canaries from [`public_frontier_benchmark_scenarios.json`](../python/optiqal/data/public_frontier_benchmark_scenarios.json)
- optional generated stratified scenarios
- hard-fail rules such as:
  - banned top-ranked items
  - banned visible items
  - required visible items
  - forbidden co-ranking pairs
  - expected airway decision-state presence

The LLM-judge scaffold lives in:

- [`public_frontier_judge_prompt.md`](../python/optiqal/data/public_frontier_judge_prompt.md)

## Run it

From [`python`](../python/):

```bash
./.venv/bin/python scripts/run_public_frontier_benchmark.py
./.venv/bin/python scripts/run_public_frontier_benchmark.py --json
./.venv/bin/python scripts/run_public_frontier_benchmark.py --cases-per-stratum 2 --seed 42
```

To save a full candidate report for later pairwise review:

```bash
./.venv/bin/python scripts/run_public_frontier_benchmark.py --output-report /tmp/candidate-a.json
```

To compare the current candidate against another saved report and emit judge packets:

```bash
./.venv/bin/python scripts/run_public_frontier_benchmark.py \
  --judge-against-report /tmp/incumbent.json \
  --emit-judge-packets /tmp/judge-packets.json
```

To combine offline judge verdicts back into a hybrid score:

```bash
./.venv/bin/python scripts/run_public_frontier_benchmark.py \
  --judge-verdicts /tmp/judge-verdicts.json \
  --json
```

## Current edit boundary

If you use AutoAgent or another optimizer, restrict edits to the public-policy layer:

- [`public_policy_lanes.json`](../python/optiqal/data/public_policy_lanes.json)
- [`public_policy_conditions.json`](../python/optiqal/data/public_policy_conditions.json)
- [`public_policy_items.json`](../python/optiqal/data/public_policy_items.json)
- narrowly scoped policy helpers in [`catalog.py`](../python/optiqal/catalog.py)

Do not let an optimizer mutate the full mortality/QALY engine just to improve this benchmark.

## LLM judge pattern

Recommended use:

1. Run the benchmark and keep hard-rule failures as the dominant signal.
2. For the same scenario, compare candidate A vs B frontier outputs with the judge prompt.
3. Use the judge only as a secondary preference signal after hard constraints pass.

The intended pairwise question is:

- which candidate is safer and more plausible for a public product?

Not:

- which candidate is more interesting
- which candidate has more interventions
- which candidate has lower modeled cost/QALY in isolation

The current runner supports:

- hard benchmark score
- pairwise judge packet generation against a saved incumbent report
- offline verdict parsing
- hybrid score computation

Hybrid scoring rule:

- if hard benchmark score is below `1.0`, that score dominates
- judge preference only affects the result once hard rules pass

## Success criterion

Short term, the benchmark should stay at `1.0` on canonical canaries while policy edits are made.

Longer term, the harness should expand with:

- more scenario strata
- more pairwise judge cases
- more hard-fail public-safety rules
