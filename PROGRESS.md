# PR D progress

## State

In progress on `rebuild/d-evidence-table`. The loader, evidence seed, live lineage
links, debt ratchets, and lint report are implemented; final full-suite verification
and the delivery report remain.

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
- Linked 15 catalog entries and nine intervention YAMLs to their applicable validated
  rows, with a regression test rejecting any dangling live lineage id.
- Generated and seeded exact live-debt snapshots: 74 unsourced claims, 114 unverified
  atoms, and 130 judgment atoms.
- Added bidirectional ratchet tests, deterministic snapshot writing, and per-item lint
  output with the three summary counts.
- Restored the fallback virtualenv's editable package link offline so subprocess tests
  use the same checkout; the first complete run otherwise reached 499 passing tests.

## Next

- Run all required verification commands and record their results.
