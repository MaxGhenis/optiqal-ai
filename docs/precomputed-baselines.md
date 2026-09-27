# Precomputed baselines

## What this is

`python/optiqal/data/baselines.json` pre-tabulates remaining life expectancy,
remaining QALYs, cause fractions and quality weights for ages 0-100, so
`LifecycleModel` can replace roughly 70 interpolations per simulation with O(1)
array lookups.

## Files

- `scripts/precompute_baselines.py` generates the table from
  `python/optiqal/lifecycle.py`, which itself loads the committed snapshots in
  `python/optiqal/data/snapshots/`.
- `python/optiqal/data/baselines.json` is the generated table, loaded once and
  cached in memory.
- `python/examples/precomputed_example.py` shows the lookups and benchmarks the
  fast and slow paths.

`scripts/prepare-model-deploy.mjs` copies the whole `python/optiqal` tree into
`.model-service/`, so the deployed model service reads the same file.

Before rebuild PR B there was a second copy at `public/precomputed/baselines.json`
for the TypeScript engine, plus `src/lib/evidence/baseline/precomputed.ts` to read
it. Both are deleted.

## How lifecycle.py uses it

```python
from optiqal.lifecycle import LifecycleModel, PathwayHRs

# Fast path (default)
model = LifecycleModel(start_age=40, sex="male", use_precomputed=True)
result = model.calculate(PathwayHRs(cvd=0.8, cancer=1.0, other=1.0))

# Direct lookups
from optiqal.lifecycle import get_precomputed_baseline_qalys
qalys = get_precomputed_baseline_qalys(age=40, sex="male")
```

`LifecycleModel.__init__` caches the precomputed value only when
`use_precomputed` is true, `discount_rate == 0.03` and
`baseline_mortality_multiplier == 1.0`. Any other combination interpolates.

## Regenerating

```bash
python scripts/precompute_baselines.py
```

Rerun this after changing any snapshot the life table depends on.

## Limits

- Integer ages only, 0-100.
- QALYs are tabulated at the 3% discount rate only.
- The table must be regenerated when its input snapshots change; nothing checks
  that automatically.
