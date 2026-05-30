"""Reference-case QALY primitives for health-economic evaluation.

This module is intentionally narrow: it gives Optiqal a public-health style
spine for utilities, discounting, and morbidity QALY accounting without forcing
every existing personal model to migrate at once.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal, Mapping


UtilityInstrument = Literal[
    "eq_5d",
    "sf_6d",
    "hui",
    "time_tradeoff",
    "standard_gamble",
    "mapping",
    "gbd_disability_weight",
    "expert_judgment",
    "personal_utility",
]

UtilityValueType = Literal["utility", "disutility"]
MorbidityDirection = Literal["cause", "avoid"]
ReferenceCaseStatus = Literal[
    "reference_case",
    "acceptable_mapped",
    "fallback",
    "non_reference_case",
]


@dataclass(frozen=True)
class ReferenceCase:
    """Reference-case assumptions for cost-utility analysis."""

    id: str
    name: str
    perspective: str
    health_discount_rate: float
    cost_discount_rate: float
    utility_preference_order: tuple[UtilityInstrument, ...]
    reporting_standard: str
    source_urls: tuple[str, ...]
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


US_SECOND_PANEL_REFERENCE_CASE = ReferenceCase(
    id="us_second_panel_healthcare_sector_3pct",
    name="US Second Panel health care sector reference case",
    perspective="health_care_sector",
    health_discount_rate=0.03,
    cost_discount_rate=0.03,
    utility_preference_order=(
        "eq_5d",
        "sf_6d",
        "hui",
        "mapping",
        "gbd_disability_weight",
        "expert_judgment",
        "personal_utility",
    ),
    reporting_standard="CHEERS 2022",
    source_urls=(
        "https://jamanetwork.com/journals/jama/fullarticle/2552214",
        "https://www.bmj.com/content/376/bmj-2021-067975",
    ),
    notes=(
        "Use preference-based health utilities where available.",
        "Report health care sector and societal perspectives separately when costs extend beyond health care.",
        "Discount both health effects and costs at 3% in the base case, with sensitivity analyses.",
    ),
)


NICE_REFERENCE_CASE = ReferenceCase(
    id="nice_technology_appraisal_reference_case",
    name="NICE technology appraisal reference case",
    perspective="nhs_and_personal_social_services",
    health_discount_rate=0.035,
    cost_discount_rate=0.035,
    utility_preference_order=(
        "eq_5d",
        "mapping",
        "sf_6d",
        "hui",
        "gbd_disability_weight",
        "expert_judgment",
        "personal_utility",
    ),
    reporting_standard="NICE health technology evaluation manual",
    source_urls=(
        "https://www.ncbi.nlm.nih.gov/books/NBK425820/",
        "https://www.nice.org.uk/process/pmg36",
    ),
    notes=(
        "EQ-5D is the preferred adult utility instrument in the NICE reference case.",
        "Non-reference-case utilities should be clearly labeled and justified.",
    ),
)


DEFAULT_REFERENCE_CASE = US_SECOND_PANEL_REFERENCE_CASE
REFERENCE_CASES = {
    US_SECOND_PANEL_REFERENCE_CASE.id: US_SECOND_PANEL_REFERENCE_CASE,
    NICE_REFERENCE_CASE.id: NICE_REFERENCE_CASE,
}


@dataclass(frozen=True)
class UtilityWeight:
    """Preference-based utility or disutility for a health state."""

    id: str
    label: str
    value: float
    value_type: UtilityValueType
    instrument: UtilityInstrument
    source_url: str
    citation: str | None = None
    population: str | None = None
    lower: float | None = None
    upper: float | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.value <= 1:
            raise ValueError(f"Utility weight {self.id} must be in [0, 1], got {self.value}")
        if self.lower is not None and not 0 <= self.lower <= 1:
            raise ValueError(f"Utility weight {self.id} lower bound must be in [0, 1]")
        if self.upper is not None and not 0 <= self.upper <= 1:
            raise ValueError(f"Utility weight {self.id} upper bound must be in [0, 1]")
        if self.lower is not None and self.upper is not None and self.lower > self.upper:
            raise ValueError(f"Utility weight {self.id} lower bound cannot exceed upper bound")

    @property
    def utility_decrement(self) -> float:
        """Return the QALY decrement associated with this health state."""
        if self.value_type == "utility":
            return 1.0 - self.value
        return self.value

    @property
    def reference_case_status(self) -> ReferenceCaseStatus:
        return utility_reference_case_status(self.instrument)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["utility_decrement"] = self.utility_decrement
        payload["reference_case_status"] = self.reference_case_status
        return payload


PUBLIC_HEALTH_UTILITY_WEIGHTS: dict[str, UtilityWeight] = {
    "infectious_disease_acute_episode_mild_disability_weight_europe_2015": UtilityWeight(
        id="infectious_disease_acute_episode_mild_disability_weight_europe_2015",
        label="Mild acute episode disability weight",
        value=0.007,
        value_type="disutility",
        instrument="gbd_disability_weight",
        source_url="https://www.ecdc.europa.eu/sites/default/files/documents/Haagsma-PopHealthMetrics-2014-Disability-weights.pdf",
        citation=(
            "Haagsma et al. 2015, Assessing disability weights based on the responses "
            "of 30,660 people from four European countries, Table 3"
        ),
        population="30,660 respondents from four European countries",
        lower=0.005,
        upper=0.010,
        notes="Fallback anchor for short mild adverse-event disutility.",
    ),
    "infectious_disease_acute_episode_moderate_disability_weight_europe_2015": UtilityWeight(
        id="infectious_disease_acute_episode_moderate_disability_weight_europe_2015",
        label="Moderate acute episode disability weight",
        value=0.051,
        value_type="disutility",
        instrument="gbd_disability_weight",
        source_url="https://www.ecdc.europa.eu/sites/default/files/documents/Haagsma-PopHealthMetrics-2014-Disability-weights.pdf",
        citation=(
            "Haagsma et al. 2015, Assessing disability weights based on the responses "
            "of 30,660 people from four European countries, Table 3"
        ),
        population="30,660 respondents from four European countries",
        lower=0.039,
        upper=0.060,
        notes="Fallback anchor for short moderate adverse-event disutility.",
    ),
    "infectious_disease_acute_episode_severe_disability_weight_europe_2015": UtilityWeight(
        id="infectious_disease_acute_episode_severe_disability_weight_europe_2015",
        label="Severe acute episode disability weight",
        value=0.125,
        value_type="disutility",
        instrument="gbd_disability_weight",
        source_url="https://www.ecdc.europa.eu/sites/default/files/documents/Haagsma-PopHealthMetrics-2014-Disability-weights.pdf",
        citation=(
            "Haagsma et al. 2015, Assessing disability weights based on the responses "
            "of 30,660 people from four European countries, Table 3"
        ),
        population="30,660 respondents from four European countries",
        lower=0.104,
        upper=0.152,
        notes="Fallback anchor for short severe adverse-event disutility.",
    ),
    "erectile_dysfunction_tto_utility_gain_stolk_2000": UtilityWeight(
        id="erectile_dysfunction_tto_utility_gain_stolk_2000",
        label="Erectile dysfunction treatment utility gain",
        value=0.11,
        value_type="disutility",
        instrument="time_tradeoff",
        source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC27357/",
        citation=(
            "Stolk et al. 2000, Cost utility analysis of sildenafil compared with "
            "papaverine-phentolamine injections, BMJ"
        ),
        population="Dutch general-public time-tradeoff sample valuing erectile dysfunction states",
        notes=(
            "Represents the mean utility gain attributed to sildenafil in ED state valuation; "
            "used as a sexual-function utility anchor, not as the modeled annual effect."
        ),
    ),
    "mild_alopecia_areata_tto_proxy_2024": UtilityWeight(
        id="mild_alopecia_areata_tto_proxy_2024",
        label="Mild alopecia utility proxy",
        value=0.919,
        value_type="utility",
        instrument="mapping",
        source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC11116246/",
        citation=(
            "Aggio et al. 2024, Estimation of health utility values for alopecia areata, "
            "SALT 0-10 health state"
        ),
        population="UK public time-tradeoff vignette valuation for alopecia areata health states",
        notes=(
            "Mapped proxy for valued hair-preservation utility; androgenetic alopecia is not "
            "the same disease state as alopecia areata."
        ),
    ),
    "insomnia_disability_weight_europe_2015": UtilityWeight(
        id="insomnia_disability_weight_europe_2015",
        label="Insomnia disability weight",
        value=0.023,
        value_type="disutility",
        instrument="gbd_disability_weight",
        source_url="https://link.springer.com/article/10.1186/s12963-015-0042-4/tables/3",
        citation=(
            "Haagsma et al. 2015, Assessing disability weights based on the responses "
            "of 30,660 people from four European countries, Table 3"
        ),
        population="30,660 respondents from four European countries",
        lower=0.017,
        upper=0.028,
        notes="Used as a public-health fallback anchor for non-breathing sleep burden.",
    ),
    "sleep_apnoea_disability_weight_europe_2015": UtilityWeight(
        id="sleep_apnoea_disability_weight_europe_2015",
        label="Sleep apnoea disability weight",
        value=0.036,
        value_type="disutility",
        instrument="gbd_disability_weight",
        source_url="https://link.springer.com/article/10.1186/s12963-015-0042-4/tables/3",
        citation=(
            "Haagsma et al. 2015, Assessing disability weights based on the responses "
            "of 30,660 people from four European countries, Table 3"
        ),
        population="30,660 respondents from four European countries",
        lower=0.027,
        upper=0.044,
        notes="Used as a public-health fallback anchor for sleep-disordered-breathing burden.",
    ),
    "anxiety_disorders_mild_disability_weight_europe_2015": UtilityWeight(
        id="anxiety_disorders_mild_disability_weight_europe_2015",
        label="Mild anxiety disorders disability weight",
        value=0.045,
        value_type="disutility",
        instrument="gbd_disability_weight",
        source_url="https://www.ecdc.europa.eu/sites/default/files/documents/Haagsma-PopHealthMetrics-2014-Disability-weights.pdf",
        citation=(
            "Haagsma et al. 2015, Assessing disability weights based on the responses "
            "of 30,660 people from four European countries, Table 3"
        ),
        population="30,660 respondents from four European countries",
        lower=0.035,
        upper=0.054,
        notes="Fallback anchor for stress, worry, and calmness-related quality-of-life overlays.",
    ),
    "gerd_disability_weight_europe_2015": UtilityWeight(
        id="gerd_disability_weight_europe_2015",
        label="Heartburn and reflux disability weight",
        value=0.038,
        value_type="disutility",
        instrument="gbd_disability_weight",
        source_url="https://www.ecdc.europa.eu/sites/default/files/documents/Haagsma-PopHealthMetrics-2014-Disability-weights.pdf",
        citation=(
            "Haagsma et al. 2015, Assessing disability weights based on the responses "
            "of 30,660 people from four European countries, Table 3"
        ),
        population="30,660 respondents from four European countries",
        lower=0.029,
        upper=0.046,
        notes="Fallback anchor for upper-GI comfort overlays.",
    ),
    "constipation_disability_weight_europe_2015": UtilityWeight(
        id="constipation_disability_weight_europe_2015",
        label="Constipation disability weight",
        value=0.075,
        value_type="disutility",
        instrument="gbd_disability_weight",
        source_url="https://www.ecdc.europa.eu/sites/default/files/documents/Haagsma-PopHealthMetrics-2014-Disability-weights.pdf",
        citation=(
            "Haagsma et al. 2015, Assessing disability weights based on the responses "
            "of 30,660 people from four European countries, Table 3"
        ),
        population="30,660 respondents from four European countries",
        lower=0.061,
        upper=0.092,
        notes="Fallback anchor for bowel-habit quality-of-life overlays.",
    ),
    "irritable_bowel_syndrome_disability_weight_europe_2015": UtilityWeight(
        id="irritable_bowel_syndrome_disability_weight_europe_2015",
        label="Irritable bowel syndrome disability weight",
        value=0.062,
        value_type="disutility",
        instrument="gbd_disability_weight",
        source_url="https://www.ecdc.europa.eu/sites/default/files/documents/Haagsma-PopHealthMetrics-2014-Disability-weights.pdf",
        citation=(
            "Haagsma et al. 2015, Assessing disability weights based on the responses "
            "of 30,660 people from four European countries, Table 3"
        ),
        population="30,660 respondents from four European countries",
        lower=0.050,
        upper=0.077,
        notes="Fallback anchor for broader GI symptom quality-of-life overlays.",
    ),
    "low_back_pain_mild_disability_weight_europe_2015": UtilityWeight(
        id="low_back_pain_mild_disability_weight_europe_2015",
        label="Mild low back pain disability weight",
        value=0.024,
        value_type="disutility",
        instrument="gbd_disability_weight",
        source_url="https://www.ecdc.europa.eu/sites/default/files/documents/Haagsma-PopHealthMetrics-2014-Disability-weights.pdf",
        citation=(
            "Haagsma et al. 2015, Assessing disability weights based on the responses "
            "of 30,660 people from four European countries, Table 3"
        ),
        population="30,660 respondents from four European countries",
        lower=0.018,
        upper=0.030,
        notes="Fallback anchor for mild musculoskeletal discomfort and mobility-confidence overlays.",
    ),
    "distance_vision_mild_impairment_disability_weight_europe_2015": UtilityWeight(
        id="distance_vision_mild_impairment_disability_weight_europe_2015",
        label="Mild distance-vision impairment disability weight",
        value=0.004,
        value_type="disutility",
        instrument="gbd_disability_weight",
        source_url="https://www.ecdc.europa.eu/sites/default/files/documents/Haagsma-PopHealthMetrics-2014-Disability-weights.pdf",
        citation=(
            "Haagsma et al. 2015, Assessing disability weights based on the responses "
            "of 30,660 people from four European countries, Table 3"
        ),
        population="30,660 respondents from four European countries",
        lower=0.002,
        upper=0.005,
        notes="Fallback anchor for mild vision-preservation overlays.",
    ),
    "motor_impairment_mild_disability_weight_europe_2015": UtilityWeight(
        id="motor_impairment_mild_disability_weight_europe_2015",
        label="Mild motor impairment disability weight",
        value=0.011,
        value_type="disutility",
        instrument="gbd_disability_weight",
        source_url="https://www.ecdc.europa.eu/sites/default/files/documents/Haagsma-PopHealthMetrics-2014-Disability-weights.pdf",
        citation=(
            "Haagsma et al. 2015, Assessing disability weights based on the responses "
            "of 30,660 people from four European countries, Table 3"
        ),
        population="30,660 respondents from four European countries",
        lower=0.008,
        upper=0.014,
        notes="Fallback anchor for small function, exercise tolerance, and physical-performance overlays.",
    ),
}


def get_public_health_utility_weight(weight_id: str) -> UtilityWeight:
    """Return a named utility/disability weight used by Optiqal models."""
    try:
        return PUBLIC_HEALTH_UTILITY_WEIGHTS[weight_id]
    except KeyError as exc:
        raise KeyError(f"Unknown public-health utility weight: {weight_id}") from exc


@dataclass(frozen=True)
class MorbidityEffect:
    """Expected utility effect from causing or avoiding a health state."""

    id: str
    utility_weight_id: str
    duration_years: float
    probability: float = 1.0
    severity_multiplier: float = 1.0
    direction: MorbidityDirection = "cause"

    def __post_init__(self) -> None:
        if self.duration_years < 0:
            raise ValueError("duration_years must be nonnegative")
        if not 0 <= self.probability <= 1:
            raise ValueError("probability must be in [0, 1]")
        if self.severity_multiplier < 0:
            raise ValueError("severity_multiplier must be nonnegative")


def utility_reference_case_status(instrument: UtilityInstrument) -> ReferenceCaseStatus:
    """Classify whether a utility source is compatible with reference-case CUA."""
    if instrument in {"eq_5d", "sf_6d", "hui", "time_tradeoff", "standard_gamble"}:
        return "reference_case"
    if instrument == "mapping":
        return "acceptable_mapped"
    if instrument == "gbd_disability_weight":
        return "fallback"
    return "non_reference_case"


def discounted_years(years: float, annual_rate: float) -> float:
    """Present-value years for a constant annual utility effect."""
    if years < 0:
        raise ValueError("years must be nonnegative")
    if annual_rate < 0:
        raise ValueError("annual_rate must be nonnegative")
    if years == 0:
        return 0.0

    full_years = int(years)
    remainder = years - full_years
    total = sum(1.0 / ((1.0 + annual_rate) ** t) for t in range(full_years))
    if remainder:
        total += remainder / ((1.0 + annual_rate) ** full_years)
    return total


def morbidity_qaly(
    effect: MorbidityEffect,
    utility_weights: Mapping[str, UtilityWeight],
    *,
    reference_case: ReferenceCase = DEFAULT_REFERENCE_CASE,
) -> float:
    """Expected QALY gain/loss for one morbidity effect.

    Positive values mean the intervention avoids morbidity. Negative values mean
    the intervention causes morbidity.
    """
    if effect.utility_weight_id not in utility_weights:
        raise KeyError(f"Unknown utility weight: {effect.utility_weight_id}")
    weight = utility_weights[effect.utility_weight_id]
    magnitude = (
        effect.probability
        * effect.severity_multiplier
        * weight.utility_decrement
        * discounted_years(effect.duration_years, reference_case.health_discount_rate)
    )
    if effect.direction == "avoid":
        return magnitude
    return -magnitude


def morbidity_qaly_breakdown(
    effects: tuple[MorbidityEffect, ...],
    utility_weights: Mapping[str, UtilityWeight],
    *,
    reference_case: ReferenceCase = DEFAULT_REFERENCE_CASE,
) -> dict[str, object]:
    """Return itemized and total morbidity QALYs for reporting."""
    rows = []
    total = 0.0
    for effect in effects:
        weight = utility_weights[effect.utility_weight_id]
        qaly = morbidity_qaly(effect, utility_weights, reference_case=reference_case)
        total += qaly
        rows.append({
            "effect_id": effect.id,
            "utility_weight_id": effect.utility_weight_id,
            "label": weight.label,
            "instrument": weight.instrument,
            "reference_case_status": weight.reference_case_status,
            "probability": effect.probability,
            "duration_years": effect.duration_years,
            "severity_multiplier": effect.severity_multiplier,
            "direction": effect.direction,
            "qaly": round(qaly, 6),
            "source_url": weight.source_url,
        })
    return {
        "reference_case": reference_case.id,
        "total_qaly": round(total, 6),
        "effects": rows,
    }
