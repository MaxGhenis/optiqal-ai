"""
Monte Carlo Simulation Module

Fast QALY estimation without full MCMC.
"""

from dataclasses import dataclass
from typing import Literal, Optional, Union
import numpy as np

from .intervention import Intervention
from .lifecycle import LifecycleModel, PathwayHRs, get_mortality_rate, get_quality_weight, get_cause_fraction, QUALITY_WEIGHT_STD
from .confounding import adjust_hr
from .profile import Profile, get_baseline_mortality_multiplier, get_intervention_modifier


@dataclass
class SimulationResult:
    """Result of Monte Carlo QALY simulation."""

    median: float
    mean: float
    std: float
    ci95: tuple  # (low, high)
    ci50: tuple  # (low, high)
    prob_positive: float
    prob_more_than_one_year: float

    # Pathway contributions
    cvd_contribution: float
    cancer_contribution: float
    other_contribution: float

    # Life years
    life_years_gained: float

    # Confounding
    causal_fraction_mean: Optional[float] = None
    causal_fraction_ci: Optional[tuple] = None

    # Settings
    n_simulations: int = 10000
    discount_rate: float = 0.03


def simulate_qaly_profile_vectorized(
    intervention: Intervention,
    profile: Profile,
    n_simulations: int = 10000,
    discount_rate: float = 0.03,
    apply_confounding: bool = True,
    random_state: Optional[int] = None,
) -> SimulationResult:
    """
    Vectorized Monte Carlo simulation - ~100x faster than loop version.

    Uses NumPy broadcasting to process all simulations at once.
    """
    rng = np.random.default_rng(random_state)

    if intervention.mortality is None:
        return SimulationResult(
            median=0, mean=0, std=0, ci95=(0, 0), ci50=(0, 0),
            prob_positive=0.5, prob_more_than_one_year=0,
            cvd_contribution=0, cancer_contribution=0, other_contribution=0,
            life_years_gained=0, n_simulations=n_simulations, discount_rate=discount_rate,
        )

    # Profile adjustments
    baseline_mortality_multiplier = get_baseline_mortality_multiplier(profile)
    intervention_effect_modifier = get_intervention_modifier(profile, intervention.category)

    # Pre-compute year arrays (static for all simulations)
    max_age = 100
    n_years = max_age - profile.age
    years = np.arange(n_years)
    ages = profile.age + years

    # Base mortality rates, quality weights, discounts, cause fractions
    base_qx = np.array([get_mortality_rate(int(a), profile.sex) for a in ages])
    base_qx = np.minimum(base_qx * baseline_mortality_multiplier, 0.99)
    base_quality = np.array([get_quality_weight(int(a)) for a in ages])
    discount = (1 / (1 + discount_rate)) ** years

    # Cause fractions (n_years, 3)
    cause_fracs = np.array([[get_cause_fraction(int(a))[k] for k in ['cvd', 'cancer', 'other']] for a in ages])

    # Sample quality weight offsets (MEPS calibration: within-age σ=0.117)
    # Each simulation gets a person-specific offset that persists across years
    quality_offsets = rng.normal(0, QUALITY_WEIGHT_STD, n_simulations)  # (n_simulations,)
    # Quality weights vary by simulation: (n_simulations, n_years)
    quality = np.clip(base_quality[None, :] + quality_offsets[:, None], 0.1, 1.0)

    # Sample HRs and causal fractions (n_simulations,)
    hr_samples = intervention.mortality.hazard_ratio.sample(n_simulations, random_state)

    if intervention_effect_modifier != 1.0:
        hr_samples = np.exp(np.log(hr_samples) * intervention_effect_modifier)

    if apply_confounding and intervention.confounding_prior is not None:
        causal_samples = intervention.confounding_prior.sample(n_simulations, random_state)
        causal_fraction_mean = intervention.confounding_prior.mean
        causal_fraction_ci = intervention.confounding_prior.ci(0.95)
    else:
        causal_samples = np.ones(n_simulations)
        causal_fraction_mean = None
        causal_fraction_ci = None

    # Adjust HRs for confounding: log(adjusted_hr) = causal_fraction * log(observed_hr)
    adjusted_hrs = np.exp(causal_samples * np.log(hr_samples))  # (n_simulations,)

    # Pathway HRs: CVD gets 1.3x, cancer 0.8x, other 0.6x on log scale
    log_hr = np.log(adjusted_hrs)  # (n_simulations,)
    pathway_hrs = np.stack([
        np.exp(log_hr * 1.3),  # CVD
        np.exp(log_hr * 0.8),  # Cancer
        np.exp(log_hr * 0.6),  # Other
    ], axis=1)  # (n_simulations, 3)

    # Intervention mortality: base_qx * weighted sum of pathway HRs
    # intervention_qx[s, y] = base_qx[y] * sum_k(cause_fracs[y, k] * pathway_hrs[s, k])
    # Shape: (n_simulations, n_years)
    intervention_qx = base_qx[None, :] * np.einsum('yk,sk->sy', cause_fracs, pathway_hrs)
    intervention_qx = np.minimum(intervention_qx, 0.99)

    # Baseline survival (deterministic, same for all simulations)
    baseline_survival = np.cumprod(1 - base_qx)
    baseline_survival = np.concatenate([[1.0], baseline_survival[:-1]])  # Shift for start-of-year
    baseline_life_years = np.sum(baseline_survival)

    # Baseline QALYs now vary by simulation due to quality weight heterogeneity
    # baseline_qalys_per_year: (n_simulations, n_years)
    baseline_qalys_per_year = baseline_survival[None, :] * quality * discount[None, :]
    baseline_qalys_total = np.sum(baseline_qalys_per_year, axis=1)  # (n_simulations,)

    # Intervention survival curves (n_simulations, n_years)
    intervention_survival = np.cumprod(1 - intervention_qx, axis=1)
    intervention_survival = np.concatenate([
        np.ones((n_simulations, 1)),
        intervention_survival[:, :-1]
    ], axis=1)

    # Intervention QALYs (n_simulations,) - quality is already (n_simulations, n_years)
    intervention_qalys_per_year = intervention_survival * quality * discount[None, :]
    intervention_qalys_total = np.sum(intervention_qalys_per_year, axis=1)
    intervention_life_years = np.sum(intervention_survival, axis=1)

    # QALY gains
    qaly_gains = intervention_qalys_total - baseline_qalys_total
    life_years_gained = intervention_life_years - baseline_life_years

    # Pathway contributions (approximate - using median HR)
    median_hr = np.median(adjusted_hrs)
    log_median = np.log(median_hr)
    cvd_contrib = (1 - np.exp(log_median * 1.3)) * np.mean(cause_fracs[:, 0])
    cancer_contrib = (1 - np.exp(log_median * 0.8)) * np.mean(cause_fracs[:, 1])
    other_contrib = (1 - np.exp(log_median * 0.6)) * np.mean(cause_fracs[:, 2])
    total_contrib = cvd_contrib + cancer_contrib + other_contrib
    if total_contrib > 0:
        cvd_contrib /= total_contrib
        cancer_contrib /= total_contrib
        other_contrib /= total_contrib

    return SimulationResult(
        median=float(np.median(qaly_gains)),
        mean=float(np.mean(qaly_gains)),
        std=float(np.std(qaly_gains)),
        ci95=(float(np.percentile(qaly_gains, 2.5)), float(np.percentile(qaly_gains, 97.5))),
        ci50=(float(np.percentile(qaly_gains, 25)), float(np.percentile(qaly_gains, 75))),
        prob_positive=float(np.mean(qaly_gains > 0)),
        prob_more_than_one_year=float(np.mean(qaly_gains > 1)),
        cvd_contribution=float(cvd_contrib),
        cancer_contribution=float(cancer_contrib),
        other_contribution=float(other_contrib),
        life_years_gained=float(np.median(life_years_gained)),
        causal_fraction_mean=causal_fraction_mean,
        causal_fraction_ci=causal_fraction_ci,
        n_simulations=n_simulations,
        discount_rate=discount_rate,
    )


def simulate_qaly(
    intervention: Intervention,
    age: int,
    sex: Literal["male", "female"],
    n_simulations: int = 10000,
    discount_rate: float = 0.03,
    apply_confounding: bool = True,
    random_state: Optional[int] = None,
) -> SimulationResult:
    """
    Run Monte Carlo simulation to estimate QALY impact.

    Args:
        intervention: Intervention to simulate
        age: Starting age
        sex: Biological sex for life table lookup
        n_simulations: Number of Monte Carlo iterations
        discount_rate: Annual discount rate (default 3%)
        apply_confounding: Whether to apply confounding adjustment
        random_state: Random seed for reproducibility

    Returns:
        SimulationResult with QALY estimates and uncertainty
    """
    rng = np.random.default_rng(random_state)

    if intervention.mortality is None:
        # No mortality effect, return zeros
        return SimulationResult(
            median=0,
            mean=0,
            std=0,
            ci95=(0, 0),
            ci50=(0, 0),
            prob_positive=0.5,
            prob_more_than_one_year=0,
            cvd_contribution=0,
            cancer_contribution=0,
            other_contribution=0,
            life_years_gained=0,
            n_simulations=n_simulations,
            discount_rate=discount_rate,
        )

    # Sample from distributions
    hr_samples = intervention.mortality.hazard_ratio.sample(n_simulations, random_state)

    # Sample causal fractions if applying confounding
    if apply_confounding and intervention.confounding_prior is not None:
        causal_samples = intervention.confounding_prior.sample(n_simulations, random_state)
        causal_fraction_mean = intervention.confounding_prior.mean
        causal_fraction_ci = intervention.confounding_prior.ci(0.95)
    else:
        causal_samples = np.ones(n_simulations)
        causal_fraction_mean = None
        causal_fraction_ci = None

    # Run lifecycle calculations
    qaly_gains = np.zeros(n_simulations)
    life_years = np.zeros(n_simulations)
    cvd_contributions = np.zeros(n_simulations)
    cancer_contributions = np.zeros(n_simulations)
    other_contributions = np.zeros(n_simulations)

    lifecycle = LifecycleModel(
        start_age=age,
        sex=sex,
        discount_rate=discount_rate,
    )

    # Base HR for pathway distribution
    base_hr = intervention.mortality.hazard_ratio.mean

    for i in range(n_simulations):
        # Sample HR and causal fraction
        sampled_hr = hr_samples[i]
        causal_fraction = causal_samples[i]

        # Adjust HR for confounding
        adjusted_hr = adjust_hr(sampled_hr, causal_fraction)

        # Convert to pathway HRs
        log_hr = np.log(adjusted_hr)
        pathway_hrs = PathwayHRs(
            cvd=np.exp(log_hr * 1.3),  # CVD gets stronger effect
            cancer=np.exp(log_hr * 0.8),
            other=np.exp(log_hr * 0.6),
        )

        # Run lifecycle calculation
        result = lifecycle.calculate(pathway_hrs)

        qaly_gains[i] = result.qaly_gain
        life_years[i] = result.life_years_gained
        cvd_contributions[i] = result.pathway_contributions["cvd"]
        cancer_contributions[i] = result.pathway_contributions["cancer"]
        other_contributions[i] = result.pathway_contributions["other"]

    # Calculate statistics
    return SimulationResult(
        median=float(np.median(qaly_gains)),
        mean=float(np.mean(qaly_gains)),
        std=float(np.std(qaly_gains)),
        ci95=(float(np.percentile(qaly_gains, 2.5)), float(np.percentile(qaly_gains, 97.5))),
        ci50=(float(np.percentile(qaly_gains, 25)), float(np.percentile(qaly_gains, 75))),
        prob_positive=float(np.mean(qaly_gains > 0)),
        prob_more_than_one_year=float(np.mean(qaly_gains > 1)),
        cvd_contribution=float(np.median(cvd_contributions)),
        cancer_contribution=float(np.median(cancer_contributions)),
        other_contribution=float(np.median(other_contributions)),
        life_years_gained=float(np.median(life_years)),
        causal_fraction_mean=causal_fraction_mean,
        causal_fraction_ci=causal_fraction_ci,
        n_simulations=n_simulations,
        discount_rate=discount_rate,
    )


def simulate_qaly_profile(
    intervention: Intervention,
    profile: Profile,
    n_simulations: int = 10000,
    discount_rate: float = 0.03,
    apply_confounding: bool = True,
    random_state: Optional[int] = None,
) -> SimulationResult:
    """
    Run Monte Carlo simulation for a specific demographic profile.

    This extends simulate_qaly to incorporate profile-specific adjustments:
    1. Baseline mortality adjusted for BMI, smoking, diabetes
    2. Intervention effect modified based on profile characteristics

    Args:
        intervention: Intervention to simulate
        profile: Demographic profile (age, sex, BMI, smoking, diabetes)
        n_simulations: Number of Monte Carlo iterations
        discount_rate: Annual discount rate (default 3%)
        apply_confounding: Whether to apply confounding adjustment
        random_state: Random seed for reproducibility

    Returns:
        SimulationResult with QALY estimates and uncertainty
    """
    rng = np.random.default_rng(random_state)

    if intervention.mortality is None:
        return SimulationResult(
            median=0,
            mean=0,
            std=0,
            ci95=(0, 0),
            ci50=(0, 0),
            prob_positive=0.5,
            prob_more_than_one_year=0,
            cvd_contribution=0,
            cancer_contribution=0,
            other_contribution=0,
            life_years_gained=0,
            n_simulations=n_simulations,
            discount_rate=discount_rate,
        )

    # Get profile-specific adjustments
    baseline_mortality_multiplier = get_baseline_mortality_multiplier(profile)
    intervention_effect_modifier = get_intervention_modifier(profile, intervention.category)

    # Sample from distributions
    hr_samples = intervention.mortality.hazard_ratio.sample(n_simulations, random_state)

    # Apply intervention effect modifier
    # If modifier > 1, intervention is more effective (HR moves further from 1)
    # log(adjusted_hr) = log(hr) * modifier (for HR < 1)
    if intervention_effect_modifier != 1.0:
        log_hr = np.log(hr_samples)
        hr_samples = np.exp(log_hr * intervention_effect_modifier)

    # Sample causal fractions if applying confounding
    if apply_confounding and intervention.confounding_prior is not None:
        causal_samples = intervention.confounding_prior.sample(n_simulations, random_state)
        causal_fraction_mean = intervention.confounding_prior.mean
        causal_fraction_ci = intervention.confounding_prior.ci(0.95)
    else:
        causal_samples = np.ones(n_simulations)
        causal_fraction_mean = None
        causal_fraction_ci = None

    # Run lifecycle calculations
    qaly_gains = np.zeros(n_simulations)
    life_years = np.zeros(n_simulations)
    cvd_contributions = np.zeros(n_simulations)
    cancer_contributions = np.zeros(n_simulations)
    other_contributions = np.zeros(n_simulations)

    lifecycle = LifecycleModel(
        start_age=profile.age,
        sex=profile.sex,
        discount_rate=discount_rate,
        baseline_mortality_multiplier=baseline_mortality_multiplier,
    )

    for i in range(n_simulations):
        sampled_hr = hr_samples[i]
        causal_fraction = causal_samples[i]

        # Adjust HR for confounding
        adjusted_hr = adjust_hr(sampled_hr, causal_fraction)

        # Convert to pathway HRs
        log_hr = np.log(adjusted_hr)
        pathway_hrs = PathwayHRs(
            cvd=np.exp(log_hr * 1.3),
            cancer=np.exp(log_hr * 0.8),
            other=np.exp(log_hr * 0.6),
        )

        result = lifecycle.calculate(pathway_hrs)

        qaly_gains[i] = result.qaly_gain
        life_years[i] = result.life_years_gained
        cvd_contributions[i] = result.pathway_contributions["cvd"]
        cancer_contributions[i] = result.pathway_contributions["cancer"]
        other_contributions[i] = result.pathway_contributions["other"]

    return SimulationResult(
        median=float(np.median(qaly_gains)),
        mean=float(np.mean(qaly_gains)),
        std=float(np.std(qaly_gains)),
        ci95=(float(np.percentile(qaly_gains, 2.5)), float(np.percentile(qaly_gains, 97.5))),
        ci50=(float(np.percentile(qaly_gains, 25)), float(np.percentile(qaly_gains, 75))),
        prob_positive=float(np.mean(qaly_gains > 0)),
        prob_more_than_one_year=float(np.mean(qaly_gains > 1)),
        cvd_contribution=float(np.median(cvd_contributions)),
        cancer_contribution=float(np.median(cancer_contributions)),
        other_contribution=float(np.median(other_contributions)),
        life_years_gained=float(np.median(life_years)),
        causal_fraction_mean=causal_fraction_mean,
        causal_fraction_ci=causal_fraction_ci,
        n_simulations=n_simulations,
        discount_rate=discount_rate,
    )
