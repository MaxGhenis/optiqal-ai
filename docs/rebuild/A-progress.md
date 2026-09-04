# PR A progress

## State

Complete on `rebuild/a-rng-priors`; final evidence is recorded in `PR_A_REPORT.md`.

## Done

- Read the rebuild charter, provenance and canonical-model notes, and every source file named in the PR brief.
- Prepared the Python environment with the system packages available to the sandbox.
- Captured the pre-change RNG coupling, walking estimate, catalog mortality estimates, and default public frontier.
- Audited the prior-loading and documentation-drift surfaces in parallel.
- Derived independent quality, hazard-ratio, causal-fraction, and harm streams from one seed sequence.
- Made point-null and absent direct mortality arms exact across vectorized, loop, catalog, and analyzer paths.
- Added regressions for stream correlation, seeded reproducibility, null mortality, and seeded-vs-unseeded agreement.
- Moved category, intervention, protocol, evidence-tier, and QoL transport priors into one validated registry.
- Added a frozen 2026-09-04 fixture, runtime-equivalence checks, and a guard against numeric `ConfoundingPrior` literals.
- Aligned shipped walking and Mediterranean-diet priors plus both documentation tables to the served registry values.
- Added drift tests covering all eight documented categories and every shipped intervention YAML.
- Corrected the exercise-prior interval and tail, the protective E-value formula, both reported E-values, and the sensitivity-analysis label through executable paper values.
- Ran the model-regression rebaseline exactly once and recorded mortality-bearing and QoL-only comparison values.
- Rebased the optimizer sign regression: aspirin remains a negative drop case, while vitamin D is now a positive keep case under independent streams.
- Made protocol draw-count defaults resolve at call time so the end-to-end shape/I/O smoke test can use 1,000 draws while production remains at 40,000.
- Verified the canonical default public frontier after the changes.
- Passed the exact full Python suite (512 tests) and Ruff check.
- Recorded the final handoff report.

## Next

- Ready for review; the branch has not been pushed.

## Review round 1 (2026-09-04)

State: fixing the read-only review findings in place on `rebuild/a-rng-priors`.

### Round-1 items

1. Rewrite the RNG independence test so it observes the simulator's own draws.
2. Restore the mortality arm on the decisions path when `override_hr` is set.
3. Rewrite walking and Mediterranean rationales off the superseded sibling estimate.
4. Add the three missing facts to `PR_A_REPORT.md`.
5. Document the eight item-level prior overrides and fix the appendix conclusion.
6. Nice-to-have: extend the drift test to the methodology YAML blocks and the paper Mean column.
7. Nice-to-have: extend the AST guard to `make_spec` / `StackSpec`.
8. Nice-to-have: de-flake the seeded-versus-unseeded walking test.
9. Nice-to-have: add a slow 40,000-draw protocol smoke test.
10. Nice-to-have: correct the hand-set protocol prior count.

### Done

- Moved the progress file to `docs/rebuild/A-progress.md`.
- Item 1: rewrote the RNG independence test so it observes the simulator's own draws
  through a spy on `Distribution.sample`, `ConfoundingPrior.sample` and the
  quality-offset generator, and asserts the hazard-ratio draw receives a `Generator`.
  Confirmed by experiment that the rewritten test fails when the four-line coupling is
  restored in `simulate_qaly_profile_vectorized` (4 failures) and passes on the branch.

- Applied `ruff format` to the four files the branch left unformatted.
- Item 2: `_decision_has_mortality_arm` restores the mortality arm on the decisions
  path when a decision supplies an `override_hr` other than 1.0. Measured at n=1,000,
  seed 42, the 45-year-old male never-smoker profile: `hiit_2x_week` with
  `override_hr=0.85` moved from 0.0 to 0.104779 QALY, the no-override ADD decision
  stays exactly 0.0, and a 1.0 override stays exactly 0.0.

### Next

- Item 8: de-flake the seeded-versus-unseeded walking comparison.
