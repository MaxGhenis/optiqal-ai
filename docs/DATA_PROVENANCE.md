# Data provenance

This document records the source, location, and consumer of each data asset the
Optiqal Python engine depends on, and flags the assets whose provenance is
incomplete. Every entry below was verified against the file it describes.

## Summary

| Asset | Source | Location | Consumed by | Provenance |
| --- | --- | --- | --- | --- |
| Legacy life-table anchors | Transcribed from the pre-snapshot engine; historically attributed to CDC 2021, but not a match for NVSR 72-12 | `python/optiqal/data/snapshots/cdc_life_table.json` plus source comparison | lifecycle / analyzer / web API | Runtime gap closed; source mismatch recorded |
| Cause fractions | Transcribed approximation attributed to CDC WONDER 2021; no saved query or export | `python/optiqal/data/snapshots/cause_fractions.json` | lifecycle / analyzer / web API | Runtime gap closed; historical query absent |
| MEPS quality weights | Committed AHRQ MEPS 2019–2022 calibration, SF-12→EQ-5D (Franks 2004), plus an authored age-95 anchor | `python/optiqal/data/snapshots/meps_quality_weights.json`; calibration artifact in `python/optiqal/data/meps/` | lifecycle | Generated from calibration; authored value labeled |
| Disability weights | Haagsma et al. (GBD-style), ECDC PDF | `python/optiqal/reference_case.py` | reference-case utilities | Documented in code |
| `baselines.json` | Derived from the legacy life-table and quality-weight values now held in snapshots | `python/optiqal/data/baselines.json` | lifecycle, `scripts/precompute_baselines.py` | Derived; historical CDC label is not source validation |
| `condition_joint_distribution.json` | Comment said "from MEPS"; no embedded source | Removed at `9bbbabaa` | nothing (its only reader, `markov.py`, was deleted) | Gap closed by removal |
| Raw MEPS parquet (5 files) | AHRQ MEPS Full-Year Consolidated | Removed at `9bbbabaa`; `fetch_meps.py` re-downloads on demand | nothing at runtime | Gap closed by removal |

---

## Runtime snapshot pattern

`python/optiqal/lifecycle.py` contains no lifecycle data tables. It loads three
committed JSON snapshots through `python/optiqal/snapshots.py` at import while
retaining the public names `CDC_LIFE_TABLE`, `CAUSE_FRACTIONS`, `QUALITY_WEIGHTS`,
`QUALITY_WEIGHT_STD`, and `CONDITION_DECREMENTS`.

Every snapshot has a `provenance` block (`source`, `url`, `table`, `retrieved`,
`generator`, and schema `version`) and a `data` block. It also carries the sha256
of a canonical serialization of `data`, in which every numeric leaf is rendered as
a float: the loader reads all numbers through `float()`, so `1` and `1.0` are one
value to the engine and must be one checksum. The loader names the file and raises
at import for a missing or malformed file, incomplete provenance, checksum drift,
NaN/Infinity, a float literal that overflows to infinity during parsing, a
negative or out-of-range runtime value, non-monotone age keys, or an age table
or age-row table that has lost or gained an anchor. `lifecycle.py` pins all three
anchor sets explicitly as `LIFE_TABLE_AGES` (22 ages), `QUALITY_WEIGHT_AGES`
(8 ages), and `CAUSE_FRACTION_AGES` (6 ages), so a snapshot that drops a row fails
at import rather than being clamped or interpolated across the hole. The
cause-fraction pin is not redundant with the row-sum check: dropping a whole age
leaves every remaining row summing to 1.0. The dated fixture
`python/tests/fixtures/lifecycle_constants_2026-09-04.json` proves every loaded
numeric leaf equals the former literal at absolute tolerance `1e-12`.

Run the commands from `python/` after `uv sync`:

```bash
uv run python -m optiqal.data_build.meps_quality_weights
uv run python -m optiqal.data_build.cdc_life_table
uv run python -m optiqal.data_build.cause_fractions
```

The MEPS command rewrites its snapshot from the committed calibration artifact.
The other two commands validate independently pinned checksums and print manual
source-refresh steps; they do not claim an automatic fetch or rewrite values
whose derivations are absent. Each snapshot repeats its command in
`provenance.generator`.

All three accept `--check`, which writes nothing and exits non-zero on drift; for
MEPS that compares the committed bytes against a rebuild. Use it to audit the
snapshots without regenerating them.

## Legacy life-table anchors and the CDC comparison

- **Runtime source.** The values are transcribed verbatim from the legacy
  `CDC_LIFE_TABLE` introduced in Optiqal commit `5e472e22` on 2025-12-21. That
  commit cited the generic CDC life-table landing page but included no raw table,
  extraction code, or intermediate artifact.
- **Published source checked.** Arias, Xu, and Kochanek, *United States Life
  Tables, 2021*, NVSR 72(12), DOI `10.15620/cdc:132418`, Table 2 (males) and
  Table 3 (females), `qx` column. The report and its Table02/Table03 spreadsheet
  URLs are recorded in the snapshot comparison provenance.
- **They do not match.** The committed
  `cdc_life_table_2021_source_comparison.json` contains the published value,
  production value, delta, and ratio for every one of the 44 anchors. There are
  zero exact matches. Excluding age 100, production/published ratios range from
  `0.632411067194` (female age 35) to `1.309523809524` (male age 10). At age 100,
  the CDC tables use `qx = 1.000000` for the open-ended “100 and older” interval;
  production uses `0.275` for males and `0.255` for females as annual rates.
- **Status.** The runtime transcription gap is closed: one committed snapshot is
  loaded and checksum-validated. The empirical attribution is not repaired.
  Production is **not** using the CDC 2021 life table the old docs cited.
  Replacing the values from Tables 2–3 is a behavior-changing follow-up PR.
- **Consumer and determinism.** `get_mortality_rate` performs deterministic
  lookup/interpolation over the snapshot; it feeds the analyzer, web API, and
  baseline calculations.

## Cause-of-death fractions

- **Runtime source.** The values are transcribed verbatim from the legacy
  `CAUSE_FRACTIONS` introduced in Optiqal commit `5e472e22`, where they were
  labeled only “CDC WONDER 2021.” No saved query, export, table identifier,
  retrieval date, population filters, or exact cause definitions survive.
- **History evidence.** Ages 40–80 are numerically identical to What Nut's
  hand-authored “CDC WONDER, 2021 US mortality data (approximate)” values. Two
  What Nut locations hold those values and both citations are true. The origin is
  `CAUSE_FRACTIONS_BY_AGE` in `src/whatnut/lifecycle_pathways.py` at What Nut
  commit `c67a7232` (2025-12-20, the day before Optiqal's `5e472e22`), which
  carries that header as a comment. What Nut later mirrored the same values into
  `src/whatnut/data/cause_fractions.yaml` at commit `0ff87e2` (2026-02-20) under
  the same header; the two What Nut spellings are numerically identical, so the
  YAML is a mirror of the constant and not a second source. Against either, the
  Optiqal age-90 row is `0.45/0.12/0.43` versus What Nut's `0.45/0.10/0.45`.
  Adaptation is likely given that similarity and the module's “Based on whatnut
  methodology” header, but similarity is evidence, not proof of inheritance.
- **Status.** The runtime table now has one checksum-pinned snapshot and cannot
  drift from `lifecycle.py`. It remains a transcribed approximation, not a
  source-validated CDC WONDER result. The validator refuses to invent the lost
  query and prints the query parameters and raw export a future replacement must
  commit.
- **Consumer and determinism.** `get_cause_fraction` performs deterministic
  lookup/interpolation over the snapshot.

## MEPS quality weights (SF-12 → EQ-5D)

- **Source.** AHRQ Medical Expenditure Panel Survey (MEPS) Full-Year Consolidated
  Files. SF-12 PCS/MCS scores are mapped to EQ-5D utility using the **Franks et
  al. 2004 (Med Care)** regression. The mapping formula and the per-year AHRQ
  download URLs are documented in `python/optiqal/data/meps/fetch_meps.py`
  (e.g. HC-233 for 2022, HC-209 for 2019).
- **Sample.** The calibration artifact
  `python/optiqal/data/meps/quality_weight_calibration.json` records the pooled
  sample as `n = 66786`, broken down by age band and by condition. It was built
  from survey years **2019–2022** (the fetch script lists 2017–2022 as
  available). The raw parquet for those years is no longer committed; see
  "Removals" below.
- **What the runtime uses.** `meps_quality_weights.json` contains seven age
  anchors derived from `by_age.mean`, `QUALITY_WEIGHT_STD` derived from
  `within_age_std`, and six condition decrements derived from
  `by_condition.*.decrement`, each rounded to three decimals exactly as the old
  engine did. The age-95 quality weight (`0.75`) has no MEPS row and is explicitly
  recorded as an authored extrapolation transcribed from the legacy engine.
- **Provenance chain.** `fetch_meps.py` downloads/processes AHRQ data, applies the
  Franks 2004 mapping, and writes `quality_weight_calibration.json`; it now also
  invokes the snapshot writer. Independently, the regenerate command above reads
  the committed calibration and rewrites the runtime snapshot. The snapshot pins
  the calibration artifact's exact byte checksum. The model reads only the small
  validated snapshot at runtime.
- **Retrieval caveat.** Repository history records when the calibration and fetch
  code were committed, not when the AHRQ files were originally downloaded. The
  snapshot's `retrieved` date is when PR E inspected the committed artifact and
  verified its source URLs; it does not assert an unrecorded original fetch date.
- **Provenance status.** The manual transcription/drift gap is closed. Derived
  values regenerate from the committed calibration, and the one authored value
  is separated from the MEPS claim. A full network/parquet refresh through
  `fetch_meps.py` remains a separate data-acquisition workflow; it needs
  `requests` and `pyarrow`, which are not project dependencies (see the
  regeneration command under "Raw MEPS parquet" below).

## Disability weights

- **Source.** GBD-style disability weights for acute episodes, attributed in code
  to **Haagsma et al.** The `source_url` for each weight points to the ECDC PDF
  `Haagsma-PopHealthMetrics-2014-Disability-weights.pdf`.
- **Location.** `python/optiqal/reference_case.py`, in the
  `PUBLIC_HEALTH_UTILITY_WEIGHTS` dict of `UtilityWeight` entries (each carries
  `value`, `instrument="gbd_disability_weight"`, `source_url`, `citation`,
  `population`, and `lower`/`upper` bounds).
- **Citation in code.** The `citation` field reads "Haagsma et al. 2015, Assessing
  disability weights based on the responses of 30,660 people from four European
  countries, Table 3" with `population="30,660 respondents from four European
  countries"`. Note the document year is recorded inconsistently: the linked PDF
  filename says **2014** while the citation text and entry ids say **2015**. The
  underlying study is the same; flagging only so the year is not over-asserted.
- **Reference cases.** The same module defines the US Second Panel and NICE
  reference cases (`US_SECOND_PANEL_REFERENCE_CASE`, `NICE_REFERENCE_CASE`), each
  with `source_urls` (JAMA Second Panel, BMJ, NICE PMG36, etc.) and discount-rate
  assumptions.
- **Provenance status.** Documented in code (per-weight source URL, citation, and
  population present).

## `baselines.json`

- **What it is.** Pre-tabulated remaining life expectancy and remaining-QALY
  values for ages 0–100, by sex, used to replace runtime interpolation with O(1)
  lookups.
- **Source / generator.** Derived data, **not** a primary source. Generated by
  `scripts/precompute_baselines.py`, which imports `python/optiqal/lifecycle.py`
  (now backed by the snapshots above) and writes the JSON. The current file's
  embedded `"source": "CDC National Vital Statistics Life Tables (2021)"` is a
  historical label inherited from the legacy attribution; it is not evidence
  that the input anchors match NVSR 72-12.
- **Location.** `python/optiqal/data/baselines.json`, written by the generator.
  `scripts/prepare-model-deploy.mjs` copies the whole `python/optiqal` tree into
  `.model-service/optiqal/`, so the deployed model service reads the same file.
  The `public/precomputed/baselines.json` twin and its `.vercel` static mirror
  went with the TypeScript engine in rebuild PR B.
- **Consumers.** `python/optiqal/lifecycle.py` and
  `scripts/precompute_baselines.py`.
- **Determinism.** Pure life-table arithmetic, no RNG. PR E did not regenerate
  this derived artifact because its inputs are numerically unchanged; its values
  continue to come from the same anchors now stored in snapshots.
- **Provenance status.** Reproducible as derived output from the committed
  snapshots. Its historical source label is superseded by the life-table
  snapshot and comparison evidence above.

---

## Removals (rebuild PR B, 2026-09-04)

Both provenance gaps this document previously listed as action items were closed
by deleting the assets rather than by sourcing them. The removal commit is
`9bbbabaa` ("Remove the raw MEPS parquet and the unsourced condition joint
distribution") on `rebuild/b-deletion`. **Git history was not rewritten**: the
blobs remain reachable from every commit before that one, exactly as the earlier
recommendation in this file asked. The repository stops carrying them forward
only from `9bbbabaa` on.

### 1. `condition_joint_distribution.json` — removed, not sourced

The file held a joint distribution of six conditions (diabetes, hypertension,
heart disease, stroke, cancer, arthritis) across age bins. Its only reader was
`_load_joint_distribution` in `python/optiqal/markov.py`, deleted in the
preceding commit `12e73eab`. The JSON itself carried no `source`, `generator`,
or `version` key, no script in the repository produced it, and the "from MEPS"
claim in `markov.py` could not be checked against the artifact. Nothing derived
from it reached a served number: `web_api.build_baseline_response` and
`build_frontier_response` never imported `markov`.

Nothing regenerates it, because nothing needs it. Should a future PR want a
condition joint distribution, it has to be built from the MEPS microdata by a
committed generator that embeds `source`, `generated` and input years, mirroring
the pattern the snapshots in `python/optiqal/data/snapshots/` already use.

### 2. Raw MEPS parquet — removed, regenerated on demand

`python/optiqal/data/meps/` held four AHRQ MEPS Full-Year Consolidated files
(`meps_2019.parquet` … `meps_2022.parquet`, 50 MB) plus `meps_combined.parquet`
(1.7 MB), committed without git-LFS. The four year files were read at runtime
only by `python/optiqal/population.py`, which no module imported and which was
deleted in `12e73eab`; `meps_combined.parquet` was written and read only by
`fetch_meps.py`.

Kept in place: `fetch_meps.py`, `quality_weight_calibration.json` (a few KB), and
the runtime snapshot `python/optiqal/data/snapshots/meps_quality_weights.json`,
whose provenance block pins the calibration artifact's byte checksum. The model
reads only that snapshot, so no loaded value changed.

`.gitignore` now carries `python/optiqal/data/meps/*.parquet`, so re-running the
fetch restores the local download cache without recommitting the binaries.

**Regeneration.** From `python/`:

```bash
uv run --with requests --with pyarrow python optiqal/data/meps/fetch_meps.py
```

The two `--with` packages are not project dependencies, so plain `uv sync` plus
`uv run python optiqal/data/meps/fetch_meps.py` fails at `import requests`, and
pandas has no parquet engine for the cache files without `pyarrow`. They are kept
out of `pyproject.toml` because nothing at runtime or in CI needs them.

`download_meps_file` looks for `meps_<year>.parquet` next to the script and
downloads the year's zip from the AHRQ URL in `MEPS_FILES` when it is absent, so
this rebuilds the cache from the network, rewrites
`quality_weight_calibration.json` and `meps_combined.parquet`, and calls
`write_quality_weight_snapshot` to refresh the runtime snapshot. It needs network
access and the `pandas` Stata reader. To audit the committed snapshot without
touching the network or rewriting anything:

```bash
uv run python -m optiqal.data_build.meps_quality_weights --check
```
