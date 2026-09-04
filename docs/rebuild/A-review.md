# Review PR A of the Optiqal rebuild (read-only)

Review the branch `rebuild/a-rng-priors` in `/Users/maxghenis/optiqal-ai-rebuild-a` against its
base `rebuild/one-engine` (`git diff rebuild/one-engine...HEAD`; ignore `docs/rebuild/*.md`
appearing deleted, the branch predates them). The brief: `/Users/maxghenis/optiqal-ai-rebuild/docs/rebuild/A-rng-priors.md`;
the charter: `/Users/maxghenis/optiqal-ai-rebuild/REBUILD.md`; the lane's report:
`/Users/maxghenis/optiqal-ai-rebuild-a/PR_A_REPORT.md`.

Read-only: no commits, no file changes, no `git checkout`. Run tests with
`cd /Users/maxghenis/optiqal-ai-rebuild-a/python && PYTHONPATH=. uv run --no-sync pytest -q tests/test_simulate_streams.py tests/test_priors_drift.py tests/test_confounding.py tests/test_simulate.py tests/test_analyzer.py`
and anything else you need; the full suite takes 18 minutes and the lane reports 512 green.

Attack, in order of what would hurt most if wrong:

1. **RNG independence.** Reconstruct the draws the way `simulate_qaly_profile_vectorized`
   now makes them and confirm the quality-offset and log-HR streams are independent at seeds
   42, 1, 7, and that the loop simulators (`simulate_qaly`, `simulate_qaly_profile`) and
   `analyzer._simulate_one` no longer share a seed either. Confirm an HR-1.0 item yields
   exactly 0.0 mortality QALY through the analyzer path, not just the vectorized one.
   Confirm seeded runs are bit-reproducible.
2. **priors.yaml is behavior-preserving except where stated.** The lane moved every prior
   into `python/optiqal/data/priors.yaml` and then changed the SERVED value of two
   intervention YAMLs (walking Beta(2.5,5) → Beta(1.2,6); mediterranean Beta(6,2.5) → Beta(3,3))
   on the rule "code value wins". Check: (a) the frozen fixture equals the base branch's
   literals for every category and tier (diff programmatically against
   `git show rebuild/one-engine:python/optiqal/confounding.py`, `qol_evidence.py`, `catalog.py`);
   (b) no OTHER served value changed: run the catalog analyzer on the base and the branch for
   the same profile and seed for the 13 mortality-bearing personal items and confirm only
   the RNG shift and the two declared prior changes explain differences; (c) walking's
   post-change mean 0.1017 is consistent with the 17% prior (ratio to the 33% value).
3. **The drift test really parses the docs.** Break a Beta value in `docs/methodology.md`
   in a temp copy and show the test catches it; confirm it parses `docs/index.md`'s table
   and every intervention YAML, and that a new YAML without a prior is caught.
4. **Paper corrections are computed, not typed.** Confirm the interval 0.8–49.0%, the tail
   0.039, and the E-values 2.21 and 5.04 are rendered from code (`docs/optiqal_results.py`
   or tests against scipy / `calculate_e_value`) rather than pasted.
5. **Goldens.** The rebaseline commit lists before and after for walking and three catalog
   items; confirm the numbers in the commit body match what the tests now assert, and that
   the QoL-only items did not move.
6. **The "Rebase protocol optimizer sign cases" and "Bound protocol smoke-test runtime"
   commits.** These were not in the brief. Read them: do they change model behavior or hide
   a failure? Say exactly what they do.
7. Anything else outside scope; any weakened test.

Return findings as the FINAL MESSAGE (write no files): a verdict line (merge / merge after
fixes / do not merge), then findings ranked by severity with file:line, what you ran, and
the fix. Mark every claim READ, COMPUTED, or INFERRED.
