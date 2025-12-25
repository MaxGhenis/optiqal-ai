#!/usr/bin/env python3
"""
Precompute QALY results across demographic profiles.

This script generates precomputed QALY estimates for all combinations of:
- Age (25-80 in 5-year increments)
- Sex (male, female)
- BMI category (normal, overweight, obese, severely_obese)
- Smoking status (never, former, current)
- Diabetes status (no, yes)

Total: 12 × 2 × 4 × 3 × 2 = 576 profiles per intervention
With 10 interventions = 5,760 total profiles

Usage:
    python scripts/precompute_profiles.py [--intervention walking_30min_daily] [--n-samples 5000]

Output:
    public/precomputed/{intervention_id}_profiles.json
"""

import argparse
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "python"))

from optiqal.intervention import Intervention
from optiqal.precompute import precompute_intervention_profiles, precompute_all_profiles
from optiqal.profile import count_profiles


def main():
    parser = argparse.ArgumentParser(
        description="Precompute QALY results across demographic profiles"
    )
    parser.add_argument(
        "--intervention",
        type=str,
        help="Specific intervention ID to precompute (default: all)",
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

    intervention_dir = project_root / "src" / "lib" / "qaly" / "interventions"
    output_dir = Path(args.output_dir)

    # Parse ages
    if args.quick:
        ages = [30, 50, 70]
        n_samples = 1000
        print("Quick mode: ages=[30, 50, 70], n_samples=1000")
    else:
        ages = [int(a) for a in args.ages.split(",")]
        n_samples = args.n_samples

    # Calculate total profiles
    total_profiles = count_profiles(ages=ages)
    print(f"\nGrid configuration:")
    print(f"  Ages: {ages}")
    print(f"  Sexes: male, female")
    print(f"  BMI: normal, overweight, obese, severely_obese")
    print(f"  Smoking: never, former, current")
    print(f"  Diabetes: no, yes")
    print(f"  → {total_profiles} profiles per intervention")
    print(f"  → {n_samples} samples per profile")
    print()

    start_time = time.time()

    if args.intervention:
        # Single intervention
        yaml_path = intervention_dir / f"{args.intervention}.yaml"
        if not yaml_path.exists():
            print(f"Error: Intervention not found: {yaml_path}")
            sys.exit(1)

        intervention = Intervention.from_yaml(yaml_path)
        print(f"Precomputing: {intervention.name}")

        def progress(completed, total):
            elapsed = time.time() - start_time
            rate = completed / elapsed if elapsed > 0 else 0
            eta = (total - completed) / rate if rate > 0 else 0
            print(
                f"  Profile {completed}/{total} ({100*completed/total:.0f}%) "
                f"[{elapsed:.0f}s elapsed, ~{eta:.0f}s remaining]",
                end="\r"
            )

        result = precompute_intervention_profiles(
            intervention,
            ages=ages,
            n_samples=n_samples,
            progress_callback=progress,
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{intervention.id}_profiles.json"
        result.save(output_file)

        print(f"\n\nSaved to: {output_file}")
        print(f"QALY range: {result.summary['qaly_min']:.3f} - {result.summary['qaly_max']:.3f}")

    else:
        # All interventions
        yaml_files = list(intervention_dir.glob("*.yaml"))
        print(f"Found {len(yaml_files)} interventions")
        print(f"Total profiles to compute: {total_profiles * len(yaml_files):,}")
        print()

        results = precompute_all_profiles(
            intervention_dir,
            output_dir,
            ages=ages,
            n_samples=n_samples,
        )

        print(f"\n\nCompleted {len(results)} interventions")

    elapsed = time.time() - start_time
    print(f"Total time: {elapsed:.1f}s ({elapsed/60:.1f} min)")


if __name__ == "__main__":
    main()
