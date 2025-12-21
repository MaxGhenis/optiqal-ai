"""
Monte Carlo Simulation Module

Fast QALY estimation without full MCMC.
"""

from dataclasses import dataclass
from typing import Literal, Optional
import numpy as np

from .intervention import Intervention
from .lifecycle import LifecycleModel, PathwayHRs
from .confounding import adjust_hr


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
