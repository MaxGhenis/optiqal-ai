# PR E: load the life table and quality weights from committed snapshots

You are building PR E of the Optiqal rebuild. Worktree: `/Users/maxghenis/optiqal-ai-rebuild-e`,
branch `rebuild/e-load-snapshots` (already created, checked out, clean). Read `REBUILD.md` at
the worktree root first, then `docs/DATA_PROVENANCE.md` in full, then
`python/optiqal/lifecycle.py`, `python/optiqal/data/meps/fetch_meps.py`,
`python/optiqal/data/meps/quality_weight_calibration.json`, `python/optiqal/data/baselines.json`,
and `scripts/precompute_baselines.py`.

Setup: `cd /Users/maxghenis/optiqal-ai-rebuild-e/python && uv sync`. All Python commands run
from that directory with `uv run`. Node is not needed.

## HEADLESS EXECUTION

You run as a single headless turn. There are no later turns. Never use background jobs,
sleep-and-poll, "I'll wait for", or "standing by" patterns; run every command synchronously
to completion. Your final message is the deliverable. If you cannot finish, say exactly what
is done and what is not.

## The problem (verified 2026-09-03)

`lifecycle.py` holds `CDC_LIFE_TABLE` (line ~18), `CAUSE_FRACTIONS` (~70), `QUALITY_WEIGHTS`
(~82), `QUALITY_WEIGHT_STD` (~95) and `CONDITION_DECREMENTS` (~99) as typed constants.
`docs/DATA_PROVENANCE.md` records (lines ~24 and ~48) that the CDC 2021 life table is
"hardcoded" and that the MEPS-derived numbers are "transcribed as constants" from
`quality_weight_calibration.json`, so they drift whenever `fetch_meps.py` is rerun without
someone retyping them. What Nut, the sibling project, already solved this: every data YAML is
regenerated from a committed raw snapshot by a `data_build` module, and the file header prints
the regenerate command. Port that pattern.

## Do

1. For each constant block, identify the artifact that produced it. Where a generator and a
   calibration file exist (MEPS quality weights: `fetch_meps.py` writes
   `quality_weight_calibration.json`), make the generator write the snapshot in the format
   below and make `lifecycle.py` load it. Where the constants were typed from a published table
   (the CDC 2021 US life table; the cause fractions; the condition decrements), write a
   snapshot file whose provenance says exactly where the numbers came from, and a generator
   under `python/optiqal/data_build/` that either fetches and parses the source (document the
   URL and the table id) or, if the source cannot be fetched in this lane, validates the
   committed snapshot against a checksum and prints the manual regeneration steps. Never
   claim a fetch you did not do; provenance must say "transcribed from <source>" when that is
   the truth.
2. Snapshot format, `python/optiqal/data/snapshots/<name>.json`:

       {"provenance": {"source": "...", "url": "...", "table": "...", "retrieved": "YYYY-MM-DD",
                       "generator": "python -m optiqal.data_build.<module>", "version": 1},
        "data": {...}}

3. `lifecycle.py` loads the snapshots at import through a small loader
   (`python/optiqal/snapshots.py`) that fails closed: missing file, missing provenance, NaN,
   negative rates, or a table whose ages are not monotone raise at import with a message naming
   the file. The module-level names (`CDC_LIFE_TABLE` and the rest) keep their names and
   types so no importer changes.
4. Behavior-preserving proof: copy today's literal dicts verbatim into
   `python/tests/fixtures/lifecycle_constants_2026-09-04.json` and add
   `python/tests/test_snapshots.py` asserting the loaded values equal them to 1e-12, plus tests
   for each fail-closed path (use a tmp file and monkeypatch the snapshot directory).
5. Update `docs/DATA_PROVENANCE.md`: mark the transcription gap closed, describe the snapshot
   pattern and the regenerate commands, and leave the MEPS parquet and
   `condition_joint_distribution.json` items in place (PR B handles their removal).

## Verification before your final commit

    cd /Users/maxghenis/optiqal-ai-rebuild-e/python
    uv run ruff check .
    uv run pytest -q

Both green, and `tests/test_model_regression.py` and `tests/test_sleep.py` must pass
untouched: this PR changes no number.

## Rules

Commit in small steps on `rebuild/e-load-snapshots`; imperative subjects; bodies that say
what moved and why; every message ends with the trailer
`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Never push. Never touch other
worktrees, `origin`, or `~/clawd/data/health.db`. Do not edit `REBUILD.md` except to append a
dated "PR E notes" section. Never invent a source.

## Final message

1. Commits (hash, subject).
2. A table: constant block, snapshot file, generator, provenance status (fetched / validated
   against source / transcribed, with the source).
3. Last lines of `pytest` and `ruff`.
4. Anything not done, and why.
