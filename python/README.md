# Optiqal Python

QALY estimation for lifestyle interventions. This package is the engine: the two
served routes, the analysis paths and the deployed model service all call into
it, and nothing else computes a number.

## Installation

Development, from this directory:

```bash
uv sync --all-extras
```

As a dependency:

```bash
uv pip install optiqal                # engine only
uv pip install "optiqal[validation]"  # plus the Pan-UKB plotting tooling
uv pip install "optiqal[dev]"         # plus pytest, ruff, mypy
uv pip install "optiqal[all]"         # both extras
```

## Quick start

```python
from optiqal import Intervention, simulate_qaly

# Load one of the shipped definitions from optiqal/data/interventions/
intervention = Intervention.packaged("walking_30min_daily")

# Run Monte Carlo simulation
result = simulate_qaly(
    intervention,
    age=40,
    sex="male",
    n_simulations=10000,
    random_state=42,
)

print(f"QALY gain: {result.median:.2f} [{result.ci95[0]:.2f}, {result.ci95[1]:.2f}]")
```

`Intervention.from_yaml(path)` loads an arbitrary file;
`optiqal.packaged_intervention_path(id)` resolves a shipped one.

## What the web serves

`optiqal/web_api.py` exposes `build_baseline_response(payload)` and
`build_frontier_response(payload)`. Both take a plain dict and return a plain
dict; they are the only entry points any surface uses.

- Locally, `src/lib/python-bridge.ts` spawns `scripts/web_baseline.py` or
  `scripts/web_frontier.py` from this directory, writes the payload to stdin and
  reads JSON from stdout.
- In production, `backend/main.py` is a FastAPI wrapper importing those same two
  functions, deployed as the `optiqal-model` Vercel project by
  `scripts/prepare-model-deploy.mjs`, which copies `backend/` and this whole
  package into `.model-service/`.

Reproduce a served response without the web app:

```bash
uv run python scripts/web_frontier.py < request.json
```

## Where the numbers come from

- `optiqal/data/priors.yaml` holds every Beta prior, shrinkage schedule and
  transport prior; `optiqal/priors.py` loads and validates it. No module holds
  literal Beta parameters.
- `optiqal/data/snapshots/` holds the life table, the cause fractions and the
  MEPS quality weights as provenance-stamped JSON. `optiqal/snapshots.py` is a
  fail-closed loader: a checksum mismatch, a missing provenance field or a lost
  age anchor raises at import.
- `optiqal/data/interventions/` holds the ten shipped intervention YAMLs.
- `docs/DATA_PROVENANCE.md` at the repository root records the source and the
  open questions for every asset.

## Precomputation

`optiqal/precompute.py` runs the engine over an age/sex grid or the full profile
grid and writes JSON. The output is a local artifact under `build/precomputed/`;
nothing the site serves reads it.

```python
from optiqal.precompute import precompute_all_interventions

precompute_all_interventions(
    intervention_dir="optiqal/data/interventions/",
    output_dir="../build/precomputed/",
)
```

## Product quantity accounting

Product removal/replacement quantity accounting has a separate
[integration contract](../docs/product-composition-accounting.md), including
synthetic examples, explicit unknown amounts, and the boundary that prevents
product changes from entering catalog QALY rankings without an effect mapping.

## Validation CLI

Pan-UKB validation is available as an optional packaged workflow:

```bash
optiqal-pan-ukb describe
optiqal-pan-ukb download
optiqal-pan-ukb analyze
```

Raw Pan-UKB files live outside the repo by default at:

```text
~/.cache/optiqal/validation/pan-ukb
```

Override that with `OPTIQAL_PAN_UKB_DATA_DIR=/path/to/pan-ukb` when needed.

## Checks

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

## Key features

- **Monte Carlo simulation** with independent draw streams per semantic
  quantity, seeded reproducibly from one `SeedSequence`
- **Loaded life tables**: committed, checksum-validated snapshots rather than
  transcribed constants
- **Pathway decomposition**: separates effects into CVD, cancer, and other
  mortality
- **Confounding adjustment**: Beta priors by intervention category and evidence
  type, all read from `priors.yaml`
- **E-value calculation**: robustness assessment per VanderWeele & Ding (2017)
- **Discounting**: health effects and costs discounted at 3% by default (US
  Second Panel reference case); 0–10% supported for sensitivity analysis

## License

MIT
