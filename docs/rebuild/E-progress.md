# PR E progress: load the life table and quality weights from committed snapshots

Branch `rebuild/e-load-snapshots`. Charter: `REBUILD.md` (PR E row). Updated as work lands.
This file lives at `docs/rebuild/E-progress.md` rather than the repository root because the
sibling rebuild lanes each write a root `PROGRESS.md` and those would collide on merge.

## State

Review rounds 1 and 2 complete. All nine findings from the read-only review are
closed, plus two warts the review exposed indirectly: the generators swallowed
`--check` (round 1), and the cause-fraction table was the one age table left
without an anchor pin (round 2). Verification tails, naming the commit they
cover, are under "Verification" at the end of this file.

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
  (Those counts describe the build through `136c12cb`. Round 1 adds 14 tests and
  re-runs everything at the tip; see "Verification" below.)

## Review round 1 (2026-09-04)

Findings closed, in the order the review numbered them.

1. **Verification now covers the tip.** The earlier report's tails covered
   `136c12cb` while HEAD was `42cb63de`. Ruff and the full suite were re-run at
   `d29ed48d` and the tails are recorded below.
2. **The two What Nut citations are reconciled.** Both are true and they are the
   same numbers. `CAUSE_FRACTIONS_BY_AGE` in `src/whatnut/lifecycle_pathways.py`
   at What Nut commit `c67a7232` (2025-12-20, the day before Optiqal's
   `5e472e22`) is the origin, under the comment "CDC WONDER, 2021 US mortality
   data (approximate)". What Nut later mirrored the same values into
   `src/whatnut/data/cause_fractions.yaml` at commit `0ff87e2` (2026-02-20) under
   the same header; the two What Nut spellings are numerically identical, so the
   YAML is a mirror of the constant and not a second source. Against either,
   Optiqal ages 40-80 are identical and age 90 is `0.45/0.12/0.43` here versus
   `0.45/0.10/0.45` there. Similarity is evidence, not proof of inheritance.
   Verified read-only with `git -C /Users/maxghenis/whatnut show`. The same facts
   in the same order now appear in `cause_fractions.json`'s provenance, in
   `docs/DATA_PROVENANCE.md`, and here.
3. **`age_table` pins its age set.** `ages: tuple[int, ...] = ()` mirrors
   `named_table`'s `keys=`. `lifecycle.py` passes `LIFE_TABLE_AGES` (22) and
   `QUALITY_WEIGHT_AGES` (8). A missing or extra age raises `SnapshotError`
   naming the file and printing both sets. Tests:
   `test_age_table_rejects_a_missing_age_and_names_file`,
   `test_age_table_rejects_an_extra_age_and_names_file`,
   `test_age_table_without_a_pin_still_accepts_any_increasing_ages`,
   `test_dropped_life_table_age_fails_during_lifecycle_import`,
   `test_extra_quality_weight_age_fails_during_lifecycle_import`,
   `test_life_table_age_pin_matches_the_generator_pin`,
   `test_runtime_age_pins_match_the_committed_snapshots`. Round 2 extended the
   same pin to `age_rows` and the cause fractions; see below.
4. **The overflow literal no longer escapes bare.** `1e400` is valid JSON grammar,
   so `parse_constant` never sees it; `json` parses it to `inf` through
   `parse_float`, and `canonical_json`'s `allow_nan=False` raised a bare
   `ValueError` naming no file. `data_checksum` is now inside a try block and
   re-raises `SnapshotError` with the path. Test:
   `test_overflowing_float_literal_fails_closed_and_names_file`.
5. **`_fail` is `NoReturn`.** `data_build/cdc_life_table.py` now matches
   `Snapshot.fail`.
6. **`1` and `1.0` hash alike.** `canonical_json` coerces numeric leaves to
   `float` before dumping, booleans excluded. Tests:
   `test_canonical_json_hashes_int_and_float_spellings_alike`,
   `test_canonical_json_keeps_booleans_out_of_the_numeric_coercion`,
   `test_int_and_float_spellings_load_under_one_committed_checksum`.
7. **`cdc_life_table.json` carries a `retrieval_note`**, matching the MEPS
   snapshot's: the date is when the legacy artifact was inspected, not a
   retrieval. Provenance only; the data block and its digest did not move.
8. **Progress moved** from the repository root to `docs/rebuild/E-progress.md`,
   referenced from `REBUILD.md`'s PR E notes.
9. **Import cost and reads measured**, below.

### Regeneration and byte identity

Each generator was run at the tip. `git status` stayed clean, so every committed
byte is unchanged by regeneration. The MEPS generator genuinely rewrites its file
and reproduced it byte for byte; the other two validate pinned checksums.

Against the pre-review tip `786fc905`, all four snapshots' `data` blocks are
byte-identical. Three `sha256_of_data` values are unchanged. One moved:
`cdc_life_table_2021_source_comparison.json`, `a7d0c351...` -> `574890b2...`,
because its `data` holds four integer leaves (`summary.anchors_compared` 44,
`summary.exact_matches` 0, and the two `summary.*_ratio.age` entries) that the
new canonical form renders as floats. That file is audit evidence, not runtime
data; no comparison value changed. Re-pinned in the snapshot provenance and in
`data_build.cdc_life_table.EXPECTED_COMPARISON_DATA_SHA256`.

Independently of the test suite, every loaded value still equals the pre-PR
literal in `009acd90:python/optiqal/lifecycle.py` exactly: max delta `0.0` across
all five blocks, and `0.0` for `get_mortality_rate` over ages 0-100 for both
sexes. `QUALITY_WEIGHT_STD` is still `float` and age keys are still `int`.

### Beyond the findings: `--check` was a write path

The review's verification recipe runs each generator with `--check`. All three
modules read `sys.argv` and ignored it, so `--check` was silently swallowed and
`python -m optiqal.data_build.meps_quality_weights --check` *rewrote* the
snapshot. A flag that reads as a dry run must not write. All three now parse
arguments: `--check` writes nothing and exits non-zero on drift (for MEPS by
comparing committed bytes against a rebuild), and unknown flags are rejected.
Tests: `test_meps_check_mode_confirms_the_committed_bytes`,
`test_meps_check_mode_detects_drift`,
`test_generator_check_flags_are_parsed_not_ignored`.

### Import cost and what import reads

`python -c "import optiqal.lifecycle"` takes about **0.36 s** wall, re-measured at
the round-2 tip over five warm in-process runs: 371.9, 363.9, 357.2, 346.8,
351.9 ms; `/usr/bin/time -p` on the whole process reads `real 0.44`. (Round 1
recorded 0.39 s because its five-run mean included a cold 583.7 ms first
measurement.)

Almost none of that is PR E. Loading and validating all three snapshots is
**0.29 ms**. `-X importtime` puts `optiqal.lifecycle`'s own module body at
**1.5 ms** cumulative, of which `optiqal.snapshots` is 0.6 ms; the enclosing
`optiqal` package is 476 ms, because `optiqal/__init__.py` imports
`analyzer` -> `catalog` -> `confounding` -> `scipy.stats`, and
`scipy.stats._stats_py` alone accounts for 260 ms.

The review asked whether import reads anything outside `optiqal/data/snapshots/`
and noted `strace` is unavailable. Rather than reason from the code, this was
measured: a `sys.addaudithook` on CPython's `open` audit event recorded every
file opened during the import, with the calling `optiqal` module attributed by
walking the stack. Result:

| opened file | opened by |
| --- | --- |
| `data/snapshots/cdc_life_table.json` | `snapshots.py` |
| `data/snapshots/cause_fractions.json` | `snapshots.py` |
| `data/snapshots/meps_quality_weights.json` | `snapshots.py` |
| `data/public_policy_lanes.json` | `catalog.py` |
| `data/public_policy_conditions.json` | `catalog.py` |
| `data/public_policy_items.json` | `catalog.py` |
| `data/public_frontier_benchmark_scenarios.json` | `public_frontier_benchmark.py` |

So the strict form of the claim is false and should be stated precisely: the
*import statement* reads four files outside the snapshot directory, because
`import optiqal.lifecycle` executes `optiqal/__init__.py`, which pulls in
`catalog.py` and `public_frontier_benchmark.py`. Those four reads pre-date this
branch and are untouched by it. What is true is the part PR E owns:
**`lifecycle.py` itself reads only `optiqal/data/snapshots/`.** `baselines.json`
was confirmed *not* opened during import -- `load_precomputed_baselines()` is
lazy.

Re-measured at the round-1 tip, the audit hook also records three opens the
earlier wording denied, none of them made by `optiqal` code: CPython's
`_osx_support` opens `/System/Library/CoreServices/SystemVersion.plist`, the
import machinery probes the interpreter's `python3xx.zip`, and `importlib.metadata`
opens NumPy's `dist-info/direct_url.json` under `.venv`. All three sit under the
SciPy chain reached through `optiqal/confounding.py`. So the accurate statement
is the narrow one: **no `optiqal` module opens a file outside the `optiqal`
package**, and `lifecycle.py` opens only `optiqal/data/snapshots/`.

## Review round 2 (2026-09-04)

Round 2 re-derived all nine round-1 findings from the code and the sibling
repository rather than trusting the round-1 write-up. Every one held. Three
things changed.

### The cause fractions were the one table still unpinned

Round 1 gave `age_table` an `ages=` pin because a one-row table satisfied every
check the loader had. `age_rows` has the identical hole, and `CAUSE_FRACTIONS`
is loaded through it at import. `get_cause_fraction` clamps below age 40 and
above age 90 and interpolates straight across a missing interior anchor, so a
snapshot that lost age 70 would still import and quietly shift every
intermediate cause mix. The row-sum check does not cover it: dropping a whole
age leaves every remaining row summing to 1.0.

`age_rows` now takes `ages=`, mirroring `age_table` exactly (opt-in, defaulting
to `()`), and `lifecycle.py` passes `CAUSE_FRACTION_AGES = (40, 50, 60, 70, 80,
90)`. `data_build.cause_fractions` keeps calling `age_rows` unpinned and
checking its own `EXPECTED_AGES`, as `cdc_life_table.py` does; a test holds the
two equal. Tests: `test_age_rows_rejects_a_missing_age_and_names_file`,
`test_age_rows_rejects_an_extra_age_and_names_file`,
`test_age_rows_without_a_pin_still_accepts_any_increasing_ages`,
`test_cause_fraction_age_pin_matches_the_generator_pin`,
`test_dropped_cause_fraction_age_fails_during_lifecycle_import`, and
`test_runtime_age_pins_match_the_committed_snapshots` extended to the six
cause-fraction anchors. No loaded value moved and no snapshot byte changed.

### An overstated claim about what import reads

Round 1 closed with "No file outside the `optiqal` package (and outside
`.venv`) is opened." Re-running the audit hook shows that is false: three such
opens occur, all from the standard library under the SciPy chain. The paragraph
above now states the accurate, narrower claim. The finding this branch owns is
unaffected.

### Verification now covers the actual tip

Round 1's tails named `d29ed48d` while HEAD was `486bd794` — two documentation
commits later. That is finding 1 recurring in miniature. The tails below name
the commit whose tree they ran against, and the rule that makes them cover the
tip is stated with them.

## Verification

Run from `python/` against the tree of commit `4d123998`, which is the last
commit touching any file under `python/`. Later commits on this branch change
only `docs/` and `REBUILD.md`; `git diff --stat 4d123998..HEAD -- python/` is
empty, so these tails cover the tip's code exactly.

```
$ uv run --no-sync ruff check .
All checks passed!

$ uv run --no-sync ruff format --check .
80 files already formatted

$ PYTHONPATH=. uv run --no-sync pytest -q -n auto
509 passed in 218.61s (0:03:38)

$ PYTHONPATH=. uv run --no-sync pytest -q tests/test_model_regression.py \
      tests/test_sleep.py tests/test_snapshots.py tests/test_lifecycle.py
66 passed in 8.86s

$ for m in cdc_life_table cause_fractions meps_quality_weights; do
    PYTHONPATH=. uv run --no-sync python -m optiqal.data_build.$m --check; done
Validated the transcribed CDC snapshot and NVSR 72-12 comparison.
Validated the transcribed cause-fraction snapshot against its checksum.
.../optiqal/data/snapshots/meps_quality_weights.json is byte-identical to a rebuild.
```

509 tests is 490 before review, plus 14 from round 1, plus 5 from round 2.
`tests/test_model_regression.py` and `tests/test_sleep.py` have no diff against
`009acd90` and pass.

Regeneration was re-run in write mode, not only `--check`: all three generators
were executed with no flags and `git status` stayed empty, so every one of the
four committed snapshot files is byte-identical to a fresh build. Their sha256
file digests before and after the run are the same four values.

## Next

1. No work remains in PR E. Every runtime table is now checksum-pinned,
   anchor-pinned, and regenerable or explicitly marked as unregenerable.
2. A later behavior-changing PR should replace the legacy life-table anchors from an agreed
   source and replace the cause fractions only with a committed reproducible query/export.
3. Optional, outside this lane: wire `--check` on the three generators into CI so snapshot
   drift fails the build rather than waiting for a reviewer.
