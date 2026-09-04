# PR B: the deletion

You are building PR B of the Optiqal rebuild. Worktree: `/Users/maxghenis/optiqal-ai-rebuild-b`,
branch `rebuild/b-deletion`, branched from `rebuild/one-engine` after PR A landed. Read
`REBUILD.md` at the worktree root first, then `docs/rebuild/A-rng-priors.md` (what PR A
changed: `priors.yaml`, the drift test that globs `src/lib/qaly/interventions/*.yaml`, the
paper corrections), `docs/DATA_PROVENANCE.md`, `REPRODUCIBILITY.md`, `python/README.md`,
`README.md`, `PRODUCT_STRATEGY.md`, `python/optiqal/__init__.py`, `python/optiqal/precompute.py`,
`python/optiqal/intervention.py` (the `from_yaml` loader and its default paths),
`src/app/api/frontier/route.ts`, `src/app/api/baseline/route.ts`, `src/lib/python-bridge.ts`,
and `scripts/prepare-model-deploy.mjs`.

Setup: `cd /Users/maxghenis/optiqal-ai-rebuild-b/python && uv sync`; then at the worktree root
`bun install` (the lockfile is `bun.lock`). Use `bun`, never npm.

## HEADLESS EXECUTION

You run as a single headless turn. There are no later turns. Never use background jobs,
sleep-and-poll, "I'll wait for", or "standing by" patterns; run every command synchronously
to completion (`bun run build` and the Python suite each take minutes; that is fine). Your
final message is the deliverable. If you cannot finish, say exactly what is done and what is
not.

## Verified facts (2026-09-03, refuters with repo access)

- `src/lib/qaly` (52 files, 12,817 non-test lines) has no importers from `src/app` or
  `src/components`, direct or transitive. Its only importer anywhere is
  `src/lib/evidence/baseline/uncertain-baseline.ts`, which `src/lib/evidence/baseline/index.ts`
  re-exports and which `src/lib/qaly/simulate.ts` imports back: the two directories import
  each other and nothing outside them. `REPRODUCIBILITY.md` lines 14-16 already call the
  TypeScript engine legacy.
- The served pages `/predict` and `/analyze` POST to `/api/baseline` and `/api/frontier`
  (`src/components/predict/baseline-workbench.tsx:152`,
  `src/components/analyze/frontier-workbench.tsx:367`). Both routes run the Python engine:
  locally by spawning `python/scripts/web_baseline.py` and `web_frontier.py` through
  `src/lib/python-bridge.ts`; in production through the FastAPI wrapper `backend/main.py`,
  which imports the same `optiqal.web_api` functions (deployed as the `optiqal-model` Vercel
  project by `scripts/prepare-model-deploy.mjs`).
- `import optiqal.web_api` loads `optiqal.bayesian` (and arviz, pytensor, about two seconds
  of cold start) because `optiqal/__init__.py` line ~79 imports `precompute` at top level and
  `precompute.py` lines ~23-28 import `bayesian` inside a try-except. With `bayesian`,
  `markov`, `bayesian_updating`, `population` and `validation.pan_ukb` blocked, the frontier
  and baseline JSON for the canonical scenarios were byte-identical.
- Importers of the modules to delete: `markov` from `population.py` (lazy) and
  `scripts/precompute_baseline_profiles.py:36` and `python/tests/test_mortality_multipliers.py:15`;
  `bayesian` from `__init__.py` (lazy, inside `run_mcmc`) and `precompute.py`;
  `bayesian_updating` from `python/tests/test_bayesian_updating.py` only; `population` from
  nothing. `scripts/precompute_all.py`, `scripts/precompute_profiles.py`,
  `python/tests/test_precompute.py` and `python/README.md` reference `precompute`, which
  stays.
- `python/optiqal/data/meps/` holds four raw AHRQ MEPS parquet files plus
  `meps_combined.parquet` (about 50 MB, committed without git-LFS) that only the orphaned
  `population.py` reads at runtime; `condition_joint_distribution.json` is read only by
  `markov.py` and has no recorded source. `docs/DATA_PROVENANCE.md` lines ~132-153 already
  recommend hosting the parquet externally and say: do not rewrite git history.
- `public/precomputed/` is 11 MB of JSON generated for the TypeScript engine.
- `PRODUCT_STRATEGY.md` lines ~154-170 describe free, paid-individual and paid-pro tiers; no
  auth, payments or accounts exist in the code.

## Do

1. Delete `src/lib/qaly` and `src/lib/evidence` in one commit, after moving the ten
   intervention YAMLs from `src/lib/qaly/interventions/` to
   `python/optiqal/data/interventions/` and updating every path that reads them:
   `intervention.py`'s `from_yaml` defaults and docstrings, `optiqal/__init__.py`'s docstring
   example, `precompute.py`, the tests, and PR A's `tests/test_priors_drift.py` glob. Before
   deleting `public/precomputed`, grep `src/` and `next.config.ts` for readers; delete it only
   if nothing served reads it, and say what you found.
2. Delete `python/optiqal/bayesian.py`, `bayesian_updating.py`, `markov.py`, `population.py`,
   `python/tests/test_bayesian_updating.py`, `python/tests/test_mortality_multipliers.py`,
   `scripts/precompute_baseline_profiles.py`; strip the `bayesian` try-except and the
   `use_mcmc` branch from `precompute.py` and the lazy `run_mcmc` export from `__init__.py`;
   fix `scripts/precompute_all.py`, `scripts/precompute_profiles.py` and
   `python/tests/test_precompute.py` accordingly; drop the `bayesian` optional-dependency
   group from `python/pyproject.toml` and refresh `uv.lock`. Keep `validation/pan_ukb.py` and
   its console script (the Mendelian-randomization pipeline is a future calibration-row
   source).
3. `git rm` the five parquet files and `condition_joint_distribution.json`; keep
   `fetch_meps.py` and `quality_weight_calibration.json` (and PR E's snapshots). In
   `docs/DATA_PROVENANCE.md`, record the removal commit, that history was not rewritten, and
   the regeneration command.
4. `PRODUCT_STRATEGY.md`: replace the tier section with a short statement of the open-engine
   positioning (the engine, the evidence table, the results file and the scoreboard are the
   product; there are no tiers). Present tense, sentence case, no argument with an absent
   critic.
5. Rewrite `REPRODUCIBILITY.md`, `python/README.md` and the relevant `README.md` sections to
   describe what remains: one Python engine, the two routes, the FastAPI wrapper, the
   rebuild charter. Remove every mention of the TypeScript engine, MCMC, Markov and the
   precomputed-profiles JSON as served artifacts. Delete `PRECOMPUTED_BASELINES_SUMMARY.md`
   if it describes only the deleted system; otherwise trim it.
6. Leave `docs/optiqal_results.py`, `docs/index.md` and `deploy-paper.yml` alone except to
   remove references to `paper-results.ts` (PR F retires the paper). Leave `autoagent/` and
   the public-frontier benchmark alone.

## Verification before your final commit

Before your first deletion, on the base commit, capture the served outputs:

    cd /Users/maxghenis/optiqal-ai-rebuild-b/python
    uv run python -c "import json; from optiqal.web_api import build_frontier_response, build_baseline_response, CANONICAL_PUBLIC_FRONTIER_SCENARIOS as S; \
      print(json.dumps([build_frontier_response(s) for s in S[:3]], sort_keys=True))" > /tmp/optiqal-b-frontier-before.json

(adapt to the real shape of `CANONICAL_PUBLIC_FRONTIER_SCENARIOS` and to
`build_baseline_response`'s payload; read `web_api.py` first). Repeat after the last deletion
and `diff` the files: they must be byte-identical, and the final message carries both sha256s.

Then, all green:

    uv run ruff check . && uv run ruff format --check . && uv run pytest -q
    cd .. && bun run typecheck && bun run lint && bun run test && bun run build

Run `bun run test:e2e` if `bunx playwright install chromium` succeeds; otherwise say so.
Also measure `python -c "import optiqal.web_api"` wall time before and after.

## Rules

Commit in steps on `rebuild/b-deletion` (the YAML move, the TypeScript deletion, the Python
deletion, the data removal, the docs), imperative subjects, bodies that say what moved and
why, every message ending with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
Never push. Never touch other worktrees, `origin`, or `~/clawd/data/health.db`. Do not edit
`REBUILD.md` except to append a dated "PR B notes" section.

## Final message

1. Commits (hash, subject) and total lines deleted (`git diff --shortstat rebuild/one-engine`).
2. The before/after sha256 of the frontier and baseline JSON, and the import wall time.
3. What `public/precomputed` grep found and what you did.
4. Tails of `pytest`, `ruff`, `typecheck`, `lint`, `test`, `build`, and e2e if run.
5. Anything not done, and why.
