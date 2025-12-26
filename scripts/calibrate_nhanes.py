#!/usr/bin/env python3
"""
NHANES Microdata Calibration for Optiqal QALY Calculator

This script downloads NHANES 2017-2020 data to compute the expected population-level
hazard ratio (HR) for risk factors. Life tables already include people with conditions
like smoking, obesity, diabetes, etc. To avoid double-counting when applying individual
HRs, we need calibration factors.

The calibration approach:
1. Download NHANES microdata with sample weights
2. Compute each individual's combined HR based on their risk factors
3. Calculate weighted average HR by age group and sex
4. These become calibration factors: adjusted_baseline = life_table_LE * calibration_factor

This ensures that when we apply individual HRs, the population average matches life tables.

Output:
- data/nhanes/raw/*.XPT (cached NHANES files)
- data/nhanes/processed.parquet (processed microdata)
- data/nhanes/calibration.json (calibration factors)
- src/lib/evidence/baseline/calibration.ts (TypeScript export)

Usage:
    python scripts/calibrate_nhanes.py
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.request import urlretrieve

import numpy as np
import pandas as pd

# =============================================================================
# Configuration
# =============================================================================

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data" / "nhanes"
RAW_DIR = DATA_DIR / "raw"

# NHANES data files to download
# Using 2017-2018 and 2019-March 2020 (pre-pandemic) cycles
# URLs from https://wwwn.cdc.gov/nchs/nhanes/search/datapage.aspx
# Note: Must use wwwn.cdc.gov subdomain for direct file downloads
NHANES_FILES = {
    # 2017-2018 cycle
    "DEMO_J": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DEMO_J.xpt",
    "BMX_J": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BMX_J.xpt",
    "SMQ_J": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/SMQ_J.xpt",
    "PAQ_J": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/PAQ_J.xpt",
    "SLQ_J": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/SLQ_J.xpt",
    "DIQ_J": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DIQ_J.xpt",
    "BPQ_J": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BPQ_J.xpt",
    # 2019-March 2020 (pre-pandemic) cycle
    "P_DEMO": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_DEMO.xpt",
    "P_BMX": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_BMX.xpt",
    "P_SMQ": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_SMQ.xpt",
    "P_PAQ": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_PAQ.xpt",
    "P_SLQ": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_SLQ.xpt",
    "P_DIQ": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_DIQ.xpt",
    "P_BPQ": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_BPQ.xpt",
}

# Hazard ratios matching TypeScript code (src/lib/evidence/baseline/index.ts)
HAZARD_RATIOS = {
    "bmi": {
        "underweight": 1.51,  # BMI <18.5
        "normal": 1.0,        # BMI 18.5-25
        "overweight": 1.11,   # BMI 25-30
        "obese1": 1.44,       # BMI 30-35
        "obese2": 1.92,       # BMI 35-40
        "obese3": 2.76,       # BMI 40+
    },
    "exercise": {
        "none": 1.31,         # 0 hrs/week
        "low": 1.14,          # <2.5 hrs/week
        "recommended": 1.0,   # 2.5-5 hrs/week
        "high": 0.94,         # 5-7.5 hrs/week
        "veryHigh": 0.96,     # 7.5+ hrs/week
    },
    "sleep": {
        "short": 1.12,        # <6 hrs/night
        "normal": 1.0,        # 6-9 hrs/night
        "long": 1.30,         # >9 hrs/night
    },
    "smoking": {
        "yes": 2.8,           # Current smoker
        "no": 1.0,            # Non-smoker
    },
    "diabetes": {
        "yes": 1.80,          # Has diabetes
        "no": 1.0,            # No diabetes
    },
    "hypertension": {
        "yes": 1.50,          # Has hypertension
        "no": 1.0,            # No hypertension
    },
}

# Age groups for calibration
AGE_GROUPS = [
    (18, 24),
    (25, 34),
    (35, 44),
    (45, 54),
    (55, 64),
    (65, 74),
    (75, 84),
    (85, 100),
]


# =============================================================================
# Download Functions
# =============================================================================

def download_nhanes_files() -> Dict[str, Path]:
    """
    Download NHANES XPT files if not already cached.

    Returns:
        Dictionary mapping file names to local paths
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    file_paths = {}
    for name, url in NHANES_FILES.items():
        local_path = RAW_DIR / f"{name}.XPT"
        file_paths[name] = local_path

        if local_path.exists():
            print(f"  [cached] {name}")
        else:
            print(f"  [downloading] {name}...")
            try:
                urlretrieve(url, local_path)
                print(f"    -> {local_path.name}")
            except Exception as e:
                print(f"    ERROR: {e}")
                # Remove partial file if download failed
                if local_path.exists():
                    local_path.unlink()

    return file_paths


def load_and_merge_cycle(
    demo_file: Path,
    bmx_file: Path,
    smq_file: Path,
    paq_file: Path,
    slq_file: Path,
    diq_file: Path,
    bpq_file: Path,
    cycle_name: str,
) -> pd.DataFrame:
    """
    Load and merge all NHANES files for a single cycle.

    Args:
        *_file: Paths to XPT files for each component
        cycle_name: Name of the NHANES cycle (for logging)

    Returns:
        Merged DataFrame with all variables
    """
    print(f"  Loading {cycle_name}...")

    # Load demographics (main file with weights)
    demo = pd.read_sas(demo_file)

    # Select relevant columns
    # RIDAGEYR: Age in years
    # RIAGENDR: Sex (1=Male, 2=Female)
    # WTMEC2YR: MEC exam sample weight (for 2017-2020 we'll combine)
    # For pre-pandemic data, also check for WTMECPRP
    weight_col = "WTMECPRP" if "WTMECPRP" in demo.columns else "WTMEC2YR"
    demo = demo[["SEQN", "RIDAGEYR", "RIAGENDR", weight_col]].copy()
    demo = demo.rename(columns={weight_col: "weight"})

    # Load body measures (BMI)
    bmx = pd.read_sas(bmx_file)
    # BMXBMI: Body Mass Index
    bmx = bmx[["SEQN", "BMXBMI"]].copy()

    # Load smoking questionnaire
    smq = pd.read_sas(smq_file)
    # SMQ020: Ever smoked 100+ cigarettes (1=Yes, 2=No)
    # SMQ040: Current smoking (1=Every day, 2=Some days, 3=Not at all)
    smq = smq[["SEQN", "SMQ020", "SMQ040"]].copy()

    # Load physical activity
    paq = pd.read_sas(paq_file)
    # PAQ605: Vigorous work activity (1=Yes, 2=No)
    # PAQ610: Days vigorous work per week
    # PAD615: Minutes vigorous work per day
    # PAQ620: Moderate work activity (1=Yes, 2=No)
    # PAQ625: Days moderate work per week
    # PAD630: Minutes moderate work per day
    # PAQ650: Vigorous recreational activity
    # PAQ655: Days vigorous recreation per week
    # PAD660: Minutes vigorous recreation per day
    # PAQ665: Moderate recreational activity
    # PAQ670: Days moderate recreation per week
    # PAD675: Minutes moderate recreation per day
    paq_cols = ["SEQN"]
    for col in ["PAQ605", "PAQ610", "PAD615", "PAQ620", "PAQ625", "PAD630",
                "PAQ650", "PAQ655", "PAD660", "PAQ665", "PAQ670", "PAD675"]:
        if col in paq.columns:
            paq_cols.append(col)
    paq = paq[paq_cols].copy()

    # Load sleep
    slq = pd.read_sas(slq_file)
    # SLD012: Hours of sleep (weekdays/work days) or SLD010H
    sleep_col = "SLD012" if "SLD012" in slq.columns else "SLD010H"
    if sleep_col in slq.columns:
        slq = slq[["SEQN", sleep_col]].copy()
        slq = slq.rename(columns={sleep_col: "sleep_hours"})
    else:
        slq = slq[["SEQN"]].copy()
        slq["sleep_hours"] = np.nan

    # Load diabetes
    diq = pd.read_sas(diq_file)
    # DIQ010: Doctor told you have diabetes (1=Yes, 2=No, 3=Borderline)
    diq = diq[["SEQN", "DIQ010"]].copy()

    # Load blood pressure
    bpq = pd.read_sas(bpq_file)
    # BPQ020: Told have high blood pressure (1=Yes, 2=No)
    bpq = bpq[["SEQN", "BPQ020"]].copy()

    # Merge all on SEQN
    df = demo.merge(bmx, on="SEQN", how="left")
    df = df.merge(smq, on="SEQN", how="left")
    df = df.merge(paq, on="SEQN", how="left")
    df = df.merge(slq, on="SEQN", how="left")
    df = df.merge(diq, on="SEQN", how="left")
    df = df.merge(bpq, on="SEQN", how="left")

    df["cycle"] = cycle_name

    print(f"    Loaded {len(df)} records")
    return df


# =============================================================================
# Data Processing Functions
# =============================================================================

def compute_exercise_hours_per_week(row: pd.Series) -> float:
    """
    Compute total exercise hours per week from NHANES physical activity data.

    Combines vigorous work, moderate work, vigorous recreation, and moderate recreation.
    Vigorous activity is counted at 2x intensity (per MET equivalents).

    Returns:
        Hours of moderate-equivalent exercise per week
    """
    total_minutes = 0.0

    # Helper to safely get value
    def safe_get(col, default=0):
        if col not in row.index:
            return default
        val = row[col]
        if pd.isna(val) or val in [77, 99, 7777, 9999]:  # NHANES missing/refused codes
            return default
        return val

    # Vigorous work activity (counted as 2x)
    if safe_get("PAQ605") == 1:  # Yes, does vigorous work
        days = safe_get("PAQ610")
        mins = safe_get("PAD615")
        total_minutes += days * mins * 2  # 2x for vigorous

    # Moderate work activity
    if safe_get("PAQ620") == 1:  # Yes, does moderate work
        days = safe_get("PAQ625")
        mins = safe_get("PAD630")
        total_minutes += days * mins

    # Vigorous recreational activity (counted as 2x)
    if safe_get("PAQ650") == 1:  # Yes, does vigorous recreation
        days = safe_get("PAQ655")
        mins = safe_get("PAD660")
        total_minutes += days * mins * 2  # 2x for vigorous

    # Moderate recreational activity
    if safe_get("PAQ665") == 1:  # Yes, does moderate recreation
        days = safe_get("PAQ670")
        mins = safe_get("PAD675")
        total_minutes += days * mins

    return total_minutes / 60.0  # Convert to hours


def classify_bmi(bmi: float) -> str:
    """Classify BMI into categories matching TypeScript code."""
    if pd.isna(bmi):
        return "normal"  # Default assumption
    if bmi < 18.5:
        return "underweight"
    if bmi < 25:
        return "normal"
    if bmi < 30:
        return "overweight"
    if bmi < 35:
        return "obese1"
    if bmi < 40:
        return "obese2"
    return "obese3"


def classify_exercise(hours_per_week: float) -> str:
    """Classify exercise level matching TypeScript code."""
    if pd.isna(hours_per_week) or hours_per_week == 0:
        return "none"
    if hours_per_week < 2.5:
        return "low"
    if hours_per_week < 5:
        return "recommended"
    if hours_per_week < 7.5:
        return "high"
    return "veryHigh"


def classify_sleep(hours_per_night: float) -> str:
    """Classify sleep duration matching TypeScript code."""
    if pd.isna(hours_per_night):
        return "normal"  # Default assumption
    if hours_per_night < 6:
        return "short"
    if hours_per_night <= 9:
        return "normal"
    return "long"


def is_current_smoker(smq020: float, smq040: float) -> bool:
    """
    Determine if currently smoking.

    SMQ020=1 (smoked 100+ cigarettes) AND SMQ040 in [1, 2] (every day or some days)
    """
    if pd.isna(smq020) or smq020 != 1:
        return False
    if pd.isna(smq040):
        return False
    return smq040 in [1, 2]


def has_diabetes(diq010: float) -> bool:
    """DIQ010=1 means told by doctor have diabetes."""
    return not pd.isna(diq010) and diq010 == 1


def has_hypertension(bpq020: float) -> bool:
    """BPQ020=1 means told by doctor have high blood pressure."""
    return not pd.isna(bpq020) and bpq020 == 1


def compute_individual_hr(row: pd.Series) -> float:
    """
    Compute combined hazard ratio for an individual based on their risk factors.

    Returns:
        Multiplicative combined HR
    """
    hr = 1.0

    # BMI
    bmi_cat = classify_bmi(row.get("BMXBMI"))
    hr *= HAZARD_RATIOS["bmi"][bmi_cat]

    # Exercise
    exercise_hours = row.get("exercise_hours", 0)
    exercise_cat = classify_exercise(exercise_hours)
    hr *= HAZARD_RATIOS["exercise"][exercise_cat]

    # Sleep
    sleep_hours = row.get("sleep_hours")
    sleep_cat = classify_sleep(sleep_hours)
    hr *= HAZARD_RATIOS["sleep"][sleep_cat]

    # Smoking
    smoker = is_current_smoker(row.get("SMQ020"), row.get("SMQ040"))
    hr *= HAZARD_RATIOS["smoking"]["yes" if smoker else "no"]

    # Diabetes
    diabetes = has_diabetes(row.get("DIQ010"))
    hr *= HAZARD_RATIOS["diabetes"]["yes" if diabetes else "no"]

    # Hypertension
    hypertension = has_hypertension(row.get("BPQ020"))
    hr *= HAZARD_RATIOS["hypertension"]["yes" if hypertension else "no"]

    return hr


def process_nhanes_data(file_paths: Dict[str, Path]) -> pd.DataFrame:
    """
    Process NHANES data from both cycles.

    Returns:
        Cleaned DataFrame with risk factor categories and individual HRs
    """
    print("\nLoading NHANES cycles...")

    # Load 2017-2018 cycle
    df_2017 = load_and_merge_cycle(
        file_paths["DEMO_J"],
        file_paths["BMX_J"],
        file_paths["SMQ_J"],
        file_paths["PAQ_J"],
        file_paths["SLQ_J"],
        file_paths["DIQ_J"],
        file_paths["BPQ_J"],
        "2017-2018",
    )

    # Load 2019-March 2020 cycle (pre-pandemic)
    df_2019 = load_and_merge_cycle(
        file_paths["P_DEMO"],
        file_paths["P_BMX"],
        file_paths["P_SMQ"],
        file_paths["P_PAQ"],
        file_paths["P_SLQ"],
        file_paths["P_DIQ"],
        file_paths["P_BPQ"],
        "2019-2020",
    )

    # Combine cycles
    df = pd.concat([df_2017, df_2019], ignore_index=True)
    print(f"\nCombined: {len(df)} records")

    # Filter to adults 18+
    df = df[df["RIDAGEYR"] >= 18].copy()
    print(f"Adults 18+: {len(df)} records")

    # Filter to valid weights
    df = df[df["weight"] > 0].copy()
    print(f"With valid weights: {len(df)} records")

    # Map sex
    df["sex"] = df["RIAGENDR"].map({1: "male", 2: "female"})
    df = df[df["sex"].notna()].copy()
    print(f"With valid sex: {len(df)} records")

    # Compute exercise hours
    print("\nComputing exercise hours...")
    df["exercise_hours"] = df.apply(compute_exercise_hours_per_week, axis=1)

    # Compute risk factor categories
    print("Computing risk factor categories...")
    df["bmi_category"] = df["BMXBMI"].apply(classify_bmi)
    df["exercise_category"] = df["exercise_hours"].apply(classify_exercise)
    df["sleep_category"] = df["sleep_hours"].apply(classify_sleep)
    df["is_smoker"] = df.apply(
        lambda r: is_current_smoker(r.get("SMQ020"), r.get("SMQ040")), axis=1
    )
    df["has_diabetes"] = df["DIQ010"].apply(has_diabetes)
    df["has_hypertension"] = df["BPQ020"].apply(has_hypertension)

    # Compute individual hazard ratios
    print("Computing individual hazard ratios...")
    df["individual_hr"] = df.apply(compute_individual_hr, axis=1)

    # Assign age groups
    df["age_group"] = pd.cut(
        df["RIDAGEYR"],
        bins=[ag[0] for ag in AGE_GROUPS] + [AGE_GROUPS[-1][1] + 1],
        labels=[f"{ag[0]}-{ag[1]}" for ag in AGE_GROUPS],
        right=False,
    )

    return df


# =============================================================================
# Calibration Computation
# =============================================================================

def compute_calibration_factors(df: pd.DataFrame) -> Dict:
    """
    Compute weighted average hazard ratios by age group and sex.

    These are the expected population-level HRs that life tables implicitly include.

    Returns:
        Dictionary with calibration factors and summary statistics
    """
    print("\nComputing calibration factors...")

    calibration = {
        "metadata": {
            "source": "NHANES 2017-March 2020 (pre-pandemic)",
            "n_total": len(df),
            "description": (
                "Expected population-level hazard ratios. Life tables already include "
                "people with these conditions, so we use these factors to avoid double-counting. "
                "To get individual-adjusted baseline: baseline_LE * (1/calibration_factor) * individual_HR"
            ),
        },
        "by_age_sex": {},
        "by_age": {},
        "by_sex": {},
        "overall": {},
    }

    # Overall weighted average
    overall_hr = np.average(df["individual_hr"], weights=df["weight"])
    calibration["overall"]["weighted_mean_hr"] = round(overall_hr, 4)
    calibration["overall"]["n"] = len(df)

    # By sex
    for sex in ["male", "female"]:
        sex_df = df[df["sex"] == sex]
        if len(sex_df) > 0:
            sex_hr = np.average(sex_df["individual_hr"], weights=sex_df["weight"])
            calibration["by_sex"][sex] = {
                "weighted_mean_hr": round(sex_hr, 4),
                "n": len(sex_df),
            }

    # By age group
    for age_group in df["age_group"].cat.categories:
        age_df = df[df["age_group"] == age_group]
        if len(age_df) > 0:
            age_hr = np.average(age_df["individual_hr"], weights=age_df["weight"])
            calibration["by_age"][str(age_group)] = {
                "weighted_mean_hr": round(age_hr, 4),
                "n": len(age_df),
            }

    # By age group AND sex (primary output)
    for age_group in df["age_group"].cat.categories:
        calibration["by_age_sex"][str(age_group)] = {}
        for sex in ["male", "female"]:
            subset = df[(df["age_group"] == age_group) & (df["sex"] == sex)]
            if len(subset) > 0:
                hr = np.average(subset["individual_hr"], weights=subset["weight"])
                calibration["by_age_sex"][str(age_group)][sex] = {
                    "weighted_mean_hr": round(hr, 4),
                    "n": len(subset),
                }

    # Prevalence statistics
    calibration["prevalence"] = {
        "smoking": round((df["is_smoker"] * df["weight"]).sum() / df["weight"].sum(), 4),
        "diabetes": round((df["has_diabetes"] * df["weight"]).sum() / df["weight"].sum(), 4),
        "hypertension": round((df["has_hypertension"] * df["weight"]).sum() / df["weight"].sum(), 4),
        "bmi_categories": {},
        "exercise_categories": {},
        "sleep_categories": {},
    }

    for cat in df["bmi_category"].unique():
        mask = df["bmi_category"] == cat
        prev = (mask * df["weight"]).sum() / df["weight"].sum()
        calibration["prevalence"]["bmi_categories"][cat] = round(prev, 4)

    for cat in df["exercise_category"].unique():
        mask = df["exercise_category"] == cat
        prev = (mask * df["weight"]).sum() / df["weight"].sum()
        calibration["prevalence"]["exercise_categories"][cat] = round(prev, 4)

    for cat in df["sleep_category"].unique():
        mask = df["sleep_category"] == cat
        prev = (mask * df["weight"]).sum() / df["weight"].sum()
        calibration["prevalence"]["sleep_categories"][cat] = round(prev, 4)

    return calibration


# =============================================================================
# Output Generation
# =============================================================================

def generate_typescript_file(calibration: Dict, output_path: Path):
    """
    Generate TypeScript file exporting calibration factors.

    The TypeScript code will use these to adjust baseline life expectancy:
    adjusted_baseline = life_table_LE * (1 / calibration_factor) * individual_HR

    This ensures population average matches life tables while still allowing
    individual variation.
    """
    ts_content = '''/**
 * NHANES Calibration Factors for Baseline QALY Calculation
 *
 * Generated from NHANES 2017-March 2020 (pre-pandemic) microdata.
 *
 * These factors represent the expected population-level hazard ratio (HR)
 * for mortality risk factors. Life tables already include people with
 * conditions like smoking, obesity, diabetes, etc. To avoid double-counting
 * when applying individual HRs, we calibrate:
 *
 * adjusted_individual_HR = individual_HR / population_HR
 *
 * This ensures that:
 * - A person with average risk factors gets the life table expectancy
 * - A person with below-average risk gets longer expectancy
 * - A person with above-average risk gets shorter expectancy
 *
 * Usage:
 *   const calibrationFactor = getCalibrationFactor(age, sex);
 *   const adjustedHR = individualHR / calibrationFactor;
 *   const adjustedLE = baselineLE * hrToLifeExpectancyMultiplier(adjustedHR);
 */

export interface CalibrationData {
  weightedMeanHR: number;
  n: number;
}

/**
 * Calibration factors by age group and sex.
 * Key format: "ageStart-ageEnd" -> { male: CalibrationData, female: CalibrationData }
 */
export const CALIBRATION_BY_AGE_SEX: Record<
  string,
  Record<"male" | "female", CalibrationData>
> = '''

    # Format the by_age_sex data
    by_age_sex_formatted = {}
    for age_group, sex_data in calibration["by_age_sex"].items():
        by_age_sex_formatted[age_group] = {}
        for sex, data in sex_data.items():
            by_age_sex_formatted[age_group][sex] = {
                "weightedMeanHR": data["weighted_mean_hr"],
                "n": data["n"],
            }

    ts_content += json.dumps(by_age_sex_formatted, indent=2) + ";\n\n"

    ts_content += '''/**
 * Overall calibration factors by sex only.
 */
export const CALIBRATION_BY_SEX: Record<"male" | "female", CalibrationData> = '''

    by_sex_formatted = {}
    for sex, data in calibration["by_sex"].items():
        by_sex_formatted[sex] = {
            "weightedMeanHR": data["weighted_mean_hr"],
            "n": data["n"],
        }

    ts_content += json.dumps(by_sex_formatted, indent=2) + ";\n\n"

    ts_content += f'''/**
 * Overall population calibration factor.
 */
export const CALIBRATION_OVERALL: CalibrationData = {{
  weightedMeanHR: {calibration["overall"]["weighted_mean_hr"]},
  n: {calibration["overall"]["n"]},
}};

/**
 * Age group boundaries for lookup.
 */
const AGE_GROUP_BOUNDS: Array<[number, number, string]> = [
  [18, 24, "18-24"],
  [25, 34, "25-34"],
  [35, 44, "35-44"],
  [45, 54, "45-54"],
  [55, 64, "55-64"],
  [65, 74, "65-74"],
  [75, 84, "75-84"],
  [85, 100, "85-100"],
];

/**
 * Get the age group string for a given age.
 */
function getAgeGroup(age: number): string | null {{
  for (const [min, max, group] of AGE_GROUP_BOUNDS) {{
    if (age >= min && age <= max) {{
      return group;
    }}
  }}
  return null;
}}

/**
 * Get the calibration factor (expected population HR) for a given age and sex.
 *
 * @param age - Age in years (18+)
 * @param sex - "male" or "female"
 * @returns The weighted mean HR for this demographic, or overall if not found
 */
export function getCalibrationFactor(
  age: number,
  sex: "male" | "female" | "other"
): number {{
  // Use binary sex for lookup (average for "other")
  if (sex === "other") {{
    const male = getCalibrationFactor(age, "male");
    const female = getCalibrationFactor(age, "female");
    return (male + female) / 2;
  }}

  const ageGroup = getAgeGroup(age);
  if (ageGroup && CALIBRATION_BY_AGE_SEX[ageGroup]?.[sex]) {{
    return CALIBRATION_BY_AGE_SEX[ageGroup][sex].weightedMeanHR;
  }}

  // Fallback to sex-only calibration
  if (CALIBRATION_BY_SEX[sex]) {{
    return CALIBRATION_BY_SEX[sex].weightedMeanHR;
  }}

  // Ultimate fallback
  return CALIBRATION_OVERALL.weightedMeanHR;
}}

/**
 * Prevalence statistics from NHANES (for reference/validation).
 */
export const POPULATION_PREVALENCE = '''

    ts_content += json.dumps(calibration["prevalence"], indent=2) + ";\n"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(ts_content)

    print(f"  Saved TypeScript file: {output_path}")


def save_outputs(df: pd.DataFrame, calibration: Dict):
    """Save all output files."""
    print("\nSaving outputs...")

    # Create directories
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Save processed data as parquet
    processed_path = DATA_DIR / "processed.parquet"
    # Select columns to save
    save_cols = [
        "SEQN", "RIDAGEYR", "sex", "weight", "cycle", "age_group",
        "BMXBMI", "bmi_category",
        "exercise_hours", "exercise_category",
        "sleep_hours", "sleep_category",
        "is_smoker", "has_diabetes", "has_hypertension",
        "individual_hr",
    ]
    df_save = df[save_cols].copy()

    # Try to save as parquet, fall back to CSV if pyarrow not available
    try:
        df_save.to_parquet(processed_path)
        print(f"  Saved processed data: {processed_path}")
    except Exception as e:
        print(f"  Warning: Could not save parquet ({e}), saving as CSV instead")
        csv_path = DATA_DIR / "processed.csv"
        df_save.to_csv(csv_path, index=False)
        print(f"  Saved processed data: {csv_path}")

    # Save calibration as JSON
    calibration_path = DATA_DIR / "calibration.json"
    with open(calibration_path, "w") as f:
        json.dump(calibration, f, indent=2)
    print(f"  Saved calibration factors: {calibration_path}")

    # Generate TypeScript file
    ts_path = REPO_ROOT / "src" / "lib" / "evidence" / "baseline" / "calibration.ts"
    generate_typescript_file(calibration, ts_path)


def print_summary(calibration: Dict):
    """Print summary statistics."""
    print("\n" + "=" * 60)
    print("CALIBRATION SUMMARY")
    print("=" * 60)

    print(f"\nTotal sample size: {calibration['metadata']['n_total']:,}")
    print(f"Overall weighted mean HR: {calibration['overall']['weighted_mean_hr']:.3f}")

    print("\nBy Sex:")
    for sex, data in calibration["by_sex"].items():
        print(f"  {sex.capitalize()}: HR = {data['weighted_mean_hr']:.3f} (n={data['n']:,})")

    print("\nBy Age Group and Sex:")
    for age_group, sex_data in calibration["by_age_sex"].items():
        male_hr = sex_data.get("male", {}).get("weighted_mean_hr")
        female_hr = sex_data.get("female", {}).get("weighted_mean_hr")
        male_str = f"{male_hr:.3f}" if male_hr is not None else "N/A"
        female_str = f"{female_hr:.3f}" if female_hr is not None else "N/A"
        print(f"  {age_group}: Male={male_str}, Female={female_str}")

    print("\nPrevalence (weighted):")
    print(f"  Current smokers: {calibration['prevalence']['smoking']*100:.1f}%")
    print(f"  Diabetes: {calibration['prevalence']['diabetes']*100:.1f}%")
    print(f"  Hypertension: {calibration['prevalence']['hypertension']*100:.1f}%")

    print("\n  BMI categories:")
    for cat, prev in sorted(calibration["prevalence"]["bmi_categories"].items()):
        print(f"    {cat}: {prev*100:.1f}%")

    print("\n  Exercise categories:")
    for cat, prev in sorted(calibration["prevalence"]["exercise_categories"].items()):
        print(f"    {cat}: {prev*100:.1f}%")


# =============================================================================
# Main
# =============================================================================

def main():
    """Main entry point."""
    print("=" * 60)
    print("NHANES Microdata Calibration for Optiqal")
    print("=" * 60)

    # Download NHANES files
    print("\nDownloading NHANES files...")
    file_paths = download_nhanes_files()

    # Check all files exist
    missing = [name for name, path in file_paths.items() if not path.exists()]
    if missing:
        print(f"\nERROR: Missing files: {missing}")
        print("Please check your internet connection and try again.")
        sys.exit(1)

    # Process data
    df = process_nhanes_data(file_paths)

    # Compute calibration factors
    calibration = compute_calibration_factors(df)

    # Save outputs
    save_outputs(df, calibration)

    # Print summary
    print_summary(calibration)

    print("\n" + "=" * 60)
    print("Calibration complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
