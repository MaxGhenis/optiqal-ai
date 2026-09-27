# Precomputed baselines - implementation summary

This is the record of how `python/optiqal/data/baselines.json` came to exist. The
usage guide is [`docs/precomputed-baselines.md`](docs/precomputed-baselines.md)
and the short version is
[`docs/precomputed-quick-start.md`](docs/precomputed-quick-start.md).

## What it does

Pre-tabulates remaining life expectancy, remaining QALYs, cause fractions and
quality weights for every integer age 0-100 and both sexes, so `LifecycleModel`
can replace roughly 70 interpolations per simulation with array lookups. 404
values in about 50 KB, loaded once and cached.

## What is still here

- `scripts/precompute_baselines.py` generates the table from
  `python/optiqal/lifecycle.py`.
- `python/optiqal/data/baselines.json` is the table.
- `python/optiqal/lifecycle.py` holds `load_precomputed_baselines()`,
  `get_precomputed_baseline_qalys()`, `get_precomputed_life_expectancy()` and the
  `use_precomputed` parameter on `LifecycleModel`.
- `python/examples/precomputed_example.py` demonstrates and benchmarks it.

## What was deleted in rebuild PR B

The TypeScript half of this feature is gone: `public/precomputed/baselines.json`,
`src/lib/evidence/baseline/precomputed.ts`, its test file, `example.ts`, and the
optional `precomputed` parameters threaded through `life-tables.ts` and
`quality-weights.ts`. Nothing served read them.

## Measurements

Recorded 2026-09-04 by `python/examples/precomputed_example.py`, 1,000
simulations for a 40-year-old male: 4,871 simulations/second with the table
against 4,465 without, a 1.09x speedup. This file previously carried 2,527
against 2,349 for the same comparison, about 8%. The speedup is small and
machine-dependent.

## Limits

- Integer ages only, 0-100.
- QALYs tabulated at the 3% discount rate only; other rates fall back to runtime
  calculation.
- `LifecycleModel` only takes the fast path when `use_precomputed` is true, the
  discount rate is exactly 0.03 and `baseline_mortality_multiplier` is exactly
  1.0; otherwise it interpolates.
- Nothing checks automatically that the table is still consistent with the
  snapshots it was generated from. Rerun the generator after changing them.
