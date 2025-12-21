"""
Precomputation Module

Generates precomputed QALY results for TypeScript web app.
Run MCMC once, store results for fast client-side lookup.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional
import numpy as np

from .intervention import Intervention
from .simulate import simulate_qaly, SimulationResult

try:
    from .bayesian import run_mcmc, summarize_posterior

    HAS_BAYESIAN = True
except ImportError:
    HAS_BAYESIAN = False


@dataclass
class PrecomputedResult:
    """Precomputed QALY result for a specific age/sex combination."""

    age: int
    sex: str

    # Point estimates
    qaly_median: float
    qaly_mean: float
    qaly_ci95_low: float
    qaly_ci95_high: float

    # Pathway contributions
    cvd_contribution: float
    cancer_contribution: float
    other_contribution: float

    # Life years
    life_years_gained: float

    # Confounding
    causal_fraction_mean: float
    causal_fraction_ci95_low: float
    causal_fraction_ci95_high: float

    # Metadata
    n_samples: int
    discount_rate: float
    method: str  # "mcmc" or "monte_carlo"


@dataclass
class PrecomputedIntervention:
    """Complete precomputed results for an intervention."""

    id: str
    name: str
    category: str
    description: Optional[str]

    # Results by age and sex
    results: Dict[str, PrecomputedResult]  # key: "age_sex" e.g., "40_male"

    # Summary across all profiles
    summary: Dict[str, float]

    def get_result(self, age: int, sex: str) -> Optional[PrecomputedResult]:
        """Get precomputed result for specific profile."""
        key = f"{age}_{sex}"
        return self.results.get(key)

    def to_json(self) -> str:
        """Export as JSON for TypeScript consumption."""
        return json.dumps(asdict(self), indent=2)

    def save(self, path: Path):
        """Save to JSON file."""
        path = Path(path)
        path.write_text(self.to_json())

    @classmethod
    def load(cls, path: Path) -> "PrecomputedIntervention":
        """Load from JSON file."""
        path = Path(path)
        data = json.loads(path.read_text())

        # Reconstruct PrecomputedResult objects
        results = {}
        for key, result_data in data["results"].items():
            results[key] = PrecomputedResult(**result_data)

        return cls(
            id=data["id"],
            name=data["name"],
            category=data["category"],
            description=data.get("description"),
            results=results,
            summary=data["summary"],
        )


def precompute_intervention(
    intervention: Intervention,
    ages: List[int] = [30, 40, 50, 60, 70],
    sexes: List[Literal["male", "female"]] = ["male", "female"],
    use_mcmc: bool = True,
    n_samples: int = 2000,
    chains: int = 4,
    discount_rate: float = 0.03,
    random_seed: Optional[int] = 42,
) -> PrecomputedIntervention:
    """
    Precompute QALY results for an intervention.

    Args:
        intervention: Intervention to precompute
        ages: Ages to compute for
        sexes: Sexes to compute for
        use_mcmc: Use full MCMC (slower, more accurate) vs Monte Carlo
        n_samples: Number of samples
        chains: Number of MCMC chains (if use_mcmc)
        discount_rate: Annual discount rate
        random_seed: Random seed for reproducibility

    Returns:
        PrecomputedIntervention with results for all age/sex combinations
    """
    results = {}
    all_qaly_gains = []

    for age in ages:
        for sex in sexes:
            key = f"{age}_{sex}"

            if use_mcmc and HAS_BAYESIAN:
                # Full MCMC
                trace = run_mcmc(
                    intervention,
                    age=age,
                    sex=sex,
                    n_samples=n_samples,
                    chains=chains,
                    random_seed=random_seed,
                )

                qaly_samples = trace.posterior["qaly_gain"].values.flatten()
                causal_samples = trace.posterior["causal_fraction"].values.flatten()

                result = PrecomputedResult(
                    age=age,
                    sex=sex,
                    qaly_median=float(np.median(qaly_samples)),
                    qaly_mean=float(np.mean(qaly_samples)),
                    qaly_ci95_low=float(np.percentile(qaly_samples, 2.5)),
                    qaly_ci95_high=float(np.percentile(qaly_samples, 97.5)),
                    cvd_contribution=0,  # Would need to track in MCMC
                    cancer_contribution=0,
                    other_contribution=0,
                    life_years_gained=float(
                        np.median(trace.posterior["life_years_gained"].values.flatten())
                    ),
                    causal_fraction_mean=float(np.mean(causal_samples)),
                    causal_fraction_ci95_low=float(np.percentile(causal_samples, 2.5)),
                    causal_fraction_ci95_high=float(np.percentile(causal_samples, 97.5)),
                    n_samples=n_samples * chains,
                    discount_rate=discount_rate,
                    method="mcmc",
                )
            else:
                # Fast Monte Carlo
                sim_result = simulate_qaly(
                    intervention,
                    age=age,
                    sex=sex,
                    n_simulations=n_samples,
                    discount_rate=discount_rate,
                    random_state=random_seed,
                )

                cf_ci = sim_result.causal_fraction_ci or (0, 1)

                result = PrecomputedResult(
                    age=age,
                    sex=sex,
                    qaly_median=sim_result.median,
                    qaly_mean=sim_result.mean,
                    qaly_ci95_low=sim_result.ci95[0],
                    qaly_ci95_high=sim_result.ci95[1],
                    cvd_contribution=sim_result.cvd_contribution,
                    cancer_contribution=sim_result.cancer_contribution,
                    other_contribution=sim_result.other_contribution,
                    life_years_gained=sim_result.life_years_gained,
                    causal_fraction_mean=sim_result.causal_fraction_mean or 1.0,
                    causal_fraction_ci95_low=cf_ci[0],
                    causal_fraction_ci95_high=cf_ci[1],
                    n_samples=n_samples,
                    discount_rate=discount_rate,
                    method="monte_carlo",
                )

            results[key] = result
            all_qaly_gains.append(result.qaly_median)

    # Summary statistics
    summary = {
        "qaly_median_all": float(np.median(all_qaly_gains)),
        "qaly_mean_all": float(np.mean(all_qaly_gains)),
        "qaly_min": float(np.min(all_qaly_gains)),
        "qaly_max": float(np.max(all_qaly_gains)),
    }

    return PrecomputedIntervention(
        id=intervention.id,
        name=intervention.name,
        category=intervention.category,
        description=intervention.description,
        results=results,
        summary=summary,
    )


def precompute_all_interventions(
    intervention_dir: Path,
    output_dir: Path,
    **kwargs,
) -> List[PrecomputedIntervention]:
    """
    Precompute all interventions from a directory.

    Args:
        intervention_dir: Directory containing YAML intervention files
        output_dir: Directory to save JSON results
        **kwargs: Arguments to pass to precompute_intervention

    Returns:
        List of PrecomputedIntervention objects
    """
    intervention_dir = Path(intervention_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []

    for yaml_file in intervention_dir.glob("*.yaml"):
        print(f"Processing {yaml_file.name}...")

        intervention = Intervention.from_yaml(yaml_file)
        precomputed = precompute_intervention(intervention, **kwargs)

        output_file = output_dir / f"{intervention.id}.json"
        precomputed.save(output_file)

        results.append(precomputed)
        print(f"  Saved to {output_file}")

    return results
