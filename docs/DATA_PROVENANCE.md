# Data provenance

This document records the source, location, and consumer of each data asset the
Optiqal Python engine depends on, and flags the assets whose provenance is
incomplete. Every entry below was verified against the file it describes.

## Summary

| Asset | Source | Location | Consumed by | Provenance |
| --- | --- | --- | --- | --- |
| CDC 2021 life table | CDC NVSS Life Tables (2021) + CDC WONDER 2021 | `python/optiqal/lifecycle.py` | lifecycle / analyzer / web API | Documented in code |
| MEPS quality weights | AHRQ MEPS 2019–2022, SF-12→EQ-5D (Franks 2004) | constants in `python/optiqal/lifecycle.py`; calibration artifact in `python/optiqal/data/meps/` | lifecycle (constants) | Documented; see notes |
| Disability weights | Haagsma et al. (GBD-style), ECDC PDF | `python/optiqal/reference_case.py` | reference-case utilities | Documented in code |
| `baselines.json` | Derived from CDC life table | `python/optiqal/data/baselines.json` (+ mirrors) | lifecycle, precompute/validate scripts, legacy TS | Derived + self-documenting |
| `condition_joint_distribution.json` | Comment says "from MEPS"; no embedded source | `python/optiqal/data/condition_joint_distribution.json` | `python/optiqal/markov.py` | **GAP — no source/generator** |
| Raw MEPS parquet (4 files) | AHRQ MEPS Full-Year Consolidated | `python/optiqal/data/meps/meps_20{19..22}.parquet` | only `python/optiqal/population.py` (orphaned) | **GAP — ~48 MB raw, no git-LFS** |

---

## CDC 2021 life table

- **Source.** CDC National Vital Statistics System Life Tables (2021), with
  age-varying cause-of-death fractions from CDC WONDER (2021).
- **Location.** Hardcoded in `python/optiqal/lifecycle.py` as the `CDC_LIFE_TABLE`
  dict (one-year mortality probability `qx` by age and sex) and the
  `CAUSE_FRACTIONS` dict.
- **Citation in code.** A header comment cites
  `https://www.cdc.gov/nchs/products/life_tables.htm`.
- **Consumers.** `get_mortality_rate` / `get_cause_fraction` in `lifecycle.py`,
  which feed the analyzer and web API survival curves; also the source for
  `baselines.json` (below).
- **Determinism.** Pure table lookup / interpolation, no RNG.
- **Provenance status.** Documented in code (source URL + year present).

## MEPS quality weights (SF-12 → EQ-5D)

- **Source.** AHRQ Medical Expenditure Panel Survey (MEPS) Full-Year Consolidated
  Files. SF-12 PCS/MCS scores are mapped to EQ-5D utility using the **Franks et
  al. 2004 (Med Care)** regression. The mapping formula and the per-year AHRQ
  download URLs are documented in `python/optiqal/data/meps/fetch_meps.py`
  (e.g. HC-233 for 2022, HC-209 for 2019).
- **Sample.** The calibration artifact
  `python/optiqal/data/meps/quality_weight_calibration.json` records the pooled
  sample as `n = 66786`, broken down by age band and by condition. The committed
  parquet files cover survey years **2019–2022** (the fetch script lists
  2017–2022 as available, but only 2019–2022 are committed).
- **What the runtime actually uses.** The model does **not** read the calibration
  JSON at runtime. The MEPS-derived numbers are transcribed as constants in
  `python/optiqal/lifecycle.py`: the `QUALITY_WEIGHTS` table (age → utility),
  `QUALITY_WEIGHT_STD = 0.117`, and the condition-specific decrements. Each is
  annotated with a `# MEPS 2019-2022 ...` comment, and the values match the
  rounded means in `quality_weight_calibration.json`.
- **Provenance chain.** `fetch_meps.py` (downloads AHRQ data, applies Franks 2004,
  writes `quality_weight_calibration.json` and `meps_combined.parquet`) →
  constants hand-copied into `lifecycle.py` → consumed by the simulation. The
  calibration JSON is the upstream record; it is generated and read only by
  `fetch_meps.py`.
- **Provenance status.** Documented (AHRQ source URLs, mapping citation, sample n
  all present). Minor caveat: the runtime constants are a manual transcription of
  the calibration artifact rather than loaded from it, so the two can drift if
  `fetch_meps.py` is re-run without updating `lifecycle.py`.

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
  (the CDC 2021 life table above) and writes the JSON. The file embeds its own
  `"source": "CDC National Vital Statistics Life Tables (2021)"` and a
  `"generated"` marker.
- **Locations.** `python/optiqal/data/baselines.json` (Python) and
  `public/precomputed/baselines.json` (TypeScript) are written by the generator;
  identical copies also appear under `.model-service/optiqal/data/` and
  `.vercel/output/static/precomputed/` as deployment mirrors.
- **Consumers.** `python/optiqal/lifecycle.py`, `scripts/precompute_baselines.py`,
  `scripts/validate_precomputed.py`, and the legacy
  `src/lib/evidence/baseline/precomputed.ts`.
- **Determinism.** Pure life-table arithmetic, no RNG; regenerating from the same
  `lifecycle.py` reproduces the file.
- **Provenance status.** Well documented — it carries its own source and generator
  metadata and is reproducible from code.

---

## Provenance gaps (action items)

### 1. `condition_joint_distribution.json` has no recorded source or generator

`python/optiqal/data/condition_joint_distribution.json` holds the empirical joint
distribution of six conditions (diabetes, hypertension, heart disease, stroke,
cancer, arthritis) across age bins, with marginal prevalences and joint
probabilities. It is loaded by `python/optiqal/markov.py`
(`_load_joint_distribution`) to sample initial condition states.

- A comment in `markov.py` says the distribution is "from MEPS" and the module
  docstring says "Calibrated to MEPS 2019-2022 longitudinal data," but **the JSON
  file itself contains no `source`, `generator`, `version`, or other provenance
  keys**, and **no script that produces this file exists in the repository**.
- Because there is no committed generator, the file cannot be regenerated or
  independently re-derived from the raw MEPS data, and the MEPS-derivation claim
  cannot be verified from the artifact alone.

**Recommendation.** Add a committed generator script (analogous to
`scripts/precompute_baselines.py`) that builds this JSON from the MEPS parquet,
and embed `source` / `generated` / input-years metadata in the file, mirroring the
self-documenting pattern already used by `baselines.json`.

### 2. ~48 MB of raw MEPS parquet committed without git-LFS, consumed only by orphaned code

`python/optiqal/data/meps/` contains four raw AHRQ MEPS parquet files
(`meps_2019.parquet` … `meps_2022.parquet`, ~48 MB total) plus
`meps_combined.parquet`. These are committed directly to the repository (the only
`.gitattributes` rule is an unrelated beads merge driver, so **git-LFS is not
configured** for them).

- The four year files are read at runtime only by `python/optiqal/population.py`,
  and `population.py` is **not imported by any other module** in the package — it
  is orphaned. `meps_combined.parquet` is referenced only by `fetch_meps.py`.
- So the largest binary payload in the repo is consumed exclusively by dead /
  fetch-only code, while the values that actually drive the model are the small
  hand-transcribed constants in `lifecycle.py` and the
  `quality_weight_calibration.json` summary.

**Recommendation.** Move the raw MEPS parquet to git-LFS or host it externally
(e.g. fetched on demand by `fetch_meps.py`), and/or remove the dependency by
retiring the orphaned `population.py`. Do **not** rewrite git history to purge the
blobs — track the change going forward only. The derived
`quality_weight_calibration.json` (a few KB) is sufficient to reproduce the
model's quality-weight inputs and can stay in-repo.
