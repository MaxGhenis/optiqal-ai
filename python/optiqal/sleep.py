"""Sleep phenotype and burden estimation.

This is the first vertical slice of a more explicit evidence-pathway model:

sleep metrics -> phenotype components -> annual utility burden

The component structure is designed to be more inspectable than a single
hand-tuned scalar:
- duration
- continuity / fragmentation
- subjective sleep quality
- regularity / circadian stability
- daytime impairment
- sleep-disordered-breathing signal

The weights are intentionally conservative and utility-first. They aim to
capture the direct QALY burden of suboptimal sleep for personal decisions,
without claiming a large hard-outcome mortality effect from consumer metrics
alone.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Mapping, Optional


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


@dataclass(frozen=True)
class SleepMetrics:
    duration_hours: Optional[float] = None
    recovery_score: Optional[float] = None
    sleep_quality_score: Optional[float] = None
    waso_min: Optional[float] = None
    routine_score: Optional[float] = None
    social_jetlag_min: Optional[float] = None
    latency_min: Optional[float] = None
    breathing_score: Optional[float] = None
    spo2: Optional[float] = None
    snore_pct: Optional[float] = None
    sleep_debt_min: Optional[float] = None
    airway_response_signal: Optional[float] = None


@dataclass(frozen=True)
class SleepStudyResult:
    study_type: str
    rei: float
    mean_spo2: Optional[float] = None
    nadir_spo2: Optional[float] = None
    total_sleep_hours: Optional[float] = None
    obstructive_apneas: Optional[int] = None
    hypopneas: Optional[int] = None
    central_apneas: Optional[int] = None
    mixed_apneas: Optional[int] = None
    supine_fraction: Optional[float] = None
    supine_rei: Optional[float] = None
    used_nasal_steroid: bool = False
    used_nasal_strips: bool = False


@dataclass(frozen=True)
class AirwayContributorEstimate:
    upper_airway_probability: float
    nasal_inflammation_probability: float
    mucus_probability: float
    response_signal: float


@dataclass(frozen=True)
class SleepBurdenEstimate:
    component_burdens: Dict[str, float]
    component_losses: Dict[str, float]
    annual_qaly_loss: float
    mortality_signal: float
    airway: Optional[AirwayContributorEstimate] = None


COMPONENT_MAX_ANNUAL_QALY_LOSS = {
    "duration": 0.0060,
    "continuity": 0.0040,
    "quality": 0.0050,
    "regularity": 0.0030,
    "daytime": 0.0060,
    "breathing": 0.0200,
}

# Mortality is only supported well enough to use a subset of sleep components.
# The strongest evidence is for short sleep duration, sleep regularity, and
# sleep-disordered breathing. We intentionally exclude "quality" and "daytime"
# from the mortality path and leave continuity out until we have a better
# component-level evidence mapping.
MORTALITY_COMPONENT_WEIGHTS = {
    "duration": 0.40,
    "regularity": 0.25,
    "breathing": 0.35,
}

# Literature-scale signal for pronounced poor sleep / airway pathology is often
# in the ~1.3-1.6 HR range. Consumer-device-derived sleep phenotypes should not
# inherit the full effect, so we transport only a fraction of that signal until
# more definitive sleep-study data are available.
EXTREME_SLEEP_MORTALITY_HR = 1.50
CONSUMER_SLEEP_MORTALITY_TRANSPORT = 0.30
DEFAULT_AIRWAY_TARGET_MULTIPLIER = 0.35

SLEEP_COMPONENT_BENEFIT_TAGS = {
    "duration": "sleep_duration_support",
    "continuity": "sleep_continuity_support",
    "quality": "sleep_quality_support",
    "regularity": "sleep_regularity_support",
    "daytime": "sleep_daytime_support",
    "breathing": "sleep_breathing_support",
}


def _duration_burden(duration_hours: Optional[float]) -> float:
    if duration_hours is None:
        return 0.0
    if duration_hours < 7.0:
        return _clamp((7.0 - duration_hours) / 1.5)
    if duration_hours > 9.0:
        return _clamp((duration_hours - 9.0) / 2.0)
    return 0.0


def _continuity_burden(waso_min: Optional[float], latency_min: Optional[float]) -> float:
    waso = _clamp(((waso_min or 0.0) - 20.0) / 40.0)
    latency = _clamp(((latency_min or 0.0) - 20.0) / 30.0)
    return _clamp(0.7 * waso + 0.3 * latency)


def _quality_burden(sleep_quality_score: Optional[float]) -> float:
    if sleep_quality_score is None:
        return 0.0
    return _clamp((85.0 - sleep_quality_score) / 25.0)


def _regularity_burden(
    routine_score: Optional[float],
    social_jetlag_min: Optional[float],
) -> float:
    routine = _clamp((85.0 - (routine_score or 85.0)) / 25.0)
    jetlag = _clamp(((social_jetlag_min or 0.0) - 20.0) / 60.0)
    return _clamp(0.7 * routine + 0.3 * jetlag)


def _daytime_burden(recovery_score: Optional[float], sleep_debt_min: Optional[float]) -> float:
    recovery = _clamp((65.0 - (recovery_score or 65.0)) / 20.0)
    debt = _clamp(((sleep_debt_min or 0.0) - 30.0) / 150.0)
    return _clamp(0.8 * recovery + 0.2 * debt)


def _breathing_burden(
    breathing_score: Optional[float],
    spo2: Optional[float],
    snore_pct: Optional[float],
) -> float:
    breathing = _clamp((0.8 - (breathing_score or 0.8)) / 0.5)
    oxygen = _clamp((96.0 - (spo2 or 96.0)) / 4.0)
    snore = _clamp(((snore_pct or 0.0) - 5.0) / 20.0)
    return _clamp(max(breathing, 0.7 * oxygen + 0.3 * snore))


def estimate_airway_response_signal(
    pre: Optional[SleepMetrics],
    post: Optional[SleepMetrics],
) -> float:
    """Estimate how strongly an airway-targeted trial appears to have helped."""
    if pre is None or post is None:
        return 0.0

    breathing = _clamp(((post.breathing_score or 0.0) - (pre.breathing_score or 0.0)) / 0.20)
    oxygen = _clamp(((post.spo2 or 0.0) - (pre.spo2 or 0.0)) / 1.0)
    snore = _clamp(((pre.snore_pct or 0.0) - (post.snore_pct or 0.0)) / 5.0)
    latency = _clamp(((pre.latency_min or 0.0) - (post.latency_min or 0.0)) / 20.0)
    waso = _clamp(((pre.waso_min or 0.0) - (post.waso_min or 0.0)) / 20.0)
    quality = _clamp(((post.sleep_quality_score or 0.0) - (pre.sleep_quality_score or 0.0)) / 20.0)

    return _clamp(
        0.25 * breathing
        + 0.15 * oxygen
        + 0.20 * snore
        + 0.15 * latency
        + 0.15 * waso
        + 0.10 * quality
    )


def _estimate_airway_contributors(
    metrics: SleepMetrics,
    burdens: Mapping[str, float],
) -> AirwayContributorEstimate:
    response_signal = _clamp(metrics.airway_response_signal or 0.0)
    breathing_burden = float(burdens.get("breathing", 0.0))
    snore_signal = _clamp(((metrics.snore_pct or 0.0) - 5.0) / 15.0)

    upper_airway = _clamp(
        0.08
        + 0.45 * breathing_burden
        + 0.10 * snore_signal
        + 0.35 * response_signal
    )
    nasal_inflammation = _clamp(
        0.05
        + 0.30 * breathing_burden
        + 0.45 * response_signal
    )
    mucus = _clamp(
        0.02
        + 0.12 * breathing_burden
        + 0.08 * snore_signal
        + 0.18 * response_signal
    )

    return AirwayContributorEstimate(
        upper_airway_probability=upper_airway,
        nasal_inflammation_probability=nasal_inflammation,
        mucus_probability=mucus,
        response_signal=response_signal,
    )


def estimate_sleep_burden(metrics: SleepMetrics) -> SleepBurdenEstimate:
    """Estimate annual direct QALY burden from a sleep phenotype."""
    burdens = {
        "duration": _duration_burden(metrics.duration_hours),
        "continuity": _continuity_burden(metrics.waso_min, metrics.latency_min),
        "quality": _quality_burden(metrics.sleep_quality_score),
        "regularity": _regularity_burden(metrics.routine_score, metrics.social_jetlag_min),
        "daytime": _daytime_burden(metrics.recovery_score, metrics.sleep_debt_min),
        "breathing": _breathing_burden(metrics.breathing_score, metrics.spo2, metrics.snore_pct),
    }
    losses = {
        component: burden * COMPONENT_MAX_ANNUAL_QALY_LOSS[component]
        for component, burden in burdens.items()
    }
    mortality_signal = _clamp(
        sum(
            MORTALITY_COMPONENT_WEIGHTS[component] * burdens[component]
            for component in MORTALITY_COMPONENT_WEIGHTS
        )
    )
    airway = _estimate_airway_contributors(metrics, burdens)
    return SleepBurdenEstimate(
        component_burdens=burdens,
        component_losses=losses,
        annual_qaly_loss=sum(losses.values()),
        mortality_signal=mortality_signal,
        airway=airway,
    )


def _study_breathing_burden(study: SleepStudyResult) -> float:
    """Translate a sleep-study result into a breathing-burden signal."""
    if study.rei < 5.0:
        severity_core = 0.10 * _clamp(study.rei / 5.0)
    elif study.rei < 15.0:
        severity_core = 0.25 + 0.25 * _clamp((study.rei - 5.0) / 10.0)
    elif study.rei < 30.0:
        severity_core = 0.50 + 0.30 * _clamp((study.rei - 15.0) / 15.0)
    else:
        severity_core = 0.80 + 0.20 * _clamp((study.rei - 30.0) / 30.0)

    mean_oxygen_signal = _clamp(((97.0 - (study.mean_spo2 or 97.0)) / 3.0))
    nadir_oxygen_signal = _clamp(((95.0 - (study.nadir_spo2 or 95.0)) / 6.0))

    underestimation_multiplier = 1.0
    if study.study_type.lower() == "home":
        underestimation_multiplier += 0.08
    if study.used_nasal_steroid or study.used_nasal_strips:
        underestimation_multiplier += 0.05

    burden = (severity_core + 0.06 * mean_oxygen_signal + 0.10 * nadir_oxygen_signal)
    return _clamp(burden * underestimation_multiplier)


def apply_sleep_study(
    estimate: SleepBurdenEstimate,
    study: Optional[SleepStudyResult],
) -> SleepBurdenEstimate:
    """Update a wearable-derived sleep phenotype with diagnostic study evidence."""
    if study is None:
        return estimate

    burdens = dict(estimate.component_burdens)
    losses = dict(estimate.component_losses)

    study_breathing_burden = _study_breathing_burden(study)
    burdens["breathing"] = max(
        float(burdens.get("breathing", 0.0)),
        0.25 * float(burdens.get("breathing", 0.0)) + 0.75 * study_breathing_burden,
    )
    losses["breathing"] = burdens["breathing"] * COMPONENT_MAX_ANNUAL_QALY_LOSS["breathing"]

    mortality_signal = _clamp(
        sum(
            MORTALITY_COMPONENT_WEIGHTS[component] * burdens[component]
            for component in MORTALITY_COMPONENT_WEIGHTS
        )
    )

    airway = estimate.airway
    response_signal = float(airway.response_signal) if airway is not None else 0.0
    total_events = max(
        1,
        int(study.obstructive_apneas or 0)
        + int(study.hypopneas or 0)
        + int(study.central_apneas or 0)
        + int(study.mixed_apneas or 0),
    )
    obstructive_fraction = (
        (int(study.obstructive_apneas or 0) + int(study.hypopneas or 0)) / total_events
    )
    severity_fraction = _clamp(study.rei / 15.0)
    upper_airway_probability = _clamp(
        0.40
        + 0.30 * severity_fraction
        + 0.15 * response_signal
        + 0.10 * obstructive_fraction
    )
    nasal_inflammation_probability = _clamp(
        0.12
        + 0.10 * severity_fraction
        + 0.25 * response_signal
        + (0.15 if study.used_nasal_steroid else 0.0)
        + (0.08 if study.used_nasal_strips else 0.0)
    )
    mucus_probability = _clamp(
        0.03
        + 0.08 * response_signal
        + 0.05 * severity_fraction
    )

    return SleepBurdenEstimate(
        component_burdens=burdens,
        component_losses=losses,
        annual_qaly_loss=sum(losses.values()),
        mortality_signal=mortality_signal,
        airway=AirwayContributorEstimate(
            upper_airway_probability=upper_airway_probability,
            nasal_inflammation_probability=nasal_inflammation_probability,
            mucus_probability=mucus_probability,
            response_signal=response_signal,
        ),
    )


def estimate_sleep_relief_annual_qaly(
    estimate: SleepBurdenEstimate,
    component_relief: Mapping[str, float],
) -> float:
    """Map intervention-specific sleep component relief into annual QALY benefit."""
    relief = 0.0
    for component, fraction in component_relief.items():
        if component not in estimate.component_losses:
            continue
        relief += estimate.component_losses[component] * _clamp(float(fraction))
    return relief


def estimate_airway_target_multiplier(
    estimate: Optional[SleepBurdenEstimate],
    target_weights: Optional[Mapping[str, float]],
) -> float:
    """Map latent airway contributors into an intervention-specific effect multiplier."""
    if not target_weights:
        return 1.0
    if estimate is None or estimate.airway is None:
        return DEFAULT_AIRWAY_TARGET_MULTIPLIER

    airway = estimate.airway
    lookup = {
        "upper_airway": airway.upper_airway_probability,
        "nasal_inflammation": airway.nasal_inflammation_probability,
        "mucus": airway.mucus_probability,
    }
    denom = sum(max(0.0, float(weight)) for weight in target_weights.values())
    if denom <= 0:
        return DEFAULT_AIRWAY_TARGET_MULTIPLIER
    numerator = sum(
        max(0.0, float(weight)) * lookup.get(target, DEFAULT_AIRWAY_TARGET_MULTIPLIER)
        for target, weight in target_weights.items()
    )
    return _clamp(numerator / denom)


def effective_sleep_component_relief(
    estimate: Optional[SleepBurdenEstimate],
    component_relief: Mapping[str, float],
    airway_target_weights: Optional[Mapping[str, float]] = None,
) -> Dict[str, float]:
    """Scale sleep-component relief by the relevant airway phenotype when needed."""
    multiplier = estimate_airway_target_multiplier(estimate, airway_target_weights)
    return {
        component: _clamp(float(fraction) * multiplier)
        for component, fraction in component_relief.items()
    }


def estimate_sleep_mortality_relief_fraction(
    estimate: SleepBurdenEstimate,
    component_relief: Mapping[str, float],
) -> float:
    """Fraction of the current sleep mortality signal relieved by an intervention."""
    denominator = 0.0
    numerator = 0.0
    for component, weight in MORTALITY_COMPONENT_WEIGHTS.items():
        burden = float(estimate.component_burdens.get(component, 0.0))
        denominator += weight * burden
        numerator += weight * burden * _clamp(float(component_relief.get(component, 0.0)))
    if denominator <= 0:
        return 0.0
    return _clamp(numerator / denominator)


def sleep_baseline_mortality_multiplier(estimate: Optional[SleepBurdenEstimate]) -> float:
    """Translate the latent sleep mortality signal into a modest baseline hazard multiplier."""
    if estimate is None:
        return 1.0
    return float(
        math.exp(
            math.log(EXTREME_SLEEP_MORTALITY_HR)
            * CONSUMER_SLEEP_MORTALITY_TRANSPORT
            * _clamp(estimate.mortality_signal)
        )
    )


def sleep_intervention_mortality_hr_multiplier(
    estimate: Optional[SleepBurdenEstimate],
    component_relief: Mapping[str, float],
) -> float:
    """Relative hazard multiplier from relieving part of the user's sleep mortality burden."""
    if estimate is None or not component_relief:
        return 1.0
    baseline_multiplier = sleep_baseline_mortality_multiplier(estimate)
    relief_fraction = estimate_sleep_mortality_relief_fraction(estimate, component_relief)
    if baseline_multiplier <= 1.0 or relief_fraction <= 0:
        return 1.0
    return float(math.exp(-math.log(baseline_multiplier) * relief_fraction))


def sleep_component_overlap_multipliers(
    estimate: SleepBurdenEstimate,
) -> Dict[str, float]:
    """Map unmet sleep-component burden into overlap-penalty multipliers."""
    multipliers: Dict[str, float] = {}
    for component, tag in SLEEP_COMPONENT_BENEFIT_TAGS.items():
        burden = float(estimate.component_burdens.get(component, 0.0))
        multipliers[tag] = round(max(0.55, 1.0 - 0.75 * burden), 3)
    return multipliers


def sleep_support_overlap_multiplier(estimate: SleepBurdenEstimate) -> float:
    """Lower multiplier means less overlap penalty because there is more unmet need."""
    burdens = estimate.component_burdens
    headroom = (
        0.45 * burdens["daytime"]
        + 0.25 * burdens["duration"]
        + 0.15 * burdens["continuity"]
        + 0.15 * burdens["regularity"]
    )
    return round(max(0.55, 1.0 - 0.35 * headroom), 3)
