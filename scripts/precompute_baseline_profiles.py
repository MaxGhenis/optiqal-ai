#!/usr/bin/env python3 -u
"""
Precompute baseline life expectancy across demographic profiles.

This generates precomputed baseline predictions (no intervention) for:
- Age (25-80 in 5-year increments): 12 values
- Sex (male, female): 2 values
- BMI category (normal, overweight, obese, severely_obese): 4 values
- Smoking status (never, former, current): 3 values
- Diabetes status (no, yes): 2 values
- Hypertension status (no, yes): 2 values
- Activity level (light): 1 value

= 1,152 profiles

Output:
    public/precomputed/baseline_profiles.json
"""

import argparse
import json
import sys
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "python"))

from optiqal.profile import Profile, generate_all_profiles, get_baseline_mortality_multiplier
from optiqal.markov import simulate_lifetime_markov, HealthState


@dataclass
class BaselineResult:
    """Baseline prediction for a single profile."""
    age: int
    sex: str
    bmi_category: str
    smoking_status: str
    has_diabetes: bool
    has_hypertension: bool
    activity_level: str

    # Life expectancy
    life_years_median: float
    life_years_mean: float
    life_years_p5: float
    life_years_p95: float

    # QALYs (for future use)
    qalys_median: float
    qalys_mean: float
    qalys_p5: float
    qalys_p95: float

    # Mortality multiplier applied
    mortality_multiplier: float

    # Metadata
    n_samples: int
    discount_rate: float


def simulate_baseline_vectorized(
    profile: Profile,
    n_samples: int = 5000,
    discount_rate: float = 0.03,
    seed: int = 42,
) -> BaselineResult:
    """
    Run vectorized simulations for a single profile's baseline life expectancy.
    """
    rng = np.random.default_rng(seed)

    # Get mortality multiplier for this profile
    mortality_multiplier = get_baseline_mortality_multiplier(profile)

    # Initial health state from profile
    initial_state = HealthState(
        diabetes=profile.has_diabetes,
        hypertension=profile.has_hypertension,
    )

    life_years_list = []
    qalys_list = []

    for _ in range(n_samples):
        result = simulate_lifetime_markov(
            start_age=profile.age,
            sex=profile.sex,
            intervention_hr=mortality_multiplier,  # Apply as mortality modifier
            initial_state=initial_state,
            discount_rate=discount_rate,
            rng=rng,
        )
        life_years_list.append(result.life_years)
        qalys_list.append(result.qalys)

    life_years = np.array(life_years_list)
    qalys = np.array(qalys_list)

    return BaselineResult(
        age=profile.age,
        sex=profile.sex,
        bmi_category=profile.bmi_category,
        smoking_status=profile.smoking_status,
        has_diabetes=profile.has_diabetes,
        has_hypertension=profile.has_hypertension,
        activity_level=profile.activity_level,
        life_years_median=float(np.median(life_years)),
        life_years_mean=float(np.mean(life_years)),
        life_years_p5=float(np.percentile(life_years, 5)),
        life_years_p95=float(np.percentile(life_years, 95)),
        qalys_median=float(np.median(qalys)),
        qalys_mean=float(np.mean(qalys)),
        qalys_p5=float(np.percentile(qalys, 5)),
        qalys_p95=float(np.percentile(qalys, 95)),
        mortality_multiplier=mortality_multiplier,
        n_samples=n_samples,
        discount_rate=discount_rate,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Precompute baseline life expectancy across demographic profiles"
    )
    parser.add_argument(
        "--n-samples",
        type=int,
        default=5000,
        help="Number of Monte Carlo samples per profile (default: 5000)",
    )
    parser.add_argument(
        "--ages",
        type=str,
        default="25,30,35,40,45,50,55,60,65,70,75,80",
        help="Comma-separated ages (default: 25-80 in 5-year increments)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: fewer ages (30,50,70), fewer samples (1000)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root / "public" / "precomputed",
        help="Output directory (default: public/precomputed)",
    )

    args = parser.parse_args()

    # Parse ages
    if args.quick:
        ages = [30, 50, 70]
        n_samples = 1000
        print("Quick mode: ages=[30, 50, 70], n_samples=1000")
    else:
        ages = [int(a) for a in args.ages.split(",")]
        n_samples = args.n_samples

    # Activity levels (just light for now)
    activity_levels = ["light"]

    # Generate profile grid
    profiles = list(generate_all_profiles(ages=ages, activity_levels=activity_levels))
    print(f"\nPrecomputing baselines for {len(profiles)} profiles")
    print(f"  Ages: {ages}")
    print(f"  n_samples: {n_samples}")
    print()

    start_time = time.time()
    results = {}

    for i, profile in enumerate(profiles):
        elapsed = time.time() - start_time
        rate = (i + 1) / elapsed if elapsed > 0 else 0
        eta = (len(profiles) - i - 1) / rate if rate > 0 else 0
        print(
            f"  Profile {i+1}/{len(profiles)} ({100*(i+1)/len(profiles):.0f}%) "
            f"[{elapsed:.0f}s elapsed, ~{eta:.0f}s remaining]",
            end="\r"
        )

        result = simulate_baseline_vectorized(
            profile=profile,
            n_samples=n_samples,
            seed=42 + i,  # Different seed per profile for reproducibility
        )
        results[profile.key] = asdict(result)

    print(f"\n\nCompleted {len(results)} profiles in {time.time() - start_time:.1f}s")

    # Build output data
    output = {
        "version": "1.0.0",
        "description": "Baseline life expectancy by demographic profile",
        "n_profiles": len(results),
        "n_samples": n_samples,
        "discount_rate": 0.03,
        "results": results,
    }

    # Save
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "baseline_profiles.json"

    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Saved to: {output_file}")

    # Summary stats
    life_years = [r["life_years_median"] for r in results.values()]
    print(f"\nSummary:")
    print(f"  Life years range: {min(life_years):.1f} - {max(life_years):.1f}")
    print(f"  Mean life years: {np.mean(life_years):.1f}")


if __name__ == "__main__":
    main()
