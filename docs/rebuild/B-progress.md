# PR B progress: the deletion

Lane brief: `docs/rebuild/B-deletion.md`. Branch `rebuild/b-deletion`, worktree
`/Users/maxghenis/optiqal-ai-rebuild-b`, based on `rebuild/one-engine` at `550f5cf0`.

## State

All five steps done. The intervention YAMLs live in the Python package; the
TypeScript engine, its served JSON, the orphaned Python modules and the
unconsumed MEPS binaries are gone; the docs describe what is left.

## Baseline captured before the first deletion (at `550f5cf0`)

| Artifact | sha256 |
| --- | --- |
| `/tmp/optiqal-b-frontier-before.json` (15 canonical scenarios) | `546d18e87ec0578bdf64bb444bea6868a6aab22089e7edd0c587c98c5e62a601` |
| `/tmp/optiqal-b-baseline-before.json` (same 15 payloads) | `8899d31c4c6fb9a3916b0e382993dddf7a4c809e49484eb29cf54e83f93f00f5` |

Both come from `/tmp/optiqal-b-capture.py`, which calls
`optiqal.web_api.build_frontier_response` and `build_baseline_response` over every
`CANONICAL_PUBLIC_FRONTIER_SCENARIOS` payload and dumps sorted-key JSON.

Reference measurements at the base commit:

- `uv run pytest -q -n auto`: 559 passed in 774 s.
- `python -c "import optiqal.web_api"` in a subprocess: mean 0.440 s over five runs
  (min 0.429, max 0.449). PyMC and ArviZ are not installed in this worktree, so
  `bayesian.py` imports with `HAS_PYMC = False`; the module still loads.

## Done

1. **Move the intervention YAMLs.** `git mv` of the ten files from
   `src/lib/qaly/interventions/` to `python/optiqal/data/interventions/`.
   `intervention.py` gained `INTERVENTIONS_DIR` and `packaged_intervention_path()`
   (its `from_yaml` had no default path to update, only a docstring). Readers
   updated: `optiqal/__init__.py` docstring and exports, `tests/test_priors_drift.py`
   (PR A's glob), `tests/test_simulate_streams.py`, `scripts/precompute_all.py`,
   `scripts/precompute_profiles.py`, `scripts/README.md`, `python/README.md`.

2. **Delete the TypeScript engine.** `src/lib/qaly` (41 files after the YAML move),
   `src/lib/evidence` (11 files) and `public/precomputed` (14 JSON files, 11 MB).
   Grep before deleting `public/precomputed`: the only readers of `/precomputed/*`
   are `src/lib/evidence/baseline/precomputed.ts`,
   `src/lib/evidence/baseline/precomputed-profiles.ts` and
   `src/lib/qaly/precomputed-profiles.ts`, all inside the deleted directories.
   Nothing under `src/app`, `src/components` or `next.config.ts` reads it.
   `seedrandom` and `@types/seedrandom` went with `src/lib/qaly/random.ts`, their
   only importer. `scripts/precompute_all.py`, `precompute_profiles.py` and
   `validate_precomputed.py` now write and read `build/precomputed/` (gitignored);
   `precompute_baselines.py` writes only the Python copy. The thesis page no longer
   claims a TypeScript simulation path.

3. **Delete the orphaned Python modules.** `bayesian.py`, `bayesian_updating.py`,
   `markov.py`, `population.py`, `tests/test_bayesian_updating.py`,
   `tests/test_mortality_multipliers.py`, `scripts/precompute_baseline_profiles.py`.
   `precompute.py` lost its `bayesian` try-except and its `use_mcmc` branch;
   `__init__.py` lost the lazy `run_mcmc` export. `pyproject.toml` lost the
   `bayesian` extra and `uv.lock` was refreshed (pymc, pytensor, arviz, xarray,
   numba and their transitive dependencies dropped). Python tests fall from 559 to
   546; the 13 removed all covered deleted modules.

   `profile.get_baseline_mortality_multiplier` carried a NOTE saying diabetes and
   hypertension were excluded because `markov.HealthState` applied them. That is no
   longer a live reason. The comment now records what the code actually does:
   `web_api.build_baseline_response` applies both condition relative risks itself,
   while the `simulate.py` and `stack_interactions.py` callers apply neither and
   never read `profile.has_diabetes` or `profile.has_hypertension`. The gap is
   recorded rather than closed, because closing it moves served numbers.

   Import cost, measured in one venv with the base-commit tree restored under
   `/tmp/optiqal-b-before-tree`: cumulative `-X importtime` for `optiqal.web_api`
   is 0.556 s before and 0.539 s after (median of seven subprocess runs). PyMC and
   ArviZ are not installed here, so `bayesian.py` cost only its own parse and
   execute; the roughly two-second cold start the lane brief cites needs the
   `bayesian` extra, which no longer exists.

4. **Remove the unconsumed data.** The four AHRQ MEPS year parquet files plus
   `meps_combined.parquet` (50 MB, no git-LFS) and `condition_joint_distribution.json`
   (88 KB, no recorded source) are gone at `9bbbabaa`; history is not rewritten.
   `fetch_meps.py`, `quality_weight_calibration.json` and PR E's snapshots stay.
   `.gitignore` now excludes `python/optiqal/data/meps/*.parquet`.
   `docs/DATA_PROVENANCE.md` replaces its two open gaps with a Removals section
   carrying the commit hash, the no-history-rewrite statement and the regeneration
   command, and its `baselines.json` section no longer points at the deleted
   TypeScript mirrors.

5. **Rewrite the docs to match what is left.**
   - `PRODUCT_STRATEGY.md`: the free/paid-individual/paid-pro tier list is
     replaced by a "What ships" section — the engine, the evidence table, the
     results file and the scoreboard, all public, no tiers. Go-to-market phase 3
     no longer proposes team plans.
   - `REPRODUCIBILITY.md`: rewritten around one engine. It now names the two
     routes, the bridge, the FastAPI wrapper, `_spawn_generators` (four streams
     vectorized, two in the loop simulators), the snapshot loader and
     `priors.yaml`. The legacy TypeScript section and the `paper-results.ts`
     paragraph are gone.
   - `python/README.md`: rewritten. No MCMC install path, no MCMC example, no
     "for TypeScript web app". Adds what the web serves and where the numbers
     come from.
   - `README.md`: adds a "How it is put together" section naming the one engine
     and the two routes; fixes the absolute-path link to `PRODUCT_STRATEGY.md`
     and drops "monetization plan"; corrects the stack (Next.js 16, not 15).
   - `PRECOMPUTED_BASELINES_SUMMARY.md`, `docs/precomputed-baselines.md` and
     `docs/precomputed-quick-start.md`: trimmed to the surviving Python half.
     Each of the three described a mixed system, so none was deleted outright.
     The 8% speedup claim was re-measured this session (4,871 against 4,465
     simulations/second) instead of inherited.
   - `docs/optiqal_results.py`: the docstring no longer says it wraps
     `paper-results.ts`. It now says the exercise prior comes from `priors.yaml`
     and the rest are hand-entered literals no code reproduces.
   - `src/app/thesis/page.tsx`: "450 TypeScript tests passing" and "121 Python
     tests passing" were both stale before this branch. They are now 546 Python
     engine tests and 43 web tests, both measured today.
   - `scripts/calibrate_nhanes.py`: dropped `generate_typescript_file`, which
     wrote into the deleted `src/lib/evidence/baseline/`.
   - `REBUILD.md`: PR B notes appended, nothing else touched.

## Not done, and why

- `python/optiqal/web_api.py` holds the NHANES calibration factors as literals
  (`CALIBRATION_BY_AGE_SEX`, `CALIBRATION_BY_SEX`) rather than reading
  `data/nhanes/calibration.json`. That is a live provenance gap, but closing it is
  a load-from-snapshot change of the kind PR E did, not a deletion.
- `docs/index.md`, `docs/methodology.md` and `docs/appendix.md` are left alone
  beyond the `paper-results.ts` reference, per the lane brief. PR F retires the
  paper.
- `autoagent/` and the public-frontier benchmark are untouched, per the brief.
