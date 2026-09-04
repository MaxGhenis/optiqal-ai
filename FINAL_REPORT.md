# PR D final report

Date: 2026-09-04
Branch: `rebuild/d-evidence-table`

## Outcome

PR D is implemented and verified. It adds a fail-closed evidence table and loader,
an offline/refreshable identifier fixture, catalog and intervention lineage links,
three exact evidence-debt ratchets, and a per-catalog-item lint view. No
`hr_observed` or `qol_annual` value changed, and
`python/tests/test_model_regression.py` is untouched.

The committed table contains 48 abstract-supported estimate rows backed by 46
identifier records. Fifteen catalog entries and nine of the ten intervention YAMLs
link to applicable verified rows; every intervention YAML now has the canonical
`lineage.study_ids` field. Strength-training citations that did not provide a
compatible abstract estimate and confidence interval remain visible in the
unverified ratchet.

## Commits

- `0b59d180` — Start the PR D progress ledger.
- `108eab94` — Wire verified study ids through intervention lineage.
- `2c429c50` — Add the fail-closed evidence loader.
- `28baffd4` — Seed the verified evidence table.
- `bd6fcb52` — Link verified rows to live intervention claims.
- `e9579da1` — Add evidence debt ratchets.
- The delivery ledger and this report are committed together in the commit that
  contains this file.

Every commit uses an imperative subject, an explanatory body, and the required
`Co-Authored-By` trailer.

## Ratchets

- `known_unsourced_claims`: 74
- `known_unverified_atoms`: 114
- `known_judgment_atoms`: 130

The tests compare generated and committed IDs in both directions, so they reject
both new unacknowledged debt and stale debt that should have been removed.

## Typed values for PR G

These ten catalog items have at least one linked ratio estimate that differs from
the typed `hr_observed` by more than 1%. Each is committed as a judgment atom with
the exact reason `typed value differs from study row`.

| Catalog item | Typed value | Differing verified row(s) |
|---|---:|---|
| `finasteride_1.25mg` | 0.93 | `thompson2013_pcpt_survival` = 1.02 HR |
| `tadalafil_2.5mg` | 0.88 | `anderson2016_pde5_mortality` = 0.54 HR |
| `aspirin_81mg` | 0.94 | `mcneil2018_aspree_mortality` = 1.14 HR |
| `statin_5mg` | 0.88 | `ctt2010_ldl_vascular` = 0.78 RR |
| `omega3_clo` | 0.92 | `aung2018_omega3_vascular` = 0.97 RR |
| `vitamin_k2` | 0.92 | `geleijnse2004_k2_mortality` = 0.91 RR |
| `omega3_epa_2g` | 0.955 | `manson2019_vital_cvd` = 0.92 HR; `bhatt2019_reduceit_primary` = 0.75 HR |
| `glucosamine_sulfate_750` | 1.0 | `li2020_glucosamine_mortality` = 0.85 HR; `suissa2022_glucosamine_selection_bias` = 0.84 HR |
| `magnesium_citrate_150` | 1.0 | `fang2016_magnesium_mortality` = 0.90 RR |
| `traditional_sauna_4x_week` | 1.0 | `laukkanen2015_sauna_scd` = 0.37 HR |

Some rows differ in population, dose, endpoint, or evidentiary role. That is why the
ratchet exposes them for adjudication rather than changing a model number in PR D.

## Verification tails

All commands were run from `python/` with `uv run`.

### `uv run pytest -q`

```text
................................. [ 83%]
........................................................................ [ 97%]
...............                                                          [100%]
519 passed in 1110.37s (0:18:30)
```

### `uv run ruff check .`

```text
All checks passed!
```

The additional formatter gate also passed: `79 files already formatted`.

### `uv run python scripts/verify_evidence.py --check`

```text
Evidence check passed: 48 study rows, 46 identifiers.
```

### `uv run python -m optiqal.lint | tail -5`

```text
zinc_carnosine_75	hr_observed=0.97	study_ids=[]	ratchet_status=unsourced,judgment
zone2_cardio_2x_week	hr_observed=1.0	study_ids=[]	ratchet_status=unsourced,unverified,judgment
known_unsourced_claims: 74
known_unverified_atoms: 114
known_judgment_atoms: 130
```

## Limitations and unfinished external operations

- The requested `uv sync` could not complete in this sandbox: the default uv cache
  is outside the writable roots, and package-index DNS was unavailable from shell
  commands. I rebuilt the local virtualenv from installed/cached packages, added the
  checkout as an offline editable install, and ran every reported Python command
  through `uv run` with the writable cache and syncing disabled. The exact full suite
  is green under that environment.
- A live `verify_evidence.py --refresh` could not be completed from the shell because
  Europe PMC REST access was unavailable there. The refresh implementation is present;
  citation metadata and abstract claims were cross-checked through available official
  PubMed/PMC, BMJ, and publisher-indexed pages, and the committed fixture passes the
  strict offline table/fixture check. CI intentionally runs `--check` only.

No other requested implementation work remains. The acknowledged evidence and
judgment debt is deliberately left for later ratchet-reducing PRs, especially PR G.
