"""
Precomputation Module

Generates precomputed QALY results for TypeScript web app.
Run MCMC once, store results for fast client-side lookup.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np

from .intervention import Intervention
from .simulate import simulate_qaly, simulate_qaly_profile, SimulationResult
from .profile import Profile, generate_all_profiles, count_profiles

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


# =============================================================================
# PROFILE-BASED PRECOMPUTATION
# =============================================================================


@dataclass
class ProfilePrecomputedResult:
    """Precomputed QALY result for a specific profile."""

    # Profile dimensions
    age: int
    sex: str
    bmi_category: str
    smoking_status: str
    has_diabetes: bool

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

    # Baseline mortality context
    baseline_mortality_multiplier: float

    # Metadata
    n_samples: int
    discount_rate: float


@dataclass
class ProfilePrecomputedIntervention:
    """Complete precomputed results for an intervention across all profiles."""

    id: str
    name: str
    category: str
    description: Optional[str]

    # Results by profile key
    results: Dict[str, ProfilePrecomputedResult]

    # Summary statistics
    summary: Dict[str, float]

    # Grid metadata
    grid: Dict[str, List]

    def get_result(self, profile: Profile) -> Optional[ProfilePrecomputedResult]:
        """Get precomputed result for specific profile."""
        return self.results.get(profile.key)

    def get_result_by_key(self, key: str) -> Optional[ProfilePrecomputedResult]:
        """Get precomputed result by key string."""
        return self.results.get(key)

    def to_json(self) -> str:
        """Export as JSON for TypeScript consumption."""
        return json.dumps(asdict(self), indent=2)

    def save(self, path: Path):
        """Save to JSON file."""
        path = Path(path)
        path.write_text(self.to_json())

    @classmethod
    def load(cls, path: Path) -> "ProfilePrecomputedIntervention":
        """Load from JSON file."""
        path = Path(path)
        data = json.loads(path.read_text())

        results = {}
        for key, result_data in data["results"].items():
            results[key] = ProfilePrecomputedResult(**result_data)

        return cls(
            id=data["id"],
            name=data["name"],
            category=data["category"],
            description=data.get("description"),
            results=results,
            summary=data["summary"],
            grid=data["grid"],
        )


def _simulate_single_profile(args):
    """Worker function for parallel profile simulation."""
    intervention, profile, n_samples, discount_rate, random_seed = args
    from .profile import get_baseline_mortality_multiplier

    sim_result = simulate_qaly_profile(
        intervention,
        profile,
        n_simulations=n_samples,
        discount_rate=discount_rate,
        random_state=random_seed,
    )

    cf_ci = sim_result.causal_fraction_ci or (0, 1)

    return profile.key, ProfilePrecomputedResult(
        age=profile.age,
        sex=profile.sex,
        bmi_category=profile.bmi_category,
        smoking_status=profile.smoking_status,
        has_diabetes=profile.has_diabetes,
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
        baseline_mortality_multiplier=get_baseline_mortality_multiplier(profile),
        n_samples=n_samples,
        discount_rate=discount_rate,
    )


def precompute_intervention_profiles(
    intervention: Intervention,
    ages: Optional[List[int]] = None,
    sexes: Optional[List[str]] = None,
    bmi_categories: Optional[List[str]] = None,
    smoking_statuses: Optional[List[str]] = None,
    diabetes_statuses: Optional[List[bool]] = None,
    n_samples: int = 5000,
    discount_rate: float = 0.03,
    random_seed: Optional[int] = 42,
    n_workers: Optional[int] = None,
    progress_callback=None,
) -> ProfilePrecomputedIntervention:
    """
    Precompute QALY results for an intervention across all profile combinations.

    Args:
        intervention: Intervention to precompute
        ages: Ages to compute for (default: 25-80 in 5-year increments)
        sexes: Sexes to compute for
        bmi_categories: BMI categories
        smoking_statuses: Smoking statuses
        diabetes_statuses: Diabetes status (True/False)
        n_samples: Number of Monte Carlo samples per profile
        discount_rate: Annual discount rate
        random_seed: Random seed for reproducibility
        n_workers: Number of parallel workers (default: CPU count)
        progress_callback: Optional callback(completed, total) for progress

    Returns:
        ProfilePrecomputedIntervention with results for all profiles
    """
    # Build grid parameters
    if ages is None:
        ages = list(range(25, 85, 5))
    if sexes is None:
        sexes = ["male", "female"]
    if bmi_categories is None:
        bmi_categories = ["normal", "overweight", "obese", "severely_obese"]
    if smoking_statuses is None:
        smoking_statuses = ["never", "former", "current"]
    if diabetes_statuses is None:
        diabetes_statuses = [False, True]

    grid = {
        "ages": ages,
        "sexes": sexes,
        "bmi_categories": bmi_categories,
        "smoking_statuses": smoking_statuses,
        "diabetes_statuses": diabetes_statuses,
    }

    # Generate all profiles
    profiles = list(generate_all_profiles(
        ages=ages,
        sexes=sexes,
        bmi_categories=bmi_categories,
        smoking_statuses=smoking_statuses,
        diabetes_statuses=diabetes_statuses,
    ))

    total_profiles = len(profiles)
    results = {}
    all_qaly_gains = []

    # Prepare work items
    work_items = [
        (intervention, profile, n_samples, discount_rate, random_seed)
        for profile in profiles
    ]

    # Sequential execution (simpler, more reliable for now)
    # TODO: Add parallel execution option
    for i, (intervention, profile, n_samples, discount_rate, seed) in enumerate(work_items):
        key, result = _simulate_single_profile(
            (intervention, profile, n_samples, discount_rate, seed)
        )
        results[key] = result
        all_qaly_gains.append(result.qaly_median)

        if progress_callback:
            progress_callback(i + 1, total_profiles)

    # Summary statistics
    summary = {
        "qaly_median_all": float(np.median(all_qaly_gains)),
        "qaly_mean_all": float(np.mean(all_qaly_gains)),
        "qaly_min": float(np.min(all_qaly_gains)),
        "qaly_max": float(np.max(all_qaly_gains)),
        "qaly_std": float(np.std(all_qaly_gains)),
        "n_profiles": total_profiles,
    }

    return ProfilePrecomputedIntervention(
        id=intervention.id,
        name=intervention.name,
        category=intervention.category,
        description=intervention.description,
        results=results,
        summary=summary,
        grid=grid,
    )


def precompute_all_profiles(
    intervention_dir: Path,
    output_dir: Path,
    **kwargs,
) -> List[ProfilePrecomputedIntervention]:
    """
    Precompute all interventions with full profile grid.

    Args:
        intervention_dir: Directory containing YAML intervention files
        output_dir: Directory to save JSON results
        **kwargs: Arguments to pass to precompute_intervention_profiles

    Returns:
        List of ProfilePrecomputedIntervention objects
    """
    intervention_dir = Path(intervention_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []

    yaml_files = list(intervention_dir.glob("*.yaml"))
    total_interventions = len(yaml_files)

    for idx, yaml_file in enumerate(yaml_files):
        print(f"[{idx + 1}/{total_interventions}] Processing {yaml_file.name}...")

        intervention = Intervention.from_yaml(yaml_file)

        def progress(completed, total):
            print(f"  Profile {completed}/{total} ({100*completed/total:.0f}%)", end="\r")

        precomputed = precompute_intervention_profiles(
            intervention,
            progress_callback=progress,
            **kwargs
        )

        output_file = output_dir / f"{intervention.id}_profiles.json"
        precomputed.save(output_file)

        results.append(precomputed)
        print(f"\n  Saved to {output_file}")
        print(f"  QALY range: {precomputed.summary['qaly_min']:.3f} - {precomputed.summary['qaly_max']:.3f}")

    return results
