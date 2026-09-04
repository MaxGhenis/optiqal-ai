# PR D progress

## State

Review round 1 fixes in progress on `rebuild/d-evidence-table`. The eleven findings
from the read-only review are being closed in order; each step lands as its own commit.

## Done

- Read `REBUILD.md`, the PR D brief, `evidence.py`, `ratchets.py`, `verify_evidence.py`,
  `studies.yaml`, `doi_fixture.json`, `test_evidence.py`, `test_ratchets.py`,
  `FINAL_REPORT.md`, and the previous progress ledger.
- Read the `Refresh the DOI fixture from Europe PMC` commit diff: the refreshed fixture
  carries real titles and years and an empty `journal` for all 46 identifiers.
- Matched all 48 rows against the 46 cached Europe PMC abstracts offline. Every row has at
  least one verbatim abstract sentence carrying its point estimate and both interval bounds.
- Moved the progress ledger to `docs/rebuild/D-progress.md`.

## Next

- Extend the schema (`ci_level`, `verified_by`), the quote rules, and the loader.
- Rewrite every `notes` field as the verbatim abstract sentence.
- Teach `verify_evidence.py` the `journalInfo.journal.title` key, abstract hashing, per-row
  quote digests, and the offline `--abstracts-cache` refresh mode.
- Demote cross-population, cross-exposure and cross-endpoint links to `transport`.
- Make `known_unsourced_claims` require an endpoint-compatible linked row and regenerate
  the three ratchets.
- Rewrite `FINAL_REPORT.md`'s verification claims and append the PR D notes to `REBUILD.md`.
