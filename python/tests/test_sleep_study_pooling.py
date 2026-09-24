"""Pooling home sleep studies, and the two GW studies encoded in the protocol."""

from __future__ import annotations

from dataclasses import replace

import pytest

from optiqal.protocol_ground_up import (
    DEFAULT_PROTOCOL_CONTEXT,
    HOME_SLEEP_STUDY_2026_03_25,
    HOME_SLEEP_STUDY_2026_06_01_REPORTED,
    home_sleep_study_2026_06_01,
    pooled_home_sleep_study,
    sleep_study_payload,
    sleep_study_subject,
)
from optiqal.sleep import (
    SleepMetrics,
    SleepStudyResult,
    apply_sleep_study,
    estimate_sleep_burden,
    pool_sleep_studies,
)

MARCH_TST_H = 423 / 60
JUNE_TST_H = 453.5 / 60


def _june(flag: bool | None = None) -> SleepStudyResult:
    return home_sleep_study_2026_06_01(used_nasal_steroid=flag, used_nasal_strips=flag)


def test_pooled_rei_is_total_events_over_total_sleep_hours():
    pooled = pool_sleep_studies([HOME_SLEEP_STUDY_2026_03_25, _june()])
    events = (35 + 19 + 0 + 0) + (55 + 8 + 0 + 0)
    assert pooled.rei == pytest.approx(events / (MARCH_TST_H + JUNE_TST_H), abs=1e-12)
    assert pooled.rei == pytest.approx(8.00913, abs=1e-5)
    assert pooled.total_sleep_hours == pytest.approx(MARCH_TST_H + JUNE_TST_H)
    assert pooled.obstructive_apneas == 90
    assert pooled.hypopneas == 27
    assert pooled.central_apneas == 0
    assert pooled.mixed_apneas == 0


def test_pooled_supine_metrics_weight_by_supine_hours():
    pooled = pool_sleep_studies([HOME_SLEEP_STUDY_2026_03_25, _june()])
    march_supine = 0.52 * MARCH_TST_H
    june_supine = 0.47 * JUNE_TST_H
    assert pooled.supine_fraction == pytest.approx(
        (march_supine + june_supine) / (MARCH_TST_H + JUNE_TST_H), abs=1e-12
    )
    assert pooled.supine_rei == pytest.approx(
        (5.2 * march_supine + 13.4 * june_supine) / (march_supine + june_supine),
        abs=1e-12,
    )
    assert pooled.supine_rei == pytest.approx(9.2355, abs=1e-4)


def test_pooled_oxygen_uses_sleep_weighted_mean_and_minimum():
    pooled = pool_sleep_studies([HOME_SLEEP_STUDY_2026_03_25, _june()])
    assert pooled.mean_spo2 == pytest.approx(
        (97.0 * MARCH_TST_H + 98.0 * JUNE_TST_H) / (MARCH_TST_H + JUNE_TST_H),
        abs=1e-12,
    )
    assert pooled.nadir_spo2 == 94.0


def test_pooled_record_keeps_every_night_unchanged():
    june = _june()
    pooled = pool_sleep_studies([HOME_SLEEP_STUDY_2026_03_25, june])
    assert pooled.nights == (HOME_SLEEP_STUDY_2026_03_25, june)
    assert pooled.study_date is None
    assert pooled.study_type == "home"


def test_single_study_pools_to_itself():
    assert pool_sleep_studies([HOME_SLEEP_STUDY_2026_03_25]) is (
        HOME_SLEEP_STUDY_2026_03_25
    )


def test_nasal_flags_pool_only_when_nights_agree():
    march = replace(
        HOME_SLEEP_STUDY_2026_03_25, used_nasal_steroid=True, used_nasal_strips=True
    )
    agreeing = pool_sleep_studies([march, _june(True)])
    assert agreeing.used_nasal_steroid is True
    assert agreeing.used_nasal_strips is True
    with pytest.raises(ValueError, match="nights disagree on used_nasal_steroid"):
        pool_sleep_studies([march, _june(False)])
    explicit = pool_sleep_studies(
        [march, _june(False)],
        used_nasal_steroid=False,
        used_nasal_strips=True,
    )
    assert explicit.used_nasal_steroid is False
    assert explicit.used_nasal_strips is True
    # The explicit pooled value never rewrites what a night recorded.
    assert explicit.nights[0].used_nasal_steroid is True


@pytest.mark.parametrize("flag", [None, False, True])
def test_unknown_nasal_flags_stay_unknown_when_pooled(flag):
    pooled = pool_sleep_studies([HOME_SLEEP_STUDY_2026_03_25, _june(flag)])
    assert HOME_SLEEP_STUDY_2026_03_25.used_nasal_steroid is None
    assert HOME_SLEEP_STUDY_2026_03_25.used_nasal_strips is None
    assert pooled.used_nasal_steroid is None
    assert pooled.used_nasal_strips is None


def test_pooling_fails_closed_on_unpoolable_input():
    with pytest.raises(ValueError, match="at least one"):
        pool_sleep_studies([])
    with pytest.raises(ValueError, match="different study types"):
        pool_sleep_studies(
            [HOME_SLEEP_STUDY_2026_03_25, replace(_june(), study_type="psg")]
        )
    with pytest.raises(ValueError, match="total_sleep_hours"):
        pool_sleep_studies(
            [HOME_SLEEP_STUDY_2026_03_25, replace(_june(), total_sleep_hours=None)]
        )
    with pytest.raises(ValueError, match="imply REI"):
        pool_sleep_studies(
            [HOME_SLEEP_STUDY_2026_03_25, replace(_june(), obstructive_apneas=550)]
        )


def test_night_without_counts_contributes_rei_times_hours():
    no_counts = replace(
        _june(),
        obstructive_apneas=None,
        hypopneas=None,
        central_apneas=None,
        mixed_apneas=None,
    )
    pooled = pool_sleep_studies([HOME_SLEEP_STUDY_2026_03_25, no_counts])
    assert pooled.rei == pytest.approx(
        (54 + 8.3 * JUNE_TST_H) / (MARCH_TST_H + JUNE_TST_H), abs=1e-12
    )
    assert pooled.obstructive_apneas is None


def test_unreported_nasal_flags_default_to_unknown():
    assert "used_nasal_steroid" not in HOME_SLEEP_STUDY_2026_06_01_REPORTED
    assert "used_nasal_strips" not in HOME_SLEEP_STUDY_2026_06_01_REPORTED
    june = home_sleep_study_2026_06_01()
    assert june.used_nasal_steroid is None
    assert june.used_nasal_strips is None
    assert pooled_home_sleep_study().used_nasal_steroid is None
    assert pooled_home_sleep_study().used_nasal_strips is None
    assert (june.rei, june.mean_spo2, june.nadir_spo2) == (8.3, 98.0, 95.0)
    assert (june.obstructive_apneas, june.hypopneas) == (55, 8)
    assert (june.supine_fraction, june.supine_rei) == (0.47, 13.4)
    assert june.study_date == "2026-06-01"


# The March study exactly as protocol_ground_up encoded it before the June
# study was added (total sleep time rounded to 7.1 h, no date).
LEGACY_MARCH = SleepStudyResult(
    study_type="home",
    rei=7.7,
    mean_spo2=97.0,
    nadir_spo2=94.0,
    total_sleep_hours=7.1,
    obstructive_apneas=35,
    hypopneas=19,
    central_apneas=0,
    mixed_apneas=0,
    supine_fraction=0.52,
    supine_rei=5.2,
    used_nasal_steroid=True,
    used_nasal_strips=True,
)


def test_default_context_pools_both_studies_with_unknown_nasal_flags():
    assert DEFAULT_PROTOCOL_CONTEXT.home_sleep_study == pooled_home_sleep_study()
    assert len(DEFAULT_PROTOCOL_CONTEXT.home_sleep_study.nights) == 2
    assert DEFAULT_PROTOCOL_CONTEXT.home_sleep_study.used_nasal_steroid is None
    assert DEFAULT_PROTOCOL_CONTEXT.home_sleep_study.used_nasal_strips is None


def test_study_sleep_time_date_and_nasal_flags_are_descriptive():
    """Descriptive fields do not alter a fixed diagnostic REI's model output."""
    wearable = estimate_sleep_burden(
        SleepMetrics(
            duration_hours=6.6,
            recovery_score=60.0,
            sleep_quality_score=78.0,
            waso_min=30.0,
            breathing_score=0.9,
            spo2=95.5,
            snore_pct=6.0,
            airway_response_signal=0.1,
        )
    )
    new = apply_sleep_study(wearable, HOME_SLEEP_STUDY_2026_03_25)
    old = apply_sleep_study(wearable, LEGACY_MARCH)
    assert new.annual_qaly_loss == pytest.approx(old.annual_qaly_loss, abs=1e-12)
    assert new.mortality_signal == pytest.approx(old.mortality_signal, abs=1e-12)
    for component, value in old.component_burdens.items():
        assert new.component_burdens[component] == pytest.approx(value, abs=1e-12)
    assert new.airway == old.airway


def test_single_study_payload_reports_unknown_nasal_flags():
    assert sleep_study_payload(HOME_SLEEP_STUDY_2026_03_25) == {
        "date": "2026-03-25",
        "type": "home",
        "rei": 7.7,
        "mean_spo2": 97.0,
        "nadir_spo2": 94.0,
        "obstructive_apneas": 35,
        "hypopneas": 19,
        "supine_fraction": 0.52,
        "supine_rei": 5.2,
        "used_nasal_steroid": None,
        "used_nasal_strips": None,
    }


def test_pooled_payload_and_wording_name_both_nights():
    pooled = pooled_home_sleep_study(
        june_used_nasal_steroid=True, june_used_nasal_strips=True
    )
    payload = sleep_study_payload(pooled)
    assert payload["pooled"] is True
    assert payload["dates"] == ["2026-03-25", "2026-06-01"]
    assert payload["rei"] == 8.0091
    assert [night["rei"] for night in payload["nights"]] == [7.7, 8.3]
    assert payload["nights"][1]["total_sleep_hours"] == round(JUNE_TST_H, 4)
    assert sleep_study_subject(payload, dated=True) == (
        "Your pooled home studies (March 25, 2026 and June 1, 2026)"
    )
    assert sleep_study_subject(payload, dated=False) == "Your pooled home studies"
    march = sleep_study_payload(HOME_SLEEP_STUDY_2026_03_25)
    assert sleep_study_subject(march, dated=True) == "Your March 25, 2026 home study"
    assert sleep_study_subject(march, dated=False) == "Your home study"


def test_osa_personalization_describes_the_study_the_context_carries():
    from optiqal.protocol_ground_up import (
        build_additional_specs,
        load_baseline,
        resolve_protocol_context,
    )

    march_context = replace(
        resolve_protocol_context(None), home_sleep_study=HOME_SLEEP_STUDY_2026_03_25
    )
    march_specs = build_additional_specs(load_baseline(march_context), march_context)
    assert march_specs["apap_nightly"].personalization.startswith(
        "Your March 25, 2026 home study showed mild OSA (REI 7.7/hr), "
    )
    assert march_specs["oral_appliance_custom"].personalization.startswith(
        "Your home study is already in the nonsevere range (REI 7.7/hr)"
    )

    pooled_context = replace(
        march_context,
        home_sleep_study=pooled_home_sleep_study(
            june_used_nasal_steroid=True, june_used_nasal_strips=True
        ),
    )
    pooled_specs = build_additional_specs(load_baseline(pooled_context), pooled_context)
    assert pooled_specs["apap_nightly"].personalization.startswith(
        "Your pooled home studies (March 25, 2026 and June 1, 2026) showed mild OSA "
        "(REI 8.0/hr), "
    )
    assert pooled_specs["oral_appliance_custom"].personalization.startswith(
        "Your pooled home studies are already in the nonsevere range (REI 8.0/hr)"
    )
