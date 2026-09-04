# PR D: the evidence table, a fail-closed loader, and the ratchets

You are building PR D of the Optiqal rebuild. Worktree: `/Users/maxghenis/optiqal-ai-rebuild-d`,
branch `rebuild/d-evidence-table` (already created, checked out, clean). Read `REBUILD.md` at
the worktree root first (the `studies.yaml` and ratchet schemas are there), then
`docs/canonical-model-v1.md`, `python/optiqal/catalog.py` (the `CatalogEntry` dataclass near
line 555 and the `sources` / `study_quality` fields near 578-584), `python/optiqal/intervention.py`
(the `InterventionLineage` parser near lines 250-290 and 413-419),
`python/optiqal/confounding.py` (`STUDY_QUALITY_SHRINKAGE` near line 246 is the design
vocabulary), `python/optiqal/combination.py` (`OVERLAP_MATRIX`), the ten files in
`src/lib/qaly/interventions/*.yaml`, `docs/appendix.md` (the calibration rows near lines
289-297) and `docs/references.bib`.

Setup: `cd /Users/maxghenis/optiqal-ai-rebuild-d/python && uv sync`. All Python commands run
from that directory with `uv run`. Network access is allowed in this lane for resolving
citations (Europe PMC REST: `https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:<doi>&format=json&resultType=core`;
use `query=EXT_ID:<pmid>` for PMIDs; PubMed, BMJ and publisher sites often return 403, so do
not depend on them).

## HEADLESS EXECUTION

You run as a single headless turn. There are no later turns. Never use background jobs,
sleep-and-poll, "I'll wait for", or "standing by" patterns; run every command synchronously
to completion. Your final message is the deliverable. If you cannot finish, say exactly what
is done and what is not.

## Why (verified 2026-09-03)

Of 92 catalog entries, 51 have no sources; 50 of the 61 that claim a mortality effect are
unsourced; 7 carry a PMID or DOI anywhere. No intervention YAML has the `lineage:` block that
`canonical-model-v1.md` says is in the schema. The catalog's `hr_observed` values are typed
scalars. The rebuild's rule is that every number reaching a public surface terminates in a
study row, and this PR builds the table, the loader that refuses anything untraceable, and
the ratchets that make the remaining debt visible and only shrinkable.

## Do

1. `python/optiqal/evidence.py`: a `StudyRow` dataclass matching the `studies.yaml` schema in
   `REBUILD.md`; `load_studies()` reads `python/optiqal/data/evidence/studies.yaml` and
   validates every row: `design` in the `STUDY_QUALITY_SHRINKAGE` vocabulary (add
   `cohort_meta_analysis` and `mendelian_randomization` to the vocabulary if absent, with a
   retention value copied from the closest existing tier and a comment saying so); the CI
   brackets the point (on the log scale for HR, RR and OR); `estimate.type` in
   {HR, RR, OR, MD, SMD}; `role` in the enum; a DOI or PMID present; and the identifier present
   in `python/optiqal/data/evidence/doi_fixture.json`. Any violation raises with the row id.
2. `scripts/verify_evidence.py`: `--refresh` resolves every identifier through Europe PMC and
   writes the fixture (`{identifier: {title, journal, year, pmid, doi, resolved_at}}`);
   `--check` compares fixture and table offline and exits non-zero on a gap. CI runs `--check`
   only; add it to `python/tests/test_evidence.py` too.
3. Seed rows. Extract every citation you can find in: the ten intervention YAMLs (their
   `sources` / `studies` / `evidence` blocks); every catalog entry whose `sources` or `notes`
   contain a DOI, a PMID, or an author-year citation, and every entry whose `study_quality`
   is `rct_preregistered_hard_endpoint`, `meta_analysis_rcts`, `rct_standard`, or
   `cohort_large`; the appendix calibration rows and the paper's prior derivations (the
   references they cite). Resolve each through Europe PMC. For each resolved paper whose
   abstract states the estimate the repo uses, write a row with the estimate as the abstract
   gives it, the abstract sentence quoted in `notes`, `extracted_by` naming you, and
   `verified` set to today. If the abstract does not state the estimate, or the identifier
   does not resolve, do not write a row: list the item in `known_unverified_atoms.yaml` with
   the reason. Never invent an estimate, an identifier, or an author.
4. Ratchets, `python/optiqal/ratchets.py`, generating three lists from the live catalog and
   the table, and reading or writing `python/optiqal/data/ratchets/*.yaml`:
   - `known_unsourced_claims.yaml`: catalog ids with `hr_observed != 1.0` or a nonzero
     `qol_annual` and no verified study row;
   - `known_unverified_atoms.yaml`: entries whose sources exist but did not resolve, and
     study rows awaiting resolution;
   - `known_judgment_atoms.yaml`: hand-set numbers: every per-item `(conf_alpha, conf_beta)`
     that differs from its category prior, every `OVERLAP_MATRIX` entry, every
     `STUDY_QUALITY_SHRINKAGE` retention, every `EVIDENCE_EFFECT_MULTIPLIERS` value.
   Each entry is `{id, reason, since}`. `python -m optiqal.ratchets --write` seeds the files
   today; commit them. `python/tests/test_ratchets.py` fails when the generated list has an id
   the file lacks (new debt) and when the file has an id the generator no longer produces
   (a fixed debt that must be removed from the file).
5. Wiring: add `study_ids: list[str]` to `CatalogEntry` (default empty) and to the
   intervention YAML lineage block, reusing `InterventionLineage`; populate it on every entry
   that has a verified row. Do not change any `hr_observed` value. Where a verified row's
   estimate differs from the typed `hr_observed` by more than 1%, add the item to
   `known_judgment_atoms.yaml` with the reason "typed value differs from study row" and list
   it in the final message for PR G.
6. `python -m optiqal.lint`: prints one line per catalog item (id, hr_observed, study_ids,
   ratchet status) and the three counts at the end. Paste the counts in the final message.

## Verification before your final commit

    cd /Users/maxghenis/optiqal-ai-rebuild-d/python
    uv run ruff check .
    uv run pytest -q
    uv run python scripts/verify_evidence.py --check
    uv run python -m optiqal.lint | tail -5

All green. `tests/test_model_regression.py` must pass untouched: this PR changes no number.

## Rules

Commit in small steps on `rebuild/d-evidence-table`; imperative subjects; bodies that say
what moved and why; every message ends with the trailer
`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Never push. Never touch other
worktrees, `origin`, or `~/clawd/data/health.db`. Do not edit `REBUILD.md` except to append a
dated "PR D notes" section if the schema needed to change.

## Final message

1. Commits (hash, subject).
2. Counts: citations found, resolved, rows written, rows refused and why; the three ratchet
   sizes.
3. The list of items whose study row disagrees with the typed value by more than 1%.
4. The tail of `optiqal.lint`, `pytest`, `ruff`, and `verify_evidence.py --check`.
5. Anything not done, and why.
