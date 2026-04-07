# Public Frontier Policy Optimization

You are improving Optiqal's public `/analyze` recommendation policy, not the core mortality/QALY model.

Your goal is to maximize the public-frontier benchmark while keeping outputs conservative and plausible for a public product.

## Objective

Optimize the candidate policy in [`agent.py`](./agent.py) so that:

1. hard benchmark score moves toward `1.0` and improves over the incumbent baseline
2. generated stratified scenarios stay plausible
3. pairwise judge packets would likely prefer the candidate over the incumbent

## Edit boundary

Only edit the `CANDIDATE_POLICY` object and nearby editable constants in [`agent.py`](./agent.py).

Do not:

- edit the fixed adapter section
- edit the benchmark runner
- edit the core Optiqal model
- edit catalog evidence or intervention math

## Benchmark command

From this directory:

```bash
python agent.py --summary-json
```

For a stronger benchmark:

```bash
python agent.py --summary-json --cases-per-stratum 8
```

To emit pairwise judge packets for manual or LLM review:

```bash
python agent.py --summary-json --emit-judge-packets /tmp/public-frontier-packets.json
```

## What good changes look like

- broad public profiles keep sane leaders like exercise and strength
- Rx and condition-specific items only surface when the qualifying signal is present
- airway decision states only appear when airway signal is meaningful
- score improvements come from cleaner public policy, not from suppressing too much

## What to avoid

- gaming the benchmark by hiding almost everything
- promoting clinician-mediated Rx for healthy public profiles
- making the candidate more permissive than the incumbent without a strong reason

## Working style

1. inspect the current comparison output
2. identify the weakest scenario deltas
3. make one small policy change
4. rerun the benchmark
5. keep changes only if the result improves or stays clean while becoming more plausible
