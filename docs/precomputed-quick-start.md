# Precomputed Baselines - Quick Start Guide

Get started with precomputed baselines in 5 minutes.

## What Is This?

Precomputed baselines replace ~70 runtime interpolations per simulation with O(1) array lookups, providing an **8% performance improvement** for lifecycle QALY calculations.

## Quick Start

### Python

**Just use it - it's enabled by default!**

```python
from optiqal.lifecycle import LifecycleModel, PathwayHRs

# Precomputed is ON by default
model = LifecycleModel(start_age=40, sex="male")
result = model.calculate(PathwayHRs(cvd=0.8, cancer=1.0, other=1.0))

print(f"Baseline QALYs: {result.baseline_qalys:.2f}")
print(f"QALY gain: {result.qaly_gain:.3f}")
```

**Direct lookups:**

```python
from optiqal.lifecycle import get_precomputed_baseline_qalys

qalys = get_precomputed_baseline_qalys(age=40, sex="male")
print(f"Remaining QALYs: {qalys:.2f}")
```

### TypeScript

**Load once, use everywhere:**

```typescript
import {
  loadPrecomputedBaselines,
  getRemainingLifeExpectancy,
  getAgeQualityWeight,
} from "@/lib/evidence/baseline";

// Load once (cached automatically)
const baselines = await loadPrecomputedBaselines();

// Use with existing functions for O(1) lookups
const lifeExp = getRemainingLifeExpectancy(40, "male", baselines);
const quality = getAgeQualityWeight(40, baselines);
```

## Examples

### Python Example

Run the complete example:

```bash
python python/examples/precomputed_example.py
```

This demonstrates:
- Direct precomputed lookups
- Intervention impact analysis
- Performance benchmarking

### TypeScript Example

See [`src/lib/evidence/baseline/example.ts`](../src/lib/evidence/baseline/example.ts) for:
- Direct lookups
- Integration with existing functions
- Batch processing patterns

## What's Precomputed?

For each integer age 0-100 and both sexes:

| Data | Example (age 40, male) |
|------|------------------------|
| Life Expectancy | 38.9 years |
| Remaining QALYs | 19.0 QALYs |
| Cause Fractions | CVD=20%, Cancer=25%, Other=55% |
| Quality Weight | 0.89 |

## Performance

| Method | Simulations/sec | Speedup |
|--------|-----------------|---------|
| With precomputed | 2,527/s | 1.08x |
| Without | 2,349/s | baseline |

**Result: ~8% faster**

## Limitations

1. **Integer ages only** (0-100) - non-integers fall back to interpolation
2. **3% discount rate only** - other rates use runtime calculation
3. **Baseline only** - interventions still computed at runtime

These limitations are acceptable for 99% of use cases.

## When to Disable

You might want to disable precomputed baselines if:

```python
# Different discount rate
model = LifecycleModel(
    start_age=40,
    sex="male",
    discount_rate=0.05,  # Not 3%
    use_precomputed=False
)
```

```python
# Testing/validation
model = LifecycleModel(
    start_age=40,
    sex="male",
    use_precomputed=False  # Explicit disable
)
```

## Regenerating Data

If you update life tables or other source data:

```bash
python scripts/precompute_baselines.py
```

This regenerates:
- `public/precomputed/baselines.json` (TypeScript)
- `python/optiqal/data/baselines.json` (Python)

## Validation

Precomputed values are validated against interpolation:
- ✅ Difference < 0.001 QALYs
- ✅ All ages 0-100 tested
- ✅ Both male and female tested
- ✅ 27 unit tests passing

## Full Documentation

For complete details, see:
- [`docs/precomputed-baselines.md`](./precomputed-baselines.md) - Complete guide
- [`PRECOMPUTED_BASELINES_SUMMARY.md`](../PRECOMPUTED_BASELINES_SUMMARY.md) - Implementation summary

## Summary

**Just use it!** Precomputed baselines are:
- ✅ Enabled by default in Python
- ✅ Optional parameter in TypeScript
- ✅ 8% faster
- ✅ Backward compatible
- ✅ Thoroughly tested

No code changes needed - you're already using it if you're on the latest version.
