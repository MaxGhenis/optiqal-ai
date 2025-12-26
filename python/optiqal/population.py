"""
Population sampling module for personalized QALY predictions.

Uses MEPS microdata to sample from P(all_variables | known_variables).
As users enter more profile information, the conditional distribution narrows.
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Literal, Any
from dataclasses import dataclass, field


# Cache for loaded population data
_POPULATION_CACHE: Optional[pd.DataFrame] = None


def _load_population_data() -> pd.DataFrame:
    """Load and prepare the MEPS population data."""
    global _POPULATION_CACHE

    if _POPULATION_CACHE is not None:
        return _POPULATION_CACHE

    data_dir = Path(__file__).parent / "data" / "meps"

    # Load all years
    dfs = []
    for year in [2019, 2020, 2021, 2022]:
        parquet_file = data_dir / f"meps_{year}.parquet"
        if parquet_file.exists():
            df = pd.read_parquet(parquet_file)
            df["year"] = year
            dfs.append(df)

    if not dfs:
        raise FileNotFoundError("No MEPS parquet files found")

    raw = pd.concat(dfs, ignore_index=True)

    # Extract and standardize key variables
    pop = pd.DataFrame()

    # Demographics
    pop["age"] = raw.get("AGE31X", raw.get("AGE42X", raw.get("APTS31X")))
    pop["sex"] = raw.get("SEX").map({1: "male", 2: "female"})

    # Race/ethnicity
    race_col = raw.get("RACETHX", raw.get("RACEV2X"))
    pop["race"] = race_col.map({
        1: "hispanic",
        2: "white",
        3: "black",
        4: "asian",
        5: "other"
    })

    # BMI
    bmi_col = None
    for col in ["BMINDX53", "BMINDX42", "BMINDX31"]:
        if col in raw.columns:
            bmi_col = raw[col]
            break
    if bmi_col is not None:
        pop["bmi"] = bmi_col.replace([-1, -7, -8, -9], np.nan)

    # Smoking (ADSMOK42: 1=current, 2=former, 3=never)
    if "ADSMOK42" in raw.columns:
        pop["smoking"] = raw["ADSMOK42"].map({
            1: "current",
            2: "former",
            3: "never"
        })

    # Education
    if "HIDEG" in raw.columns:
        pop["education"] = raw["HIDEG"].map({
            1: "no_degree",
            2: "ged",
            3: "high_school",
            4: "bachelors",
            5: "masters",
            6: "doctorate",
            7: "other"
        })

    # Income category (federal poverty level)
    for col in ["POVCAT22", "POVCAT21", "POVCAT20", "POVCAT19"]:
        if col in raw.columns:
            pop["income_category"] = raw[col].map({
                1: "poor",        # < 100% FPL
                2: "near_poor",   # 100-125% FPL
                3: "low_income",  # 125-200% FPL
                4: "middle",      # 200-400% FPL
                5: "high"         # > 400% FPL
            })
            break

    # Employment
    for col in ["EMPST53", "EMPST42", "EMPST31"]:
        if col in raw.columns:
            pop["employment"] = raw[col].map({
                1: "employed",
                2: "job_waiting",
                3: "unemployed",
                4: "retired",
                34: "retired",  # Some years code differently
            })
            break

    # Marital status
    for col in ["MARRY53X", "MARRY42X", "MARRY31X"]:
        if col in raw.columns:
            pop["marital"] = raw[col].map({
                1: "married",
                2: "widowed",
                3: "divorced",
                4: "separated",
                5: "never_married",
                -7: np.nan,
                -8: np.nan,
                -9: np.nan,
            })
            break

    # Insurance
    for col in ["INSCOV22", "INSCOV21", "INSCOV20", "INSCOV19"]:
        if col in raw.columns:
            pop["insurance"] = raw[col].map({
                1: "private",
                2: "public",
                3: "uninsured"
            })
            break

    # Chronic conditions (1=Yes, 2=No, -1=Inapplicable, etc.)
    condition_mapping = {
        "diabetes": ["DIABDX_M18", "DIABDX"],
        "hypertension": ["HIBPDX"],
        "heart_disease": ["CHDDX", "ANGIDX", "MIDX"],  # Any of these
        "stroke": ["STRKDX"],
        "cancer": ["CANCERDX"],
        "arthritis": ["ARTHDX"],
        "asthma": ["ASTHDX"],
    }

    for cond, cols in condition_mapping.items():
        cond_val = pd.Series(False, index=raw.index)
        for col in cols:
            if col in raw.columns:
                cond_val = cond_val | (raw[col] == 1)
        pop[cond] = cond_val

    # SF-12 / EQ-5D quality score
    pcs = None
    mcs = None
    for pcs_col, mcs_col in [("VPCS42", "VMCS42"), ("ADPCS42", "ADMCS42")]:
        if pcs_col in raw.columns and mcs_col in raw.columns:
            pcs = raw[pcs_col].replace([-1, -7, -8, -9], np.nan)
            mcs = raw[mcs_col].replace([-1, -7, -8, -9], np.nan)
            break

    if pcs is not None and mcs is not None:
        # SF-12 to EQ-5D mapping (Franks et al. 2004)
        pop["eq5d"] = (
            0.057867 + 0.010367 * pcs + 0.00822 * mcs
            - 0.000034 * pcs * mcs - 0.01067
        ).clip(upper=1.0)

    # Sample weights (use most recent available)
    for col in ["PERWT22F", "PERWT21F", "PERWT20F", "PERWT19F"]:
        if col in raw.columns:
            pop["weight"] = raw[col].replace([-1], 0).fillna(0)
            break

    # Filter to valid observations
    pop = pop.dropna(subset=["age", "sex"])
    pop = pop[pop["age"] >= 18]  # Adults only
    pop = pop[pop["age"] <= 100]

    _POPULATION_CACHE = pop
    return pop


@dataclass
class ProfileConstraints:
    """Constraints on population profile from user inputs."""

    # Exact matches
    age: Optional[int] = None
    age_range: Optional[tuple] = None  # (min, max) inclusive
    sex: Optional[Literal["male", "female"]] = None

    # Categorical
    race: Optional[str] = None
    smoking: Optional[Literal["current", "former", "never"]] = None
    education: Optional[str] = None
    income_category: Optional[str] = None
    employment: Optional[str] = None
    marital: Optional[str] = None
    insurance: Optional[str] = None

    # Continuous with tolerance
    bmi: Optional[float] = None
    bmi_tolerance: float = 3.0  # +/- kg/m²

    # Conditions (True = has, False = doesn't have, None = unknown)
    diabetes: Optional[bool] = None
    hypertension: Optional[bool] = None
    heart_disease: Optional[bool] = None
    stroke: Optional[bool] = None
    cancer: Optional[bool] = None
    arthritis: Optional[bool] = None
    asthma: Optional[bool] = None


def sample_from_population(
    constraints: ProfileConstraints,
    n_samples: int = 1000,
    rng: Optional[np.random.Generator] = None,
    use_weights: bool = True,
    min_pool_size: int = 50,
    use_propensity_weights: bool = True,
) -> pd.DataFrame:
    """
    Sample profiles from population matching given constraints.

    Uses a hybrid approach:
    1. Apply hard constraints (sex, conditions) that must match exactly
    2. Apply soft constraints (age, BMI) with propensity weighting
    3. When pool is small, use propensity weighting to match rare profiles

    Args:
        constraints: Profile constraints from user inputs
        n_samples: Number of samples to draw
        rng: Random number generator
        use_weights: Whether to use survey weights
        min_pool_size: Minimum matching observations before using propensity weighting
        use_propensity_weights: If True, use propensity weighting for rare profiles

    Returns:
        DataFrame of sampled profiles
    """
    if rng is None:
        rng = np.random.default_rng()

    pop = _load_population_data()

    # Phase 1: Apply HARD constraints (must match exactly)
    # These are binary and must be respected
    hard_mask = pd.Series(True, index=pop.index)
    hard_constraints = []

    # Sex is fundamental
    if constraints.sex:
        hard_mask = hard_mask & (pop["sex"] == constraints.sex)
        hard_constraints.append("sex")

    # Conditions are known facts about the person
    for cond in ["diabetes", "hypertension", "heart_disease", "stroke", "cancer", "arthritis"]:
        value = getattr(constraints, cond, None)
        if value is not None:
            hard_mask = hard_mask & (pop[cond] == value)
            hard_constraints.append(cond)

    hard_pool = pop[hard_mask]

    if len(hard_pool) < min_pool_size:
        # Pool too small even with just hard constraints
        # Fall back to just sex
        hard_mask = pd.Series(True, index=pop.index)
        if constraints.sex:
            hard_mask = hard_mask & (pop["sex"] == constraints.sex)
        hard_pool = pop[hard_mask]
        hard_constraints = ["sex"] if constraints.sex else []

    # Phase 2: Apply SOFT constraints via propensity weighting
    # These shift the distribution toward the target profile
    propensity_weights = np.ones(len(hard_pool))

    # Age: weight by proximity to target
    if constraints.age is not None:
        age_diff = np.abs(hard_pool["age"].values - constraints.age)
        # Gaussian kernel with width 5 years
        age_weights = np.exp(-0.5 * (age_diff / 5) ** 2)
        propensity_weights *= age_weights
    elif constraints.age_range is not None:
        in_range = (hard_pool["age"].values >= constraints.age_range[0]) & \
                   (hard_pool["age"].values <= constraints.age_range[1])
        propensity_weights *= np.where(in_range, 1.0, 0.2)

    # BMI: weight by proximity to target
    if constraints.bmi is not None and "bmi" in hard_pool.columns:
        bmi_vals = hard_pool["bmi"].fillna(constraints.bmi).values
        bmi_diff = np.abs(bmi_vals - constraints.bmi)
        bmi_weights = np.exp(-0.5 * (bmi_diff / constraints.bmi_tolerance) ** 2)
        propensity_weights *= bmi_weights

    # Smoking: weight toward target category
    if constraints.smoking is not None and "smoking" in hard_pool.columns:
        smoking_match = (hard_pool["smoking"] == constraints.smoking).values
        propensity_weights *= np.where(smoking_match, 3.0, 0.5)

    # Race: weight toward target category
    if constraints.race is not None and "race" in hard_pool.columns:
        race_match = (hard_pool["race"] == constraints.race).values
        propensity_weights *= np.where(race_match, 2.0, 0.5)

    # Combine with survey weights
    if use_weights and "weight" in hard_pool.columns:
        survey_weights = hard_pool["weight"].values
        survey_weights = np.maximum(survey_weights, 0)
    else:
        survey_weights = np.ones(len(hard_pool))

    final_weights = propensity_weights * survey_weights
    final_weights = final_weights / final_weights.sum()

    # Sample
    indices = rng.choice(len(hard_pool), size=n_samples, replace=True, p=final_weights)
    samples = hard_pool.iloc[indices].copy()

    # Compute effective sample size (ESS) to measure weighting quality
    ess = 1.0 / np.sum(final_weights ** 2) if final_weights.sum() > 0 else 0

    samples["_pool_size"] = len(hard_pool)
    samples["_effective_sample_size"] = ess
    samples["_constraints_applied"] = ",".join(hard_constraints)

    return samples


def get_conditional_distribution(
    constraints: ProfileConstraints,
    variable: str,
) -> Dict[str, float]:
    """
    Get the distribution of a variable conditional on constraints.

    Args:
        constraints: Profile constraints
        variable: Variable to get distribution for

    Returns:
        Dict mapping values to probabilities
    """
    samples = sample_from_population(constraints, n_samples=5000)

    if variable not in samples.columns:
        return {}

    counts = samples[variable].value_counts(normalize=True)
    return counts.to_dict()


def estimate_remaining_qalys(
    constraints: ProfileConstraints,
    n_simulations: int = 1000,
    discount_rate: float = 0.03,
    random_state: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Estimate remaining QALYs for a profile with uncertainty.

    This samples from the population conditional on known attributes,
    then runs lifetime simulations for each sampled profile.

    Args:
        constraints: Known profile attributes
        n_simulations: Number of Monte Carlo samples
        discount_rate: Annual discount rate
        random_state: Random seed

    Returns:
        Dict with expected QALYs, confidence intervals, and metadata
    """
    from .markov import simulate_lifetime_markov, HealthState

    rng = np.random.default_rng(random_state)

    # Sample profiles from population
    samples = sample_from_population(constraints, n_samples=n_simulations, rng=rng)

    qalys_list = []
    life_years_list = []

    for _, row in samples.iterrows():
        # Create initial health state from sampled profile
        initial_state = HealthState(
            diabetes=bool(row.get("diabetes", False)),
            hypertension=bool(row.get("hypertension", False)),
            heart_disease=bool(row.get("heart_disease", False)),
            stroke=bool(row.get("stroke", False)),
            cancer=bool(row.get("cancer", False)),
            arthritis=bool(row.get("arthritis", False)),
        )

        result = simulate_lifetime_markov(
            start_age=int(row["age"]),
            sex=row["sex"],
            initial_state=initial_state,
            discount_rate=discount_rate,
            rng=rng,
        )

        qalys_list.append(result.qalys)
        life_years_list.append(result.life_years)

    qalys = np.array(qalys_list)
    life_years = np.array(life_years_list)

    # Count how many constraints were known
    known_count = sum(1 for attr in [
        "age", "sex", "race", "smoking", "bmi", "education",
        "diabetes", "hypertension", "heart_disease", "stroke"
    ] if getattr(constraints, attr, None) is not None)

    certainty = "low" if known_count <= 2 else "medium" if known_count <= 5 else "high"

    return {
        "expected_qalys": float(np.mean(qalys)),
        "qaly_std": float(np.std(qalys)),
        "qaly_median": float(np.median(qalys)),
        "qaly_ci95": (float(np.percentile(qalys, 2.5)), float(np.percentile(qalys, 97.5))),
        "qaly_p10_p90": (float(np.percentile(qalys, 10)), float(np.percentile(qalys, 90))),
        "expected_life_years": float(np.mean(life_years)),
        "n_simulations": n_simulations,
        "pool_size": int(samples["_pool_size"].iloc[0]),
        "certainty_level": certainty,
        "known_attributes": known_count,
    }


if __name__ == "__main__":
    # Test the population sampling
    print("Testing population sampling")
    print("=" * 60)

    # Load data
    pop = _load_population_data()
    print(f"Loaded {len(pop)} observations")
    print(f"Columns: {list(pop.columns)}")
    print()

    # Test sampling with constraints
    constraints = ProfileConstraints(
        age=50,
        sex="male",
        smoking="never",
    )

    samples = sample_from_population(constraints, n_samples=100)
    print(f"Sampled {len(samples)} profiles for 50yo male never-smoker")
    print(f"Pool size: {samples['_pool_size'].iloc[0]}")
    print(f"Constraints applied: {samples['_constraints_applied'].iloc[0]}")
    print()

    # Check condition distribution in sample
    print("Condition prevalence in sample:")
    for cond in ["diabetes", "hypertension", "heart_disease"]:
        print(f"  {cond}: {samples[cond].mean()*100:.1f}%")
