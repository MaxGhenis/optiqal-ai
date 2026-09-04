# PR D final report

Date: 2026-09-04 (rewritten after review round one)
Branch: `rebuild/d-evidence-table`

## Outcome

PR D adds a fail-closed evidence table and loader, a refreshable identifier fixture that
binds every quoted estimate to the abstract it came from, catalog and intervention lineage
links, three exact evidence-debt ratchets, and a per-catalog-item lint view.

The committed table holds 48 estimate rows backed by 46 Europe PMC identifiers. Every row's
`notes` field is the verbatim abstract sentence that states the row's point estimate and both
interval bounds; the loader refuses a row whose quote does not carry those three numbers or
whose quote does not hash to the digest a refresh recorded. Fifteen catalog entries and nine
of the ten intervention YAMLs link to applicable rows, and every intervention YAML carries
the canonical `lineage.study_ids` field.

No `hr_observed` and no `qol_annual` changed. That is checked programmatically, not asserted:
loading `python/optiqal/catalog.py` from this branch and from the branch point at `009acd90`
and comparing both fields across all 92 items reports no difference, and the same comparison
against `rebuild/one-engine` at `9a2c35ec` also reports none. `test_model_regression.py` is
byte-identical to both and passes. The only edits to `src/lib/qaly/interventions/*.yaml` are
added `lineage` blocks; no distribution or number in them moved. `rebuild/one-engine` has
since advanced past `9a2c35ec` with work of its own, so `009acd90` is the stable baseline.

## What was verified, by whom, and how

The previous version of this report said that "citation metadata and abstract claims were
cross-checked through available official PubMed/PMC, BMJ, and publisher-indexed pages."
That did not happen, and the claim is withdrawn. What did happen, in three stages:

**1. Extraction — `gpt-5.6-sol lane 2026-09-04`, recorded in each row's `extracted_by`.**
This lane chose the 48 rows, the estimates, and the identifiers, and wrote the first fixture.
It had no working Europe PMC access from its shell. Its `notes` fields were clipped
fragments set in quotation marks, and the fixture it committed asserted `resolved_at`
dates for resolutions that had not occurred. Nothing in that stage was confirmed against
a fetched source, and it shows: of those 48 `notes`, exactly one was a verbatim substring
of the abstract as written, 15 became one once the sentence-final period the lane added
is removed, and 33 have no matching text in the abstract at all.

**2. Identifier refresh — main session with network, 2026-09-04, commit `8975c0fc`.**
`scripts/verify_evidence.py --refresh` ran against the Europe PMC REST search and rewrote the
fixture from the responses. The committed titles, years, PMIDs and DOIs are Europe PMC's
records for those identifiers. All 46 identifiers resolved. The `journal` field came back
empty for every one of them, because the script read the top-level `journalTitle` key that a
`resultType=core` result does not carry.

**3. Quote verification — `claude-opus-5 review lane 2026-09-04`, recorded in `verified_by`.**
The main session fetched the full `abstractText` for all 46 identifiers with network and left
them in a local cache; this lane ran with no network. Every one of the 48 rows was re-read
against the abstract for its identifier. Each `notes` field was replaced with the exact
sentence from that abstract that states the row's estimate, HTML tags stripped and whitespace
collapsed. `scripts/verify_evidence.py --refresh --abstracts-cache <path>` then rewrote the
fixture from the same cache, recording for each identifier the sha256 of its canonicalized
abstract and, per row, the sha256 of the quoted sentence — written only after confirming the
quote is a substring of that abstract. It also filled all 46 journals, reading
`journalInfo.journal.title` as well as `journalTitle`.

No abstract text is committed. What is committed is the quoted sentences (in `notes`) and the
digests, so the offline `--check` re-establishes the binding without a network call: it
recomputes each row's quote digest and fails on a mismatch, and independently requires the
row's point estimate and both interval bounds to appear as numbers inside the quote.

Nine deliberate mutations of a committed row were run against `--check` to confirm it bites:
a paraphrased quote, a point estimate outside its own interval, a point estimate inside the
interval but absent from the quote, an interval bound absent from the quote, a fixture that
forgot the row's quote, a tampered digest, empty notes, a `ci_level` above 1, and an
unclassified endpoint. All nine are rejected, naming the row.

### What is still not verified

- **Only abstracts were read.** No full text, no supplementary table, no publisher page. A
  row is evidence that the abstract states that number for that endpoint — nothing more.
- **Titles, journals and years are Europe PMC's records**, not independently confirmed
  against the publisher.
- **`role` is this lane's judgment**, argued from what each abstract says about its
  population, exposure and endpoint. It is not a computed property.
- **The typed catalog values were not re-derived.** Where a row disagrees with the typed
  `hr_observed`, PR D records the disagreement rather than resolving it; see the PR G table.
- **`known_judgment_atoms` is unaudited debt** carried forward, not evidence.

## Schema changes

`REBUILD.md` carries the row as it now stands, in a dated "PR D notes" section. Four fields
moved:

- `estimate.ci_level`, a float defaulting to 0.95 and rejected outside the open interval
  (0.5, 1). Two rows are not 95% intervals and now say so:
  `jha2013_male_smoking_mortality` records 0.99 and `zinman2015_empareg_mace` records 0.9502,
  both as their abstracts state them.
- `verified_by`, optional, naming the lane that re-checked the quote against a refreshed
  abstract. All 48 rows carry it.
- `extracted_by` now names the lane that actually read the abstract and wrote the row, which
  is the `gpt-5.6-sol` lane, not the review lane.
- `endpoint` must appear in `ENDPOINT_CLASSES`, an exhaustive map from endpoint to
  `mortality`, `quality_of_life` or `intermediate`. A new endpoint has to be classified
  before a row can use it, which is what makes the unsourced ratchet's endpoint test
  possible.

The fixture gained `abstract_sha256` per identifier and `quotes`, a map from row id to the
sha256 of that row's quoted sentence.

`mcneil2018_aspree_mortality` and `bhatt2019_reduceit_primary` were singled out by the review
because their abstracts had not been available. Both are in the cache and both verified like
every other row: ASPREE's HR 1.14 (1.01 to 1.29) for death from any cause and REDUCE-IT's
HR 0.75 (0.68 to 0.83) for the primary end point are each quoted from the sentence that
states them.

## Commits

- `0b59d180` — Start the PR D progress ledger.
- `108eab94` — Wire verified study ids through intervention lineage.
- `2c429c50` — Add the fail-closed evidence loader.
- `28baffd4` — Seed the verified evidence table.
- `bd6fcb52` — Link verified rows to live intervention claims.
- `e9579da1` — Add evidence debt ratchets.
- `761a5eee` — Record PR D completion.
- `8975c0fc` — Refresh the DOI fixture from Europe PMC.
- `79282f09` — Move the PR D ledger under docs/rebuild.
- `aa6bf0cd` — Quote every estimate verbatim and bind it to the abstract by hash.
- `aaf2c742` — Demote cross-population and cross-endpoint links to transport.
- `90d5d1f7` — Discharge an unsourced claim only with a matching endpoint.
- `e2e8c7ba` — Record the PR D schema changes in the charter.
- `7b5f1e1a` — Demote four more links that need a transport step.
- `8dc69386` — Record the round-one fixes in the PR D ledger.
- This report is committed in the commit that contains this file.

Every commit uses an imperative subject, an explanatory body, and the required
`Co-Authored-By` trailer.

## Rows refused

None. All 48 rows survived quote verification: for each one, the Europe PMC abstract carries
a sentence stating that row's point estimate and both interval bounds. Two rows were
corrected rather than refused, both in `aa6bf0cd`:

- `green2011_sunscreen_melanoma` paired the invasive-melanoma endpoint with the
  all-primary-melanoma number. The abstract reports HR 0.50 (0.24 to 1.02) for new primary
  melanomas and HR 0.27 (0.08 to 0.97) for invasive melanoma. `daily_sunscreen.yaml` claims
  `condition: melanoma` with `incidence_rr: LogNormal(-0.69, 0.37)`, whose median is 0.50 and
  whose spread was taken from 0.24-1.02, so the number is the one the model actually uses and
  the endpoint moved to `primary_melanoma_incidence`.
- `daghlas2019_short_sleep_mi` quoted a sentence that does not exist and typed a Mendelian
  randomization estimate as an odds ratio. The abstract reports HR 1.19 (1.09 to 1.29) in
  CARDIoGRAMplusC4D; the estimate type is now `HR`, the design was already
  `mendelian_randomization`, and the population names the sample the quoted sentence reports.

Strength-training citations that provide no compatible abstract estimate and interval were
never written as rows and remain visible in `known_unverified_atoms`.

## Ratchets

| Ratchet | Before review | After review |
|---|---:|---:|
| `known_unsourced_claims` | 74 | 85 |
| `known_unverified_atoms` | 114 | 114 |
| `known_judgment_atoms` | 130 | 130 |

`known_unsourced_claims` grew because a linked row no longer discharges a claim it cannot
speak to. A catalog item's mortality leg now needs a linked `direct` or `transport` row whose
endpoint is in the `mortality` class, and its QoL leg needs one in the `quality_of_life`
class; classes come from `ENDPOINT_CLASSES` in `evidence.py`, which the loader requires every
endpoint to appear in. The eleven items that became visible are `aspirin_81mg`,
`cocoa_flavanols_500`, `empagliflozin`, `finasteride_1.25mg`, `melatonin_300mcg`,
`omega3_clo`, `omega3_epa_2g`, `semaglutide`, `statin_5mg`, `tadalafil_2.5mg` and
`traditional_sauna_4x_week` — each was previously discharged by a row that answers a
composite cardiovascular endpoint, or by a mortality row standing in for a QoL claim, or the
reverse. Four of the fifteen linked items stay off the list: `vitamin_d_2000` and `vitamin_k2`,
whose only nonzero leg is mortality and which each link a mortality row, and
`glucosamine_sulfate_750` and `magnesium_citrate_150`, which claim no effect on either
leg and so have nothing to discharge.

The other two counts did not move. `known_unverified_atoms` asks whether a citation is
answered by a verified row at all, and both `direct` and `transport` rows answer it, so
relabelling links inside that pair moves no citation debt. `known_judgment_atoms` counts
hand-set numbers, which this PR does not touch.

The tests compare generated and committed ids in both directions, so they reject new
unacknowledged debt and stale debt alike.

## Evidentiary roles

A link is `direct` only when the row's population, exposure and endpoint are the claim's. The
model consumes `hr_observed` as an all-cause mortality hazard ratio and `qol_annual` as an
annual QALY rate, and each intervention YAML asserts a mortality hazard ratio or a named
condition effect. Sixteen links were demoted to `transport` across two commits.

The three the review named:

| Link | Why it is not direct |
|---|---|
| `statin_5mg` → `ctt2010_ldl_vascular` | Exposure is a 1 mmol/L LDL reduction, not a 5 mg dose; endpoint is major vascular events, not mortality. |
| `tadalafil_2.5mg` → `anderson2016_pde5_mortality` | Retrospective cohort of men with type 2 diabetes, exposed to the PDE5-inhibitor class rather than tadalafil 2.5 mg. |
| `vitamin_k2` → `geleijnse2004_k2_mortality` | Dietary menaquinone tertiles in the Rotterdam Study, not a K2 supplement dose. |

Nine more failed the same rule in `aaf2c742`: `manson2019_vital_cvd` and
`aung2018_omega3_vascular` (major cardiovascular and major vascular events feeding mortality
claims), `lincoff2023_select_mace` and `zinman2015_empareg_mace` (MACE, in cohorts restricted
to established cardiovascular disease with overweight and to type 2 diabetes at high
cardiovascular risk), `sesso2022_cosmos_cvd` (total cardiovascular events feeding a mortality
claim), `estruch2018_predimed_evoo_mace` and `estruch2018_predimed_nuts_mace` (MACE in adults
at high cardiovascular risk feeding `mediterranean_diet`'s mortality hazard ratio),
`vanderpols2006_sunscreen_scc` (squamous cell carcinoma, where `daily_sunscreen.yaml` claims
the broader non-melanoma skin cancer), and `ferraciolioda2013_melatonin_sleep_quality`
(adults and children with diagnosed primary sleep disorders feeding a general QoL claim).

Four more were found by re-reading the abstracts in `7b5f1e1a`:

| Link | Why it is not direct |
|---|---|
| `aspirin_81mg` → `mcneil2018_aspree_mortality` | ASPREE enrolled only community-dwelling people 70 or older — 65 or older among blacks and Hispanics in the United States — without cardiovascular disease, dementia or disability, and randomized them to 100 mg. The item carries neither the age floor nor the dose. |
| `vitamin_d_2000` → `bjelakovic2014_vitamin_d3_mortality` | "Most trials included women older than 70 years", 77% women, and a conclusion about "elderly people living independently or in institutional care". The pooled RR spans doses the abstract splits at 800 IU/day, so it is not a 2000 IU estimate. |
| `finasteride_1.25mg` → `thompson2013_pcpt_survival` | The abstract states no finasteride dose, so nothing in it establishes the item's 1.25 mg; the population is men randomized in a prostate-cancer prevention trial. |
| `meditation_daily` → `goyal2014_meditation_anxiety` | The endpoint is an eight-week anxiety effect size in "diverse adult clinical populations"; the claim it feeds is an annual subjective-wellbeing rate. |

Eleven rows were left `direct`, ten of them linked. The line drawn: a population
restriction demotes when it plausibly changes the estimate for the claim's population — an age floor, a disease-restricted
cohort, an institutional setting — and not when sex-stratified estimates jointly span the
claim's population and agree, as the three smoking rows do (2.8 in men, 2.76 and 2.81 in
women). The rows left `direct` measure the claim's exposure on the claim's endpoint in a
population the claim covers: the three smoking rows, the three short-sleep rows,
`hamer2008_walking_mortality`, `wen2011_low_volume_activity_mortality`,
`abdelhamid2020_omega3_mortality`, `green2011_sunscreen_melanoma`, and
`black2015_mindfulness_sleep`. The last of those is not linked to any catalog item or
intervention, so its role currently governs nothing.

## Typed values for PR G

These ten catalog items have at least one linked ratio estimate that differs from the typed
`hr_observed` by more than 1%. Each is committed as a judgment atom with the exact reason
`typed value differs from study row`.

| Catalog item | Typed value | Differing verified row(s) |
|---|---:|---|
| `aspirin_81mg` | 0.94 | `mcneil2018_aspree_mortality` = 1.14 HR |
| `finasteride_1.25mg` | 0.93 | `thompson2013_pcpt_survival` = 1.02 HR |
| `glucosamine_sulfate_750` | 1.0 | `li2020_glucosamine_mortality` = 0.85 HR; `suissa2022_glucosamine_selection_bias` = 0.84 HR |
| `magnesium_citrate_150` | 1.0 | `fang2016_magnesium_mortality` = 0.90 RR |
| `omega3_clo` | 0.92 | `aung2018_omega3_vascular` = 0.97 RR |
| `omega3_epa_2g` | 0.955 | `manson2019_vital_cvd` = 0.92 HR; `bhatt2019_reduceit_primary` = 0.75 HR |
| `statin_5mg` | 0.88 | `ctt2010_ldl_vascular` = 0.78 RR |
| `tadalafil_2.5mg` | 0.88 | `anderson2016_pde5_mortality` = 0.54 HR |
| `traditional_sauna_4x_week` | 1.0 | `laukkanen2015_sauna_scd` = 0.37 HR |
| `vitamin_k2` | 0.92 | `geleijnse2004_k2_mortality` = 0.91 RR |

Eleven of these twelve rows carry a `transport` role and the twelfth,
`suissa2022_glucosamine_selection_bias`, is `calibration`. That is the point: none of them
is the claim's own estimate, so the ratchet exposes the disagreement for adjudication
rather than changing a model number in PR D.

## Verification tails

All commands were run from `python/` with `uv run --no-sync`, against commit `8dc69386` plus
this report.

### `uv run python scripts/verify_evidence.py --check`

```text
Evidence check passed: 48 study rows, 46 identifiers.
```

### `uv run python -m optiqal.lint | tail -8`

```text
vitamin_c_500_extra	hr_observed=0.97	study_ids=[]	ratchet_status=unsourced,unverified,judgment
vitamin_d_2000	hr_observed=0.94	study_ids=[bjelakovic2014_vitamin_d3_mortality]	ratchet_status=judgment
vitamin_k2	hr_observed=0.92	study_ids=[geleijnse2004_k2_mortality]	ratchet_status=judgment
zinc_carnosine_75	hr_observed=0.97	study_ids=[]	ratchet_status=unsourced,judgment
zone2_cardio_2x_week	hr_observed=1.0	study_ids=[]	ratchet_status=unsourced,unverified,judgment
known_unsourced_claims: 85
known_unverified_atoms: 114
known_judgment_atoms: 130
```

### `uv run ruff check .` and `uv run ruff format --check .`

```text
All checks passed!
79 files already formatted
```

### `uv run pytest -q`

```text
........................................................................ [ 80%]
........................................................................ [ 94%]
...............................                                          [100%]
535 passed in 941.58s (0:15:41)
```

All 535 tests pass, `test_model_regression.py` among them, untouched.

## Limitations and unfinished external operations

- The review lane had no network. Every abstract it checked came from a local cache the main
  session fetched from Europe PMC with network on 2026-09-04, holding the full `abstractText`
  for all 46 identifiers. The cache is deliberately not committed; the fixture's
  `abstract_sha256` is what lets a future lane prove it fetched the same text.
- `uv sync` still cannot complete in this sandbox: the default uv cache is outside the
  writable roots and the package index is unreachable from shell commands. Every reported
  command ran through `uv run --no-sync` against the prebuilt local virtualenv.
- CI runs `--check` only, by design. `--refresh` needs network and `--refresh
  --abstracts-cache` needs a cache file; `--check` refuses `--abstracts-cache` outright.

The acknowledged evidence and judgment debt is deliberately left for later ratchet-reducing
PRs, especially PR G.
