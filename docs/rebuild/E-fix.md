# PR E fixes (review round 1)

You are fixing PR E of the Optiqal rebuild in place. Worktree: `/Users/maxghenis/optiqal-ai-rebuild-e`,
branch `rebuild/e-load-snapshots` at `42cb63de`. Read `REBUILD.md`, `docs/rebuild/E-load-snapshots.md`
(the original brief, in the integration worktree `/Users/maxghenis/optiqal-ai-rebuild/docs/rebuild/`),
`python/optiqal/snapshots.py`, `python/optiqal/data_build/*.py`, `python/optiqal/lifecycle.py`,
`python/tests/test_snapshots.py`, `PROGRESS.md`, and `docs/DATA_PROVENANCE.md`.

Setup: `cd /Users/maxghenis/optiqal-ai-rebuild-e/python`; the venv exists; use
`PYTHONPATH=. uv run --no-sync pytest`.

## HEADLESS EXECUTION

Single headless turn; no background jobs, no waiting patterns; every command synchronous.
Final message is the deliverable.

## The findings to close (from the read-only review; all confirmed by reading)

1. **Verification did not cover the tip.** The report lists nine commits ending at `136c12cb`;
   HEAD is `42cb63de`. Re-run `ruff check .`, `ruff format --check .` and the full suite at
   the new tip after the fixes below; put the tails in `PROGRESS.md` and in the final message,
   naming the commit they cover.
2. **Two lineage citations for the cause fractions, reconciled.** Both are true, and they are
   the same numbers: `CAUSE_FRACTIONS_BY_AGE` in `src/whatnut/lifecycle_pathways.py` at What
   Nut commit `c67a7232` (2025-12-20, the day before Optiqal's `5e472e22`) is the origin;
   `src/whatnut/data/cause_fractions.yaml` at `0ff87e2` (2026-02-20) mirrors it, header
   "CDC WONDER, 2021 US mortality data (approximate)". State both, in that order, with the
   relationship, in `cause_fractions.json`'s provenance, `PROGRESS.md`, and
   `docs/DATA_PROVENANCE.md`, so the three agree word for word on the facts. Verify with
   `git -C /Users/maxghenis/whatnut show c67a7232:src/whatnut/lifecycle_pathways.py | grep -A12 CAUSE_FRACTIONS_BY_AGE`
   and `git -C /Users/maxghenis/whatnut show 0ff87e2:src/whatnut/data/cause_fractions.yaml`
   (read-only).
3. **`age_table` accepts a one-row table.** Add `ages: tuple[int, ...] = ()` mirroring
   `named_table`'s `keys=`; pass the 22 life-table ages and the 8 quality-weight ages from
   `lifecycle.py`; a snapshot with a missing or extra age raises `SnapshotError` naming the
   file. Test it.
4. **A float-overflow literal escapes as a bare `ValueError`.** `data_checksum(data)` at
   `snapshots.py:268` sits outside the try block; `1e400` parses to `inf` through
   `parse_float` and reaches `json.dumps(allow_nan=False)`. Wrap it and re-raise as
   `SnapshotError` with the path. Test with raw text `{"rates": {"1": 1e400}}`.
5. `data_build/cdc_life_table.py:54` `_fail` is annotated `-> None`; make it `NoReturn` like
   `Snapshot.fail`.
6. `canonical_json` hashes `1` and `1.0` differently while `_number` treats them alike;
   coerce numeric leaves to `float` before dumping (bools excluded), and add a test that the
   two spellings hash the same. Regenerate every snapshot with its generator and confirm the
   committed bytes and `sha256_of_data` are unchanged (or state exactly what changed and why).
7. `cdc_life_table.json` has a `retrieved` date and no `retrieval_note`; add the same
   one-line note the MEPS snapshot carries, saying the date is when the legacy artifact was
   inspected.
8. Move `PROGRESS.md` from the repository root to `docs/rebuild/E-progress.md` (sibling lanes
   each write a root `PROGRESS.md` and the merges collide). Update the reference in
   `REBUILD.md`'s PR E notes.
9. Confirm `python -c "import optiqal.lifecycle"` wall time (report it) and that import reads
   nothing outside `optiqal/data/snapshots/` (strace is unavailable; reason from the code and
   say so).

## Verification before your final commit

    cd /Users/maxghenis/optiqal-ai-rebuild-e/python
    uv run --no-sync ruff check . && uv run --no-sync ruff format --check .
    PYTHONPATH=. uv run --no-sync pytest -q
    for m in cdc_life_table cause_fractions meps_quality_weights; do PYTHONPATH=. uv run --no-sync python -m optiqal.data_build.$m --check || echo "no --check flag: run the generator to a temp path and diff"; done

`tests/test_model_regression.py` and `tests/test_sleep.py` must still pass untouched.

## Rules

Small commits on `rebuild/e-load-snapshots`, imperative subjects, explanatory bodies,
`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Never push. Never touch other
worktrees, `origin`, or `~/clawd/data/health.db`. Never change a loaded value.

## Final message

Commits; the reconciled citation text; the age-set and overflow test names; the regeneration
byte-identity result; the import time; tails of ruff and pytest naming the commit they cover.
