# Runtime data snapshots

These committed files are the only source for the five lifecycle data blocks
exported by `optiqal.lifecycle`. Each runtime snapshot has this shape:

```json
{
  "provenance": {
    "source": "...",
    "url": "...",
    "table": "...",
    "retrieved": "YYYY-MM-DD",
    "generator": "python -m optiqal.data_build.<module>",
    "version": 1,
    "sha256_of_data": "..."
  },
  "data": {}
}
```

The loader checks required provenance, the canonical data checksum, finite
non-negative runtime values, rate bounds, table shape, and numeric age order.
Do not render snapshot JSON with sorted keys: lexicographic sorting would put
age 100 before age 15 and fail the intentional monotonic-age check.

## Files and status

| File | Runtime blocks | Status |
| --- | --- | --- |
| `cdc_life_table.json` | `CDC_LIFE_TABLE` | Generated from `optiqal/data/cdc/nvsr72-12_tables_2_3.txt`, the committed text of NVSR 72-12 Tables 2–3: published qx at ages 0–99, age 100 converted from the open-ended row. |
| `cdc_life_table_2021_source_comparison.json` | None (audit evidence) | The legacy anchors the runtime used before 2026-09-27, with all 44 published values, deltas, and ratios; zero matches. |
| `cause_fractions.json` | `CAUSE_FRACTIONS` | Transcribed approximation. No saved CDC WONDER query or export survives. |
| `meps_quality_weights.json` | `QUALITY_WEIGHTS`, `QUALITY_WEIGHT_STD`, `CONDITION_DECREMENTS` | Generated from the committed calibration; age 95 is separately labeled authored. |

## Regenerate or validate

From `python/`, after `uv sync`:

```bash
uv run python -m optiqal.data_build.meps_quality_weights
uv run python -m optiqal.data_build.cdc_life_table
uv run python -m optiqal.data_build.cause_fractions
```

Each module also takes `--check`, which writes nothing and exits non-zero on
drift. For MEPS and the life table that compares the committed bytes with a
rebuild; for cause fractions it validates the pinned checksum and suppresses the
manual-refresh text:

```bash
uv run python -m optiqal.data_build.meps_quality_weights --check
uv run python -m optiqal.data_build.cdc_life_table --check
uv run python -m optiqal.data_build.cause_fractions --check
```

The MEPS command regenerates its snapshot from
`optiqal/data/meps/quality_weight_calibration.json`, and the life-table command
regenerates its snapshot from the committed NVSR 72-12 source text after checking
every row against the table's own columns. The cause-fraction command validates
a pinned checksum and prints manual source-refresh steps; it does not fetch or
rewrite historically transcribed values. When the full
`fetch_meps.py` data-acquisition workflow is run in an environment with its
download and parquet tooling, it also rewrites the MEPS runtime snapshot after
updating the calibration artifact.

Changing a transcribed runtime value is a behavior change: update the source
evidence, snapshot, pinned checksum, dated behavior fixture, and downstream
goldens together in a dedicated number-changing PR.
