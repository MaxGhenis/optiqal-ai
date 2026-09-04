# PR D progress

## State

In progress on `rebuild/d-evidence-table`. The rebuild charter, data provenance note,
canonical model, and required evidence-bearing code and documentation are under review.

## Done

- Confirmed the requested branch and clean starting worktree.
- Read `REBUILD.md`, `docs/DATA_PROVENANCE.md`, and `docs/canonical-model-v1.md`.
- Began inventories of catalog claims, intervention citations, calibration references,
  lineage parsing, and the live judgment vocabularies.
- Attempted `uv sync`; the sandbox blocks the global uv cache and external package DNS,
  so dependency setup is being recovered from the existing local cache.

## Next

- Add the fail-closed study schema, fixture verification command, and tests.
- Resolve and seed eligible study rows; record every refused atom with its reason.
- Wire verified study ids into the catalog and intervention lineage.
- Generate the three ratchets and add the lint report.
- Run all required verification commands and record their results.
