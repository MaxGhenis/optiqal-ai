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
