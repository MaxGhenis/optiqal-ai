"""
Profile Module

Defines demographic profiles for precomputation with relative mortality adjustments.
"""

from dataclasses import dataclass
from typing import Iterator, Literal, Optional
import numpy as np


@dataclass(frozen=True)
class Profile:
    """
    Demographic profile for QALY calculation.

    Represents a combination of risk factors that affect baseline mortality
    and intervention effectiveness.
    """

    age: int
    sex: Literal["male", "female"]
    bmi_category: Literal["normal", "overweight", "obese", "severely_obese"]
    smoking_status: Literal["never", "former", "current"]
    has_diabetes: bool

    @property
    def bmi_midpoint(self) -> float:
        """Representative BMI value for category."""
        return {
            "normal": 22.0,
            "overweight": 27.5,
            "obese": 32.5,
            "severely_obese": 40.0,
        }[self.bmi_category]

    @property
    def key(self) -> str:
        """Unique key for lookup table."""
        diabetes_str = "diabetic" if self.has_diabetes else "nondiabetic"
        return f"{self.age}_{self.sex}_{self.bmi_category}_{self.smoking_status}_{diabetes_str}"

    def __str__(self) -> str:
        return self.key


# =============================================================================
# RELATIVE MORTALITY RISKS
# =============================================================================

# BMI relative mortality risks (vs normal weight, BMI 18.5-25)
# Source: Global BMI Mortality Collaboration 2016, Lancet
# https://doi.org/10.1016/S0140-6736(16)30175-1
BMI_MORTALITY_RR = {
    "normal": 1.0,
    "overweight": 1.11,      # BMI 25-30: RR 1.11 (1.10-1.11)
    "obese": 1.44,           # BMI 30-35: RR 1.44 (1.38-1.50)
    "severely_obese": 2.06,  # BMI 35+: RR 2.06 (1.90-2.23)
}

# Smoking relative mortality risks (vs never smokers)
# Source: Jha et al 2013, NEJM; CDC mortality data
SMOKING_MORTALITY_RR = {
    "never": 1.0,
    "former": 1.34,    # Former smokers retain ~34% excess risk
    "current": 2.80,   # Current smokers: 2.8x all-cause mortality
}

# Diabetes relative mortality risk (vs non-diabetic)
# Source: Emerging Risk Factors Collaboration 2011, NEJM
# Adjusted for age, sex, smoking, BMI
DIABETES_MORTALITY_RR = 1.80  # HR 1.80 (1.71-1.90)


def get_baseline_mortality_multiplier(profile: Profile) -> float:
    """
    Calculate multiplicative adjustment to baseline mortality.

    Combines relative risks from BMI, smoking, and diabetes.
    Uses multiplicative model (conservative for overlapping risks).

    Args:
        profile: Demographic profile

    Returns:
        Mortality rate multiplier (1.0 = no adjustment)
    """
    bmi_rr = BMI_MORTALITY_RR[profile.bmi_category]
    smoking_rr = SMOKING_MORTALITY_RR[profile.smoking_status]
    diabetes_rr = DIABETES_MORTALITY_RR if profile.has_diabetes else 1.0

    # Multiplicative model
    # Note: This may overestimate combined risk but is conservative
    return bmi_rr * smoking_rr * diabetes_rr


# =============================================================================
# INTERVENTION EFFECT MODIFIERS
# =============================================================================

# Some interventions have modified effectiveness by profile
# These are multiplicative adjustments to the intervention's hazard ratio effect

def get_intervention_modifier(
    profile: Profile,
    intervention_category: str
) -> float:
    """
    Get multiplicative modifier for intervention effect.

    Some interventions work differently based on baseline risk profile.

    Args:
        profile: Demographic profile
        intervention_category: Category of intervention (exercise, diet, etc.)

    Returns:
        Effect modifier (1.0 = no modification, >1 = enhanced effect)
    """
    modifier = 1.0

    if intervention_category == "exercise":
        # Exercise has larger absolute benefit for higher-risk individuals
        # but similar relative risk reduction
        # Obese individuals may see larger metabolic improvements
        if profile.bmi_category in ("obese", "severely_obese"):
            modifier *= 1.15  # ~15% larger effect

        # Elderly (age > 70) have slightly smaller mortality effect
        # but larger functional/quality benefits
        if profile.age > 70:
            modifier *= 0.90  # ~10% smaller mortality effect

    elif intervention_category == "diet":
        # Diet interventions more effective for those with poor baseline
        if profile.bmi_category in ("obese", "severely_obese"):
            modifier *= 1.20  # ~20% larger effect

        # Diabetics see larger metabolic improvements
        if profile.has_diabetes:
            modifier *= 1.10

    elif intervention_category == "smoking":
        # Smoking cessation: younger quitters benefit more
        if profile.age < 40:
            modifier *= 1.30  # Nearly eliminate excess risk
        elif profile.age > 60:
            modifier *= 0.85  # Still beneficial but reduced

    elif intervention_category == "alcohol":
        # Heavy baseline drinkers (not modeled) would benefit more
        pass

    return modifier


# =============================================================================
# PROFILE GENERATION
# =============================================================================

def generate_all_profiles(
    ages: Optional[list] = None,
    sexes: Optional[list] = None,
    bmi_categories: Optional[list] = None,
    smoking_statuses: Optional[list] = None,
    diabetes_statuses: Optional[list] = None,
) -> Iterator[Profile]:
    """
    Generate all profile combinations for precomputation.

    Default grid:
    - Ages: 25, 30, 35, ..., 80 (12 points)
    - Sexes: male, female (2)
    - BMI: normal, overweight, obese, severely_obese (4)
    - Smoking: never, former, current (3)
    - Diabetes: False, True (2)

    Total: 12 × 2 × 4 × 3 × 2 = 576 profiles per intervention

    Yields:
        Profile objects for each combination
    """
    if ages is None:
        ages = list(range(25, 85, 5))  # 25, 30, 35, ..., 80

    if sexes is None:
        sexes = ["male", "female"]

    if bmi_categories is None:
        bmi_categories = ["normal", "overweight", "obese", "severely_obese"]

    if smoking_statuses is None:
        smoking_statuses = ["never", "former", "current"]

    if diabetes_statuses is None:
        diabetes_statuses = [False, True]

    for age in ages:
        for sex in sexes:
            for bmi in bmi_categories:
                for smoking in smoking_statuses:
                    for diabetes in diabetes_statuses:
                        yield Profile(
                            age=age,
                            sex=sex,
                            bmi_category=bmi,
                            smoking_status=smoking,
                            has_diabetes=diabetes,
                        )


def count_profiles(**kwargs) -> int:
    """Count total profiles without generating them."""
    ages = kwargs.get("ages", list(range(25, 85, 5)))
    sexes = kwargs.get("sexes", ["male", "female"])
    bmi_categories = kwargs.get("bmi_categories", ["normal", "overweight", "obese", "severely_obese"])
    smoking_statuses = kwargs.get("smoking_statuses", ["never", "former", "current"])
    diabetes_statuses = kwargs.get("diabetes_statuses", [False, True])

    return (
        len(ages)
        * len(sexes)
        * len(bmi_categories)
        * len(smoking_statuses)
        * len(diabetes_statuses)
    )
