"""
Lifecycle QALY Model

CDC life tables, pathway decomposition, and survival curve integration.
Based on whatnut methodology.
"""

from dataclasses import dataclass
from typing import Literal, Optional
import json
from pathlib import Path
import numpy as np

# CDC National Vital Statistics Life Tables (2021)
# Probability of dying within one year (qx) by age
# Source: https://www.cdc.gov/nchs/products/life_tables.htm
CDC_LIFE_TABLE = {
    "male": {
        0: 0.00566,
        1: 0.00039,
        5: 0.00012,
        10: 0.00011,
        15: 0.00050,
        20: 0.00129,
        25: 0.00156,
        30: 0.00175,
        35: 0.00209,
        40: 0.00261,
        45: 0.00369,
        50: 0.00547,
        55: 0.00832,
        60: 0.01206,
        65: 0.01697,
        70: 0.02467,
        75: 0.03711,
        80: 0.05640,
        85: 0.08737,
        90: 0.13510,
        95: 0.19853,
        100: 0.27500,
    },
    "female": {
        0: 0.00476,
        1: 0.00031,
        5: 0.00010,
        10: 0.00009,
        15: 0.00025,
        20: 0.00047,
        25: 0.00059,
        30: 0.00073,
        35: 0.00096,
        40: 0.00136,
        45: 0.00204,
        50: 0.00310,
        55: 0.00469,
        60: 0.00692,
        65: 0.01019,
        70: 0.01556,
        75: 0.02502,
        80: 0.04085,
        85: 0.06837,
        90: 0.11295,
        95: 0.17639,
        100: 0.25500,
    },
}

# Age-varying cause-of-death fractions (CDC WONDER 2021)
CAUSE_FRACTIONS = {
    40: {"cvd": 0.20, "cancer": 0.25, "other": 0.55},
    50: {"cvd": 0.25, "cancer": 0.35, "other": 0.40},
    60: {"cvd": 0.30, "cancer": 0.35, "other": 0.35},
    70: {"cvd": 0.35, "cancer": 0.30, "other": 0.35},
    80: {"cvd": 0.40, "cancer": 0.20, "other": 0.40},
    90: {"cvd": 0.45, "cancer": 0.12, "other": 0.43},
}

# Age-varying quality weights (Sullivan et al. 2006, GBD 2019)
QUALITY_WEIGHTS = {
    25: 0.92,
    35: 0.90,
    45: 0.88,
    55: 0.85,
    65: 0.82,
    75: 0.78,
    85: 0.72,
    95: 0.65,
}


def interpolate_table(table: dict, age: float) -> float:
    """Log-linear interpolation for mortality rates."""
    ages = sorted(table.keys())

    if age <= ages[0]:
        return table[ages[0]]
    if age >= ages[-1]:
        return table[ages[-1]]

    for i in range(len(ages) - 1):
        if ages[i] <= age < ages[i + 1]:
            lower_age, upper_age = ages[i], ages[i + 1]
            break
    else:
        return table[ages[-1]]

    lower_val = table[lower_age]
    upper_val = table[upper_age]
    fraction = (age - lower_age) / (upper_age - lower_age)

    # Log-linear for mortality rates
    if lower_val > 0 and upper_val > 0:
        return np.exp(
            np.log(lower_val) + fraction * (np.log(upper_val) - np.log(lower_val))
        )
    else:
        return lower_val + fraction * (upper_val - lower_val)


def get_mortality_rate(age: float, sex: Literal["male", "female"]) -> float:
    """Get annual mortality rate (qx) for given age and sex."""
    return interpolate_table(CDC_LIFE_TABLE[sex], age)


def get_cause_fraction(age: float) -> dict:
    """Get cause-of-death fractions for given age."""
    ages = sorted(CAUSE_FRACTIONS.keys())

    if age <= ages[0]:
        return CAUSE_FRACTIONS[ages[0]].copy()
    if age >= ages[-1]:
        return CAUSE_FRACTIONS[ages[-1]].copy()

    for i in range(len(ages) - 1):
        if ages[i] <= age < ages[i + 1]:
            lower_age, upper_age = ages[i], ages[i + 1]
            break
    else:
        return CAUSE_FRACTIONS[ages[-1]].copy()

    fraction = (age - lower_age) / (upper_age - lower_age)
    lower = CAUSE_FRACTIONS[lower_age]
    upper = CAUSE_FRACTIONS[upper_age]

    return {
        "cvd": lower["cvd"] + fraction * (upper["cvd"] - lower["cvd"]),
        "cancer": lower["cancer"] + fraction * (upper["cancer"] - lower["cancer"]),
        "other": lower["other"] + fraction * (upper["other"] - lower["other"]),
    }


def get_quality_weight(age: float) -> float:
    """Get quality weight for given age."""
    ages = sorted(QUALITY_WEIGHTS.keys())

    if age <= ages[0]:
        return QUALITY_WEIGHTS[ages[0]]
    if age >= ages[-1]:
        return QUALITY_WEIGHTS[ages[-1]]

    for i in range(len(ages) - 1):
        if ages[i] <= age < ages[i + 1]:
            lower_age, upper_age = ages[i], ages[i + 1]
            break
    else:
        return QUALITY_WEIGHTS[ages[-1]]

    fraction = (age - lower_age) / (upper_age - lower_age)
    return QUALITY_WEIGHTS[lower_age] + fraction * (
        QUALITY_WEIGHTS[upper_age] - QUALITY_WEIGHTS[lower_age]
    )


# Precomputed baselines cache
_PRECOMPUTED_BASELINES: Optional[dict] = None


def load_precomputed_baselines() -> dict:
    """Load precomputed baseline data from JSON file."""
    global _PRECOMPUTED_BASELINES

    if _PRECOMPUTED_BASELINES is None:
        data_path = Path(__file__).parent / "data" / "baselines.json"
        with open(data_path, "r") as f:
            _PRECOMPUTED_BASELINES = json.load(f)

    return _PRECOMPUTED_BASELINES


def get_precomputed_baseline_qalys(
    age: int, sex: Literal["male", "female"]
) -> Optional[float]:
    """
    Get precomputed baseline QALYs for a given age and sex.

    Args:
        age: Integer age (0-100)
        sex: "male" or "female"

    Returns:
        Remaining QALYs if available, None otherwise
    """
    if age < 0 or age > 100:
        return None

    try:
        baselines = load_precomputed_baselines()
        return baselines["remaining_qalys"][sex][str(age)]
    except (KeyError, FileNotFoundError):
        return None


def get_precomputed_life_expectancy(
    age: int, sex: Literal["male", "female"]
) -> Optional[float]:
    """
    Get precomputed life expectancy for a given age and sex.

    Args:
        age: Integer age (0-100)
        sex: "male" or "female"

    Returns:
        Remaining life expectancy if available, None otherwise
    """
    if age < 0 or age > 100:
        return None

    try:
        baselines = load_precomputed_baselines()
        return baselines["life_expectancy"][sex][str(age)]
    except (KeyError, FileNotFoundError):
        return None


@dataclass
class PathwayHRs:
    """Pathway-specific hazard ratios."""

    cvd: float
    cancer: float
    other: float

    def to_dict(self) -> dict:
        return {"cvd": self.cvd, "cancer": self.cancer, "other": self.other}


@dataclass
class LifecycleResult:
    """Result of lifecycle QALY calculation."""

    baseline_qalys: float
    intervention_qalys: float
    qaly_gain: float
    life_years_gained: float
    pathway_contributions: dict  # {"cvd": x, "cancer": y, "other": z}
    discount_rate: float


class LifecycleModel:
    """
    Lifecycle QALY model with pathway decomposition.

    QALY = ∫₀^∞ S(t) × Q(t) × D(t) dt

    Where:
    - S(t) = survival probability at time t
    - Q(t) = quality weight at time t
    - D(t) = discount factor at time t
    """

    def __init__(
        self,
        start_age: int,
        sex: Literal["male", "female"],
        discount_rate: float = 0.03,
        max_age: int = 100,
        use_precomputed: bool = True,
        baseline_mortality_multiplier: float = 1.0,
    ):
        self.start_age = start_age
        self.sex = sex
        self.discount_rate = discount_rate
        self.max_age = max_age
        self.use_precomputed = use_precomputed
        self.baseline_mortality_multiplier = baseline_mortality_multiplier

        # Cache precomputed baseline if available
        # Only use precomputed if no mortality adjustment (default population)
        self._precomputed_baseline_qalys = None
        if use_precomputed and discount_rate == 0.03 and baseline_mortality_multiplier == 1.0:
            self._precomputed_baseline_qalys = get_precomputed_baseline_qalys(
                start_age, sex
            )

    def calculate(self, pathway_hrs: PathwayHRs) -> LifecycleResult:
        """
        Calculate lifetime QALYs with and without intervention.

        Args:
            pathway_hrs: Hazard ratios for each mortality pathway
                        (CVD, cancer, other). HR < 1 means reduced mortality.

        Returns:
            LifecycleResult with baseline, intervention, and gain QALYs.
        """
        # Use precomputed baseline if available (fast path)
        # Only for default population (no mortality adjustment)
        if self._precomputed_baseline_qalys is not None:
            baseline_qalys = self._precomputed_baseline_qalys
            # Still need to compute baseline_life_years
            baseline_survival = 1.0
            baseline_life_years = 0.0
            for year in range(self.max_age - self.start_age):
                current_age = self.start_age + year
                base_qx = get_mortality_rate(current_age, self.sex)
                baseline_life_years += baseline_survival
                baseline_survival *= 1 - base_qx
                if baseline_survival < 0.001:
                    break
        else:
            # Full computation path (used when mortality is adjusted)
            baseline_qalys = 0.0
            baseline_survival = 1.0
            baseline_life_years = 0.0

            for year in range(self.max_age - self.start_age):
                current_age = self.start_age + year
                # Apply mortality multiplier for risk factors (BMI, smoking, diabetes)
                base_qx = get_mortality_rate(current_age, self.sex) * self.baseline_mortality_multiplier
                # Cap at 1.0 (can't have >100% mortality probability)
                base_qx = min(base_qx, 0.99)
                quality = get_quality_weight(current_age)
                discount = 1 / (1 + self.discount_rate) ** year

                baseline_qaly = baseline_survival * quality * discount
                baseline_qalys += baseline_qaly
                baseline_life_years += baseline_survival

                baseline_survival *= 1 - base_qx

                if baseline_survival < 0.001:
                    break

        # Always compute intervention path
        intervention_qalys = 0.0
        intervention_life_years = 0.0

        cvd_contribution = 0.0
        cancer_contribution = 0.0
        other_contribution = 0.0

        baseline_survival = 1.0
        intervention_survival = 1.0

        for year in range(self.max_age - self.start_age):
            current_age = self.start_age + year
            # Apply mortality multiplier for risk factors
            base_qx = get_mortality_rate(current_age, self.sex) * self.baseline_mortality_multiplier
            base_qx = min(base_qx, 0.99)
            cause_frac = get_cause_fraction(current_age)
            quality = get_quality_weight(current_age)
            discount = 1 / (1 + self.discount_rate) ** year

            # Baseline QALY (for pathway contribution tracking)
            baseline_qaly = baseline_survival * quality * discount

            # Intervention mortality rate (intervention HR applies to the adjusted baseline)
            intervention_qx = base_qx * (
                cause_frac["cvd"] * pathway_hrs.cvd
                + cause_frac["cancer"] * pathway_hrs.cancer
                + cause_frac["other"] * pathway_hrs.other
            )

            # Intervention QALY
            intervention_qaly = intervention_survival * quality * discount
            intervention_qalys += intervention_qaly
            intervention_life_years += intervention_survival

            # Track pathway contributions
            qaly_diff = intervention_qaly - baseline_qaly
            if qaly_diff > 0:
                total_reduction = (
                    cause_frac["cvd"] * (1 - pathway_hrs.cvd)
                    + cause_frac["cancer"] * (1 - pathway_hrs.cancer)
                    + cause_frac["other"] * (1 - pathway_hrs.other)
                )
                if total_reduction > 0:
                    cvd_contribution += (
                        qaly_diff * cause_frac["cvd"] * (1 - pathway_hrs.cvd)
                    ) / total_reduction
                    cancer_contribution += (
                        qaly_diff * cause_frac["cancer"] * (1 - pathway_hrs.cancer)
                    ) / total_reduction
                    other_contribution += (
                        qaly_diff * cause_frac["other"] * (1 - pathway_hrs.other)
                    ) / total_reduction

            # Update survival
            baseline_survival *= 1 - base_qx
            intervention_survival *= 1 - intervention_qx

            if baseline_survival < 0.001 and intervention_survival < 0.001:
                break

        return LifecycleResult(
            baseline_qalys=baseline_qalys,
            intervention_qalys=intervention_qalys,
            qaly_gain=intervention_qalys - baseline_qalys,
            life_years_gained=intervention_life_years - baseline_life_years,
            pathway_contributions={
                "cvd": cvd_contribution,
                "cancer": cancer_contribution,
                "other": other_contribution,
            },
            discount_rate=self.discount_rate,
        )
