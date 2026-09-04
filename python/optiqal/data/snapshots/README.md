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
| `cdc_life_table.json` | `CDC_LIFE_TABLE` | Legacy values transcribed and independently checksum-pinned. They do not match the cited NVSR 72-12 Tables 2–3. |
| `cdc_life_table_2021_source_comparison.json` | None (audit evidence) | All 44 production/published values, deltas, and ratios; zero matches. |
| `cause_fractions.json` | `CAUSE_FRACTIONS` | Transcribed approximation. No saved CDC WONDER query or export survives. |
| `meps_quality_weights.json` | `QUALITY_WEIGHTS`, `QUALITY_WEIGHT_STD`, `CONDITION_DECREMENTS` | Generated from the committed calibration; age 95 is separately labeled authored. |

## Regenerate or validate

From `python/`, after `uv sync`:

```bash
uv run python -m optiqal.data_build.meps_quality_weights
uv run python -m optiqal.data_build.cdc_life_table
uv run python -m optiqal.data_build.cause_fractions
```

The MEPS command regenerates its snapshot from
`optiqal/data/meps/quality_weight_calibration.json`. The CDC and cause-fraction
commands validate pinned checksums and print manual source-refresh steps. They
do not fetch or rewrite historically transcribed values. When the full
`fetch_meps.py` data-acquisition workflow is run in an environment with its
download and parquet tooling, it also rewrites the MEPS runtime snapshot after
updating the calibration artifact.

Changing a transcribed runtime value is a behavior change: update the source
evidence, snapshot, pinned checksum, dated behavior fixture, and downstream
goldens together in a dedicated number-changing PR.
