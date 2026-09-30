"""The runtime life table is NVSR 72-12 Tables 2-3, and stays that way.

Invariants:

- Every published row parses: 101 single-year rows per sex, 0-99 plus the
  open-ended "100 and older" row.
- The published columns agree with each other within their printed rounding
  (lx, dx, qx, Lx, Tx, ex), and a corruption beyond rounding in any one cell is
  detected.
- The runtime qx equals the published qx at every age 0-99. Age 100 is the
  annual rate of a constant hazard whose mean remaining life is the published
  e100.
- The runtime table reproduces CDC's survivorship column lx at every age.
- The 2026-09-04 hand transcription of 44 anchors agrees with the machine
  parse, and the dated legacy fixture is the legacy column of that evidence.
- ``get_mortality_rate`` is a probability everywhere, rises with age from 30,
  and between two integer ages lies between their published values.
- ``baselines.json`` is exactly what its generator writes from this table.
"""

from __future__ import annotations

import importlib.util
import json
import math
import shutil
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from optiqal import snapshots
from optiqal.data_build import cdc_life_table
from optiqal.lifecycle import CDC_LIFE_TABLE, LIFE_TABLE_AGES, get_mortality_rate

REPO_ROOT = Path(__file__).resolve().parents[2]
TABLES = cdc_life_table.load_source_tables()
SEXES = ("male", "female")


def _copy_tables():
    return {
        sex: {age: dict(row) for age, row in rows.items()}
        for sex, rows in TABLES.items()
    }


def test_source_text_parses_every_single_year_row():
    for sex in SEXES:
        assert tuple(TABLES[sex]) == tuple(range(101))
    # Spot values read from the printed report (pages 16 and 18).
    assert TABLES["male"][0] == {
        "qx": 0.005833,
        "lx": 100000,
        "dx": 583,
        "Lx": 99489,
        "Tx": 7354986,
        "ex": 73.5,
    }
    assert TABLES["female"][0]["ex"] == 79.3
    assert TABLES["male"][100] == {
        "qx": 1.0,
        "lx": 657,
        "dx": 657,
        "Lx": 1281,
        "Tx": 1281,
        "ex": 1.9,
    }
    assert TABLES["female"][100]["lx"] == 2127
    assert TABLES["female"][100]["Tx"] == 4710


def test_parser_rejects_a_row_it_cannot_read():
    text = cdc_life_table.SOURCE_PATH.read_text(encoding="utf-8")
    broken = text.replace("0.005833", "0.00583x", 1)

    with pytest.raises(cdc_life_table.LifeTableSourceError, match="unparseable row"):
        cdc_life_table.parse_source_text(broken)


def test_parser_rejects_a_missing_row():
    lines = cdc_life_table.SOURCE_PATH.read_text(encoding="utf-8").splitlines()
    without_age_42 = "\n".join(line for line in lines if not line.startswith("42–43"))

    with pytest.raises(
        cdc_life_table.LifeTableSourceError, match=r"missing ages \[42\]"
    ):
        cdc_life_table.parse_source_text(without_age_42)


def test_parser_rejects_a_duplicated_row():
    lines = cdc_life_table.SOURCE_PATH.read_text(encoding="utf-8").splitlines()
    row = next(line for line in lines if line.startswith("42–43"))
    duplicated = "\n".join(
        lines[: lines.index(row) + 1] + [row] + lines[lines.index(row) + 1 :]
    )

    with pytest.raises(cdc_life_table.LifeTableSourceError, match="duplicate"):
        cdc_life_table.parse_source_text(duplicated)


def test_source_text_is_pinned(tmp_path):
    tampered = tmp_path / "nvsr72-12_tables_2_3.txt"
    tampered.write_text(
        cdc_life_table.SOURCE_PATH.read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )

    with pytest.raises(snapshots.SnapshotError, match="pinned checksum"):
        cdc_life_table.load_source_tables(tampered)


def test_published_identities_hold_for_the_committed_table():
    cdc_life_table.check_published_identities(_copy_tables())


# Smallest shift per column that no rounding can hide (see the tolerances in
# cdc_life_table): a count off by 3 or more, an expectation off by 0.2 or more,
# a qx whose change moves qx*lx by 2.2 people or more, and an open-interval qx
# below 1.


@settings(max_examples=300, deadline=None)
@given(
    sex=st.sampled_from(SEXES),
    age=st.integers(min_value=0, max_value=100),
    column=st.sampled_from(("qx", "lx", "dx", "Lx", "Tx", "ex")),
    magnitude=st.floats(min_value=1.0, max_value=50.0),
    sign=st.sampled_from((-1, 1)),
)
def test_any_single_cell_corruption_beyond_rounding_is_detected(
    sex, age, column, magnitude, sign
):
    tables = _copy_tables()
    row = tables[sex][age]
    if column == "qx":
        if age == 100:
            row["qx"] = 1.0 - 0.01 * magnitude / 50
        else:
            row["qx"] = row["qx"] + sign * 2.2 * magnitude / row["lx"]
    elif column == "ex":
        row["ex"] = row["ex"] + sign * 0.2 * magnitude
    else:
        row[column] = row[column] + sign * math.ceil(3 * magnitude)

    with pytest.raises(cdc_life_table.LifeTableSourceError):
        cdc_life_table.check_published_identities(tables)


def test_runtime_table_is_the_published_qx_at_every_age():
    assert LIFE_TABLE_AGES == tuple(range(101))
    for sex in SEXES:
        for age in range(100):
            assert CDC_LIFE_TABLE[sex][age] == TABLES[sex][age]["qx"], (sex, age)
            assert get_mortality_rate(age, sex) == TABLES[sex][age]["qx"], (sex, age)


def test_open_interval_rate_reproduces_the_published_e100():
    for sex in SEXES:
        row = TABLES[sex][100]
        annual = CDC_LIFE_TABLE[sex][100]
        assert annual == round(1 - math.exp(-row["lx"] / row["Tx"]), 6)
        # A constant hazard -log(1 - q) has mean remaining life 1 / hazard.
        assert -1 / math.log(1 - annual) == pytest.approx(
            row["Tx"] / row["lx"], abs=1e-5
        )
        assert abs(-1 / math.log(1 - annual) - row["ex"]) <= 0.05
        # Continues the published rise rather than jumping to certain death.
        assert TABLES[sex][99]["qx"] < annual < 0.5
        assert get_mortality_rate(110, sex) == annual


def test_runtime_table_reproduces_published_survivorship():
    """Differential: prod(1 - qx) from the runtime equals CDC's lx column."""
    for sex in SEXES:
        survival = 1.0
        for age in range(101):
            # lx is printed as an integer and qx to six decimals; the worst
            # case over both tables is 0.71 of a person, at female age 48.
            assert (
                abs(cdc_life_table.RADIX * survival - TABLES[sex][age]["lx"]) <= 1.0
            ), (
                sex,
                age,
            )
            survival *= 1 - CDC_LIFE_TABLE[sex][age]


def test_engine_survival_sum_differs_from_published_ex_only_by_year_convention():
    """Differential: the engine's life-expectancy loop against CDC's ex.

    ``web_api._calculate_projection`` adds the survival probability at the start
    of each year, so a year begun alive counts in full. CDC's ex counts
    person-years, about half a year in the year of death. With the published
    table the two therefore differ by roughly one half year at every age, and
    by nothing else.
    """
    for sex in SEXES:
        for age in range(101):
            survival, start_of_year_sum = 1.0, 0.0
            for current in range(age, 111):
                start_of_year_sum += survival
                survival *= 1 - min(get_mortality_rate(current, sex), 0.99)
            offset = start_of_year_sum - TABLES[sex][age]["ex"]
            assert 0.4 <= offset <= 0.6, (sex, age, offset)


@settings(max_examples=500, deadline=None)
@given(
    sex=st.sampled_from(SEXES),
    age=st.floats(min_value=0, max_value=120, allow_nan=False),
)
def test_mortality_rate_is_a_probability_at_every_age(sex, age):
    assert 0 < get_mortality_rate(age, sex) < 1


@settings(max_examples=500, deadline=None)
@given(
    sex=st.sampled_from(SEXES),
    younger=st.floats(min_value=30, max_value=120, allow_nan=False),
    gap=st.floats(min_value=0, max_value=90, allow_nan=False),
)
def test_mortality_rate_never_falls_with_age_from_30(sex, younger, gap):
    older = min(younger + gap, 120.0)
    assert get_mortality_rate(younger, sex) <= get_mortality_rate(older, sex)


@settings(max_examples=500, deadline=None)
@given(
    sex=st.sampled_from(SEXES),
    age=st.integers(min_value=0, max_value=99),
    fraction=st.floats(min_value=0, max_value=1, exclude_max=True, allow_nan=False),
)
def test_fractional_ages_stay_between_neighbouring_published_rates(sex, age, fraction):
    low, high = sorted((CDC_LIFE_TABLE[sex][age], CDC_LIFE_TABLE[sex][age + 1]))
    rate = get_mortality_rate(age + fraction, sex)
    assert low * (1 - 1e-12) <= rate <= high * (1 + 1e-12)


def test_hand_transcribed_anchors_agree_with_the_machine_parse():
    comparison = snapshots.load_snapshot(cdc_life_table.COMPARISON_NAME)
    for sex in SEXES:
        for age, row in comparison.data["rows"][sex].items():
            assert row["published_qx"] == TABLES[sex][int(age)]["qx"], (sex, age)


def test_legacy_fixture_is_the_legacy_column_of_the_comparison():
    """The dated pre-refactor literals are what the comparison calls legacy."""
    fixture = json.loads(
        (
            Path(__file__).parent / "fixtures" / "lifecycle_constants_2026-09-04.json"
        ).read_text(encoding="utf-8")
    )["CDC_LIFE_TABLE"]
    comparison = snapshots.load_snapshot(cdc_life_table.COMPARISON_NAME)
    for sex in SEXES:
        legacy = {
            age: row["snapshot_qx"] for age, row in comparison.data["rows"][sex].items()
        }
        assert legacy == fixture[sex]


def test_committed_artifacts_validate():
    cdc_life_table.validate_committed_artifacts()


def test_check_mode_confirms_the_committed_bytes():
    before = cdc_life_table.SNAPSHOT_PATH.read_bytes()

    assert cdc_life_table.check_life_table_snapshot() is True
    cdc_life_table.main(["--check"])

    assert cdc_life_table.SNAPSHOT_PATH.read_bytes() == before


def test_check_mode_detects_drift(tmp_path):
    drifted = tmp_path / "cdc_life_table.json"
    shutil.copy2(cdc_life_table.SNAPSHOT_PATH, drifted)
    payload = json.loads(drifted.read_text(encoding="utf-8"))
    payload["data"]["life_table"]["male"]["40"] = 0.00261
    drifted.write_text(json.dumps(payload), encoding="utf-8")

    assert cdc_life_table.check_life_table_snapshot(output_path=drifted) is False
    assert (
        cdc_life_table.check_life_table_snapshot(output_path=tmp_path / "absent.json")
        is False
    )


def test_baselines_json_is_what_its_generator_writes():
    """The derived lookup table cannot drift from the life table it tabulates."""
    spec = importlib.util.spec_from_file_location(
        "precompute_baselines", REPO_ROOT / "scripts" / "precompute_baselines.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    rebuilt = json.loads(json.dumps(module.precompute_baselines(), sort_keys=True))
    committed = json.loads(
        (REPO_ROOT / "python" / "optiqal" / "data" / "baselines.json").read_text(
            encoding="utf-8"
        )
    )

    assert committed == rebuilt
