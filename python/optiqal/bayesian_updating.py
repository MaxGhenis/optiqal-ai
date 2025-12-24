"""
Bayesian Posterior Updating Module

Updates imputation distributions as users provide personal observations.

P(state | observation) ∝ P(observation | state) × P(state)

This sharpens QALY estimates by reducing uncertainty about the
individual's true baseline.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple
import numpy as np
from scipy import stats


@dataclass
class ImputationPrior:
    """
    Prior distribution for an imputed variable.

    Based on population statistics from NHANES/UK Biobank,
    conditional on demographics.
    """
    variable: str
    mean: float
    std: float
    distribution: Literal["normal", "lognormal", "truncated_normal"] = "normal"
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None

    def sample(self, n: int = 1, rng: Optional[np.random.Generator] = None) -> np.ndarray:
        """Sample from the prior."""
        if rng is None:
            rng = np.random.default_rng()

        if self.distribution == "normal":
            samples = rng.normal(self.mean, self.std, size=n)
        elif self.distribution == "lognormal":
            log_mean = np.log(self.mean) - 0.5 * np.log(1 + (self.std/self.mean)**2)
            log_std = np.sqrt(np.log(1 + (self.std/self.mean)**2))
            samples = rng.lognormal(log_mean, log_std, size=n)
        elif self.distribution == "truncated_normal":
            samples = rng.normal(self.mean, self.std, size=n)
            if self.lower_bound is not None:
                samples = np.maximum(samples, self.lower_bound)
            if self.upper_bound is not None:
                samples = np.minimum(samples, self.upper_bound)

        return samples

    def pdf(self, x: float) -> float:
        """Evaluate prior density at x."""
        if self.distribution == "normal":
            return stats.norm.pdf(x, self.mean, self.std)
        elif self.distribution == "lognormal":
            log_mean = np.log(self.mean) - 0.5 * np.log(1 + (self.std/self.mean)**2)
            log_std = np.sqrt(np.log(1 + (self.std/self.mean)**2))
            return stats.lognorm.pdf(x, s=log_std, scale=np.exp(log_mean))
        elif self.distribution == "truncated_normal":
            if self.lower_bound is not None and x < self.lower_bound:
                return 0.0
            if self.upper_bound is not None and x > self.upper_bound:
                return 0.0
            return stats.norm.pdf(x, self.mean, self.std)


@dataclass
class Observation:
    """
    User-provided observation about their state.

    Can be exact (e.g., "I exercise 100 min/week") or
    categorical (e.g., "I exercise regularly").
    """
    variable: str
    value: Optional[float] = None  # Exact value if known
    category: Optional[str] = None  # Categorical response
    measurement_error: float = 0.0  # Standard error of measurement

    def likelihood(self, true_value: float) -> float:
        """
        P(observation | true_value)

        Assumes normal measurement error around true value.
        """
        if self.value is not None:
            # Exact observation with measurement error
            if self.measurement_error > 0:
                return stats.norm.pdf(self.value, true_value, self.measurement_error)
            else:
                # No measurement error: likelihood is 1 if close, 0 otherwise
                # Use small tolerance
                return 1.0 if abs(self.value - true_value) < 1e-6 else 0.0

        elif self.category is not None:
            # Categorical observation - map to probability
            return self._categorical_likelihood(true_value)

        return 1.0  # No information

    def _categorical_likelihood(self, true_value: float) -> float:
        """Map categorical responses to likelihood given true value."""
        # Define category thresholds based on variable
        category_maps = {
            "exercise_min_per_week": {
                "sedentary": (0, 30),
                "light": (30, 75),
                "moderate": (75, 150),
                "active": (150, 300),
                "very_active": (300, float('inf')),
            },
            "bmi": {
                "underweight": (0, 18.5),
                "normal": (18.5, 25),
                "overweight": (25, 30),
                "obese": (30, 40),
                "severely_obese": (40, float('inf')),
            },
            "sleep_hours": {
                "very_short": (0, 5),
                "short": (5, 6),
                "normal": (6, 8),
                "long": (8, 9),
                "very_long": (9, float('inf')),
            },
        }

        if self.variable in category_maps and self.category in category_maps[self.variable]:
            low, high = category_maps[self.variable][self.category]
            # Return 1 if true_value in category, 0 otherwise
            # (Could smooth this with a sigmoid for soft boundaries)
            return 1.0 if low <= true_value < high else 0.0

        return 1.0  # Unknown category


@dataclass
class PosteriorState:
    """
    Posterior distribution after incorporating observations.

    Stores updated mean, std, and samples for QALY calculation.
    """
    variable: str
    prior_mean: float
    prior_std: float
    posterior_mean: float
    posterior_std: float
    observations: List[Observation] = field(default_factory=list)
    samples: Optional[np.ndarray] = None

    @property
    def uncertainty_reduction(self) -> float:
        """How much uncertainty was reduced by observations."""
        return 1.0 - (self.posterior_std / self.prior_std)


def bayesian_update(
    prior: ImputationPrior,
    observations: List[Observation],
    n_samples: int = 10000,
    random_state: Optional[int] = None,
) -> PosteriorState:
    """
    Update prior distribution given observations using Bayes' rule.

    P(state | observations) ∝ P(observations | state) × P(state)

    Uses importance sampling for computational efficiency.

    Args:
        prior: Prior distribution from imputation model
        observations: List of user-provided observations
        n_samples: Number of samples for posterior approximation
        random_state: Random seed for reproducibility

    Returns:
        PosteriorState with updated distribution
    """
    rng = np.random.default_rng(random_state)

    # Sample from prior
    prior_samples = prior.sample(n_samples, rng)

    # Calculate importance weights: P(observations | sample)
    weights = np.ones(n_samples)
    for obs in observations:
        for i, sample in enumerate(prior_samples):
            weights[i] *= obs.likelihood(sample)

    # Normalize weights
    weight_sum = np.sum(weights)
    if weight_sum < 1e-10:
        # No samples compatible with observations - expand prior
        print(f"Warning: observations incompatible with prior for {prior.variable}")
        weights = np.ones(n_samples) / n_samples
    else:
        weights = weights / weight_sum

    # Compute posterior statistics
    posterior_mean = np.sum(weights * prior_samples)
    posterior_var = np.sum(weights * (prior_samples - posterior_mean)**2)
    posterior_std = np.sqrt(posterior_var)

    # Resample to get posterior samples (importance resampling)
    indices = rng.choice(n_samples, size=n_samples, p=weights)
    posterior_samples = prior_samples[indices]

    return PosteriorState(
        variable=prior.variable,
        prior_mean=prior.mean,
        prior_std=prior.std,
        posterior_mean=float(posterior_mean),
        posterior_std=float(posterior_std),
        observations=observations,
        samples=posterior_samples,
    )


def update_state_from_observations(
    priors: Dict[str, ImputationPrior],
    observations: List[Observation],
    n_samples: int = 10000,
    random_state: Optional[int] = None,
) -> Dict[str, PosteriorState]:
    """
    Update all imputed variables given user observations.

    Args:
        priors: Dict of variable name -> ImputationPrior
        observations: List of all user observations
        n_samples: Number of posterior samples
        random_state: Random seed

    Returns:
        Dict of variable name -> PosteriorState
    """
    # Group observations by variable
    obs_by_var: Dict[str, List[Observation]] = {}
    for obs in observations:
        if obs.variable not in obs_by_var:
            obs_by_var[obs.variable] = []
        obs_by_var[obs.variable].append(obs)

    # Update each variable
    posteriors = {}
    for var, prior in priors.items():
        var_obs = obs_by_var.get(var, [])
        if var_obs:
            posteriors[var] = bayesian_update(
                prior, var_obs, n_samples, random_state
            )
        else:
            # No observations for this variable - posterior = prior
            rng = np.random.default_rng(random_state)
            posteriors[var] = PosteriorState(
                variable=var,
                prior_mean=prior.mean,
                prior_std=prior.std,
                posterior_mean=prior.mean,
                posterior_std=prior.std,
                observations=[],
                samples=prior.sample(n_samples, rng),
            )

    return posteriors


# Default priors for common variables (based on NHANES)
# These are age/sex-specific; simplified here for demo
DEFAULT_PRIORS = {
    "exercise_min_per_week": ImputationPrior(
        variable="exercise_min_per_week",
        mean=100,  # Average American
        std=80,
        distribution="truncated_normal",
        lower_bound=0,
    ),
    "bmi": ImputationPrior(
        variable="bmi",
        mean=28.5,  # Average American adult
        std=6.0,
        distribution="truncated_normal",
        lower_bound=15,
        upper_bound=60,
    ),
    "sleep_hours": ImputationPrior(
        variable="sleep_hours",
        mean=6.8,
        std=1.2,
        distribution="truncated_normal",
        lower_bound=3,
        upper_bound=12,
    ),
    "systolic_bp": ImputationPrior(
        variable="systolic_bp",
        mean=128,
        std=18,
        distribution="truncated_normal",
        lower_bound=80,
        upper_bound=200,
    ),
    "diet_adherence": ImputationPrior(
        variable="diet_adherence",
        mean=0.4,
        std=0.2,
        distribution="truncated_normal",
        lower_bound=0,
        upper_bound=1,
    ),
}


def demo_bayesian_updating():
    """Demonstrate Bayesian updating with example observations."""
    print("=" * 60)
    print("Bayesian Updating Demo")
    print("=" * 60)

    # Prior: imputed exercise for average 40-year-old
    exercise_prior = DEFAULT_PRIORS["exercise_min_per_week"]
    print(f"\nPrior (imputed): Exercise = {exercise_prior.mean:.0f} ± {exercise_prior.std:.0f} min/week")

    # User says: "I exercise about 150 minutes per week"
    observation = Observation(
        variable="exercise_min_per_week",
        value=150,
        measurement_error=30,  # They might be off by ±30 min
    )

    posterior = bayesian_update(exercise_prior, [observation], random_state=42)

    print(f"\nObservation: User reports ~150 min/week (±30 measurement error)")
    print(f"\nPosterior: Exercise = {posterior.posterior_mean:.0f} ± {posterior.posterior_std:.0f} min/week")
    print(f"Uncertainty reduction: {posterior.uncertainty_reduction:.1%}")

    # Now show effect on QALY estimate
    print("\n" + "-" * 40)
    print("Effect on QALY uncertainty:")
    print(f"  Prior 95% CI for exercise: [{exercise_prior.mean - 2*exercise_prior.std:.0f}, {exercise_prior.mean + 2*exercise_prior.std:.0f}]")
    print(f"  Posterior 95% CI: [{posterior.posterior_mean - 2*posterior.posterior_std:.0f}, {posterior.posterior_mean + 2*posterior.posterior_std:.0f}]")
    print("\nSharper baseline state → Sharper QALY estimates")


if __name__ == "__main__":
    demo_bayesian_updating()
