#!/usr/bin/env python3
"""
Fetch and analyze MEPS data for quality weight calibration.

This script downloads MEPS Full-Year Consolidated files and extracts:
1. SF-12 PCS/MCS scores -> mapped to EQ-5D utility
2. Chronic condition indicators (diabetes, hypertension, heart disease)
3. Demographics (age, sex, BMI)
4. Panel structure for longitudinal analysis

Data sources:
- MEPS Full-Year Consolidated Files (2017-2022)
- Available in Stata (.dta) format from AHRQ

References:
- Mapping SF-12 to EQ-5D: Franks et al. 2004, Med Care
  EQ-5D = 0.057867 + 0.010367*PCS + 0.00822*MCS - 0.000034*PCS*MCS - 0.01067
"""

import os
import requests
import pandas as pd
import numpy as np
from pathlib import Path
from io import BytesIO
import zipfile

# MEPS data URLs (Full-Year Consolidated Files)
# Format: HC-XXX where XXX is the file number
MEPS_FILES = {
    2022: "https://meps.ahrq.gov/mepsweb/data_files/pufs/h233/h233dta.zip",  # HC-233
    2021: "https://meps.ahrq.gov/mepsweb/data_files/pufs/h224/h224dta.zip",  # HC-224
    2020: "https://meps.ahrq.gov/mepsweb/data_files/pufs/h216/h216dta.zip",  # HC-216
    2019: "https://meps.ahrq.gov/mepsweb/data_files/pufs/h209/h209dta.zip",  # HC-209
    2018: "https://meps.ahrq.gov/mepsweb/data_files/pufs/h201/h201dta.zip",  # HC-201
    2017: "https://meps.ahrq.gov/mepsweb/data_files/pufs/h192/h192dta.zip",  # HC-192
}

# Key variables to extract
VARIABLES = {
    # Demographics
    "DUPERSID": "Person ID",
    "PANEL": "Panel number",
    "APTS": "Panel round",
    "AGE31X": "Age at end of year",
    "SEX": "Sex (1=Male, 2=Female)",
    "RACETHX": "Race/ethnicity",
    "BMINDX53": "BMI",
    "REGION31": "Census region",

    # SF-12 scores (divide by 100 for actual values)
    "ADPCS42": "Physical Component Summary (PCS)",
    "ADMCS42": "Mental Component Summary (MCS)",
    "SFFLAG42": "SF-12 imputation flag",

    # Chronic conditions (1=Yes, 2=No)
    "DIABDX_M18": "Diabetes diagnosis",  # 2018+ naming
    "DIABDX": "Diabetes diagnosis",  # Earlier naming
    "HIBPDX": "High blood pressure diagnosis",
    "CHDDX": "Coronary heart disease",
    "ANGIDX": "Angina",
    "MIDX": "Heart attack (MI)",
    "STRKDX": "Stroke",
    "CANCERDX": "Cancer diagnosis",
    "ARTHDX": "Arthritis diagnosis",
    "ASTHDX": "Asthma diagnosis",

    # Weights
    "PERWT22F": "Person weight (2022)",  # Year-specific
    "PERWT21F": "Person weight (2021)",
    "PERWT20F": "Person weight (2020)",
    "PERWT19F": "Person weight (2019)",
    "PERWT18F": "Person weight (2018)",
    "PERWT17F": "Person weight (2017)",
    "SAQWT22F": "SAQ weight (2022)",
    "SAQWT21F": "SAQ weight (2021)",
    "SAQWT20F": "SAQ weight (2020)",
    "SAQWT19F": "SAQ weight (2019)",
    "SAQWT18F": "SAQ weight (2018)",
    "SAQWT17F": "SAQ weight (2017)",
}


def download_meps_file(year: int, cache_dir: Path) -> pd.DataFrame:
    """Download and load a MEPS full-year consolidated file."""
    cache_file = cache_dir / f"meps_{year}.parquet"

    if cache_file.exists():
        print(f"Loading cached {year} data...")
        return pd.read_parquet(cache_file)

    url = MEPS_FILES.get(year)
    if not url:
        raise ValueError(f"No URL defined for year {year}")

    print(f"Downloading MEPS {year} from {url}...")
    response = requests.get(url, timeout=120)
    response.raise_for_status()

    # Extract Stata file from zip
    with zipfile.ZipFile(BytesIO(response.content)) as zf:
        # Find the .dta file
        dta_files = [f for f in zf.namelist() if f.endswith('.dta')]
        if not dta_files:
            raise ValueError(f"No .dta file found in {url}")

        print(f"Extracting {dta_files[0]}...")
        with zf.open(dta_files[0]) as f:
            df = pd.read_stata(f, convert_categoricals=False)

    # Standardize column names to uppercase
    df.columns = df.columns.str.upper()

    # Add year column
    df["YEAR"] = year

    # Cache as parquet
    cache_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_file)
    print(f"Cached to {cache_file}")

    return df


def map_sf12_to_eq5d(pcs: pd.Series, mcs: pd.Series) -> pd.Series:
    """
    Map SF-12 PCS/MCS to EQ-5D utility score.

    Formula from Franks et al. 2004:
    EQ-5D = 0.057867 + 0.010367*PCS + 0.00822*MCS - 0.000034*PCS*MCS - 0.01067

    Truncate at 1.0 (perfect health ceiling).
    """
    eq5d = (
        0.057867
        + 0.010367 * pcs
        + 0.00822 * mcs
        - 0.000034 * pcs * mcs
        - 0.01067
    )
    return eq5d.clip(upper=1.0)


def process_meps_data(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """Process raw MEPS data to extract quality weights and conditions."""

    # Find available columns
    available_cols = set(df.columns)

    # Extract demographics
    processed = pd.DataFrame()
    processed["person_id"] = df.get("DUPERSID", df.get("DUID", ""))
    processed["year"] = year
    processed["panel"] = df.get("PANEL", np.nan)

    # Age
    age_col = next((c for c in ["AGE31X", "AGE42X", "AGE53X", "APTS"] if c in available_cols), None)
    if age_col:
        processed["age"] = pd.to_numeric(df[age_col], errors="coerce")

    # Sex
    if "SEX" in available_cols:
        processed["sex"] = df["SEX"].map({1: "male", 2: "female"})

    # BMI
    bmi_col = next((c for c in ["BMINDX53", "BMINDX42", "BMINDX31"] if c in available_cols), None)
    if bmi_col:
        processed["bmi"] = pd.to_numeric(df[bmi_col], errors="coerce")
        processed.loc[processed["bmi"] < 0, "bmi"] = np.nan

    # SF-12/VR-12 scores (standard scale: mean=50, sd=10, range ~0-100)
    pcs_col = next((c for c in ["VPCS42", "ADPCS42", "PCS42", "SFPCS42"] if c in available_cols), None)
    mcs_col = next((c for c in ["VMCS42", "ADMCS42", "MCS42", "SFMCS42"] if c in available_cols), None)

    if pcs_col and mcs_col:
        pcs = pd.to_numeric(df[pcs_col], errors="coerce")
        mcs = pd.to_numeric(df[mcs_col], errors="coerce")

        # Filter invalid scores (negative = missing in MEPS)
        pcs = pcs.where((pcs > 0) & (pcs <= 100))
        mcs = mcs.where((mcs > 0) & (mcs <= 100))

        processed["pcs"] = pcs
        processed["mcs"] = mcs
        processed["eq5d"] = map_sf12_to_eq5d(pcs, mcs)

    # Chronic conditions (1=Yes, 2=No, negative=missing)
    condition_cols = {
        "diabetes": ["DIABDX_M18", "DIABDX", "DIABW22", "DIABW21"],
        "hypertension": ["HIBPDX", "HIBPW22", "HIBPW21"],
        "heart_disease": ["CHDDX", "ANGIDX", "MIDX"],
        "stroke": ["STRKDX"],
        "cancer": ["CANCERDX"],
        "arthritis": ["ARTHDX"],
        "asthma": ["ASTHDX"],
    }

    for condition, possible_cols in condition_cols.items():
        col = next((c for c in possible_cols if c in available_cols), None)
        if col:
            values = pd.to_numeric(df[col], errors="coerce")
            processed[condition] = (values == 1).astype(float)
            processed.loc[values < 0, condition] = np.nan

    # Weights
    weight_col = f"PERWT{str(year)[-2:]}F"
    saq_weight_col = f"SAQWT{str(year)[-2:]}F"

    if weight_col in available_cols:
        processed["weight"] = pd.to_numeric(df[weight_col], errors="coerce")
    if saq_weight_col in available_cols:
        processed["saq_weight"] = pd.to_numeric(df[saq_weight_col], errors="coerce")

    return processed


def analyze_quality_weights(df: pd.DataFrame) -> dict:
    """
    Analyze quality weight distribution by age and condition.

    Returns calibration parameters for the lifecycle model.
    """
    results = {}

    # Filter to valid EQ-5D scores
    valid = df[df["eq5d"].notna() & (df["eq5d"] > 0) & (df["eq5d"] <= 1)].copy()

    if len(valid) == 0:
        print("No valid EQ-5D scores found")
        return results

    print(f"\nAnalyzing {len(valid):,} observations with valid EQ-5D scores")

    # Overall statistics
    results["overall"] = {
        "mean": valid["eq5d"].mean(),
        "std": valid["eq5d"].std(),
        "median": valid["eq5d"].median(),
        "p25": valid["eq5d"].quantile(0.25),
        "p75": valid["eq5d"].quantile(0.75),
        "n": len(valid),
    }
    print(f"\nOverall EQ-5D: mean={results['overall']['mean']:.3f}, std={results['overall']['std']:.3f}")

    # By age group
    valid["age_group"] = pd.cut(valid["age"], bins=[18, 30, 40, 50, 60, 70, 80, 100])
    age_stats = valid.groupby("age_group")["eq5d"].agg(["mean", "std", "count"])
    results["by_age"] = age_stats.to_dict()
    print("\nEQ-5D by age group:")
    print(age_stats)

    # By condition
    conditions = ["diabetes", "hypertension", "heart_disease", "stroke", "cancer", "arthritis"]
    results["by_condition"] = {}

    print("\nEQ-5D by condition (mean ± std):")
    for condition in conditions:
        if condition in valid.columns:
            has_condition = valid[valid[condition] == 1]["eq5d"]
            no_condition = valid[valid[condition] == 0]["eq5d"]

            if len(has_condition) > 100 and len(no_condition) > 100:
                decrement = no_condition.mean() - has_condition.mean()
                results["by_condition"][condition] = {
                    "with_condition_mean": has_condition.mean(),
                    "with_condition_std": has_condition.std(),
                    "without_condition_mean": no_condition.mean(),
                    "without_condition_std": no_condition.std(),
                    "decrement": decrement,
                    "n_with": len(has_condition),
                    "n_without": len(no_condition),
                }
                print(f"  {condition:15}: with={has_condition.mean():.3f}±{has_condition.std():.3f} "
                      f"vs without={no_condition.mean():.3f}±{no_condition.std():.3f} "
                      f"(decrement={decrement:.3f})")

    # Within-age-group variance (to estimate individual heterogeneity)
    within_age_std = valid.groupby("age_group")["eq5d"].std().mean()
    results["within_age_std"] = within_age_std
    print(f"\nWithin-age-group std: {within_age_std:.3f}")

    return results


def main():
    """Main analysis pipeline."""
    cache_dir = Path(__file__).parent

    # Download and process multiple years
    all_data = []
    for year in [2022, 2021, 2020, 2019]:
        try:
            raw = download_meps_file(year, cache_dir)
            processed = process_meps_data(raw, year)
            all_data.append(processed)
            print(f"Processed {len(processed):,} records from {year}")
        except Exception as e:
            print(f"Error processing {year}: {e}")
            continue

    if not all_data:
        print("No data loaded!")
        return

    # Combine all years
    df = pd.concat(all_data, ignore_index=True)
    print(f"\nTotal records: {len(df):,}")

    # Filter to adults
    df = df[(df["age"] >= 18) & (df["age"] <= 85)]
    print(f"Adults 18-85: {len(df):,}")

    # Analyze quality weights
    results = analyze_quality_weights(df)

    # Save results
    import json
    output_file = cache_dir / "quality_weight_calibration.json"

    # Convert numpy/pandas types for JSON serialization
    def convert_for_json(obj):
        if isinstance(obj, dict):
            return {convert_for_json(k): convert_for_json(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [convert_for_json(i) for i in obj]
        if isinstance(obj, (np.int64, np.int32)):
            return int(obj)
        if isinstance(obj, (np.float64, np.float32)):
            return float(obj)
        if isinstance(obj, pd.Interval):
            return str(obj)
        return obj

    with open(output_file, "w") as f:
        json.dump(convert_for_json(results), f, indent=2)
    print(f"\nSaved calibration to {output_file}")

    # Save processed data
    df.to_parquet(cache_dir / "meps_combined.parquet")
    print(f"Saved combined data to {cache_dir / 'meps_combined.parquet'}")


if __name__ == "__main__":
    main()
