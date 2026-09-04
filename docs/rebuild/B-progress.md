# PR B progress: the deletion

Lane brief: `docs/rebuild/B-deletion.md`. Branch `rebuild/b-deletion`, worktree
`/Users/maxghenis/optiqal-ai-rebuild-b`, based on `rebuild/one-engine` at `550f5cf0`.

## State

Step 1 of 5 done: the ten shipped intervention YAMLs now live inside the Python
package.

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

## Next

2. Delete `src/lib/qaly`, `src/lib/evidence` and `public/precomputed`.
3. Delete `bayesian.py`, `bayesian_updating.py`, `markov.py`, `population.py`, their
   tests and `scripts/precompute_baseline_profiles.py`; strip the MCMC branch from
   `precompute.py` and `run_mcmc` from `__init__.py`; drop the `bayesian` extra.
4. `git rm` the five MEPS parquet files and `condition_joint_distribution.json`;
   record the removal in `docs/DATA_PROVENANCE.md`.
5. Rewrite `PRODUCT_STRATEGY.md`, `REPRODUCIBILITY.md`, `python/README.md`,
   `README.md` and `PRECOMPUTED_BASELINES_SUMMARY.md`; append PR B notes to
   `REBUILD.md`.
