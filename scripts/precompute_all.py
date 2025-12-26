#!/usr/bin/env python3
"""
Precompute QALY results for all interventions.

This script generates precomputed JSON files for all intervention YAML files
in the src/lib/qaly/interventions/ directory. The results are saved to the
public/precomputed/ directory for fast client-side lookup.

Usage:
    python scripts/precompute_all.py [--samples N] [--ages AGE1 AGE2 ...] [--dry-run]

Options:
    --samples N         Number of Monte Carlo samples (default: 5000)
    --ages AGE1 AGE2    Ages to compute for (default: 30 40 50 60 70)
    --dry-run           Print what would be done without generating files
    --help              Show this help message
"""

import argparse
import sys
from pathlib import Path

# Add python directory to path so we can import optiqal
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "python"))

from optiqal.precompute import precompute_all_interventions


def main():
    parser = argparse.ArgumentParser(
        description="Precompute QALY results for all interventions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=5000,
        help="Number of Monte Carlo samples (default: 5000)",
    )
    parser.add_argument(
        "--ages",
        type=int,
        nargs="+",
        default=[30, 40, 50, 60, 70],
        help="Ages to compute for (default: 30 40 50 60 70)",
    )
    parser.add_argument(
        "--sexes",
        type=str,
        nargs="+",
        choices=["male", "female"],
        default=["male", "female"],
        help="Sexes to compute for (default: male female)",
    )
    parser.add_argument(
        "--discount-rate",
        type=float,
        default=0.03,
        help="Annual discount rate (default: 0.03)",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without generating files",
    )

    args = parser.parse_args()

    # Define paths
    intervention_dir = project_root / "src" / "lib" / "qaly" / "interventions"
    output_dir = project_root / "public" / "precomputed"

    # Validate intervention directory exists
    if not intervention_dir.exists():
        print(f"Error: Intervention directory not found: {intervention_dir}")
        sys.exit(1)

    # Count intervention files
    yaml_files = list(intervention_dir.glob("*.yaml"))
    if not yaml_files:
        print(f"Error: No YAML files found in {intervention_dir}")
        sys.exit(1)

    print(f"Found {len(yaml_files)} intervention(s) to precompute:")
    for yaml_file in yaml_files:
        print(f"  - {yaml_file.name}")

    print(f"\nConfiguration:")
    print(f"  Monte Carlo samples: {args.samples}")
    print(f"  Ages: {args.ages}")
    print(f"  Sexes: {args.sexes}")
    print(f"  Discount rate: {args.discount_rate}")
    print(f"  Random seed: {args.random_seed}")
    print(f"  Output directory: {output_dir}")

    if args.dry_run:
        print("\n[DRY RUN] Would generate files but not writing to disk.")
        return

    print(f"\nStarting precomputation...")
    print("=" * 70)

    try:
        results = precompute_all_interventions(
            intervention_dir=intervention_dir,
            output_dir=output_dir,
            ages=args.ages,
            sexes=args.sexes,
            use_mcmc=False,  # Use fast Monte Carlo
            n_samples=args.samples,
            discount_rate=args.discount_rate,
            random_seed=args.random_seed,
        )

        print("=" * 70)
        print(f"\nSuccessfully precomputed {len(results)} intervention(s)!")
        print(f"Results saved to: {output_dir}")

        # Print summary of each result
        print("\nSummary:")
        for result in results:
            print(f"\n  {result.name} ({result.id}):")
            print(f"    Category: {result.category}")
            print(f"    Profiles: {len(result.results)}")
            print(f"    Median QALY (all): {result.summary['qaly_median_all']:.4f}")
            print(f"    QALY range: {result.summary['qaly_min']:.4f} - {result.summary['qaly_max']:.4f}")

    except Exception as e:
        print(f"\nError during precomputation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
