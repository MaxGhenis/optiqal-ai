#!/usr/bin/env python3
"""
Validate precomputed QALY JSON files.

This script checks that all precomputed JSON files:
- Are valid JSON
- Have the expected structure
- Contain reasonable values
"""

import json
import sys
from pathlib import Path


def validate_precomputed_result(result_data: dict, key: str) -> list:
    """Validate a single precomputed result."""
    errors = []

    required_fields = [
        "age", "sex", "qaly_median", "qaly_mean", "qaly_ci95_low", "qaly_ci95_high",
        "cvd_contribution", "cancer_contribution", "other_contribution",
        "life_years_gained", "causal_fraction_mean",
        "causal_fraction_ci95_low", "causal_fraction_ci95_high",
        "n_samples", "discount_rate", "method"
    ]

    for field in required_fields:
        if field not in result_data:
            errors.append(f"  {key}: Missing required field '{field}'")

    # Validate data types
    if "age" in result_data and not isinstance(result_data["age"], int):
        errors.append(f"  {key}: 'age' should be an integer")

    if "sex" in result_data and result_data["sex"] not in ["male", "female"]:
        errors.append(f"  {key}: 'sex' should be 'male' or 'female'")

    if "method" in result_data and result_data["method"] not in ["monte_carlo", "mcmc"]:
        errors.append(f"  {key}: 'method' should be 'monte_carlo' or 'mcmc'")

    # Validate numeric ranges
    if "causal_fraction_mean" in result_data:
        cf = result_data["causal_fraction_mean"]
        if not (0 <= cf <= 1):
            errors.append(f"  {key}: 'causal_fraction_mean' should be between 0 and 1, got {cf}")

    # Validate CI ordering
    if all(k in result_data for k in ["qaly_ci95_low", "qaly_ci95_high"]):
        if result_data["qaly_ci95_low"] > result_data["qaly_ci95_high"]:
            errors.append(f"  {key}: qaly_ci95_low > qaly_ci95_high")

    return errors


def validate_precomputed_intervention(file_path: Path) -> tuple[bool, list]:
    """Validate a precomputed intervention JSON file."""
    errors = []

    try:
        with open(file_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]
    except Exception as e:
        return False, [f"Error reading file: {e}"]

    # Check top-level fields
    required_top_level = ["id", "name", "category", "results", "summary"]
    for field in required_top_level:
        if field not in data:
            errors.append(f"Missing required top-level field '{field}'")

    # Validate category
    valid_categories = ["exercise", "diet", "sleep", "substance", "medical", "stress"]
    if "category" in data and data["category"] not in valid_categories:
        errors.append(f"Invalid category '{data['category']}', should be one of {valid_categories}")

    # Validate results
    if "results" in data:
        if not isinstance(data["results"], dict):
            errors.append("'results' should be a dictionary")
        elif len(data["results"]) == 0:
            errors.append("'results' is empty")
        else:
            for key, result_data in data["results"].items():
                errors.extend(validate_precomputed_result(result_data, key))

    # Validate summary
    if "summary" in data:
        required_summary = ["qaly_median_all", "qaly_mean_all", "qaly_min", "qaly_max"]
        for field in required_summary:
            if field not in data["summary"]:
                errors.append(f"Summary missing required field '{field}'")

    return len(errors) == 0, errors


def main():
    project_root = Path(__file__).parent.parent
    precomputed_dir = project_root / "public" / "precomputed"

    if not precomputed_dir.exists():
        print(f"Error: Precomputed directory not found: {precomputed_dir}")
        sys.exit(1)

    json_files = list(precomputed_dir.glob("*.json"))

    # Filter out baselines.json which has a different structure
    json_files = [f for f in json_files if f.name != "baselines.json"]

    if not json_files:
        print(f"Error: No JSON files found in {precomputed_dir}")
        sys.exit(1)

    print(f"Validating {len(json_files)} precomputed intervention file(s)...")
    print("=" * 70)

    all_valid = True

    for json_file in json_files:
        print(f"\n{json_file.name}")
        is_valid, errors = validate_precomputed_intervention(json_file)

        if is_valid:
            print("  ✓ Valid")
        else:
            print("  ✗ Invalid:")
            for error in errors:
                print(f"    - {error}")
            all_valid = False

    print("\n" + "=" * 70)

    if all_valid:
        print("✓ All files are valid!")
        sys.exit(0)
    else:
        print("✗ Some files have errors")
        sys.exit(1)


if __name__ == "__main__":
    main()
