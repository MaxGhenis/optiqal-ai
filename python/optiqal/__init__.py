"""
OptiqAL - Bayesian QALY Estimation for Lifestyle Interventions

This package provides rigorous, evidence-based QALY calculations with:
- Bayesian MCMC inference using PyMC
- CDC life tables for survival modeling
- Pathway decomposition (CVD, cancer, other)
- Confounding adjustment with calibrated priors
- Full uncertainty quantification

Usage:
    from optiqal import Intervention, LifecycleModel, run_mcmc

    # Load intervention from YAML
    walking = Intervention.from_yaml("walking_30min_daily.yaml")

    # Quick Monte Carlo estimate
    result = walking.simulate(age=40, sex="male")
    print(f"QALY gain: {result.median:.2f} (95% CI: {result.ci95})")

    # Full Bayesian MCMC
    trace = run_mcmc(walking, n_samples=2000, chains=4)
    print(f"Posterior mean: {trace.posterior['qaly_gain'].mean():.3f}")
"""

__version__ = "0.1.0"

from .intervention import Intervention
from .lifecycle import LifecycleModel, CDC_LIFE_TABLE, CAUSE_FRACTIONS
from .confounding import ConfoundingPrior, CATEGORY_PRIORS
from .simulate import simulate_qaly, SimulationResult

__all__ = [
    "Intervention",
    "LifecycleModel",
    "CDC_LIFE_TABLE",
    "CAUSE_FRACTIONS",
    "ConfoundingPrior",
    "CATEGORY_PRIORS",
    "simulate_qaly",
    "SimulationResult",
]


# Lazy import for Bayesian module (requires optional dependencies)
def run_mcmc(*args, **kwargs):
    """Run MCMC inference. Requires optiqal[bayesian] installation."""
    from .bayesian import run_mcmc as _run_mcmc

    return _run_mcmc(*args, **kwargs)
