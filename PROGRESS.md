# PR A progress

## State

Implementation in progress on `rebuild/a-rng-priors`.

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

## Next

- Run Ruff and the full pytest suite, rerun the public frontier, and record the final comparison report.
