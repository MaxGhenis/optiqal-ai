# Review PR B of the Optiqal rebuild (read-only)

Review the branch `rebuild/b-deletion` in `/Users/maxghenis/optiqal-ai-rebuild-b` against its
base `rebuild/one-engine` at `550f5cf0` (`git diff 550f5cf0...HEAD --stat`; six commits, about
330k lines deleted). The brief: `/Users/maxghenis/optiqal-ai-rebuild/docs/rebuild/B-deletion.md`;
the charter: `/Users/maxghenis/optiqal-ai-rebuild/REBUILD.md`; the lane's ledger:
`/Users/maxghenis/optiqal-ai-rebuild-b/docs/rebuild/B-progress.md`.

Read-only: no commits, no file changes, no `git checkout`. You may not have a shell; if you do,
you may run `cd /Users/maxghenis/optiqal-ai-rebuild-b/python && PYTHONPATH=. uv run --no-sync pytest -q`
and, at the worktree root, `bun run typecheck && bun run lint && bun run test`
(`node_modules` is present). If you have no shell, say so and do everything by reading.

Attack, in order:

1. **Served output unchanged.** The brief required capturing the frontier and baseline JSON
   for the canonical scenarios before the first deletion and after the last, byte-identical,
   with both sha256 in the ledger. Find that evidence in `docs/rebuild/B-progress.md` and the
   commit bodies; if the two hashes are not recorded, or were recorded on different
   scenarios, that is a finding. If you have a shell, recompute them yourself on the branch
   and on `550f5cf0` (a `git worktree` of the base is not allowed; use `git archive 550f5cf0 |
   tar -x -C /tmp/optiqal-b-base` instead).
2. **Nothing served imports anything deleted.** Grep `src/app`, `src/components`, `src/lib`
   (what remains), `backend/`, `python/optiqal/web_api.py` and its imports for references to
   `lib/qaly`, `lib/evidence`, `precomputed`, `bayesian`, `markov`, `population`,
   `condition_joint_distribution`, `meps_20`. Check `next.config.ts`, `vercel.json`,
   `scripts/prepare-model-deploy.mjs`, `scripts/deploy-vercel.mjs` and the CI workflow for
   paths that no longer exist.
3. **The YAML move.** All ten intervention YAMLs live under
   `python/optiqal/data/interventions/`; `Intervention.from_yaml` defaults, the priors drift
   test glob, `precompute.py`, the tests and the package data configuration in
   `python/pyproject.toml` point at the new location; the wheel would ship them.
4. **Data removal.** The five parquet files and `condition_joint_distribution.json` are gone
   from the tree, history was not rewritten, `fetch_meps.py` and
   `quality_weight_calibration.json` remain, and `docs/DATA_PROVENANCE.md` records the
   removal commit and the regeneration command.
5. **Docs.** `REPRODUCIBILITY.md`, `python/README.md`, `README.md` and `PRODUCT_STRATEGY.md`
   describe only what remains; no mention of the TypeScript engine, MCMC, Markov, precomputed
   profiles as served artifacts, or paid tiers survives (grep for them). Sentence case,
   present tense, no argument with an absent critic.
6. **Tests.** No test was weakened: compare test and assert counts per surviving file
   against the base; deleted test files correspond only to deleted modules.
7. **Scope.** Anything changed outside the brief; `docs/optiqal_results.py`, `docs/index.md`
   and `deploy-paper.yml` must be untouched except for `paper-results.ts` references.

Return findings as the FINAL MESSAGE (write no files): a verdict line (merge / merge after
fixes / do not merge), then findings ranked by severity with file:line and the fix. Mark every
claim READ, COMPUTED, or INFERRED.
