# PR D progress

## State

Review round one of PR D is closed on `rebuild/d-evidence-table`. All eleven findings are
addressed; each landed as its own commit. What remains is the verification sweep and the
rewritten `FINAL_REPORT.md`.

## Done

- Read `REBUILD.md`, the PR D brief, `evidence.py`, `ratchets.py`, `verify_evidence.py`,
  `studies.yaml`, `doi_fixture.json`, `test_evidence.py`, `test_ratchets.py`,
  `FINAL_REPORT.md`, and the previous progress ledger.
- Read the `Refresh the DOI fixture from Europe PMC` commit diff: the refreshed fixture
  carried real titles and years and an empty `journal` for all 46 identifiers, because the
  script read `journalTitle`, a key the `resultType=core` result does not have.
- Rewrote all 48 `notes` fields as the verbatim Europe PMC abstract sentence that states the
  row's estimate. No row was refused: every one of the 48 has a sentence carrying its point
  estimate and both interval bounds, checked against the 46 cached abstracts.
- Fixed `green2011_sunscreen_melanoma` (endpoint moved to `primary_melanoma_incidence`, which
  is the number `daily_sunscreen.yaml` uses) and `daghlas2019_short_sleep_mi` (`HR`, and a
  population naming the CARDIoGRAMplusC4D sample the quoted sentence reports).
- Added `estimate.ci_level` to the schema and the loader, rejected outside (0.5, 1);
  recorded 0.99 for `jha2013_male_smoking_mortality` and 0.9502 for `zinman2015_empareg_mace`.
- Made the loader fail closed on the quote: nonempty notes, the point and both bounds present
  as numbers, and a sha256 that matches the digest the fixture recorded when a refresh
  confirmed the quote was a substring of the abstract.
- Taught `verify_evidence.py` `journalInfo.journal.title`, `abstract_sha256`, per-row quote
  digests, and an offline `--refresh --abstracts-cache <path>` mode; regenerated the fixture
  through it, filling all 46 journals.
- Demoted sixteen links to `transport`: the three the review named, nine more found by the
  same rule, and four more found by re-reading the abstracts (`mcneil2018_aspree_mortality`,
  `bjelakovic2014_vitamin_d3_mortality`, `thompson2013_pcpt_survival`,
  `goyal2014_meditation_anxiety`).
- Made `known_unsourced_claims` require a linked `direct` or `transport` row whose endpoint
  class matches the leg; regenerated the three ratchet files (85 / 114 / 130).
- Set `extracted_by` to the lane that extracted each row and added `verified_by` naming the
  review lane and the Europe PMC refresh; carried both fields into the charter's example.
- Proved the offline check bites: nine mutations of a committed row (paraphrase, out-of-quote
  point estimate, out-of-quote bound, missing fixture digest, tampered digest, empty notes,
  out-of-range `ci_level`, unclassified endpoint) are each rejected by `--check`.

## Next

- Finish the verification sweep and paste real tails into `FINAL_REPORT.md`.
- Rewrite `FINAL_REPORT.md`'s verification claims: the original lane never cross-checked
  citations through publisher pages.
