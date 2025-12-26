# Precomputed Baselines

This document explains the precomputed baseline system for fast life expectancy and QALY calculations.

## Overview

The precomputation system replaces ~70 runtime interpolations per simulation with O(1) array lookups by pre-tabulating baseline values for ages 0-100.

### Performance Benefits

- **~8% faster** lifecycle calculations with precomputed baselines
- **O(1) lookups** instead of O(n) interpolation
- **Identical results** to interpolation (validated to <0.001 difference)
- **No code changes required** - just opt-in with a flag

### What's Precomputed

For each integer age 0-100 and both sexes:

1. **Life Expectancy**: Remaining years of life
2. **Remaining QALYs**: Discounted quality-adjusted life years (3% discount rate)
3. **Cause Fractions**: CVD, cancer, other mortality proportions
4. **Quality Weights**: Age-based health-related quality of life weights

## Data Files

### Generated Files

```
public/precomputed/baselines.json      # For TypeScript/browser use
python/optiqal/data/baselines.json     # For Python use
```

### File Structure

```json
{
  "metadata": {
    "version": "1.0.0",
    "source": "CDC National Vital Statistics Life Tables (2021)",
    "discount_rate": 0.03,
    "max_age": 100
  },
  "life_expectancy": {
    "male": { "0": 76.4, "1": 75.8, ... },
    "female": { "0": 81.8, "1": 81.2, ... }
  },
  "remaining_qalys": {
    "male": { "0": 27.1, "1": 26.9, ... },
    "female": { "0": 27.7, "1": 27.5, ... }
  },
  "cause_fractions": {
    "0": { "cvd": 0.2, "cancer": 0.25, "other": 0.55 },
    ...
  },
  "quality_weights": {
    "0": 0.9200, "1": 0.9204, ...
  }
}
```

## Regenerating Precomputed Data

To regenerate the precomputed baselines (e.g., after updating life tables):

```bash
python scripts/precompute_baselines.py
```

This will:
1. Calculate values for ages 0-100
2. Save to both TypeScript and Python locations
3. Print summary statistics

## Usage

### Python

#### Basic Usage

```python
from optiqal.lifecycle import LifecycleModel, PathwayHRs

# Use precomputed baselines (default, recommended)
model = LifecycleModel(
    start_age=40,
    sex="male",
    use_precomputed=True  # Default
)

result = model.calculate(PathwayHRs(cvd=0.8, cancer=1.0, other=1.0))
print(f"Baseline QALYs: {result.baseline_qalys:.2f}")
```

#### Direct Lookups

```python
from optiqal.lifecycle import (
    get_precomputed_baseline_qalys,
    get_precomputed_life_expectancy
)

# O(1) lookups
qalys = get_precomputed_baseline_qalys(age=40, sex="male")
life_exp = get_precomputed_life_expectancy(age=40, sex="male")

print(f"Remaining QALYs: {qalys:.2f}")
print(f"Life expectancy: {life_exp:.1f} years")
```

#### Disable Precomputed (for testing)

```python
# Use interpolation instead of precomputed
model = LifecycleModel(
    start_age=40,
    sex="male",
    use_precomputed=False
)
```

### TypeScript

#### Load Precomputed Data

```typescript
import {
  loadPrecomputedBaselines,
  getPrecomputedLifeExpectancy,
  getPrecomputedRemainingQALYs,
} from "@/lib/evidence/baseline";

// Load once, cache automatically
const baselines = await loadPrecomputedBaselines();

// O(1) lookups
const lifeExp = getPrecomputedLifeExpectancy(40, "male", baselines);
const qalys = getPrecomputedRemainingQALYs(40, "male", baselines);
```

#### Use with Existing Functions

```typescript
import {
  loadPrecomputedBaselines,
  getRemainingLifeExpectancy,
  getAgeQualityWeight,
} from "@/lib/evidence/baseline";

const baselines = await loadPrecomputedBaselines();

// Pass as optional parameter for O(1) lookup
const lifeExp = getRemainingLifeExpectancy(45, "female", baselines);
const quality = getAgeQualityWeight(45, baselines);

// Or omit for interpolation (slower)
const lifeExpSlow = getRemainingLifeExpectancy(45, "female");
```

#### Batch Processing

```typescript
import { loadPrecomputedBaselines, getPrecomputedRemainingQALYs } from "@/lib/evidence/baseline";

const baselines = await loadPrecomputedBaselines();

// Fast batch processing
const profiles = [
  { age: 30, sex: "male" },
  { age: 45, sex: "female" },
  { age: 60, sex: "male" },
];

const results = profiles.map(p => ({
  ...p,
  qalys: getPrecomputedRemainingQALYs(p.age, p.sex, baselines),
}));
```

## Examples

### Python Example

See [`python/examples/precomputed_example.py`](../python/examples/precomputed_example.py) for a complete demonstration including:

- Direct precomputed lookups
- Intervention impact analysis
- Performance benchmarking

Run it:
```bash
python python/examples/precomputed_example.py
```

### TypeScript Example

See [`src/lib/evidence/baseline/example.ts`](../src/lib/evidence/baseline/example.ts) for examples including:

- Direct lookups
- Integration with existing functions
- Batch processing
- Quality weight ranges

## Technical Details

### Precomputation Algorithm

The precomputation script (`scripts/precompute_baselines.py`):

1. **Life Expectancy**: Integrates survival curve from age to 100
   ```python
   life_years = Σ(survival_probability_at_age_t)
   ```

2. **QALYs**: Integrates quality-weighted, discounted survival
   ```python
   qalys = Σ(survival_t × quality_t × discount_t)
   ```
   - Discount rate: 3% per year
   - Quality weights: Age-dependent (Sullivan et al. 2006, GBD 2019)

3. **Cause Fractions**: Linear interpolation from CDC WONDER 2021 data

4. **Quality Weights**: Linear interpolation from GBD 2019 disability weights

### Data Sources

- **Mortality**: CDC National Vital Statistics Life Tables (2021)
- **Cause of Death**: CDC WONDER (2021)
- **Quality Weights**: Sullivan et al. (2006), GBD 2019

### Validation

Precomputed values are validated against interpolation:
- Maximum difference: <0.001 QALYs
- Tested across all ages 0-100
- Both male and female

## Performance

### Python Benchmarks

Test: 1000 lifecycle simulations, 40-year-old male, 20% CVD risk reduction

| Method | Time | Simulations/sec | Speedup |
|--------|------|-----------------|---------|
| With precomputed | 0.396s | 2,527/s | 1.08x |
| Without precomputed | 0.426s | 2,349/s | baseline |

### Memory Usage

- File size: ~50KB JSON
- Memory footprint: ~100KB when loaded
- One-time load, cached in memory

## Limitations

1. **Integer Ages Only**: Precomputed for ages 0-100 (integer values)
   - Non-integer ages fall back to interpolation
   - This is fine for most use cases

2. **3% Discount Rate Only**: QALYs precomputed at 3% discount rate
   - Different discount rates require runtime calculation
   - Use `use_precomputed=False` for other rates

3. **Baseline Only**: Precomputed for baseline (no intervention)
   - Intervention effects still computed at runtime
   - Baseline computation is the main bottleneck anyway

## Future Enhancements

Potential improvements:

1. **Multiple Discount Rates**: Precompute for common rates (0%, 3%, 5%)
2. **Sub-year Resolution**: 0.1-year granularity for more precision
3. **Intervention Scenarios**: Precompute common HR scenarios
4. **Additional Demographics**: Race, ethnicity adjustments

## Troubleshooting

### File Not Found

If you get "File not found" errors:

```bash
# Regenerate the files
python scripts/precompute_baselines.py
```

### Values Don't Match

If precomputed values differ significantly from interpolation:

1. Check that you're using the same discount rate (3%)
2. Verify life tables haven't been updated
3. Regenerate precomputed data
4. Report issue if difference persists

### Performance Not Improved

If you don't see performance improvements:

1. Ensure `use_precomputed=True` in Python
2. Pass `baselines` parameter in TypeScript
3. Check that ages are integers (0-100)
4. Verify discount rate is 3%

## Contributing

When updating baseline data:

1. Update source data in `python/optiqal/lifecycle.py`
2. Run `python scripts/precompute_baselines.py`
3. Verify output files are updated
4. Update version in metadata
5. Run tests to validate

## References

- CDC National Vital Statistics Life Tables: https://www.cdc.gov/nchs/products/life_tables.htm
- CDC WONDER: https://wonder.cdc.gov/
- GBD 2019: https://www.healthdata.org/gbd/2019
- Sullivan et al. (2006): Quality of Life Research
