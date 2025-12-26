#!/usr/bin/env python3
"""
Example: Using Precomputed Baselines for Fast QALY Calculations

This example demonstrates how to use precomputed baseline data to speed up
lifecycle QALY calculations by replacing ~70 interpolations per simulation
with O(1) lookups.
"""

import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from optiqal.lifecycle import (
    LifecycleModel,
    PathwayHRs,
    get_precomputed_baseline_qalys,
    get_precomputed_life_expectancy,
)


def benchmark_precomputed_vs_interpolation():
    """Compare performance of precomputed vs interpolation."""
    print("=" * 70)
    print("Performance Comparison: Precomputed vs Interpolation")
    print("=" * 70)

    # Test parameters
    age = 40
    sex = "male"
    n_simulations = 1000

    # Intervention scenario: 20% reduction in CVD risk
    pathway_hrs = PathwayHRs(cvd=0.8, cancer=1.0, other=1.0)

    # Method 1: With precomputed baselines (fast)
    model_fast = LifecycleModel(start_age=age, sex=sex, use_precomputed=True)

    start = time.time()
    for _ in range(n_simulations):
        result = model_fast.calculate(pathway_hrs)
    fast_duration = time.time() - start

    print(f"\nWith Precomputed Baselines (fast path):")
    print(f"  {n_simulations} simulations in {fast_duration:.3f}s")
    print(f"  {n_simulations / fast_duration:.1f} simulations/second")
    print(f"  {fast_duration / n_simulations * 1000:.2f} ms/simulation")

    # Method 2: Without precomputed baselines (slow)
    model_slow = LifecycleModel(start_age=age, sex=sex, use_precomputed=False)

    start = time.time()
    for _ in range(n_simulations):
        result = model_slow.calculate(pathway_hrs)
    slow_duration = time.time() - start

    print(f"\nWithout Precomputed Baselines (interpolation):")
    print(f"  {n_simulations} simulations in {slow_duration:.3f}s")
    print(f"  {n_simulations / slow_duration:.1f} simulations/second")
    print(f"  {slow_duration / n_simulations * 1000:.2f} ms/simulation")

    # Speedup
    speedup = slow_duration / fast_duration
    print(f"\nSpeedup: {speedup:.2f}x faster with precomputed baselines")


def demonstrate_precomputed_lookups():
    """Demonstrate direct precomputed lookups."""
    print("\n" + "=" * 70)
    print("Direct Precomputed Lookups (O(1) operations)")
    print("=" * 70)

    ages = [0, 20, 40, 60, 80]
    sexes = ["male", "female"]

    print("\nLife Expectancy (remaining years):")
    print(f"{'Age':<6} {'Male':>10} {'Female':>10}")
    print("-" * 30)
    for age in ages:
        male_le = get_precomputed_life_expectancy(age, "male")
        female_le = get_precomputed_life_expectancy(age, "female")
        print(f"{age:<6} {male_le:>10.1f} {female_le:>10.1f}")

    print("\nRemaining QALYs (3% discount rate):")
    print(f"{'Age':<6} {'Male':>10} {'Female':>10}")
    print("-" * 30)
    for age in ages:
        male_qalys = get_precomputed_baseline_qalys(age, "male")
        female_qalys = get_precomputed_baseline_qalys(age, "female")
        print(f"{age:<6} {male_qalys:>10.1f} {female_qalys:>10.1f}")


def demonstrate_intervention_calculation():
    """Demonstrate calculating intervention impact."""
    print("\n" + "=" * 70)
    print("Intervention Impact Analysis")
    print("=" * 70)

    # Scenario: 50-year-old female considering statins
    # Statins reduce CVD mortality by ~25%
    age = 50
    sex = "female"

    model = LifecycleModel(start_age=age, sex=sex, use_precomputed=True)

    # No intervention
    baseline = model.calculate(PathwayHRs(cvd=1.0, cancer=1.0, other=1.0))

    # With statin (25% CVD reduction)
    statin = model.calculate(PathwayHRs(cvd=0.75, cancer=1.0, other=1.0))

    print(f"\nProfile: {age}-year-old {sex}")
    print(f"\nBaseline (no intervention):")
    print(f"  Remaining QALYs: {baseline.baseline_qalys:.2f}")
    print(f"  Life years: {baseline.life_years_gained + baseline.baseline_qalys:.1f}")

    print(f"\nWith statin (25% CVD risk reduction):")
    print(f"  Remaining QALYs: {statin.intervention_qalys:.2f}")
    print(f"  QALY gain: {statin.qaly_gain:.3f}")
    print(f"  Life years gained: {statin.life_years_gained:.2f}")

    print(f"\nPathway contributions to QALY gain:")
    print(f"  CVD: {statin.pathway_contributions['cvd']:.3f}")
    print(f"  Cancer: {statin.pathway_contributions['cancer']:.3f}")
    print(f"  Other: {statin.pathway_contributions['other']:.3f}")


if __name__ == "__main__":
    demonstrate_precomputed_lookups()
    demonstrate_intervention_calculation()
    benchmark_precomputed_vs_interpolation()

    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(
        """
Precomputed baselines provide:
1. O(1) lookups instead of O(n) interpolation (~70 lookups/simulation)
2. Significant performance improvement for batch simulations
3. Identical results to interpolation (validated)
4. Easy integration: just set use_precomputed=True

Usage:
  model = LifecycleModel(start_age=40, sex='male', use_precomputed=True)
  result = model.calculate(PathwayHRs(cvd=0.8, cancer=1.0, other=1.0))
"""
    )
