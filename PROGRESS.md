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

## Next

- Consolidate hand-set priors in `python/optiqal/data/priors.yaml` with validation and a frozen fixture.
- Add cross-artifact drift tests and correct the documentation.
- Rebaseline once, run Ruff and the full pytest suite, and record the final comparison report.
