# PR D progress

## State

Complete on `rebuild/d-evidence-table`. The loader, evidence seed, live lineage
links, debt ratchets, lint report, full verification, and delivery report are all
committed.

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
- Verified the final committed implementation: 519 tests pass, Ruff and format checks
  pass, the offline evidence check reports 48 rows/46 identifiers, and lint reports
  ratchet counts of 74/114/130.
- Recorded the complete delivery, PR G mismatch list, verification tails, and external
  environment limitations in `FINAL_REPORT.md`.

## Next

- In PR G, adjudicate the ten typed-value differences recorded in the judgment
  ratchet without silently copying estimates across doses, populations, or endpoints.
- Reduce the committed evidence-debt snapshots only when a claim gains traceable
  abstract-supported provenance or a hand-set judgment is removed.
