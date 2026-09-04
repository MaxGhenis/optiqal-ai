# PR D progress

## State

In progress on `rebuild/d-evidence-table`. The fail-closed loader and evidence seed are
committed, and all applicable catalog/YAML lineages are linked; debt snapshots remain.

## Done

- Confirmed the requested branch and clean starting worktree.
- Read `REBUILD.md`, `docs/DATA_PROVENANCE.md`, and `docs/canonical-model-v1.md`.
- Began inventories of catalog claims, intervention citations, calibration references,
  lineage parsing, and the live judgment vocabularies.
- Attempted `uv sync`; the sandbox blocks the global uv cache and external package DNS,
  so dependency setup is being recovered from the existing local cache.
- Added canonical `study_ids` to catalog entries and intervention lineage parsing, and
  added a lineage block to all ten legacy intervention YAMLs.
- Added the strict `StudyRow` loader, offline fixture checker, Europe PMC refresh path,
  CI wiring, validation tests, and the two missing study-design tiers.
- Resolved the requested citation inventory and seeded 48 abstract-supported estimate
  rows backed by 46 offline PMID fixture records; unsupported estimates remain debt.
- Linked 14 catalog entries and nine intervention YAMLs to their applicable validated
  rows, with a regression test rejecting any dangling live lineage id.

## Next

- Generate the three ratchets and add the lint report.
- Run all required verification commands and record their results.
