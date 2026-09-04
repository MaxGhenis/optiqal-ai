# Reproducibility in Optiqal

Optiqal's QALY estimates come from Monte Carlo simulation, so reproducibility
depends on how the random number generator is seeded. This document describes
the seeding behavior that is **actually enforced in code**.

There is one engine: the Python package in `python/optiqal/`. The TypeScript
QALY engine and the precomputed JSON it served were deleted in rebuild PR B; if
you are reading an older copy of this file that describes them, it is stale.

## What runs when the app answers

The two served pages both call the Python engine.

- `/predict` POSTs to `/api/baseline`; `/analyze` POSTs to `/api/frontier`.
- Both routes go through `src/lib/python-bridge.ts`. Locally the bridge spawns
  `uv run python scripts/web_baseline.py` or `scripts/web_frontier.py` from
  `python/`, writing the request payload to stdin and reading JSON from stdout.
- In production the bridge posts to the `optiqal-model` service instead. That
  service is the FastAPI app in `backend/main.py`, which imports
  `build_baseline_response` and `build_frontier_response` from
  `optiqal.web_api` — the same two functions the local scripts call.
  `scripts/prepare-model-deploy.mjs` assembles it by copying `backend/` and the
  whole `python/optiqal` tree into `.model-service/`.

So there is one code path to reproduce, whichever surface asked.

## How randomness is seeded

The engine uses NumPy's modern Generator API. `simulate.py` derives its draw
streams from one `np.random.SeedSequence(random_state)` through
`_spawn_generators`: `simulate_qaly_profile_vectorized` spawns four (quality
offsets, hazard ratio, causal fraction, harms) and the two loop simulators spawn
two (hazard ratio, causal fraction), so those streams are independent of each
other at every seed rather than sharing one raw seed. `Distribution.sample` and
`ConfoundingPrior.sample` accept either an integer seed or an
`np.random.Generator`.

A fixed integer `random_state` produces a deterministic draw sequence;
`random_state=None` produces a fresh, nondeterministic stream on every call.

## Entry points are deterministic by default

The high-level entry points pin a fixed seed, so production responses are
reproducible:

- `AnalysisConfig` (`python/optiqal/analyzer.py`) defaults to
  `random_state = 42`, and `analyze()` passes that seed down to
  `simulate_qaly_profile_vectorized(...)`.
- `python/optiqal/web_api.py` constructs `AnalysisConfig(...)` with
  `random_state=42` explicitly.

The same request to the analyzer or the web API returns the same numbers across
runs.

## Low-level calls are NOT deterministic by default

The low-level simulation functions in `python/optiqal/simulate.py` default
`random_state` to `None`:

```python
def simulate_qaly_profile_vectorized(..., random_state: Optional[int] = None): ...
def simulate_qaly(..., random_state: Optional[int] = None): ...
def simulate_qaly_profile(..., random_state: Optional[int] = None): ...
```

If you call any of these directly (bypassing `AnalysisConfig` and the web API)
**you must pass a seed** to get reproducible output:

```python
from optiqal.simulate import simulate_qaly_profile_vectorized

# Reproducible: pass an explicit seed
result = simulate_qaly_profile_vectorized(..., random_state=42)

# Nondeterministic: omits the seed (random_state=None)
result = simulate_qaly_profile_vectorized(...)
```

## Inputs are loaded, not typed

`python/optiqal/lifecycle.py` holds no lifecycle data tables. It loads the life
table, the cause fractions and the MEPS quality weights from committed,
provenance-stamped snapshots under `python/optiqal/data/snapshots/` through the
fail-closed loader in `python/optiqal/snapshots.py`, which raises at import on a
checksum mismatch, a missing provenance field, or a lost or gained age anchor.
Every Beta prior, shrinkage schedule and transport prior comes from
`python/optiqal/data/priors.yaml` through `python/optiqal/priors.py`; no module
holds literal Beta parameters. The ten shipped intervention definitions are in
`python/optiqal/data/interventions/`. `docs/DATA_PROVENANCE.md` records where
each asset came from and which claims are still unverified.

## Scope of the guarantee

Determinism here means: same seed + same inputs + same code → same NumPy draw
sequence → same statistics, within a single environment. Results may still
differ across NumPy major versions or platforms if the underlying RNG or
floating-point behavior changes. No cross-version bit-for-bit guarantee is
enforced in code, so none is claimed here.

## Verifying reproducibility

```python
from optiqal.simulate import simulate_qaly_profile_vectorized

r1 = simulate_qaly_profile_vectorized(..., random_state=42)
r2 = simulate_qaly_profile_vectorized(..., random_state=42)
# Same seed + same inputs -> identical statistics
```

To reproduce what the routes return, call the two builders directly:

```bash
cd python
uv run python -c "
import json
from optiqal.web_api import build_frontier_response
from optiqal.public_frontier_benchmark import CANONICAL_PUBLIC_FRONTIER_SCENARIOS as S
print(json.dumps(build_frontier_response(dict(S[0].payload)), sort_keys=True))
"
```

`tests/test_simulate_streams.py` pins the stream independence and the
seed-to-seed reproducibility; `tests/test_priors_drift.py` fails if a documented
or shipped prior drifts from `priors.yaml`.
