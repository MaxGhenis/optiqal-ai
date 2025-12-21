"""
Bayesian MCMC Module

Full posterior inference using PyMC.
Requires: pip install optiqal[bayesian]
"""

from typing import List, Literal, Optional
import numpy as np

try:
    import pymc as pm
    import arviz as az

    HAS_PYMC = True
except ImportError:
    HAS_PYMC = False
    pm = None
    az = None

from .intervention import Intervention
from .lifecycle import LifecycleModel, PathwayHRs, get_quality_weight
from .confounding import CATEGORY_PRIORS


def check_pymc():
    """Check if PyMC is installed."""
    if not HAS_PYMC:
        raise ImportError(
            "PyMC is required for Bayesian inference. "
            "Install with: pip install optiqal[bayesian]"
        )


def run_mcmc(
    intervention: Intervention,
    age: int = 40,
    sex: Literal["male", "female"] = "male",
    n_samples: int = 2000,
    chains: int = 4,
    target_accept: float = 0.95,
    random_seed: Optional[int] = 42,
    return_inferencedata: bool = True,
):
    """
    Run full Bayesian MCMC inference.

    This provides proper posterior distributions for QALY estimates
    with hierarchical shrinkage and full uncertainty propagation.

    Args:
        intervention: Intervention to analyze
        age: Starting age
        sex: Biological sex
        n_samples: Number of posterior samples per chain
        chains: Number of MCMC chains
        target_accept: NUTS target acceptance rate
        random_seed: Random seed for reproducibility
        return_inferencedata: Return ArviZ InferenceData object

    Returns:
        ArviZ InferenceData or PyMC trace
    """
    check_pymc()

    if intervention.mortality is None:
        raise ValueError("Intervention must have mortality effect for MCMC")

    # Get confounding prior
    prior = intervention.confounding_prior or CATEGORY_PRIORS.get(
        intervention.category, CATEGORY_PRIORS["other"]
    )

    # Get HR distribution parameters
    hr_dist = intervention.mortality.hazard_ratio
    if hr_dist.type == "lognormal":
        hr_log_mean = hr_dist.params["log_mean"]
        hr_log_sd = hr_dist.params["log_sd"]
    else:
        # Convert to lognormal approximation
        hr_mean = hr_dist.mean
        hr_log_mean = np.log(hr_mean)
        hr_log_sd = 0.1  # Default uncertainty

    # Build PyMC model
    with pm.Model() as model:
        # Confounding prior: what fraction of observed effect is causal?
        causal_fraction = pm.Beta(
            "causal_fraction",
            alpha=prior.alpha,
            beta=prior.beta,
        )

        # Observed hazard ratio (from meta-analysis)
        observed_log_hr = pm.Normal(
            "observed_log_hr",
            mu=hr_log_mean,
            sigma=hr_log_sd,
        )

        # Causal hazard ratio (after confounding adjustment)
        causal_log_hr = pm.Deterministic(
            "causal_log_hr",
            causal_fraction * observed_log_hr,
        )

        causal_hr = pm.Deterministic("causal_hr", pm.math.exp(causal_log_hr))

        # Pathway-specific HRs
        # CVD gets stronger effect, cancer/other get weaker
        cvd_log_hr = pm.Deterministic("cvd_log_hr", causal_log_hr * 1.3)
        cancer_log_hr = pm.Deterministic("cancer_log_hr", causal_log_hr * 0.8)
        other_log_hr = pm.Deterministic("other_log_hr", causal_log_hr * 0.6)

        cvd_hr = pm.Deterministic("cvd_hr", pm.math.exp(cvd_log_hr))
        cancer_hr = pm.Deterministic("cancer_hr", pm.math.exp(cancer_log_hr))
        other_hr = pm.Deterministic("other_hr", pm.math.exp(other_log_hr))

        # Run MCMC
        trace = pm.sample(
            n_samples,
            chains=chains,
            target_accept=target_accept,
            random_seed=random_seed,
            return_inferencedata=return_inferencedata,
        )

    # Post-process: calculate QALY gains for each posterior sample
    if return_inferencedata:
        trace = _add_qaly_calculations(trace, age, sex)

    return trace


def _add_qaly_calculations(
    trace,
    age: int,
    sex: Literal["male", "female"],
    discount_rate: float = 0.03,
):
    """Add QALY gain calculations to posterior samples."""
    # Extract posterior samples
    cvd_hrs = trace.posterior["cvd_hr"].values.flatten()
    cancer_hrs = trace.posterior["cancer_hr"].values.flatten()
    other_hrs = trace.posterior["other_hr"].values.flatten()

    n_samples = len(cvd_hrs)
    qaly_gains = np.zeros(n_samples)
    life_years = np.zeros(n_samples)

    lifecycle = LifecycleModel(
        start_age=age,
        sex=sex,
        discount_rate=discount_rate,
    )

    for i in range(n_samples):
        pathway_hrs = PathwayHRs(
            cvd=cvd_hrs[i],
            cancer=cancer_hrs[i],
            other=other_hrs[i],
        )
        result = lifecycle.calculate(pathway_hrs)
        qaly_gains[i] = result.qaly_gain
        life_years[i] = result.life_years_gained

    # Add to trace as derived quantities
    import xarray as xr

    n_chains = trace.posterior.dims["chain"]
    n_draws = trace.posterior.dims["draw"]

    qaly_da = xr.DataArray(
        qaly_gains.reshape(n_chains, n_draws),
        dims=["chain", "draw"],
        name="qaly_gain",
    )
    life_years_da = xr.DataArray(
        life_years.reshape(n_chains, n_draws),
        dims=["chain", "draw"],
        name="life_years_gained",
    )

    trace.posterior["qaly_gain"] = qaly_da
    trace.posterior["life_years_gained"] = life_years_da

    return trace


def summarize_posterior(trace, var_names: Optional[List[str]] = None):
    """
    Summarize posterior distributions.

    Args:
        trace: ArviZ InferenceData object
        var_names: Variables to summarize (default: key variables)

    Returns:
        pandas DataFrame with posterior summary
    """
    check_pymc()

    if var_names is None:
        var_names = [
            "causal_fraction",
            "causal_hr",
            "cvd_hr",
            "cancer_hr",
            "other_hr",
            "qaly_gain",
            "life_years_gained",
        ]

    return az.summary(trace, var_names=var_names, hdi_prob=0.95)


def plot_posterior(trace, var_names: Optional[List[str]] = None, **kwargs):
    """
    Plot posterior distributions.

    Args:
        trace: ArviZ InferenceData object
        var_names: Variables to plot
        **kwargs: Additional arguments to az.plot_posterior

    Returns:
        matplotlib axes
    """
    check_pymc()

    if var_names is None:
        var_names = ["causal_fraction", "causal_hr", "qaly_gain"]

    return az.plot_posterior(trace, var_names=var_names, **kwargs)


def plot_trace(trace, var_names: Optional[List[str]] = None, **kwargs):
    """
    Plot MCMC trace for diagnostics.

    Args:
        trace: ArviZ InferenceData object
        var_names: Variables to plot
        **kwargs: Additional arguments to az.plot_trace

    Returns:
        matplotlib axes
    """
    check_pymc()

    if var_names is None:
        var_names = ["causal_fraction", "observed_log_hr", "qaly_gain"]

    return az.plot_trace(trace, var_names=var_names, **kwargs)
