# Precomputed baselines - quick start

`python/optiqal/data/baselines.json` replaces roughly 70 runtime interpolations
per simulation with O(1) array lookups. It is on by default.

## Use it

```python
from optiqal.lifecycle import LifecycleModel, PathwayHRs

# Precomputed is on by default
model = LifecycleModel(start_age=40, sex="male")
result = model.calculate(PathwayHRs(cvd=0.8, cancer=1.0, other=1.0))

print(f"Baseline QALYs: {result.baseline_qalys:.2f}")
print(f"QALY gain: {result.qaly_gain:.3f}")
```

Direct lookups:

```python
from optiqal.lifecycle import get_precomputed_baseline_qalys

qalys = get_precomputed_baseline_qalys(age=40, sex="male")
```

## When to turn it off

```python
# A discount rate other than 3%, or an explicit comparison against interpolation
model = LifecycleModel(
    start_age=40,
    sex="male",
    discount_rate=0.05,
    use_precomputed=False,
)
```

## Run the example

```bash
cd python
uv run python examples/precomputed_example.py
```

It benchmarks the two paths and prints the lookups. Measured on 2026-09-04 with
1,000 simulations for a 40-year-old male: 4,871 simulations/second precomputed
against 4,465 interpolating, a 1.09x speedup. The margin is small and
machine-dependent; the table's real value is that the two paths agree.

## Regenerate

```bash
python scripts/precompute_baselines.py
```

This writes `python/optiqal/data/baselines.json`. Before rebuild PR B it also
wrote `public/precomputed/baselines.json` for the deleted TypeScript engine.

Full guide: [`docs/precomputed-baselines.md`](./precomputed-baselines.md).
