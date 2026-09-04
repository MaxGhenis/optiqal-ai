# PR E progress: load the life table and quality weights from committed snapshots

Branch `rebuild/e-load-snapshots`. Charter: `REBUILD.md` (PR E row). Updated as work lands.

## State

Complete and verified on 2026-09-04.

From `python/`:

- `uv run ruff check .` -> `All checks passed!`
- `uv run ruff format --check .` -> `80 files already formatted` (CI runs this too, in
  `.github/workflows/ci.yml`)
- `uv run pytest -q -n auto` -> `490 passed in 771.90s (0:12:51)`, exit code 0
- `uv run pytest -q tests/test_model_regression.py tests/test_sleep.py tests/test_snapshots.py
  tests/test_lifecycle.py` -> `47 passed in 17.26s`

`tests/test_model_regression.py` and `tests/test_sleep.py` are untouched by this branch and
pass. Note for future lanes: `pytest` lives in the `dev` extra, so a bare `uv sync` does not
install it; use `uv sync --extra dev` or CI's `uv run --all-extras pytest -q`.

## Findings that shape the work (verified 2026-09-04, this lane)

- `python/optiqal/lifecycle.py` holds five constant blocks: `CDC_LIFE_TABLE` (line 18),
  `CAUSE_FRACTIONS` (70), `QUALITY_WEIGHTS` (82), `QUALITY_WEIGHT_STD` (95),
  `CONDITION_DECREMENTS` (99). Python importers of those names: `optiqal/__init__.py`,
  `simulate.py`, `markov.py`, `web_api.py`, `tests/test_lifecycle.py`. The TypeScript copies
  under `src/lib/` are untouched here (PR B deletes them).
- The MEPS blocks are the calibration artifact rounded to 3 decimals:
  `QUALITY_WEIGHTS` = `by_age.mean` per age band, `QUALITY_WEIGHT_STD` = `within_age_std`,
  `CONDITION_DECREMENTS` = `by_condition.*.decrement`, all from
  `python/optiqal/data/meps/quality_weight_calibration.json`. The age-95 entry (0.75) is
  authored, not MEPS: MEPS tops out at the `(80, 100]` band.
- `CDC_LIFE_TABLE` does **not** reproduce the source it cites. Fetched NVSR Vol 72 No 12
  (Arias, Xu, Kochanek, November 2023, *United States Life Tables, 2021*) Table 2 (males) and
  Table 3 (females) this session: the committed qx values run 0.63x to 1.31x the published
  ones, ~32% low at ages 30-40, and the age-100 entries (0.275 / 0.255) are not the published
  terminal qx of 1.000000. They are closer to the 2019 tables (NVSR 70-19) but match no
  published table exactly. So the snapshot's provenance says *transcribed*, and the deltas are
  committed as evidence. Adopting the published table is a number change and belongs to a
  later PR.
- `CAUSE_FRACTIONS` at ages 40-80 is numerically identical to the hand-authored
  `cause_fractions.yaml` in the sibling What Nut repo before its 2026-04 data rebuild (commit
  `0ff87e2`, header "CDC WONDER, 2021 US mortality data (approximate)"); the age-90 row
  differs (0.45/0.12/0.43 here vs 0.45/0.10/0.45 there). The inheritance is likely but not
  proven. No WONDER query id exists anywhere. What Nut has since replaced its copy with
  values derived from NVSR 73-08 Table 6.

## Done

- Added `python/optiqal/snapshots.py`, which validates required provenance, a canonical data
  checksum, finite non-negative values, bounded rates, and strictly increasing age keys.
- Added loader tests using a monkeypatched temporary snapshot directory for missing files,
  missing provenance, NaN, negative rates, non-monotone ages, and checksum drift.
- Hardened parsing so bare JSON NaN/Infinity fail before caching, age spellings cannot leak a
  raw `KeyError`, provenance types and dates are validated, and named row order is irrelevant.
- Built the MEPS runtime snapshot deterministically from the committed calibration artifact,
  retaining the authored age-95 extrapolation with an explicit provenance note.
- Made `fetch_meps.py` refresh that runtime snapshot whenever it rewrites the calibration and
  added a drift test against the committed calibration's exact byte checksum.
- Snapshotted the legacy life-table anchors as transcribed data and pinned their independent
  checksum rather than falsely regenerating them from the publication they do not match.
- Committed all 44 deltas from NVSR 72-12 Tables 2-3: none match; excluding CDC's open-ended
  age-100 rows, snapshot/source ratios range from 0.632411 to 1.309524.
- Snapshotted `CAUSE_FRACTIONS` as the transcribed approximation it is. Its validator refuses
  to invent the absent WONDER query and prints the evidence a future replacement must save.
- Replaced all five literal blocks in `lifecycle.py` with import-time snapshot accessors while
  retaining the public module names, dictionary shapes, key types, and scalar float type.
- Exported the pre-refactor literals to `tests/fixtures/lifecycle_constants_2026-09-04.json`
  and compared every loaded numeric leaf at absolute tolerance `1e-12`.
- Added an integration test that reloads `lifecycle.py` against a malformed temporary snapshot
  and proves the named-file `SnapshotError` occurs during import.
- Rewrote `docs/DATA_PROVENANCE.md` around the snapshot chain and regenerate commands, while
  retaining the PR B action items for the MEPS parquet and unsourced condition distribution.
- Added the snapshots README and appended dated PR E notes to `REBUILD.md`, including the
  explicit finding that production does not use the cited CDC 2021 table.
- Ran `ruff format` over the five files this branch touched. CI runs `ruff format --check`
  (`.github/workflows/ci.yml`), and the branch would have failed it. Formatting only; no
  statement changed, so no number moved.
- Pointed the cause-fraction provenance at the file and symbol that hold the matching values
  (`CAUSE_FRACTIONS_BY_AGE` in `src/whatnut/lifecycle_pathways.py` at What Nut `c67a7232`).
  The bare commit hash resolved to a path that does not exist at that commit.
- Re-verified independently of the test suite: every loaded value equals the pre-PR literal in
  `009acd90:python/optiqal/lifecycle.py` exactly (max delta 0.0 across `get_mortality_rate`,
  `get_quality_weight`, and `get_cause_fraction` for ages 0-100, both sexes); the dated fixture
  is an exact copy of those literals; int age keys and the float scalar are preserved; and all
  44 rows of the NVSR 72-12 comparison artifact reproduce a fresh parse of the CDC PDF
  (`nvsr72-12.pdf`, sha256 `f8aa394521fce65bfa6aa7a31516ab8b5247d6c918810597be27881ea5ee5875`).
- Passed full Ruff and all 490 Python tests. A targeted run of snapshots, lifecycle,
  model-regression, and sleep tests also passed all 47 tests before the full suite.

## Next

1. No work remains in PR E.
2. A later behavior-changing PR should replace the legacy life-table anchors from an agreed
   source and replace the cause fractions only with a committed reproducible query/export.
