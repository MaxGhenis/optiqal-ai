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
    has_hypertension: bool = False
    activity_level: Literal["sedentary", "light", "moderate", "active"] = "light"

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
        """Unique key for lookup table (v3: includes activity level)."""
        diabetes_str = "diabetic" if self.has_diabetes else "nondiabetic"
        hypertension_str = "hypertensive" if self.has_hypertension else "normotensive"
        return f"{self.age}_{self.sex}_{self.bmi_category}_{self.smoking_status}_{diabetes_str}_{hypertension_str}_{self.activity_level}"

    @property
    def key_v2(self) -> str:
        """Key format with hypertension but without activity level."""
        diabetes_str = "diabetic" if self.has_diabetes else "nondiabetic"
        hypertension_str = "hypertensive" if self.has_hypertension else "normotensive"
        return f"{self.age}_{self.sex}_{self.bmi_category}_{self.smoking_status}_{diabetes_str}_{hypertension_str}"

    @property
    def key_v1(self) -> str:
        """Legacy key format without hypertension (for backward compatibility)."""
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

# Hypertension relative mortality risk (vs normotensive)
# Source: Lewington et al 2002, Lancet (Prospective Studies Collaboration)
# ~40-69yo: each 20 mmHg SBP doubles CVD mortality
# Using ~1.5x all-cause for treated hypertension
# Untreated/uncontrolled would be higher (~2.0x)
HYPERTENSION_MORTALITY_RR = 1.50  # Conservative for "has hypertension" (may be treated)

# Physical activity relative mortality risk (vs moderate activity)
# Source: Lear et al 2017, Lancet (PURE study); Ekelund et al 2016
# Sedentary lifestyle substantially increases mortality
ACTIVITY_MORTALITY_RR = {
    "sedentary": 1.40,   # Sitting >8h/day with no exercise: RR ~1.4
    "light": 1.15,       # Some walking but <150 min/week
    "moderate": 1.00,    # Meets guidelines (150 min/week)
    "active": 0.90,      # Exceeds guidelines (300+ min/week)
}


def get_baseline_mortality_multiplier(profile: Profile) -> float:
    """
    Calculate multiplicative adjustment to baseline mortality.

    Combines relative risks from BMI, smoking, diabetes, hypertension,
    and physical activity level.
    Uses multiplicative model (conservative for overlapping risks).

    Args:
        profile: Demographic profile

    Returns:
        Mortality rate multiplier (1.0 = no adjustment)
    """
    bmi_rr = BMI_MORTALITY_RR[profile.bmi_category]
    smoking_rr = SMOKING_MORTALITY_RR[profile.smoking_status]
    diabetes_rr = DIABETES_MORTALITY_RR if profile.has_diabetes else 1.0
    hypertension_rr = HYPERTENSION_MORTALITY_RR if profile.has_hypertension else 1.0
    activity_rr = ACTIVITY_MORTALITY_RR[profile.activity_level]

    # Multiplicative model
    # Note: This may overestimate combined risk but is conservative
    return bmi_rr * smoking_rr * diabetes_rr * hypertension_rr * activity_rr


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
    Modifier > 1 means the intervention is MORE effective (HR moves further from 1).
    Modifier < 1 means the intervention is LESS effective (diminishing returns).

    Evidence sources:
    - Exercise: Kodama et al 2009, Wahid et al 2016
    - Diet: Estruch et al 2018 (PREDIMED)
    - Smoking: Doll et al 2004 (British Doctors Study)
    - Activity level effects: Ekelund et al 2016

    Args:
        profile: Demographic profile
        intervention_category: Category of intervention (exercise, diet, etc.)

    Returns:
        Effect modifier (1.0 = no modification, >1 = enhanced effect)
    """
    modifier = 1.0

    if intervention_category == "exercise":
        # Exercise interventions show diminishing returns based on baseline activity
        # Sedentary → active: full effect
        # Already active → more active: much smaller marginal effect
        activity_modifiers = {
            "sedentary": 1.20,   # Largest gains from starting exercise
            "light": 1.00,       # Baseline effect
            "moderate": 0.60,    # Already meeting guidelines, smaller marginal gain
            "active": 0.30,      # Already exceeding guidelines, minimal additional benefit
        }
        modifier *= activity_modifiers[profile.activity_level]

        # Obese individuals may see larger metabolic improvements
        if profile.bmi_category in ("obese", "severely_obese"):
            modifier *= 1.15  # ~15% larger effect

        # Elderly (age > 70) have slightly smaller mortality effect
        # but larger functional/quality benefits (not captured here)
        if profile.age > 70:
            modifier *= 0.90  # ~10% smaller mortality effect

        # Hypertensive individuals see larger BP reduction from exercise
        if profile.has_hypertension:
            modifier *= 1.10

    elif intervention_category == "diet":
        # Diet interventions more effective for those with poor metabolic health
        if profile.bmi_category in ("obese", "severely_obese"):
            modifier *= 1.20  # ~20% larger effect

        # Diabetics see larger metabolic improvements
        if profile.has_diabetes:
            modifier *= 1.15

        # Hypertensives benefit more from DASH/Mediterranean patterns
        if profile.has_hypertension:
            modifier *= 1.10

    elif intervention_category == "smoking":
        # Smoking cessation: younger quitters benefit more
        # Doll et al 2004: quitting at 30 gains ~10 years, at 60 gains ~3 years
        if profile.age < 35:
            modifier *= 1.30  # Nearly eliminate excess risk
        elif profile.age < 45:
            modifier *= 1.15
        elif profile.age < 55:
            modifier *= 1.00  # Baseline
        elif profile.age < 65:
            modifier *= 0.85
        else:
            modifier *= 0.70  # Still beneficial but reduced

    elif intervention_category == "alcohol":
        # Heavy baseline drinkers (not modeled) would benefit more
        pass

    elif intervention_category == "stress":
        # Meditation/stress interventions more effective for high-stress individuals
        # Activity level as proxy for stress management capacity
        if profile.activity_level == "sedentary":
            modifier *= 1.15  # More room for improvement

    elif intervention_category == "sleep":
        # Sleep interventions - sedentary individuals often have worse sleep
        if profile.activity_level == "sedentary":
            modifier *= 1.10

    elif intervention_category == "supplement":
        # Supplements generally less effective in healthy populations
        # More effective in those with deficiencies (proxy: poor lifestyle)
        if profile.activity_level == "sedentary" and profile.bmi_category in ("obese", "severely_obese"):
            modifier *= 1.20  # More likely to have nutritional gaps

    return modifier


def get_intervention_modifier_breakdown(
    profile: Profile,
    intervention_category: str
) -> dict:
    """
    Get detailed breakdown of intervention effect modifiers.

    Useful for explaining why effect differs by profile.

    Returns:
        Dictionary with component modifiers and final combined modifier
    """
    components = {}
    modifier = 1.0

    if intervention_category == "exercise":
        activity_mod = {
            "sedentary": 1.20,
            "light": 1.00,
            "moderate": 0.60,
            "active": 0.30,
        }[profile.activity_level]
        components["activity_level"] = activity_mod
        modifier *= activity_mod

        if profile.bmi_category in ("obese", "severely_obese"):
            components["obesity"] = 1.15
            modifier *= 1.15

        if profile.age > 70:
            components["age_over_70"] = 0.90
            modifier *= 0.90

        if profile.has_hypertension:
            components["hypertension"] = 1.10
            modifier *= 1.10

    elif intervention_category == "diet":
        if profile.bmi_category in ("obese", "severely_obese"):
            components["obesity"] = 1.20
            modifier *= 1.20

        if profile.has_diabetes:
            components["diabetes"] = 1.15
            modifier *= 1.15

        if profile.has_hypertension:
            components["hypertension"] = 1.10
            modifier *= 1.10

    elif intervention_category == "smoking":
        age_mods = [
            (35, 1.30), (45, 1.15), (55, 1.00), (65, 0.85), (999, 0.70)
        ]
        for threshold, mod in age_mods:
            if profile.age < threshold:
                components["age_effect"] = mod
                modifier *= mod
                break

    components["combined"] = modifier
    return components


# =============================================================================
# PROFILE GENERATION
# =============================================================================

def generate_all_profiles(
    ages: Optional[list] = None,
    sexes: Optional[list] = None,
    bmi_categories: Optional[list] = None,
    smoking_statuses: Optional[list] = None,
    diabetes_statuses: Optional[list] = None,
    hypertension_statuses: Optional[list] = None,
    activity_levels: Optional[list] = None,
) -> Iterator[Profile]:
    """
    Generate all profile combinations for precomputation.

    Default grid (v2 with hypertension):
    - Ages: 25, 30, 35, ..., 80 (12 points)
    - Sexes: male, female (2)
    - BMI: normal, overweight, obese, severely_obese (4)
    - Smoking: never, former, current (3)
    - Diabetes: False, True (2)
    - Hypertension: False, True (2)
    - Activity: light (fixed - only varies via effect modifiers)

    Total: 12 × 2 × 4 × 3 × 2 × 2 = 1,152 profiles per intervention

    To include activity level in the grid:
        generate_all_profiles(activity_levels=["sedentary", "light", "moderate", "active"])
        → 4,608 profiles per intervention

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

    if hypertension_statuses is None:
        hypertension_statuses = [False, True]

    if activity_levels is None:
        # Default to "light" only to keep grid manageable
        # Activity level primarily affects effect modifiers, not baseline mortality
        activity_levels = ["light"]

    for age in ages:
        for sex in sexes:
            for bmi in bmi_categories:
                for smoking in smoking_statuses:
                    for diabetes in diabetes_statuses:
                        for hypertension in hypertension_statuses:
                            for activity in activity_levels:
                                yield Profile(
                                    age=age,
                                    sex=sex,
                                    bmi_category=bmi,
                                    smoking_status=smoking,
                                    has_diabetes=diabetes,
                                    has_hypertension=hypertension,
                                    activity_level=activity,
                                )


def count_profiles(**kwargs) -> int:
    """Count total profiles without generating them."""
    ages = kwargs.get("ages", list(range(25, 85, 5)))
    sexes = kwargs.get("sexes", ["male", "female"])
    bmi_categories = kwargs.get("bmi_categories", ["normal", "overweight", "obese", "severely_obese"])
    smoking_statuses = kwargs.get("smoking_statuses", ["never", "former", "current"])
    diabetes_statuses = kwargs.get("diabetes_statuses", [False, True])
    hypertension_statuses = kwargs.get("hypertension_statuses", [False, True])
    activity_levels = kwargs.get("activity_levels", ["light"])

    return (
        len(ages)
        * len(sexes)
        * len(bmi_categories)
        * len(smoking_statuses)
        * len(diabetes_statuses)
        * len(hypertension_statuses)
        * len(activity_levels)
    )


# =============================================================================
# PRESET PROFILE CONFIGURATIONS
# =============================================================================

# Standard presets for different use cases

PRESET_MINIMAL = {
    "ages": [30, 50, 70],
    "sexes": ["male", "female"],
    "bmi_categories": ["normal", "obese"],
    "smoking_statuses": ["never", "current"],
    "diabetes_statuses": [False, True],
    "hypertension_statuses": [False],
    "activity_levels": ["light"],
}  # 3 × 2 × 2 × 2 × 2 × 1 × 1 = 48 profiles

PRESET_STANDARD = {
    "ages": list(range(25, 85, 5)),
    "sexes": ["male", "female"],
    "bmi_categories": ["normal", "overweight", "obese", "severely_obese"],
    "smoking_statuses": ["never", "former", "current"],
    "diabetes_statuses": [False, True],
    "hypertension_statuses": [False, True],
    "activity_levels": ["light"],
}  # 12 × 2 × 4 × 3 × 2 × 2 × 1 = 1,152 profiles

PRESET_FULL = {
    "ages": list(range(25, 85, 5)),
    "sexes": ["male", "female"],
    "bmi_categories": ["normal", "overweight", "obese", "severely_obese"],
    "smoking_statuses": ["never", "former", "current"],
    "diabetes_statuses": [False, True],
    "hypertension_statuses": [False, True],
    "activity_levels": ["sedentary", "light", "moderate", "active"],
}  # 12 × 2 × 4 × 3 × 2 × 2 × 4 = 4,608 profiles
