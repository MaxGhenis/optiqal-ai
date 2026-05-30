# Reproducibility in Optiqal

Optiqal's QALY estimates come from Monte Carlo simulation, so reproducibility
depends on how the random number generator is seeded. This document describes the
seeding behavior that is **actually enforced in code**, for both the production
Python engine and the legacy TypeScript engine.

## Which engine is which

The **production engine is Python** (`python/optiqal/`). The web API
(`python/optiqal/web_api.py`) and the analysis orchestrator
(`python/optiqal/analyzer.py`) drive all live estimates.

The **TypeScript QALY engine** (`src/lib/qaly/`) is **legacy** and being phased
out. The notes in the "Legacy TypeScript engine" section below remain accurate
for that code, but new work should target the Python engine.

## Python engine (production)

### How randomness is seeded

The Python engine uses NumPy's modern Generator API. Inside the low-level
simulators (`python/optiqal/simulate.py`), the seed is consumed as:

```python
rng = np.random.default_rng(random_state)
```

A fixed integer `random_state` therefore produces a deterministic draw sequence;
`random_state=None` produces a fresh, nondeterministic stream on every call.

### Entry points are deterministic by default

The high-level entry points pin a fixed seed, so production responses are
reproducible:

- `AnalysisConfig` (`python/optiqal/analyzer.py`) defaults to
  `random_state = 42`, and `analyze()` passes that seed down to
  `simulate_qaly_profile_vectorized(...)`.
- The web API (`python/optiqal/web_api.py`) constructs `AnalysisConfig(...)`
  with `random_state=42` explicitly.

As a result, the same request to the analyzer or the web API returns the same
numbers across runs.

### Low-level calls are NOT deterministic by default

The low-level simulation functions in `python/optiqal/simulate.py` default
`random_state` to `None`:

```python
def simulate_qaly_profile_vectorized(..., random_state: Optional[int] = None): ...
def simulate_qaly(..., random_state: Optional[int] = None): ...
def simulate_qaly_profile(..., random_state: Optional[int] = None): ...
```

If you call any of these directly (bypassing `AnalysisConfig` / the web API)
**you must pass a seed** to get reproducible output:

```python
from optiqal.simulate import simulate_qaly_profile_vectorized

# Reproducible: pass an explicit seed
result = simulate_qaly_profile_vectorized(..., random_state=42)

# Nondeterministic: omits the seed (random_state=None)
result = simulate_qaly_profile_vectorized(...)
```

### Scope of the guarantee

Determinism here means: same seed + same inputs + same code → same NumPy draw
sequence → same statistics, within a single environment. Results may still differ
across NumPy major versions or platforms if the underlying RNG or floating-point
behavior changes. No cross-version bit-for-bit guarantee is enforced in code, so
none is claimed here.

## Legacy TypeScript engine

> The TypeScript QALY engine is legacy and being removed. The behavior below is
> still accurate for the current `src/lib/qaly/` code.

### How randomness is seeded

The seeded PRNG lives in `src/lib/qaly/random.ts` and wraps the `seedrandom`
package:

- `setSeed(seed)` makes the stream deterministic (number or string seed).
- `resetRandom()` returns to an unseeded (nondeterministic) state.
- At module load the PRNG is **unseeded** (`seedrandom()` with no argument);
  it only becomes deterministic once a seed is set.

### Default seed lives in the simulate wrappers

The public simulation wrappers in `src/lib/qaly/simulate.ts` default to
`seed = 42` and call `setSeed(seed)` before sampling, so calling them with no
options is reproducible:

```typescript
import { simulateQALYImpact } from "@/lib/qaly/simulate";

// Uses seed=42 by default (wrapper sets the seed)
const result = simulateQALYImpact(profile, effect);

// Custom numeric or string seed
const a = simulateQALYImpact(profile, effect, { seed: 123 });
const b = simulateQALYImpact(profile, effect, { seed: "my-experiment" });
```

Note the nuance: the determinism comes from the `simulate.ts` wrappers setting
the seed, **not** from `random.ts` itself (which is unseeded until `setSeed` is
called). Code that imports `random()` directly without first calling `setSeed`
gets nondeterministic values.

### Modules using the seeded RNG

The seeded `random()` is used across the legacy QALY modules, including
`simulate.ts`, `confounding.ts`, `state-diff.ts`, `state-hazard.ts`, and
`state-lifecycle.ts`. Within the legacy engine, `Math.random()` is not used for
simulation sampling.

### Paper results

Values in `src/lib/qaly/paper-results.ts` were generated with the legacy engine
at seed 42. They are reproducible by re-running that engine with the same seed,
subject to the same code-version caveat as above.

## Verifying reproducibility

Python (production):

```python
from optiqal.simulate import simulate_qaly_profile_vectorized

r1 = simulate_qaly_profile_vectorized(..., random_state=42)
r2 = simulate_qaly_profile_vectorized(..., random_state=42)
# Same seed + same inputs -> identical statistics
```

TypeScript (legacy):

```typescript
import { simulateQALYImpact } from "@/lib/qaly/simulate";

const opts = { nSimulations: 10000, seed: 42 };
const r1 = simulateQALYImpact(profile, effect, opts);
const r2 = simulateQALYImpact(profile, effect, opts);
console.assert(r1.median === r2.median, "Results should be identical");
```
