# PR A fixes (review round 1)

You are fixing PR A of the Optiqal rebuild in place. Worktree: `/Users/maxghenis/optiqal-ai-rebuild-a`,
branch `rebuild/a-rng-priors`. Read `REBUILD.md`, the original brief
`/Users/maxghenis/optiqal-ai-rebuild/docs/rebuild/A-rng-priors.md`, `PR_A_REPORT.md`, `PROGRESS.md`,
`python/optiqal/simulate.py`, `python/optiqal/analyzer.py`, `python/optiqal/priors.py`,
`python/optiqal/data/priors.yaml`, `python/tests/test_simulate_streams.py`, `python/tests/test_priors.py`,
`python/tests/test_priors_drift.py`, `python/tests/test_analyzer.py`, and `docs/methodology.md`.

Setup: `cd /Users/maxghenis/optiqal-ai-rebuild-a/python`; the venv exists; use
`PYTHONPATH=. uv run --no-sync`.

## HEADLESS EXECUTION

Single headless turn; no background jobs, no waiting patterns; every command synchronous.
Move `PROGRESS.md` to `docs/rebuild/A-progress.md` and keep it updated with each step. Final
message is the deliverable.

## Required (from the read-only review; every claim below was confirmed by reading the code)

1. **The RNG independence test never calls the simulator.** `tests/test_simulate_streams.py:42-61`
   rebuilds `SeedSequence(seed).spawn(4)` itself and correlates its own draws, so it passes on
   the unfixed base. Rewrite it to capture what `simulate_qaly_profile_vectorized(...,
   random_state=seed)` actually draws (spy `Distribution.sample`, `ConfoundingPrior.sample`,
   and the quality-offset generator via monkeypatch) and correlate those arrays; assert the
   HR draw receives a `Generator`, not an int. Confirm the rewritten test FAILS when the base
   coupling is restored (do that experiment in a temp copy of the file, or by temporarily
   reverting the four-line change and running the test, then restoring; say what you did).
2. **`override_hr` is silently dropped for QoL-only entries.** `analyzer.py:242-247` and
   `:301-307` compute an overridden HR, but `_simulate_one` now receives
   `entry.has_direct_mortality_effect` and drops the mortality arm regardless, so
   `Decision(type="adjust", item_id="hiit_2x_week", override_hr=0.85)` yields exactly 0.0
   where the base gave a real effect. Build the arm when the override is not 1.0; add a test
   for an override on a QoL-only item and keep the exact-zero test for the no-override case.
3. **Walking's rationale argues for the number it replaced.** `priors.yaml:249-257`,
   `src/lib/qaly/interventions/walking_30min_daily.yaml:50-54` and `docs/methodology.md:493`
   still cite the sibling-comparison ~33% directly above Beta(1.2, 6.0). Rewrite the rationale
   and calibration sources to the exercise-category justification and note that the item-level
   sibling estimate is superseded pending PR G. Same check for the Mediterranean-diet item.
4. **The report omits three material facts.** Add to `PR_A_REPORT.md`: (a) the protocol
   optimizer's verdict on `vitamin_d_2000` flips from drop to keep under independent streams
   (the test rebase in `ef1e2221`); (b) mortality legs on the three personal items moved 22
   to 26% and statin's total moved +40.5%, against the brief's 6 to 8% expectation, with one
   sentence on why a difference of larger legs amplifies; (c) the "exactly 0.0" QoL-only
   figures were measured on the catalog path, which already gated on the flag; the fix's
   effect is on the decisions path, so quantify hiit_2x_week's decision-path mortality before
   and after (the review expects roughly -0.005 before, 0.0 after). Also record that the
   null-item residual shrank from about -0.035 to about +0.01 QALY.
5. **Eight item-level priors still differ from their category** (daily_exercise_moderate,
   strength_training, sleep_8_hours, moderate_alcohol, quit_smoking and three more). The
   drift test compares YAMLs to `priors.yaml.interventions`, so they are consistent by
   construction and are legitimate overrides under the charter schema, but say so: add one
   paragraph to `REBUILD.md`'s PR A notes listing them as overrides for PR G to collapse,
   and change `docs/appendix.md:297`'s "Weighted average: ~0.33" conclusion to match the
   served 17% or delete the sentence (it was never computed from anything).

## Nice to have (do them if the required set is green with time left)

6. Extend `test_priors_drift.py` to the two YAML example blocks in `docs/methodology.md`
   (~470-476, ~487-493) and to the `Mean` column of `docs/index.md`'s table.
7. Extend the AST literal guard in `test_priors.py:275-294` to `make_spec` / `StackSpec` calls
   carrying numeric `conf_alpha` / `conf_beta`.
8. De-flake `test_seeded_walking_mean_matches_independent_runs_within_mc_error` by drawing
   the ten reference runs from ten fixed seeds.
9. Add a `@pytest.mark.slow` variant of the end-to-end protocol smoke test at the production
   40,000 draws (the fast one stays at 1,000).
10. Fix the "76 hand-set Beta priors" count in the PR A notes (there are 77 keys).

## Verification before your final commit

    cd /Users/maxghenis/optiqal-ai-rebuild-a/python
    uv run --no-sync ruff check . && uv run --no-sync ruff format --check .
    PYTHONPATH=. uv run --no-sync pytest -q

`tests/test_model_regression.py` must pass without a further rebaseline (the override fix
does not touch the served catalog path; if it does move a golden, stop and say why).

## Rules

Small commits on `rebuild/a-rng-priors`, imperative subjects, explanatory bodies,
`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Never push. Never touch other
worktrees, `origin`, `src/lib/qaly/paper-results.ts`, or `~/clawd/data/health.db`. Never change
a prior value; this round changes tests, one analyzer path, and prose.

## Final message

Commits; the independence test's result on base coupling (must fail) and on the branch (must
pass); the override test's before/after numbers; the hiit_2x_week decision-path numbers; which
nice-to-haves landed; tails of ruff and pytest naming the commit they cover.
