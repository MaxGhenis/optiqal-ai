"""Tests for the sleep phenotype and burden model."""

from optiqal.sleep import (
    SleepMetrics,
    SleepStudyResult,
    apply_sleep_study,
    effective_sleep_component_relief,
    estimate_airway_response_signal,
    estimate_airway_target_multiplier,
    estimate_sleep_burden,
    estimate_sleep_mortality_relief_fraction,
    estimate_sleep_relief_annual_qaly,
    sleep_baseline_mortality_multiplier,
    sleep_component_overlap_multipliers,
    sleep_intervention_mortality_hr_multiplier,
    sleep_support_overlap_multiplier,
)


def test_good_sleep_has_low_burden():
    metrics = SleepMetrics(
        duration_hours=7.8,
        recovery_score=76.0,
        sleep_quality_score=89.0,
        waso_min=8.0,
        routine_score=92.0,
        social_jetlag_min=12.0,
        latency_min=11.0,
        breathing_score=0.92,
        spo2=98.0,
        snore_pct=1.0,
    )

    estimate = estimate_sleep_burden(metrics)

    assert estimate.annual_qaly_loss < 0.003
    assert estimate.component_losses["breathing"] < 0.001
    assert sleep_support_overlap_multiplier(estimate) > 0.9


def test_short_fragmented_sleep_has_meaningful_burden():
    metrics = SleepMetrics(
        duration_hours=6.4,
        recovery_score=50.0,
        sleep_quality_score=74.0,
        waso_min=38.0,
        routine_score=72.0,
        social_jetlag_min=58.0,
        latency_min=24.0,
        breathing_score=0.80,
        spo2=97.0,
        snore_pct=2.0,
    )

    estimate = estimate_sleep_burden(metrics)

    assert 0.007 < estimate.annual_qaly_loss < 0.02
    assert estimate.component_losses["duration"] > 0.001
    assert estimate.component_losses["daytime"] > 0.001
    assert sleep_support_overlap_multiplier(estimate) < 0.9


def test_breathing_signals_create_distinct_burden():
    base = SleepMetrics(
        duration_hours=7.1,
        recovery_score=63.0,
        sleep_quality_score=82.0,
        waso_min=18.0,
        routine_score=86.0,
        social_jetlag_min=20.0,
        latency_min=14.0,
        breathing_score=0.9,
        spo2=97.0,
        snore_pct=0.5,
    )
    apnea_like = SleepMetrics(
        duration_hours=7.1,
        recovery_score=63.0,
        sleep_quality_score=82.0,
        waso_min=18.0,
        routine_score=86.0,
        social_jetlag_min=20.0,
        latency_min=14.0,
        breathing_score=0.2,
        spo2=93.0,
        snore_pct=18.0,
    )

    base_estimate = estimate_sleep_burden(base)
    apnea_estimate = estimate_sleep_burden(apnea_like)

    assert apnea_estimate.component_losses["breathing"] > 0.01
    assert apnea_estimate.annual_qaly_loss > base_estimate.annual_qaly_loss + 0.008
    assert apnea_estimate.mortality_signal > base_estimate.mortality_signal + 0.3


def test_mortality_signal_focuses_on_duration_regularity_and_breathing():
    quality_only = SleepMetrics(
        duration_hours=7.6,
        recovery_score=60.0,
        sleep_quality_score=68.0,
        waso_min=45.0,
        routine_score=88.0,
        social_jetlag_min=12.0,
        latency_min=28.0,
        breathing_score=0.92,
        spo2=97.5,
        snore_pct=1.0,
    )
    airway_and_regularity = SleepMetrics(
        duration_hours=6.3,
        recovery_score=60.0,
        sleep_quality_score=82.0,
        waso_min=12.0,
        routine_score=62.0,
        social_jetlag_min=75.0,
        latency_min=12.0,
        breathing_score=0.35,
        spo2=93.8,
        snore_pct=14.0,
    )

    quality_estimate = estimate_sleep_burden(quality_only)
    airway_estimate = estimate_sleep_burden(airway_and_regularity)

    assert quality_estimate.annual_qaly_loss > 0
    assert airway_estimate.mortality_signal > quality_estimate.mortality_signal


def test_positive_home_sleep_study_raises_breathing_burden_and_airway_probability():
    wearable_estimate = estimate_sleep_burden(
        SleepMetrics(
            duration_hours=6.6,
            recovery_score=58.0,
            sleep_quality_score=82.0,
            waso_min=10.0,
            routine_score=78.0,
            social_jetlag_min=22.0,
            latency_min=18.0,
            breathing_score=0.92,
            spo2=96.1,
            snore_pct=1.0,
            airway_response_signal=0.40,
        )
    )

    updated = apply_sleep_study(
        wearable_estimate,
        SleepStudyResult(
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
        ),
    )

    assert updated.component_burdens["breathing"] > wearable_estimate.component_burdens["breathing"] + 0.1
    assert updated.component_losses["breathing"] > wearable_estimate.component_losses["breathing"]
    assert updated.mortality_signal > wearable_estimate.mortality_signal
    assert updated.airway is not None
    assert updated.airway.upper_airway_probability > 0.55
    assert updated.airway.nasal_inflammation_probability > 0.35
    assert updated.airway.mucus_probability < updated.airway.upper_airway_probability


def test_sleep_mortality_translation_is_modest_and_component_specific():
    metrics = SleepMetrics(
        duration_hours=6.4,
        recovery_score=52.0,
        sleep_quality_score=76.0,
        waso_min=18.0,
        routine_score=68.0,
        social_jetlag_min=55.0,
        latency_min=23.0,
        breathing_score=0.75,
        spo2=95.0,
        snore_pct=4.0,
        sleep_debt_min=70.0,
    )
    estimate = estimate_sleep_burden(metrics)
    baseline_multiplier = sleep_baseline_mortality_multiplier(estimate)
    duration_only_relief = {"duration": 0.25}
    quality_only_relief = {"quality": 1.0}

    assert 1.0 < baseline_multiplier < 1.15
    assert estimate_sleep_mortality_relief_fraction(estimate, duration_only_relief) > 0
    assert estimate_sleep_mortality_relief_fraction(estimate, quality_only_relief) == 0.0
    assert sleep_intervention_mortality_hr_multiplier(estimate, duration_only_relief) < 1.0
    assert sleep_intervention_mortality_hr_multiplier(estimate, quality_only_relief) == 1.0


def test_component_relief_only_gets_credit_for_targeted_burdens():
    metrics = SleepMetrics(
        duration_hours=6.5,
        recovery_score=52.0,
        sleep_quality_score=76.0,
        waso_min=18.0,
        routine_score=68.0,
        social_jetlag_min=55.0,
        latency_min=23.0,
        breathing_score=0.25,
        spo2=93.5,
        snore_pct=16.0,
    )
    estimate = estimate_sleep_burden(metrics)

    sleep_aid_relief = estimate_sleep_relief_annual_qaly(
        estimate,
        {
            "duration": 0.12,
            "quality": 0.18,
            "daytime": 0.10,
        },
    )
    breathing_target_relief = estimate_sleep_relief_annual_qaly(
        estimate,
        {
            "breathing": 0.30,
        },
    )

    assert sleep_aid_relief == (
        estimate.component_losses["duration"] * 0.12
        + estimate.component_losses["quality"] * 0.18
        + estimate.component_losses["daytime"] * 0.10
    )
    assert breathing_target_relief == estimate.component_losses["breathing"] * 0.30
    assert sleep_aid_relief < estimate.annual_qaly_loss * 0.25


def test_component_overlap_multiplier_tracks_component_specific_need():
    metrics = SleepMetrics(
        duration_hours=6.5,
        recovery_score=52.0,
        sleep_quality_score=76.0,
        waso_min=18.0,
        routine_score=68.0,
        social_jetlag_min=55.0,
        latency_min=23.0,
        breathing_score=0.25,
        spo2=93.5,
        snore_pct=16.0,
    )
    estimate = estimate_sleep_burden(metrics)
    multipliers = sleep_component_overlap_multipliers(estimate)

    assert 0.95 < multipliers["sleep_continuity_support"] <= 1.0
    assert multipliers["sleep_regularity_support"] < multipliers["sleep_quality_support"]
    assert multipliers["sleep_duration_support"] < 1.0
    assert multipliers["sleep_breathing_support"] < 1.0


def test_airway_response_signal_detects_meaningful_improvement():
    pre = SleepMetrics(
        sleep_quality_score=68.0,
        waso_min=26.6,
        latency_min=35.6,
        breathing_score=0.75,
        spo2=94.9,
        snore_pct=4.8,
    )
    post = SleepMetrics(
        sleep_quality_score=93.4,
        waso_min=7.9,
        latency_min=9.7,
        breathing_score=0.94,
        spo2=95.6,
        snore_pct=1.1,
    )

    signal = estimate_airway_response_signal(pre, post)

    assert 0.7 < signal <= 1.0


def test_airway_contributor_probabilities_rise_with_response_signal():
    no_response = estimate_sleep_burden(
        SleepMetrics(
            duration_hours=6.5,
            recovery_score=55.0,
            sleep_quality_score=78.0,
            waso_min=18.0,
            routine_score=78.0,
            social_jetlag_min=25.0,
            latency_min=18.0,
            breathing_score=0.74,
            spo2=94.8,
            snore_pct=7.0,
            airway_response_signal=0.0,
        )
    )
    strong_response = estimate_sleep_burden(
        SleepMetrics(
            duration_hours=6.5,
            recovery_score=55.0,
            sleep_quality_score=78.0,
            waso_min=18.0,
            routine_score=78.0,
            social_jetlag_min=25.0,
            latency_min=18.0,
            breathing_score=0.74,
            spo2=94.8,
            snore_pct=7.0,
            airway_response_signal=0.85,
        )
    )

    assert no_response.airway is not None
    assert strong_response.airway is not None
    assert strong_response.airway.upper_airway_probability > no_response.airway.upper_airway_probability
    assert strong_response.airway.nasal_inflammation_probability > no_response.airway.nasal_inflammation_probability
    assert strong_response.airway.mucus_probability > no_response.airway.mucus_probability


def test_airway_target_multiplier_is_lower_for_mucus_than_upper_airway():
    estimate = estimate_sleep_burden(
        SleepMetrics(
            duration_hours=6.5,
            recovery_score=55.0,
            sleep_quality_score=78.0,
            waso_min=18.0,
            routine_score=78.0,
            social_jetlag_min=25.0,
            latency_min=18.0,
            breathing_score=0.74,
            spo2=94.8,
            snore_pct=7.0,
            airway_response_signal=0.85,
        )
    )

    upper = estimate_airway_target_multiplier(estimate, {"upper_airway": 1.0})
    mucus = estimate_airway_target_multiplier(estimate, {"mucus": 1.0})

    assert upper > mucus
    assert 0 < mucus < 1


def test_effective_sleep_component_relief_scales_by_airway_target():
    estimate = estimate_sleep_burden(
        SleepMetrics(
            duration_hours=6.5,
            recovery_score=55.0,
            sleep_quality_score=78.0,
            waso_min=18.0,
            routine_score=78.0,
            social_jetlag_min=25.0,
            latency_min=18.0,
            breathing_score=0.74,
            spo2=94.8,
            snore_pct=7.0,
            airway_response_signal=0.85,
        )
    )

    base = {"breathing": 0.20}
    upper_scaled = effective_sleep_component_relief(estimate, base, {"upper_airway": 1.0})
    mucus_scaled = effective_sleep_component_relief(estimate, base, {"mucus": 1.0})

    assert upper_scaled["breathing"] > mucus_scaled["breathing"]
    assert upper_scaled["breathing"] <= 0.20
