#!/usr/bin/env python3
"""
Precompute baseline life expectancy and QALY data.

This script generates pre-tabulated data for ages 0-100 to replace
runtime interpolations with O(1) lookups. This improves performance
by replacing ~70 interpolations per simulation with simple array access.

Output:
- public/precomputed/baselines.json (for TypeScript)
- python/optiqal/data/baselines.json (for Python)
"""

import json
import os
from pathlib import Path

# Import from the lifecycle module
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from optiqal.lifecycle import (
    get_mortality_rate,
    get_cause_fraction,
    get_quality_weight,
)


def calculate_life_expectancy(start_age: int, sex: str, max_age: int = 100) -> float:
    """Calculate remaining life expectancy from a given age."""
    survival = 1.0
    life_years = 0.0

    for year in range(max_age - start_age):
        current_age = start_age + year
        qx = get_mortality_rate(current_age, sex)

        # Add expected life years this year
        life_years += survival

        # Update survival
        survival *= 1 - qx

        # Early termination if nearly everyone is dead
        if survival < 0.001:
            break

    return life_years


def calculate_remaining_qalys(
    start_age: int, sex: str, discount_rate: float = 0.03, max_age: int = 100
) -> float:
    """Calculate remaining QALYs from a given age with discounting."""
    survival = 1.0
    qalys = 0.0

    for year in range(max_age - start_age):
        current_age = start_age + year
        qx = get_mortality_rate(current_age, sex)
        quality = get_quality_weight(current_age)
        discount = 1 / (1 + discount_rate) ** year

        # Add QALY contribution this year
        qalys += survival * quality * discount

        # Update survival
        survival *= 1 - qx

        # Early termination
        if survival < 0.001:
            break

    return qalys


def precompute_baselines():
    """Generate all precomputed baseline data."""
    print("Precomputing baselines...")

    data = {
        "metadata": {
            "version": "1.0.0",
            "source": "CDC National Vital Statistics Life Tables (2021)",
            "discount_rate": 0.03,
            "max_age": 100,
        },
        "life_expectancy": {"male": {}, "female": {}},
        "remaining_qalys": {"male": {}, "female": {}},
        "cause_fractions": {},
        "quality_weights": {},
    }

    # Precompute for each age 0-100
    for age in range(101):
        # Life expectancy by sex
        for sex in ["male", "female"]:
            life_exp = calculate_life_expectancy(age, sex)
            data["life_expectancy"][sex][age] = round(life_exp, 3)

            qalys = calculate_remaining_qalys(age, sex)
            data["remaining_qalys"][sex][age] = round(qalys, 3)

        # Cause fractions (age-dependent, sex-independent)
        cause_frac = get_cause_fraction(age)
        data["cause_fractions"][age] = {
            "cvd": round(cause_frac["cvd"], 4),
            "cancer": round(cause_frac["cancer"], 4),
            "other": round(cause_frac["other"], 4),
        }

        # Quality weights (age-dependent, sex-independent)
        quality = get_quality_weight(age)
        data["quality_weights"][age] = round(quality, 4)

        if age % 10 == 0:
            print(f"  Processed age {age}")

    return data


def save_json(data: dict, output_path: Path):
    """Save precomputed data as JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)

    print(f"  Saved to {output_path}")


def main():
    """Main entry point."""
    # Get repository root
    repo_root = Path(__file__).parent.parent

    # Generate precomputed data
    data = precompute_baselines()

    # Save to both locations
    public_path = repo_root / "public" / "precomputed" / "baselines.json"
    python_path = repo_root / "python" / "optiqal" / "data" / "baselines.json"

    print("\nSaving output files...")
    save_json(data, public_path)
    save_json(data, python_path)

    # Print summary statistics
    print("\nSummary Statistics:")
    print(
        f"  Male life expectancy at birth: {data['life_expectancy']['male'][0]:.1f} years"
    )
    print(
        f"  Female life expectancy at birth: {data['life_expectancy']['female'][0]:.1f} years"
    )
    print(
        f"  Male remaining QALYs at birth: {data['remaining_qalys']['male'][0]:.1f}"
    )
    print(
        f"  Female remaining QALYs at birth: {data['remaining_qalys']['female'][0]:.1f}"
    )
    print(
        f"  Male remaining QALYs at age 40: {data['remaining_qalys']['male'][40]:.1f}"
    )
    print(
        f"  Female remaining QALYs at age 40: {data['remaining_qalys']['female'][40]:.1f}"
    )

    print("\nPrecomputation complete!")
    print(
        f"  Total data points: {len(data['life_expectancy']['male']) * 2 + len(data['cause_fractions']) + len(data['quality_weights'])}"
    )


if __name__ == "__main__":
    main()
