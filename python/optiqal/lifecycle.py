"""
Lifecycle QALY Model

CDC life tables, pathway decomposition, and survival curve integration.
Based on whatnut methodology.
"""

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import numpy as np

from .defaults import validate_qaly_discount_rate
from .snapshots import load_snapshot

# The exact anchor ages the interpolators expect. Pinned so a snapshot that has
# lost or gained an age fails at import instead of being silently interpolated
# across the hole. `data_build.cdc_life_table.EXPECTED_AGES` and
# `data_build.cause_fractions.EXPECTED_AGES` repeat the life-table and
# cause-fraction sets for standalone validation; test_snapshots.py holds each
# pair equal.
LIFE_TABLE_AGES = (
    0,
    1,
    5,
    10,
    15,
    20,
    25,
    30,
    35,
    40,
    45,
    50,
    55,
    60,
    65,
    70,
    75,
    80,
    85,
    90,
    95,
    100,
)
QUALITY_WEIGHT_AGES = (25, 35, 45, 55, 65, 75, 85, 95)
CAUSE_FRACTION_AGES = (40, 50, 60, 70, 80, 90)

# Runtime data is loaded and validated at import. The snapshot provenance records
# which values are derived, authored, or only transcribed from the legacy engine.
_LIFE_TABLE_SNAPSHOT = load_snapshot("cdc_life_table")
CDC_LIFE_TABLE = {
    "male": _LIFE_TABLE_SNAPSHOT.age_table(
        "life_table", "male", ages=LIFE_TABLE_AGES, maximum=1.0
    ),
    "female": _LIFE_TABLE_SNAPSHOT.age_table(
        "life_table", "female", ages=LIFE_TABLE_AGES, maximum=1.0
    ),
}

_CAUSE_FRACTION_SNAPSHOT = load_snapshot("cause_fractions")
CAUSE_FRACTIONS = _CAUSE_FRACTION_SNAPSHOT.age_rows(
    "cause_fractions",
    columns=("cvd", "cancer", "other"),
    ages=CAUSE_FRACTION_AGES,
    sums_to=1.0,
    tolerance=1e-12,
)

_QUALITY_WEIGHT_SNAPSHOT = load_snapshot("meps_quality_weights")
QUALITY_WEIGHTS = _QUALITY_WEIGHT_SNAPSHOT.age_table(
    "quality_weights", ages=QUALITY_WEIGHT_AGES, maximum=1.0
)
QUALITY_WEIGHT_STD = _QUALITY_WEIGHT_SNAPSHOT.value("quality_weight_std", maximum=1.0)
CONDITION_DECREMENTS = _QUALITY_WEIGHT_SNAPSHOT.named_table(
    "condition_decrements",
    keys=(
        "diabetes",
        "hypertension",
        "heart_disease",
        "stroke",
        "cancer",
        "arthritis",
    ),
    maximum=1.0,
)


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


# Precomputed baselines cache. These tabulated lookups (integrated to age 100 at
# a 3% discount, rounded to 3 decimals) are for direct callers only;
# LifecycleModel does not read them, because a table value cannot follow the
# model's horizon, discount rate, mortality multiplier or truncation.
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
    """Pathway-specific hazard ratios.

    Each ratio must be finite and nonnegative; ``LifecycleModel.calculate``
    raises ``ValueError`` otherwise.
    """

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


# Annual death probability ceiling, applied to the adjusted baseline and to the
# intervention rate alike (the vectorized simulator uses the same 0.99 cap), so
# survival stays in (0, 1] however large the multiplier or hazard ratio.
MAX_ANNUAL_MORTALITY = 0.99

# The integration stops after the first year that leaves both the baseline and
# the intervention survival below this level. Both series always cover the
# same years.
SURVIVAL_TRUNCATION = 0.001


def _require_nonnegative_finite(name: str, value: float) -> None:
    """Raise ValueError unless ``value`` is a finite number >= 0."""
    if not (math.isfinite(value) and value >= 0):
        raise ValueError(f"{name} must be finite and nonnegative, got {value!r}.")


class LifecycleModel:
    """
    Lifecycle QALY model with pathway decomposition.

    QALY = ∫₀^∞ S(t) × Q(t) × D(t) dt

    Where:
    - S(t) = survival probability at time t
    - Q(t) = quality weight at time t
    - D(t) = discount factor at time t

    The integral is an annual sum of start-of-year survival × quality ×
    discount over ages ``start_age`` to ``max_age - 1`` (no years when
    ``max_age <= start_age``). Baseline and intervention accumulate in one loop
    over the same years, so every pathway HR equal to 1 gives a gain of exactly
    zero. Baseline annual mortality is the life-table rate times
    ``baseline_mortality_multiplier``; the intervention rate scales that by the
    cause-fraction-weighted pathway HR. Both are capped at
    ``MAX_ANNUAL_MORTALITY``. The loop stops early once both survival curves are
    below ``SURVIVAL_TRUNCATION``.

    ``discount_rate`` must lie in the supported 0-10% range and
    ``baseline_mortality_multiplier`` must be finite and nonnegative; otherwise
    the constructor raises ``ValueError``.

    ``use_precomputed`` is accepted for backward compatibility and has no
    effect: results never come from ``data/baselines.json``, whose values are
    integrated to age 100 at a 3% discount and rounded to 3 decimals.
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
        if not math.isfinite(discount_rate):
            raise ValueError(f"discount_rate must be finite, got {discount_rate!r}.")
        _require_nonnegative_finite(
            "baseline_mortality_multiplier", baseline_mortality_multiplier
        )
        self.start_age = start_age
        self.sex = sex
        self.discount_rate = validate_qaly_discount_rate(discount_rate)
        self.max_age = max_age
        # Inert; kept so existing callers that pass it keep working.
        self.use_precomputed = use_precomputed
        self.baseline_mortality_multiplier = baseline_mortality_multiplier

    def calculate(self, pathway_hrs: PathwayHRs) -> LifecycleResult:
        """
        Calculate lifetime QALYs with and without intervention.

        Args:
            pathway_hrs: Hazard ratios for each mortality pathway
                        (CVD, cancer, other). HR < 1 means reduced mortality.
                        Each must be finite and nonnegative.

        Returns:
            LifecycleResult with baseline, intervention, and gain QALYs.

        Raises:
            ValueError: If a pathway HR is negative, infinite or NaN.
        """
        for pathway, hr in pathway_hrs.to_dict().items():
            _require_nonnegative_finite(f"{pathway} hazard ratio", hr)

        baseline_qalys = 0.0
        intervention_qalys = 0.0
        baseline_life_years = 0.0
        intervention_life_years = 0.0

        cvd_contribution = 0.0
        cancer_contribution = 0.0
        other_contribution = 0.0

        baseline_survival = 1.0
        intervention_survival = 1.0

        for year in range(self.max_age - self.start_age):
            current_age = self.start_age + year
            # Apply the caller's risk-factor multiplier to baseline mortality
            base_qx = min(
                get_mortality_rate(current_age, self.sex)
                * self.baseline_mortality_multiplier,
                MAX_ANNUAL_MORTALITY,
            )
            cause_frac = get_cause_fraction(current_age)
            quality = get_quality_weight(current_age)
            discount = 1 / (1 + self.discount_rate) ** year

            # Cause-weighted HR. Dividing by the fraction total (1 up to
            # rounding) makes it exactly 1 when every pathway HR is 1, because
            # numerator and denominator are then the same floating-point sum.
            weighted_hr = (
                cause_frac["cvd"] * pathway_hrs.cvd
                + cause_frac["cancer"] * pathway_hrs.cancer
                + cause_frac["other"] * pathway_hrs.other
            ) / (cause_frac["cvd"] + cause_frac["cancer"] + cause_frac["other"])
            # The intervention HR applies to the adjusted, capped baseline. A
            # zero baseline stays zero, even for an HR so large that the
            # weighted sum overflows (0 * inf would be NaN).
            intervention_qx = (
                min(base_qx * weighted_hr, MAX_ANNUAL_MORTALITY) if base_qx > 0 else 0.0
            )

            baseline_qaly = baseline_survival * quality * discount
            intervention_qaly = intervention_survival * quality * discount
            baseline_qalys += baseline_qaly
            intervention_qalys += intervention_qaly
            baseline_life_years += baseline_survival
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

            if (
                baseline_survival < SURVIVAL_TRUNCATION
                and intervention_survival < SURVIVAL_TRUNCATION
            ):
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
