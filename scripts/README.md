# Optiqal Scripts

This directory contains utility scripts for the Optiqal project.

## Precomputation Scripts

### precompute_all.py

Generates precomputed QALY results for all interventions defined in YAML files. This allows the web application to show instant results without running full simulations.

**Usage:**

```bash
# Basic usage (uses defaults: 5000 samples, ages 30-70)
python3 scripts/precompute_all.py

# Dry run to see what would be generated
python3 scripts/precompute_all.py --dry-run

# Custom number of samples
python3 scripts/precompute_all.py --samples 10000

# Custom ages and sexes
python3 scripts/precompute_all.py --ages 25 35 45 55 65 75 --sexes male female

# Custom discount rate
python3 scripts/precompute_all.py --discount-rate 0.05

# Show help
python3 scripts/precompute_all.py --help
```

**Output:**
- Generates JSON files in `public/precomputed/`
- One file per intervention (e.g., `walking_30min_daily.json`)
- Each file contains results for all age/sex combinations

**Performance:**
- Uses fast Monte Carlo simulation (not MCMC)
- 5000 samples provides good precision in ~1-2 seconds per intervention
- Total runtime scales linearly with number of interventions × age/sex combinations

### validate_precomputed.py

Validates the structure and content of precomputed JSON files.

**Usage:**

```bash
python3 scripts/validate_precomputed.py
```

**Checks:**
- Valid JSON syntax
- Required fields present
- Correct data types
- Reasonable value ranges (e.g., causal fraction between 0-1)
- Confidence interval ordering

## Workflow

When adding a new intervention or updating existing ones:

1. Create/update the YAML file in `src/lib/qaly/interventions/`
2. Run precomputation: `python3 scripts/precompute_all.py`
3. Validate output: `python3 scripts/validate_precomputed.py`
4. Commit both YAML and generated JSON files

## File Structure

```
src/lib/qaly/interventions/     # Input: Intervention YAML definitions
public/precomputed/             # Output: Precomputed JSON results
scripts/
  precompute_all.py            # Generate precomputed results
  validate_precomputed.py      # Validate JSON structure
```

## Testing

The precomputation functionality has comprehensive test coverage:

```bash
cd python
python3 -m pytest tests/test_precompute.py -v
```

Tests cover:
- PrecomputedResult creation and serialization
- PrecomputedIntervention JSON save/load
- Single intervention precomputation
- Batch precomputation of all interventions

## Vercel deployment

The app now deploys as two Vercel projects:

- `optiqal-ai` for the Next.js frontend
- `optiqal-model` for the Python model API

Because previews are protected by Vercel Authentication, cross-project preview
requests from the frontend to the model require an explicit protection bypass
secret. Set one shared secret for the `optiqal-model` project in Vercel’s
deployment protection settings, then export it locally before deploying:

```bash
export MODEL_PROTECTION_BYPASS_SECRET=...
```

The deploy scripts will fail fast if this variable is missing.

Preview deploy and smoke test:

```bash
bun run deploy:preview
```

Production deploy and smoke test:

```bash
bun run deploy:prod
```

The smoke test checks:

- frontend `/predict` shell content
- model `/health`
- model `/baseline`
- frontend `/api/baseline`
- frontend `/api/frontier`

This is intentional: deployment is not considered good unless the frontend can
actually reach the protected model service and return valid JSON contracts.
