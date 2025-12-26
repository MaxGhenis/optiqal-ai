#!/usr/bin/env python3
"""
Mendelian Randomization Analysis: BMI → T2DM and BMI → CVD
Uses Pan-UKB GWAS summary statistics to validate OptiqAL QALY estimates

References:
@article{panukb2022,
  title={Pan-ancestry genetic analysis of body mass index and related traits},
  author={{Pan-UKB Team}},
  year={2022},
  url={https://pan.ukbb.broadinstitute.org/}
}
"""

import gzip
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats

# Configuration
DATA_DIR = Path("data/pan-ukb/sumstats")
OUTPUT_DIR = Path("data/pan-ukb/results")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# P-value threshold for genome-wide significance
P_THRESHOLD = 5e-8
# LD clumping parameters
CLUMP_KB = 10000  # 10Mb window
CLUMP_R2 = 0.001  # Conservative LD threshold


def read_panukb(filename: str, chunksize: int = 1_000_000) -> pd.DataFrame:
    """Read Pan-UKB summary statistics (bgzip compressed TSV)"""
    filepath = DATA_DIR / filename
    print(f"Reading: {filepath}")

    # Read in chunks for memory efficiency
    chunks = []
    with gzip.open(filepath, 'rt') as f:
        reader = pd.read_csv(f, sep='\t', chunksize=chunksize)
        for i, chunk in enumerate(reader):
            chunks.append(chunk)
            if (i + 1) % 10 == 0:
                print(f"  Loaded {(i + 1) * chunksize:,} variants...")

    df = pd.concat(chunks, ignore_index=True)
    print(f"  Total: {len(df):,} variants")
    return df


def extract_instruments(df: pd.DataFrame, p_threshold: float = P_THRESHOLD) -> pd.DataFrame:
    """Extract genome-wide significant SNPs as genetic instruments"""
    # Pan-UKB uses neglog10_pval_EUR, convert back to p-value
    if 'neglog10_pval_EUR' in df.columns:
        df['pval_EUR'] = 10 ** (-df['neglog10_pval_EUR'])

    # Filter to significant SNPs
    instruments = df[df['pval_EUR'] < p_threshold].copy()
    print(f"Found {len(instruments):,} genome-wide significant SNPs (p < {p_threshold})")

    # Create unique SNP ID
    instruments['SNP'] = (
        instruments['chr'].astype(str) + ':' +
        instruments['pos'].astype(str) + ':' +
        instruments['ref'] + ':' +
        instruments['alt']
    )

    return instruments


def clump_local(instruments: pd.DataFrame, kb: int = CLUMP_KB) -> pd.DataFrame:
    """Simple distance-based pruning (conservative substitute for LD clumping)"""
    print(f"Clumping with {kb}kb window...")

    # Sort by p-value (best first)
    instruments = instruments.sort_values('pval_EUR').copy()

    keep = []
    kept_positions = {}  # chr -> list of positions

    for _, row in instruments.iterrows():
        chr_key = row['chr']
        pos = row['pos']

        # Check if too close to any kept SNP on same chromosome
        if chr_key in kept_positions:
            distances = np.abs(np.array(kept_positions[chr_key]) - pos)
            if np.any(distances < kb * 1000):
                continue

        # Keep this SNP
        keep.append(row)
        if chr_key not in kept_positions:
            kept_positions[chr_key] = []
        kept_positions[chr_key].append(pos)

    result = pd.DataFrame(keep)
    print(f"After clumping: {len(result):,} independent SNPs")
    return result


def harmonize_data(instruments: pd.DataFrame, outcome: pd.DataFrame) -> pd.DataFrame:
    """Look up instruments in outcome GWAS and harmonize alleles"""
    print("Looking up instruments in outcome GWAS...")

    # Create SNP ID in outcome
    outcome = outcome.copy()
    outcome['SNP'] = (
        outcome['chr'].astype(str) + ':' +
        outcome['pos'].astype(str) + ':' +
        outcome['ref'] + ':' +
        outcome['alt']
    )

    # Handle different column naming for binary vs continuous traits
    # Binary traits (T2DM, MI) use _meta or _EUR suffixes with different structure
    if 'beta_meta_hq' in outcome.columns:
        # Use meta-analysis results (higher quality)
        outcome['beta_out'] = outcome['beta_meta_hq']
        outcome['se_out'] = outcome['se_meta_hq']
        outcome['pval_out'] = 10 ** (-outcome['neglog10_pval_meta_hq'])
        outcome['af_out'] = outcome['af_controls_EUR'] if 'af_controls_EUR' in outcome.columns else 0.5
        print("  Using meta-analysis (HQ) results for binary outcome")
    elif 'beta_EUR' in outcome.columns:
        outcome['beta_out'] = outcome['beta_EUR']
        outcome['se_out'] = outcome['se_EUR']
        if 'neglog10_pval_EUR' in outcome.columns:
            outcome['pval_out'] = 10 ** (-outcome['neglog10_pval_EUR'])
        else:
            outcome['pval_out'] = outcome.get('pval_EUR', 0.5)
        outcome['af_out'] = outcome.get('af_EUR', 0.5)
        print("  Using EUR ancestry results")
    else:
        raise ValueError(f"Cannot find beta columns. Available: {list(outcome.columns)[:10]}")

    # Merge
    merged = instruments.merge(
        outcome[['SNP', 'beta_out', 'se_out', 'pval_out', 'af_out', 'alt', 'ref']],
        on='SNP',
        how='left',
        suffixes=('_exp', '_out')
    )

    # Keep only matched SNPs
    matched = merged.dropna(subset=['beta_out'])
    print(f"Matched {len(matched):,} of {len(instruments):,} instruments")

    # Check allele alignment and flip if needed
    flip = matched['alt_exp'] != matched['alt_out']
    if flip.any():
        matched.loc[flip, 'beta_out'] = -matched.loc[flip, 'beta_out']
        matched.loc[flip, 'af_out'] = 1 - matched.loc[flip, 'af_out']
        print(f"Flipped {flip.sum():,} SNPs for allele alignment")

    return matched


def run_mr(harmonized: pd.DataFrame) -> pd.DataFrame:
    """Run MR analysis using multiple methods"""
    print(f"\n=== Running MR Analysis ===")
    print(f"Using {len(harmonized):,} SNPs")

    # Extract exposure and outcome betas/SEs
    beta_exp = harmonized['beta_EUR'].values  # Exposure always uses EUR
    se_exp = harmonized['se_EUR'].values
    beta_out = harmonized['beta_out'].values  # Outcome uses standardized column
    se_out = harmonized['se_out'].values

    # Per-SNP Wald ratios
    wald_ratio = beta_out / beta_exp
    wald_se = np.abs(se_out / beta_exp)  # Approximate SE

    results = []

    # 1. Inverse Variance Weighted (IVW)
    weights = 1 / wald_se**2
    ivw_beta = np.sum(wald_ratio * weights) / np.sum(weights)
    ivw_se = np.sqrt(1 / np.sum(weights))
    ivw_pval = 2 * stats.norm.sf(np.abs(ivw_beta / ivw_se))

    results.append({
        'method': 'IVW',
        'beta': ivw_beta,
        'se': ivw_se,
        'pval': ivw_pval,
        'nsnp': len(harmonized)
    })
    print(f"IVW: beta = {ivw_beta:.4f}, SE = {ivw_se:.4f}")

    # 2. Weighted Median (robust to up to 50% invalid instruments)
    if len(harmonized) >= 3:
        sorted_idx = np.argsort(wald_ratio)
        cumsum_weights = np.cumsum(weights[sorted_idx]) / np.sum(weights)
        median_idx = np.where(cumsum_weights >= 0.5)[0][0]
        wm_beta = wald_ratio[sorted_idx[median_idx]]
        wm_se = ivw_se * np.sqrt(0.5)  # Approximate
        wm_pval = 2 * stats.norm.sf(np.abs(wm_beta / wm_se))

        results.append({
            'method': 'Weighted Median',
            'beta': wm_beta,
            'se': wm_se,
            'pval': wm_pval,
            'nsnp': len(harmonized)
        })
        print(f"Weighted Median: beta = {wm_beta:.4f}")

    # 3. MR-Egger (tests for pleiotropy)
    if len(harmonized) >= 3:
        # Weighted regression of beta_out on beta_exp
        W = np.diag(1 / se_out**2)
        X = np.column_stack([np.ones(len(beta_exp)), beta_exp])
        XtWX = X.T @ W @ X
        XtWy = X.T @ W @ beta_out

        try:
            coef = np.linalg.solve(XtWX, XtWy)
            residuals = beta_out - X @ coef
            sigma2 = np.sum((residuals**2) * np.diag(W)) / (len(beta_exp) - 2)
            var_coef = sigma2 * np.linalg.inv(XtWX)
            se_coef = np.sqrt(np.diag(var_coef))

            egger_intercept = coef[0]
            egger_beta = coef[1]
            egger_se = se_coef[1]
            egger_pval = 2 * stats.norm.sf(np.abs(egger_beta / egger_se))
            intercept_pval = 2 * stats.norm.sf(np.abs(egger_intercept / se_coef[0]))

            results.append({
                'method': 'MR-Egger',
                'beta': egger_beta,
                'se': egger_se,
                'pval': egger_pval,
                'nsnp': len(harmonized),
                'intercept': egger_intercept,
                'intercept_pval': intercept_pval
            })
            print(f"MR-Egger: beta = {egger_beta:.4f}, intercept = {egger_intercept:.4f} (p = {intercept_pval:.4f})")
        except np.linalg.LinAlgError:
            print("MR-Egger: Could not compute (singular matrix)")

    # Convert to DataFrame and add odds ratios
    df = pd.DataFrame(results)
    df['OR'] = np.exp(df['beta'])
    df['OR_lci'] = np.exp(df['beta'] - 1.96 * df['se'])
    df['OR_uci'] = np.exp(df['beta'] + 1.96 * df['se'])

    return df


def main():
    print("=" * 60)
    print("Pan-UKB MR Validation for OptiqAL")
    print("=" * 60)

    # 1. Read exposure data (BMI)
    print("\n--- Loading BMI exposure GWAS ---")
    bmi = read_panukb("bmi.tsv.bgz")

    # Extract and clump instruments
    bmi_instruments = extract_instruments(bmi)
    bmi_instruments = clump_local(bmi_instruments)

    # Free memory
    del bmi

    # 2. BMI -> T2DM Analysis
    print("\n--- MR: BMI -> Type 2 Diabetes ---")
    t2dm = read_panukb("t2dm.tsv.bgz")
    bmi_t2dm_harmonized = harmonize_data(bmi_instruments, t2dm)
    mr_bmi_t2dm = run_mr(bmi_t2dm_harmonized)
    print("\nResults:")
    print(mr_bmi_t2dm[['method', 'beta', 'se', 'OR', 'OR_lci', 'OR_uci', 'pval', 'nsnp']].to_string())
    del t2dm

    # 3. BMI -> CVD (MI) Analysis
    print("\n--- MR: BMI -> Myocardial Infarction ---")
    mi = read_panukb("mi.tsv.bgz")
    bmi_mi_harmonized = harmonize_data(bmi_instruments, mi)
    mr_bmi_mi = run_mr(bmi_mi_harmonized)
    print("\nResults:")
    print(mr_bmi_mi[['method', 'beta', 'se', 'OR', 'OR_lci', 'OR_uci', 'pval', 'nsnp']].to_string())
    del mi

    # 4. Save results
    print("\n--- Saving Results ---")
    mr_bmi_t2dm['exposure'] = 'BMI'
    mr_bmi_t2dm['outcome'] = 'T2DM'
    mr_bmi_mi['exposure'] = 'BMI'
    mr_bmi_mi['outcome'] = 'MI'

    results_summary = pd.concat([mr_bmi_t2dm, mr_bmi_mi], ignore_index=True)
    results_summary.to_csv(OUTPUT_DIR / "mr_results.csv", index=False)
    print(f"Results saved to: {OUTPUT_DIR / 'mr_results.csv'}")

    # 5. Compare to OptiqAL model
    print("\n" + "=" * 60)
    print("Validation Comparison")
    print("=" * 60)

    print("\nOptiqAL Model Estimates (per 5 BMI unit increase):")
    print("  T2DM: HR ~1.5-2.0 (from meta-analyses)")
    print("  CVD: HR ~1.3-1.5 (from meta-analyses)")

    ivw_t2dm = mr_bmi_t2dm[mr_bmi_t2dm['method'] == 'IVW'].iloc[0]
    ivw_mi = mr_bmi_mi[mr_bmi_mi['method'] == 'IVW'].iloc[0]

    print(f"\nMR Estimates (per 1 SD BMI, ~4-5 units):")
    print(f"  T2DM: OR {ivw_t2dm['OR']:.2f} (95% CI: {ivw_t2dm['OR_lci']:.2f}-{ivw_t2dm['OR_uci']:.2f})")
    print(f"  MI: OR {ivw_mi['OR']:.2f} (95% CI: {ivw_mi['OR_lci']:.2f}-{ivw_mi['OR_uci']:.2f})")

    # Calibration ratios
    model_t2dm_hr = 1.75  # Midpoint of 1.5-2.0
    model_cvd_hr = 1.40   # Midpoint of 1.3-1.5

    print(f"\nCalibration Ratios (MR / Model Midpoint):")
    print(f"  T2DM: {ivw_t2dm['OR'] / model_t2dm_hr:.2f}")
    print(f"  CVD: {ivw_mi['OR'] / model_cvd_hr:.2f}")

    print("\nInterpretation:")
    print("- Ratio ~1.0: Model well-calibrated")
    print("- Ratio > 1.0: Model may underestimate effect")
    print("- Ratio < 1.0: Model may overestimate effect")

    print("\n" + "=" * 60)
    print("Analysis Complete")
    print("=" * 60)

    return results_summary


if __name__ == "__main__":
    results = main()
