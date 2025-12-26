"""
Markov State-Transition Model for QALY Simulation

Models incident conditions (diabetes, stroke, etc.) that affect quality
and mortality over the lifetime. Calibrated to MEPS 2019-2022 longitudinal data.
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Literal

from .lifecycle import get_mortality_rate, get_quality_weight, CONDITION_DECREMENTS


# Condition incidence rates by age group (from MEPS 2019-2022 longitudinal analysis)
# Annual probability of acquiring condition, given no condition at start of year
INCIDENCE_RATES = {
    "diabetes": {
        30: 0.0023,  # 0.23% per year for ages 18-40
        45: 0.0071,  # 0.71% for 40-50
        55: 0.0093,  # 0.93% for 50-60
        65: 0.0104,  # 1.04% for 60-70
        75: 0.0083,  # 0.83% for 70-80
        85: 0.0063,  # 0.63% for 80+
    },
    "hypertension": {
        30: 0.0083,
        45: 0.0158,
        55: 0.0265,
        65: 0.0414,
        75: 0.0302,
        85: 0.0451,
    },
    "heart_disease": {
        30: 0.0006,
        45: 0.0030,
        55: 0.0071,
        65: 0.0107,
        75: 0.0160,
        85: 0.0171,
    },
    "stroke": {
        30: 0.0002,
        45: 0.0015,
        55: 0.0026,
        65: 0.0061,
        75: 0.0070,
        85: 0.0104,
    },
    "cancer": {
        30: 0.0013,
        45: 0.0033,
        55: 0.0079,
        65: 0.0110,
        75: 0.0226,
        85: 0.0184,
    },
    "arthritis": {
        30: 0.0046,
        45: 0.0154,
        55: 0.0284,
        65: 0.0428,
        75: 0.0472,
        85: 0.0462,
    },
}

# Mortality multipliers for conditions (from literature)
# These multiply baseline mortality when condition is present
CONDITION_MORTALITY_MULTIPLIERS = {
    "diabetes": 1.8,        # Diabetes roughly doubles mortality
    "hypertension": 1.3,    # Moderate increase
    "heart_disease": 2.0,   # Heart disease doubles mortality
    "stroke": 2.5,          # Stroke history high mortality
    "cancer": 1.5,          # Varies greatly by type, using moderate
    "arthritis": 1.1,       # Minimal direct mortality effect
}


def get_incidence_rate(condition: str, age: int) -> float:
    """Get annual incidence rate for a condition at given age."""
    rates = INCIDENCE_RATES.get(condition, {})
    if not rates:
        return 0.0

    ages = sorted(rates.keys())

    if age <= ages[0]:
        return rates[ages[0]]
    if age >= ages[-1]:
        return rates[ages[-1]]

    # Linear interpolation
    for i in range(len(ages) - 1):
        if ages[i] <= age < ages[i + 1]:
            frac = (age - ages[i]) / (ages[i + 1] - ages[i])
            return rates[ages[i]] + frac * (rates[ages[i + 1]] - rates[ages[i]])

    return rates[ages[-1]]


@dataclass
class HealthState:
    """Current health state of an individual."""
    alive: bool = True
    diabetes: bool = False
    hypertension: bool = False
    heart_disease: bool = False
    stroke: bool = False
    cancer: bool = False
    arthritis: bool = False

    def get_quality_decrement(self) -> float:
        """Total quality decrement from all conditions."""
        decrement = 0.0
        if self.diabetes:
            decrement += CONDITION_DECREMENTS.get("diabetes", 0)
        if self.hypertension:
            decrement += CONDITION_DECREMENTS.get("hypertension", 0)
        if self.heart_disease:
            decrement += CONDITION_DECREMENTS.get("heart_disease", 0)
        if self.stroke:
            decrement += CONDITION_DECREMENTS.get("stroke", 0)
        if self.cancer:
            decrement += CONDITION_DECREMENTS.get("cancer", 0)
        if self.arthritis:
            decrement += CONDITION_DECREMENTS.get("arthritis", 0)
        return decrement

    def get_mortality_multiplier(self) -> float:
        """Multiplicative mortality increase from conditions."""
        multiplier = 1.0
        if self.diabetes:
            multiplier *= CONDITION_MORTALITY_MULTIPLIERS["diabetes"]
        if self.hypertension:
            multiplier *= CONDITION_MORTALITY_MULTIPLIERS["hypertension"]
        if self.heart_disease:
            multiplier *= CONDITION_MORTALITY_MULTIPLIERS["heart_disease"]
        if self.stroke:
            multiplier *= CONDITION_MORTALITY_MULTIPLIERS["stroke"]
        if self.cancer:
            multiplier *= CONDITION_MORTALITY_MULTIPLIERS["cancer"]
        if self.arthritis:
            multiplier *= CONDITION_MORTALITY_MULTIPLIERS["arthritis"]
        return multiplier


@dataclass
class MarkovResult:
    """Result of a single Markov simulation run."""
    qalys: float
    life_years: float
    death_age: int
    conditions_acquired: Dict[str, Optional[int]]  # condition -> age acquired (or None)


def simulate_lifetime_markov(
    start_age: int,
    sex: Literal["male", "female"],
    intervention_hr: float = 1.0,
    initial_state: Optional[HealthState] = None,
    discount_rate: float = 0.03,
    max_age: int = 100,
    rng: Optional[np.random.Generator] = None,
) -> MarkovResult:
    """
    Simulate a single lifetime using Markov state transitions.

    Args:
        start_age: Starting age
        sex: Biological sex for mortality lookup
        intervention_hr: Hazard ratio for intervention (< 1 = reduced mortality)
        initial_state: Starting health state (default: healthy)
        discount_rate: Annual discount rate
        max_age: Maximum simulation age
        rng: Random number generator

    Returns:
        MarkovResult with lifetime outcomes
    """
    if rng is None:
        rng = np.random.default_rng()

    if initial_state is None:
        state = HealthState()
    else:
        state = HealthState(
            alive=initial_state.alive,
            diabetes=initial_state.diabetes,
            hypertension=initial_state.hypertension,
            heart_disease=initial_state.heart_disease,
            stroke=initial_state.stroke,
            cancer=initial_state.cancer,
            arthritis=initial_state.arthritis,
        )

    qalys = 0.0
    life_years = 0.0
    conditions_acquired = {
        "diabetes": None,
        "hypertension": None,
        "heart_disease": None,
        "stroke": None,
        "cancer": None,
        "arthritis": None,
    }

    for year in range(max_age - start_age):
        if not state.alive:
            break

        age = start_age + year
        discount = 1 / (1 + discount_rate) ** year

        # Get base quality weight for age, minus condition decrements
        base_quality = get_quality_weight(age)
        quality = max(0.1, base_quality - state.get_quality_decrement())

        # Add this year's QALY (alive at start of year)
        qalys += quality * discount
        life_years += 1

        # Check for new conditions
        conditions = ["diabetes", "hypertension", "heart_disease", "stroke", "cancer", "arthritis"]
        for cond in conditions:
            if not getattr(state, cond):  # Don't already have it
                incidence = get_incidence_rate(cond, age)
                if rng.random() < incidence:
                    setattr(state, cond, True)
                    conditions_acquired[cond] = age

        # Check for death
        base_mortality = get_mortality_rate(age, sex)
        # Apply condition multipliers and intervention HR
        mortality = base_mortality * state.get_mortality_multiplier() * intervention_hr
        mortality = min(mortality, 0.99)  # Cap at 99%

        if rng.random() < mortality:
            state.alive = False

    return MarkovResult(
        qalys=qalys,
        life_years=life_years,
        death_age=start_age + int(life_years),
        conditions_acquired=conditions_acquired,
    )


def simulate_lifetime_paired(
    start_age: int,
    sex: Literal["male", "female"],
    intervention_hr: float,
    discount_rate: float = 0.03,
    max_age: int = 100,
    rng: Optional[np.random.Generator] = None,
    initial_state: Optional[HealthState] = None,
) -> tuple:
    """
    Simulate paired baseline/intervention lifetimes with correlated outcomes.

    Uses the same random draws for condition acquisition, but different
    mortality outcomes based on intervention HR.

    Args:
        start_age: Starting age
        sex: Biological sex
        intervention_hr: Hazard ratio for intervention
        discount_rate: Annual discount rate
        max_age: Maximum simulation age
        rng: Random number generator
        initial_state: Known health conditions at start (reduces uncertainty)

    Returns:
        (baseline_result, intervention_result) tuple
    """
    if rng is None:
        rng = np.random.default_rng()

    # Pre-generate all random numbers for both scenarios
    n_years = max_age - start_age
    condition_draws = {cond: rng.random(n_years) for cond in INCIDENCE_RATES.keys()}
    mortality_draws = rng.random(n_years)

    results = []
    for hr in [1.0, intervention_hr]:
        # Start with initial state if provided, otherwise healthy
        if initial_state is not None:
            state = HealthState(
                alive=True,
                diabetes=initial_state.diabetes,
                hypertension=initial_state.hypertension,
                heart_disease=initial_state.heart_disease,
                stroke=initial_state.stroke,
                cancer=initial_state.cancer,
                arthritis=initial_state.arthritis,
            )
        else:
            state = HealthState()
        qalys = 0.0
        life_years = 0.0
        conditions_acquired = {c: None for c in INCIDENCE_RATES.keys()}

        for year in range(n_years):
            if not state.alive:
                break

            age = start_age + year
            discount = 1 / (1 + discount_rate) ** year

            # Quality weight
            base_quality = get_quality_weight(age)
            quality = max(0.1, base_quality - state.get_quality_decrement())
            qalys += quality * discount
            life_years += 1

            # Check for new conditions (same draws for both scenarios)
            for cond in INCIDENCE_RATES.keys():
                if not getattr(state, cond):
                    incidence = get_incidence_rate(cond, age)
                    if condition_draws[cond][year] < incidence:
                        setattr(state, cond, True)
                        conditions_acquired[cond] = age

            # Check for death (same underlying draw, different threshold)
            base_mortality = get_mortality_rate(age, sex)
            mortality = base_mortality * state.get_mortality_multiplier() * hr
            mortality = min(mortality, 0.99)

            if mortality_draws[year] < mortality:
                state.alive = False

        results.append(MarkovResult(
            qalys=qalys,
            life_years=life_years,
            death_age=start_age + int(life_years),
            conditions_acquired=conditions_acquired,
        ))

    return results[0], results[1]


def simulate_markov_monte_carlo(
    start_age: int,
    sex: Literal["male", "female"],
    intervention_hr: float = 1.0,
    n_simulations: int = 10000,
    discount_rate: float = 0.03,
    random_state: Optional[int] = None,
    initial_state: Optional[HealthState] = None,
) -> Dict:
    """
    Run Monte Carlo simulation with Markov state transitions.

    Uses paired simulations with correlated outcomes for baseline vs intervention.
    Returns statistics on lifetime QALYs and QALY gains vs no intervention.

    Args:
        start_age: Starting age
        sex: Biological sex
        intervention_hr: Hazard ratio for intervention
        n_simulations: Number of Monte Carlo samples
        discount_rate: Annual discount rate
        random_state: Random seed for reproducibility
        initial_state: Known health conditions at start (reduces uncertainty)
    """
    rng = np.random.default_rng(random_state)

    baseline_qalys = []
    intervention_qalys = []
    baseline_life_years = []
    intervention_life_years = []

    for _ in range(n_simulations):
        # Paired simulation with same random draws
        result_base, result_int = simulate_lifetime_paired(
            start_age=start_age,
            sex=sex,
            intervention_hr=intervention_hr,
            discount_rate=discount_rate,
            rng=rng,
            initial_state=initial_state,
        )

        baseline_qalys.append(result_base.qalys)
        intervention_qalys.append(result_int.qalys)
        baseline_life_years.append(result_base.life_years)
        intervention_life_years.append(result_int.life_years)

    baseline_qalys = np.array(baseline_qalys)
    intervention_qalys = np.array(intervention_qalys)
    qaly_gains = intervention_qalys - baseline_qalys
    life_years_gained = np.array(intervention_life_years) - np.array(baseline_life_years)

    return {
        "baseline_qalys": {
            "mean": float(np.mean(baseline_qalys)),
            "std": float(np.std(baseline_qalys)),
            "median": float(np.median(baseline_qalys)),
            "ci95": (float(np.percentile(baseline_qalys, 2.5)), float(np.percentile(baseline_qalys, 97.5))),
        },
        "intervention_qalys": {
            "mean": float(np.mean(intervention_qalys)),
            "std": float(np.std(intervention_qalys)),
        },
        "qaly_gain": {
            "mean": float(np.mean(qaly_gains)),
            "std": float(np.std(qaly_gains)),
            "median": float(np.median(qaly_gains)),
            "ci95": (float(np.percentile(qaly_gains, 2.5)), float(np.percentile(qaly_gains, 97.5))),
            "prob_positive": float(np.mean(qaly_gains > 0)),
        },
        "life_years_gained": {
            "mean": float(np.mean(life_years_gained)),
            "std": float(np.std(life_years_gained)),
            "median": float(np.median(life_years_gained)),
        },
        "n_simulations": n_simulations,
    }


# Frailty distribution parameters (captures unobserved health heterogeneity)
# Log-normal distribution: mean=0, std=0.3 gives multiplier centered around 1
# This represents individual variation in "health reserve" not captured by conditions
FRAILTY_STD = 0.3

# Age-specific prevalence rates (MEPS 2019-2022)
# Probability someone at age X already has condition
PREVALENCE_RATES = {
    "diabetes": {
        30: 0.04,   # 4% at age 30
        45: 0.10,   # 10% at age 45
        55: 0.16,   # 16% at age 55
        65: 0.23,   # 23% at age 65
        75: 0.26,   # 26% at age 75
        85: 0.24,   # 24% at age 85
    },
    "hypertension": {
        30: 0.12,
        45: 0.30,
        55: 0.45,
        65: 0.58,
        75: 0.65,
        85: 0.70,
    },
    "heart_disease": {
        30: 0.02,
        45: 0.06,
        55: 0.11,
        65: 0.18,
        75: 0.28,
        85: 0.35,
    },
    "stroke": {
        30: 0.01,
        45: 0.02,
        55: 0.03,
        65: 0.06,
        75: 0.10,
        85: 0.14,
    },
    "cancer": {
        30: 0.03,
        45: 0.05,
        55: 0.09,
        65: 0.16,
        75: 0.24,
        85: 0.30,
    },
    "arthritis": {
        30: 0.08,
        45: 0.20,
        55: 0.32,
        65: 0.42,
        75: 0.50,
        85: 0.55,
    },
}


def get_prevalence(condition: str, age: int) -> float:
    """Get prevalence rate for a condition at given age."""
    rates = PREVALENCE_RATES.get(condition, {})
    if not rates:
        return 0.0

    ages = sorted(rates.keys())

    if age <= ages[0]:
        return rates[ages[0]]
    if age >= ages[-1]:
        return rates[ages[-1]]

    # Linear interpolation
    for i in range(len(ages) - 1):
        if ages[i] <= age < ages[i + 1]:
            frac = (age - ages[i]) / (ages[i + 1] - ages[i])
            return rates[ages[i]] + frac * (rates[ages[i + 1]] - rates[ages[i]])

    return rates[ages[-1]]


def simulate_with_state_uncertainty(
    start_age: int,
    sex: Literal["male", "female"],
    n_simulations: int = 10000,
    discount_rate: float = 0.03,
    random_state: Optional[int] = None,
    known_state: Optional[Dict[str, bool]] = None,
) -> Dict:
    """
    Simulate lifetime QALYs with proper state uncertainty.

    For CONDITIONS NOT SPECIFIED by user: sample from age-specific prevalence
    For CONDITIONS SPECIFIED by user: use the known value (True/False)

    This models what happens when user enters partial profile info:
    - Unknown conditions → sampled from population distribution → adds variance
    - Known conditions → fixed → removes that source of variance

    Args:
        start_age: Starting age
        sex: Biological sex
        n_simulations: Number of Monte Carlo samples
        discount_rate: Annual discount rate
        random_state: Random seed
        known_state: Dict of condition -> bool for KNOWN conditions
                    e.g. {"diabetes": False, "hypertension": True}
                    Conditions not in dict are sampled from prevalence

    Returns:
        Dict with distribution statistics showing how variance changes
    """
    rng = np.random.default_rng(random_state)

    all_conditions = list(INCIDENCE_RATES.keys())

    if known_state is None:
        known_state = {}

    unknown_conditions = [c for c in all_conditions if c not in known_state]

    # Frailty variance decreases as we know more conditions
    fraction_unknown = len(unknown_conditions) / len(all_conditions)
    effective_frailty_std = FRAILTY_STD * np.sqrt(fraction_unknown)

    qalys_list = []
    life_years_list = []

    for _ in range(n_simulations):
        # Draw individual frailty (mortality multiplier)
        frailty = np.exp(rng.normal(0, effective_frailty_std))

        # Set up initial health state
        state = HealthState()

        # For KNOWN conditions, use the known value
        for cond, has_it in known_state.items():
            setattr(state, cond, has_it)

        # For UNKNOWN conditions, sample from prevalence
        for cond in unknown_conditions:
            prevalence = get_prevalence(cond, start_age)
            if rng.random() < prevalence:
                setattr(state, cond, True)

        qalys = 0.0
        life_years = 0.0
        max_age = 100

        for year in range(max_age - start_age):
            if not state.alive:
                break

            age = start_age + year
            discount = 1 / (1 + discount_rate) ** year

            # Quality weight with condition decrements
            base_quality = get_quality_weight(age)
            quality = max(0.1, base_quality - state.get_quality_decrement())
            qalys += quality * discount
            life_years += 1

            # Check for new conditions (incidence for conditions not already present)
            for cond in all_conditions:
                if not getattr(state, cond):
                    incidence = get_incidence_rate(cond, age)
                    if rng.random() < incidence:
                        setattr(state, cond, True)

            # Check for death (apply frailty multiplier)
            base_mortality = get_mortality_rate(age, sex)
            mortality = base_mortality * state.get_mortality_multiplier() * frailty
            mortality = min(mortality, 0.99)

            if rng.random() < mortality:
                state.alive = False

        qalys_list.append(qalys)
        life_years_list.append(life_years)

    qalys_arr = np.array(qalys_list)
    life_years_arr = np.array(life_years_list)

    return {
        "qalys": {
            "mean": float(np.mean(qalys_arr)),
            "std": float(np.std(qalys_arr)),
            "median": float(np.median(qalys_arr)),
            "ci95": (float(np.percentile(qalys_arr, 2.5)), float(np.percentile(qalys_arr, 97.5))),
            "p10": float(np.percentile(qalys_arr, 10)),
            "p90": float(np.percentile(qalys_arr, 90)),
        },
        "life_years": {
            "mean": float(np.mean(life_years_arr)),
            "std": float(np.std(life_years_arr)),
            "median": float(np.median(life_years_arr)),
        },
        "n_simulations": n_simulations,
        "known_conditions": list(known_state.keys()),
        "unknown_conditions": unknown_conditions,
        "effective_frailty_std": effective_frailty_std,
    }


# Keep the old function for backward compatibility
def simulate_with_frailty(
    start_age: int,
    sex: Literal["male", "female"],
    n_simulations: int = 10000,
    discount_rate: float = 0.03,
    random_state: Optional[int] = None,
    initial_state: Optional[HealthState] = None,
    known_conditions: Optional[List[str]] = None,
) -> Dict:
    """Deprecated: use simulate_with_state_uncertainty instead."""
    # Convert old API to new API
    known_state = {}
    if initial_state is not None and known_conditions is not None:
        for cond in known_conditions:
            known_state[cond] = getattr(initial_state, cond, False)

    return simulate_with_state_uncertainty(
        start_age=start_age,
        sex=sex,
        n_simulations=n_simulations,
        discount_rate=discount_rate,
        random_state=random_state,
        known_state=known_state,
    )


def get_outcome_distribution(
    start_age: int,
    sex: Literal["male", "female"],
    known_state: Optional[Dict[str, bool]] = None,
    n_simulations: int = 5000,
    random_state: Optional[int] = None,
) -> Dict:
    """
    Get the distribution of lifetime QALYs for a user's profile.

    This is the main API for the web app. Returns:
    - Expected QALYs with confidence interval
    - The conditions that are known vs unknown
    - Interpretation of uncertainty

    Args:
        start_age: User's current age
        sex: User's sex
        known_state: Dict of condition -> bool for conditions user has entered
                    e.g. {"diabetes": False, "hypertension": True}
        n_simulations: Number of Monte Carlo samples
        random_state: Random seed for reproducibility

    Returns:
        Dict with distribution, known/unknown breakdown, interpretation
    """
    result = simulate_with_state_uncertainty(
        start_age=start_age,
        sex=sex,
        n_simulations=n_simulations,
        random_state=random_state,
        known_state=known_state,
    )

    # Add interpretation
    n_known = len(result["known_conditions"])
    n_unknown = len(result["unknown_conditions"])
    n_total = n_known + n_unknown

    if n_known == 0:
        certainty_level = "low"
        interpretation = (
            "Based on your age and sex only. Enter your health conditions "
            "for a more personalized estimate."
        )
    elif n_known < n_total / 2:
        certainty_level = "moderate"
        interpretation = (
            f"Based on {n_known} known conditions. Enter more health "
            "information for higher certainty."
        )
    else:
        certainty_level = "high"
        interpretation = (
            f"Personalized estimate based on {n_known} known conditions."
        )

    return {
        "expected_qalys": result["qalys"]["mean"],
        "qaly_std": result["qalys"]["std"],
        "qaly_ci95": result["qalys"]["ci95"],
        "qaly_p10_p90": (result["qalys"]["p10"], result["qalys"]["p90"]),
        "expected_life_years": result["life_years"]["mean"],
        "known_conditions": result["known_conditions"],
        "unknown_conditions": result["unknown_conditions"],
        "certainty_level": certainty_level,
        "interpretation": interpretation,
        "n_simulations": n_simulations,
    }


def demonstrate_uncertainty_reduction():
    """
    Show how uncertainty in lifetime QALYs shrinks as user enters more inputs.
    """
    print("Uncertainty Reduction with Profile Inputs")
    print("=" * 60)
    print("\nKey insight: Unknown conditions are SAMPLED from prevalence,")
    print("which adds variance. Known conditions are FIXED, removing variance.")

    # Base case: 50-year-old male, nothing known
    print("\n50-year-old male:")

    # Level 1: Only age/sex known (all conditions sampled from prevalence)
    result1 = simulate_with_state_uncertainty(
        start_age=50, sex="male", n_simulations=5000, random_state=42,
        known_state={},  # Nothing known - sample all from prevalence
    )
    print(f"\n1. Only age/sex known (conditions sampled from prevalence):")
    print(f"   Expected QALYs: {result1['qalys']['mean']:.1f}")
    print(f"   Std dev: {result1['qalys']['std']:.2f}")
    print(f"   90% range: [{result1['qalys']['p10']:.1f}, {result1['qalys']['p90']:.1f}]")

    # Level 2: Know diabetes and hypertension status
    result2 = simulate_with_state_uncertainty(
        start_age=50, sex="male", n_simulations=5000, random_state=42,
        known_state={"diabetes": False, "hypertension": False},
    )
    print(f"\n2. Know: no diabetes, no hypertension (others sampled):")
    print(f"   Expected QALYs: {result2['qalys']['mean']:.1f}")
    print(f"   Std dev: {result2['qalys']['std']:.2f} (was {result1['qalys']['std']:.2f})")
    print(f"   90% range: [{result2['qalys']['p10']:.1f}, {result2['qalys']['p90']:.1f}]")

    # Level 3: Know 4 major conditions
    result3 = simulate_with_state_uncertainty(
        start_age=50, sex="male", n_simulations=5000, random_state=42,
        known_state={
            "diabetes": False,
            "hypertension": False,
            "heart_disease": False,
            "stroke": False,
        },
    )
    print(f"\n3. Know: no diabetes/hypertension/heart_disease/stroke:")
    print(f"   Expected QALYs: {result3['qalys']['mean']:.1f}")
    print(f"   Std dev: {result3['qalys']['std']:.2f} (was {result1['qalys']['std']:.2f})")
    print(f"   90% range: [{result3['qalys']['p10']:.1f}, {result3['qalys']['p90']:.1f}]")

    # Level 4: Know all conditions (all absent)
    result4 = simulate_with_state_uncertainty(
        start_age=50, sex="male", n_simulations=5000, random_state=42,
        known_state={
            "diabetes": False,
            "hypertension": False,
            "heart_disease": False,
            "stroke": False,
            "cancer": False,
            "arthritis": False,
        },
    )
    print(f"\n4. All conditions known (all absent - healthy person):")
    print(f"   Expected QALYs: {result4['qalys']['mean']:.1f}")
    print(f"   Std dev: {result4['qalys']['std']:.2f} (was {result1['qalys']['std']:.2f})")
    print(f"   90% range: [{result4['qalys']['p10']:.1f}, {result4['qalys']['p90']:.1f}]")

    # Level 5: Someone WITH conditions (all known, some present)
    result5 = simulate_with_state_uncertainty(
        start_age=50, sex="male", n_simulations=5000, random_state=42,
        known_state={
            "diabetes": True,
            "hypertension": True,
            "heart_disease": False,
            "stroke": False,
            "cancer": False,
            "arthritis": False,
        },
    )
    print(f"\n5. All known: HAS diabetes + hypertension (unhealthy person):")
    print(f"   Expected QALYs: {result5['qalys']['mean']:.1f}")
    print(f"   Std dev: {result5['qalys']['std']:.2f}")
    print(f"   90% range: [{result5['qalys']['p10']:.1f}, {result5['qalys']['p90']:.1f}]")

    # Variance reduction summary
    print(f"\n" + "=" * 60)
    print("Summary: Variance reduction as inputs are added")
    print(f"  Level 1 (age/sex only):      std = {result1['qalys']['std']:.2f}")
    print(f"  Level 2 (+2 conditions):     std = {result2['qalys']['std']:.2f} ({100*(result2['qalys']['std']-result1['qalys']['std'])/result1['qalys']['std']:+.0f}%)")
    print(f"  Level 3 (+4 conditions):     std = {result3['qalys']['std']:.2f} ({100*(result3['qalys']['std']-result1['qalys']['std'])/result1['qalys']['std']:+.0f}%)")
    print(f"  Level 4 (all 6 conditions):  std = {result4['qalys']['std']:.2f} ({100*(result4['qalys']['std']-result1['qalys']['std'])/result1['qalys']['std']:+.0f}%)")

    print(f"\nNote: Remaining variance comes from:")
    print(f"  - Future condition incidence (will they develop cancer?)")
    print(f"  - Stochastic mortality (when will they die?)")
    print(f"  - Residual frailty (unobserved health factors)")


if __name__ == "__main__":
    # Test the Markov model
    print("Markov State-Transition Model Test")
    print("=" * 50)

    # Compare with deterministic model
    from .lifecycle import LifecycleModel, PathwayHRs

    # Deterministic baseline
    det_model = LifecycleModel(start_age=40, sex="male", discount_rate=0.03)
    det_result = det_model.calculate(PathwayHRs(cvd=1.0, cancer=1.0, other=1.0))

    print(f"\nDeterministic model (40yo male):")
    print(f"  Baseline QALYs: {det_result.baseline_qalys:.2f}")

    # Markov Monte Carlo
    markov_result = simulate_markov_monte_carlo(
        start_age=40,
        sex="male",
        intervention_hr=1.0,
        n_simulations=5000,
        random_state=42,
    )

    print(f"\nMarkov model (40yo male, n=5000):")
    print(f"  Baseline QALYs: {markov_result['baseline_qalys']['mean']:.2f} ± {markov_result['baseline_qalys']['std']:.2f}")
    print(f"  95% CI: [{markov_result['baseline_qalys']['ci95'][0]:.1f}, {markov_result['baseline_qalys']['ci95'][1]:.1f}]")

    # With intervention (HR = 0.85)
    markov_int = simulate_markov_monte_carlo(
        start_age=40,
        sex="male",
        intervention_hr=0.85,
        n_simulations=5000,
        random_state=42,
    )

    print(f"\nWith intervention (HR=0.85):")
    print(f"  QALY gain: {markov_int['qaly_gain']['mean']:.2f} ± {markov_int['qaly_gain']['std']:.2f}")
    print(f"  95% CI: [{markov_int['qaly_gain']['ci95'][0]:.2f}, {markov_int['qaly_gain']['ci95'][1]:.2f}]")
    print(f"  P(gain > 0): {markov_int['qaly_gain']['prob_positive']:.1%}")
