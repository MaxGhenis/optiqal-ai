"""Pan-UK Biobank validation workflow for Optiqal."""

from __future__ import annotations

import argparse
import gzip
import os
import shutil
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

@dataclass(frozen=True)
class PanUkbPhenotype:
    key: str
    identifier: str
    description: str
    url: str
    filename: str
    use: str
    approx_size: str


PAN_UKB_PHENOTYPES: dict[str, PanUkbPhenotype] = {
    "bmi": PanUkbPhenotype(
        key="bmi",
        identifier="21001_irnt",
        description="Body Mass Index (BMI)",
        url=(
            "https://pan-ukb-us-east-1.s3.amazonaws.com/"
            "sumstats_flat_files/continuous-21001_irnt-both_sexes-EUR.tsv.bgz"
        ),
        filename="bmi.tsv.bgz",
        use="Exposure variable for MR analysis",
        approx_size="~2.3 GB",
    ),
    "t2dm": PanUkbPhenotype(
        key="t2dm",
        identifier="E11",
        description="Type 2 Diabetes Mellitus",
        url=(
            "https://pan-ukb-us-east-1.s3.amazonaws.com/"
            "sumstats_flat_files/E11-both_sexes-EUR.tsv.bgz"
        ),
        filename="t2dm.tsv.bgz",
        use="Outcome: validate BMI -> T2DM hazard ratio",
        approx_size="~2.5 GB",
    ),
    "mi": PanUkbPhenotype(
        key="mi",
        identifier="I21",
        description="Myocardial Infarction (MI/Heart Attack)",
        url=(
            "https://pan-ukb-us-east-1.s3.amazonaws.com/"
            "sumstats_flat_files/I21-both_sexes-EUR.tsv.bgz"
        ),
        filename="mi.tsv.bgz",
        use="Outcome: validate BMI -> CVD hazard ratio",
        approx_size="~1.6 GB",
    ),
    "melanoma": PanUkbPhenotype(
        key="melanoma",
        identifier="C43",
        description="Melanoma (negative control)",
        url=(
            "https://pan-ukb-us-east-1.s3.amazonaws.com/"
            "sumstats_flat_files/C43-both_sexes-EUR.tsv.bgz"
        ),
        filename="melanoma.tsv.bgz",
        use="Negative control: BMI should not cause melanoma",
        approx_size="~500 MB",
    ),
}

P_THRESHOLD = 5e-8
CLUMP_KB = 10000


@dataclass(frozen=True)
class PanUkbPaths:
    root: Path
    sumstats_dir: Path
    results_dir: Path
    phenotype_manifest_path: Path


def get_default_pan_ukb_data_dir() -> Path:
    explicit_dir = os.environ.get("OPTIQAL_PAN_UKB_DATA_DIR")
    if explicit_dir:
        return Path(explicit_dir).expanduser()

    validation_root = os.environ.get("OPTIQAL_VALIDATION_DATA_DIR")
    if validation_root:
        return Path(validation_root).expanduser() / "pan-ukb"

    cache_home = Path(
        os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
    ).expanduser()
    return cache_home / "optiqal" / "validation" / "pan-ukb"


def build_pan_ukb_paths(data_dir: str | Path | None = None) -> PanUkbPaths:
    root = (
        Path(data_dir).expanduser()
        if data_dir is not None
        else get_default_pan_ukb_data_dir()
    )
    return PanUkbPaths(
        root=root,
        sumstats_dir=root / "sumstats",
        results_dir=root / "results",
        phenotype_manifest_path=root / "phenotype_manifest.csv",
    )


def _selected_phenotypes(
    keys: Sequence[str] | None = None,
) -> list[PanUkbPhenotype]:
    if not keys:
        return list(PAN_UKB_PHENOTYPES.values())

    missing = sorted(set(keys) - set(PAN_UKB_PHENOTYPES))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"Unknown Pan-UKB phenotype key(s): {missing_text}")
    return [PAN_UKB_PHENOTYPES[key] for key in keys]


def render_download_instructions(
    paths: PanUkbPaths, keys: Sequence[str] | None = None
) -> str:
    phenotypes = _selected_phenotypes(keys)
    lines: list[str] = []
    lines.append("=" * 80)
    lines.append("PAN-UKB GWAS SUMMARY STATISTICS DOWNLOAD INSTRUCTIONS")
    lines.append("=" * 80)
    lines.append("")
    lines.append("Current Pan-UKB data directory:")
    lines.append(f"  {paths.root}")
    lines.append("")
    lines.append("Raw sumstats live outside the repo by default.")
    lines.append("Use --data-dir or OPTIQAL_PAN_UKB_DATA_DIR to override.")
    lines.append("")
    lines.append("Required phenotypes for Optiqal MR validation:")
    lines.append("")

    for phenotype in phenotypes:
        lines.append(f"  [{phenotype.key.upper()}] {phenotype.description}")
        lines.append(f"    Phenotype ID: {phenotype.identifier}")
        lines.append(f"    Use: {phenotype.use}")
        lines.append(f"    File: {phenotype.filename}")
        lines.append(f"    URL: {phenotype.url}")
        lines.append("")

    lines.append("=" * 80)
    lines.append("DOWNLOAD METHODS")
    lines.append("=" * 80)
    lines.append("")
    lines.append("Option 1: Packaged CLI")
    lines.append("-" * 40)
    lines.append("  optiqal-pan-ukb download")
    lines.append("")
    lines.append("Option 2: Manual download with wget/curl")
    lines.append("-" * 40)
    for phenotype in phenotypes:
        lines.append(f"# Download {phenotype.description}")
        lines.append(f"wget -O {paths.sumstats_dir / phenotype.filename} \\")
        lines.append(f"  '{phenotype.url}'")
        lines.append("")

    lines.append("Option 3: Generate a wget batch script")
    lines.append("-" * 40)
    lines.append("  optiqal-pan-ukb generate-wget-script > download.sh")
    lines.append("  chmod +x download.sh")
    lines.append("  ./download.sh")
    lines.append("")
    lines.append("Option 4: Repo-local compatibility wrappers")
    lines.append("-" * 40)
    lines.append("  python scripts/download-pan-ukb.py --download")
    lines.append("  python scripts/mr_analysis.py")
    lines.append("")
    lines.append("=" * 80)
    lines.append("FILE SIZES")
    lines.append("=" * 80)
    for phenotype in phenotypes:
        lines.append(f"  {phenotype.filename}: {phenotype.approx_size}")
    lines.append("")
    return "\n".join(lines)


def generate_wget_script(
    paths: PanUkbPaths, keys: Sequence[str] | None = None
) -> str:
    phenotypes = _selected_phenotypes(keys)
    lines = [
        "#!/bin/bash",
        "# Auto-generated wget script for Pan-UKB downloads",
        "",
        f'OUTPUT_DIR="{paths.sumstats_dir}"',
        'mkdir -p "$OUTPUT_DIR"',
        "",
    ]

    for phenotype in phenotypes:
        lines.extend(
            [
                f"# {phenotype.description}",
                f'echo "Downloading {phenotype.description}..."',
                f'wget -O "$OUTPUT_DIR/{phenotype.filename}" \\',
                f'  "{phenotype.url}"',
                "",
            ]
        )

    return "\n".join(lines)


def download_pan_ukb_files(
    paths: PanUkbPaths,
    keys: Sequence[str] | None = None,
    *,
    force: bool = False,
    stdout: object | None = None,
) -> list[Path]:
    phenotypes = _selected_phenotypes(keys)
    paths.sumstats_dir.mkdir(parents=True, exist_ok=True)
    stream = stdout or sys.stdout
    downloaded: list[Path] = []

    for phenotype in phenotypes:
        output_path = paths.sumstats_dir / phenotype.filename

        if output_path.exists() and not force:
            print(f"✓ {phenotype.filename} already exists, skipping", file=stream)
            downloaded.append(output_path)
            continue

        print(f"Downloading {phenotype.description}...", file=stream)
        print(f"  URL: {phenotype.url}", file=stream)
        print(f"  Output: {output_path}", file=stream)

        if output_path.exists():
            output_path.unlink()

        try:
            with urllib.request.urlopen(phenotype.url) as response:
                total_size = int(response.headers.get("content-length", 0))
                if total_size:
                    print(f"  Size: {total_size / 1e9:.2f} GB", file=stream)
                with open(output_path, "wb") as out_file:
                    shutil.copyfileobj(response, out_file)
        except Exception:
            if output_path.exists():
                output_path.unlink()
            raise

        print(f"✓ Downloaded {phenotype.filename}", file=stream)
        downloaded.append(output_path)

    return downloaded


def read_panukb(
    paths: PanUkbPaths, filename: str, chunksize: int = 1_000_000
) -> pd.DataFrame:
    import pandas as pd

    filepath = paths.sumstats_dir / filename
    print(f"Reading: {filepath}")

    chunks = []
    with gzip.open(filepath, "rt") as handle:
        reader = pd.read_csv(handle, sep="\t", chunksize=chunksize)
        for index, chunk in enumerate(reader, start=1):
            chunks.append(chunk)
            if index % 10 == 0:
                print(f"  Loaded {index * chunksize:,} variants...")

    dataframe = pd.concat(chunks, ignore_index=True)
    print(f"  Total: {len(dataframe):,} variants")
    return dataframe


def extract_instruments(
    dataframe: pd.DataFrame, p_threshold: float = P_THRESHOLD
) -> pd.DataFrame:
    if "neglog10_pval_EUR" in dataframe.columns:
        dataframe = dataframe.copy()
        dataframe["pval_EUR"] = 10 ** (-dataframe["neglog10_pval_EUR"])

    instruments = dataframe[dataframe["pval_EUR"] < p_threshold].copy()
    print(
        f"Found {len(instruments):,} genome-wide significant SNPs "
        f"(p < {p_threshold})"
    )

    instruments["SNP"] = (
        instruments["chr"].astype(str)
        + ":"
        + instruments["pos"].astype(str)
        + ":"
        + instruments["ref"]
        + ":"
        + instruments["alt"]
    )
    return instruments


def clump_local(instruments: pd.DataFrame, kb: int = CLUMP_KB) -> pd.DataFrame:
    import numpy as np
    import pandas as pd

    print(f"Clumping with {kb}kb window...")

    instruments = instruments.sort_values("pval_EUR").copy()
    keep = []
    kept_positions: dict[object, list[object]] = {}

    for _, row in instruments.iterrows():
        chromosome = row["chr"]
        position = row["pos"]
        if chromosome in kept_positions:
            distances = np.abs(np.array(kept_positions[chromosome]) - position)
            if np.any(distances < kb * 1000):
                continue

        keep.append(row)
        kept_positions.setdefault(chromosome, []).append(position)

    result = pd.DataFrame(keep)
    print(f"After clumping: {len(result):,} independent SNPs")
    return result


_PALINDROMIC_PAIRS = (frozenset(("A", "T")), frozenset(("C", "G")))


def _is_palindromic(ref: str, alt: str) -> bool:
    return frozenset((ref.upper(), alt.upper())) in _PALINDROMIC_PAIRS


def harmonize_data(
    instruments: pd.DataFrame,
    outcome: pd.DataFrame,
    *,
    drop_palindromic: bool = True,
) -> pd.DataFrame:
    """Align exposure instruments against outcome summary statistics.

    Matches on chromosome/position, recovers allele-flipped variants,
    and by default drops palindromic SNPs (A/T, C/G) whose strand cannot
    be resolved unambiguously from allele codes alone.

    Parameters
    ----------
    drop_palindromic:
        When True (default), palindromic SNPs are removed after allele
        alignment. Set False only when the caller has already resolved
        strand orientation via another channel.
    """
    print("Looking up instruments in outcome GWAS...")
    instruments = instruments.copy()
    outcome = outcome.copy()
    for dataframe in (instruments, outcome):
        dataframe["chr"] = dataframe["chr"].astype(str)
        dataframe["pos"] = dataframe["pos"].astype(str)
        dataframe["ref"] = dataframe["ref"].astype(str).str.upper()
        dataframe["alt"] = dataframe["alt"].astype(str).str.upper()
        dataframe["variant_position"] = dataframe["chr"] + ":" + dataframe["pos"]

    if "beta_meta_hq" in outcome.columns:
        outcome["beta_out"] = outcome["beta_meta_hq"]
        outcome["se_out"] = outcome["se_meta_hq"]
        outcome["pval_out"] = 10 ** (-outcome["neglog10_pval_meta_hq"])
        outcome["af_out"] = (
            outcome["af_controls_EUR"]
            if "af_controls_EUR" in outcome.columns
            else 0.5
        )
        print("  Using meta-analysis (HQ) results for binary outcome")
    elif "beta_EUR" in outcome.columns:
        outcome["beta_out"] = outcome["beta_EUR"]
        outcome["se_out"] = outcome["se_EUR"]
        if "neglog10_pval_EUR" in outcome.columns:
            outcome["pval_out"] = 10 ** (-outcome["neglog10_pval_EUR"])
        else:
            outcome["pval_out"] = outcome.get("pval_EUR", 0.5)
        outcome["af_out"] = outcome.get("af_EUR", 0.5)
        print("  Using EUR ancestry results")
    else:
        available_columns = ", ".join(outcome.columns[:10])
        raise ValueError(f"Cannot find beta columns. Available: {available_columns}")

    merged = instruments.merge(
        outcome[
            [
                "variant_position",
                "beta_out",
                "se_out",
                "pval_out",
                "af_out",
                "alt",
                "ref",
            ]
        ],
        on="variant_position",
        how="left",
        suffixes=("_exp", "_out"),
    )

    allele_match = (
        (merged["ref_exp"] == merged["ref_out"])
        & (merged["alt_exp"] == merged["alt_out"])
    ) | (
        (merged["ref_exp"] == merged["alt_out"])
        & (merged["alt_exp"] == merged["ref_out"])
    )
    matched = merged.loc[merged["beta_out"].notna() & allele_match].copy()
    matched["needs_flip"] = (
        (matched["ref_exp"] == matched["alt_out"])
        & (matched["alt_exp"] == matched["ref_out"])
    )
    matched["allele_match_rank"] = matched["needs_flip"].astype(int)
    matched = matched.sort_values(["SNP", "allele_match_rank"]).drop_duplicates(
        subset=["SNP"], keep="first"
    )

    print(f"Matched {len(matched):,} of {len(instruments):,} instruments")

    flip = matched["needs_flip"]
    if flip.any():
        matched.loc[flip, "beta_out"] = -matched.loc[flip, "beta_out"]
        matched.loc[flip, "af_out"] = 1 - matched.loc[flip, "af_out"]
        print(f"Flipped {int(flip.sum()):,} SNPs for allele alignment")

    if drop_palindromic and len(matched):
        palindromic_mask = [
            _is_palindromic(ref, alt)
            for ref, alt in zip(matched["ref_exp"], matched["alt_exp"])
        ]
        dropped = int(sum(palindromic_mask))
        if dropped:
            print(f"Dropping {dropped:,} palindromic SNPs (A/T, C/G)")
            matched = matched.loc[[not p for p in palindromic_mask]].copy()

    return matched


def _weighted_median(values, weights) -> float:
    import numpy as np

    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    order = np.argsort(values)
    cumsum = np.cumsum(weights[order]) / np.sum(weights)
    idx = int(np.searchsorted(cumsum, 0.5, side="left"))
    idx = min(idx, len(values) - 1)
    return float(values[order[idx]])


def _weighted_median_bootstrap_se(
    beta_exp,
    se_exp,
    beta_out,
    se_out,
    weights,
    *,
    n_boot: int,
    seed: int,
) -> float:
    """Parametric bootstrap SE for the weighted-median MR estimator.

    Follows Bowden et al. (2016): resample SNP-wise exposure and outcome
    effects from their reported normal distributions, recompute the
    weighted median on each replicate with the original weights held
    fixed, and return the standard deviation of the replicate estimates.
    """
    import numpy as np

    beta_exp = np.asarray(beta_exp, dtype=float)
    se_exp = np.asarray(se_exp, dtype=float)
    beta_out = np.asarray(beta_out, dtype=float)
    se_out = np.asarray(se_out, dtype=float)
    weights = np.asarray(weights, dtype=float)

    rng = np.random.default_rng(seed)
    sampled_exp = rng.normal(beta_exp, se_exp, size=(n_boot, len(beta_exp)))
    sampled_out = rng.normal(beta_out, se_out, size=(n_boot, len(beta_out)))
    sampled_ratios = sampled_out / sampled_exp

    medians = np.empty(n_boot)
    for replicate in range(n_boot):
        medians[replicate] = _weighted_median(sampled_ratios[replicate], weights)
    return float(np.std(medians, ddof=1))


def run_mr(
    harmonized: pd.DataFrame,
    *,
    weighted_median_n_boot: int = 1000,
    weighted_median_seed: int = 42,
) -> pd.DataFrame:
    import numpy as np
    import pandas as pd
    from scipy import stats

    print("\n=== Running MR Analysis ===")
    print(f"Using {len(harmonized):,} SNPs")

    beta_exp = harmonized["beta_EUR"].values
    se_exp = harmonized["se_EUR"].values
    beta_out = harmonized["beta_out"].values
    se_out = harmonized["se_out"].values

    if np.any(np.isclose(beta_exp, 0.0)):
        raise ValueError("Cannot run MR with zero-valued exposure effects")

    wald_ratio = beta_out / beta_exp
    wald_se = np.sqrt(
        (se_out**2 / beta_exp**2)
        + ((beta_out**2 * se_exp**2) / beta_exp**4)
    )

    results: list[dict[str, float | int | str]] = []

    weights = 1 / wald_se**2
    ivw_beta = np.sum(wald_ratio * weights) / np.sum(weights)
    ivw_se = np.sqrt(1 / np.sum(weights))
    ivw_pval = 2 * stats.norm.sf(np.abs(ivw_beta / ivw_se))
    results.append(
        {
            "method": "IVW",
            "beta": ivw_beta,
            "se": ivw_se,
            "pval": ivw_pval,
            "nsnp": len(harmonized),
        }
    )
    print(f"IVW: beta = {ivw_beta:.4f}, SE = {ivw_se:.4f}")

    if len(harmonized) >= 3:
        wm_beta = _weighted_median(wald_ratio, weights)
        wm_se = _weighted_median_bootstrap_se(
            beta_exp,
            se_exp,
            beta_out,
            se_out,
            weights,
            n_boot=weighted_median_n_boot,
            seed=weighted_median_seed,
        )
        wm_pval = 2 * stats.norm.sf(np.abs(wm_beta / wm_se))

        results.append(
            {
                "method": "Weighted Median",
                "beta": wm_beta,
                "se": wm_se,
                "pval": wm_pval,
                "nsnp": len(harmonized),
            }
        )
        print(f"Weighted Median: beta = {wm_beta:.4f}")

        combined_outcome_variance = se_out**2 + (ivw_beta**2 * se_exp**2)
        weights_matrix = np.diag(1 / combined_outcome_variance)
        design = np.column_stack([np.ones(len(beta_exp)), beta_exp])
        xtwx = design.T @ weights_matrix @ design
        xtwy = design.T @ weights_matrix @ beta_out

        try:
            coef = np.linalg.solve(xtwx, xtwy)
            residuals = beta_out - design @ coef
            sigma2 = np.sum((residuals**2) * np.diag(weights_matrix)) / (
                len(beta_exp) - 2
            )
            var_coef = sigma2 * np.linalg.inv(xtwx)
            se_coef = np.sqrt(np.diag(var_coef))

            egger_intercept = coef[0]
            egger_beta = coef[1]
            egger_se = se_coef[1]
            egger_pval = 2 * stats.norm.sf(np.abs(egger_beta / egger_se))
            intercept_pval = 2 * stats.norm.sf(
                np.abs(egger_intercept / se_coef[0])
            )

            results.append(
                {
                    "method": "MR-Egger",
                    "beta": egger_beta,
                    "se": egger_se,
                    "pval": egger_pval,
                    "nsnp": len(harmonized),
                    "intercept": egger_intercept,
                    "intercept_pval": intercept_pval,
                }
            )
            print(
                "MR-Egger: beta = "
                f"{egger_beta:.4f}, intercept = {egger_intercept:.4f} "
                f"(p = {intercept_pval:.4f})"
            )
        except np.linalg.LinAlgError:
            print("MR-Egger: Could not compute (singular matrix)")

    results_frame = pd.DataFrame(results)
    results_frame["OR"] = np.exp(results_frame["beta"])
    results_frame["OR_lci"] = np.exp(results_frame["beta"] - 1.96 * results_frame["se"])
    results_frame["OR_uci"] = np.exp(results_frame["beta"] + 1.96 * results_frame["se"])
    return results_frame


def render_validation_summary(results_summary: pd.DataFrame) -> str:
    ivw_t2dm = results_summary[
        (results_summary["method"] == "IVW")
        & (results_summary["outcome"] == "T2DM")
    ].iloc[0]
    ivw_mi = results_summary[
        (results_summary["method"] == "IVW")
        & (results_summary["outcome"] == "MI")
    ].iloc[0]

    model_t2dm_hr = 1.75
    model_cvd_hr = 1.40
    lines = [
        "=" * 60,
        "Validation Comparison",
        "=" * 60,
        "",
        "Optiqal Model Estimates (per 5 BMI unit increase):",
        "  T2DM: HR ~1.5-2.0 (from meta-analyses)",
        "  CVD: HR ~1.3-1.5 (from meta-analyses)",
        "",
        "MR Estimates (per 1 SD BMI, ~4-5 units):",
        (
            "  T2DM: OR "
            f"{ivw_t2dm['OR']:.2f} "
            f"(95% CI: {ivw_t2dm['OR_lci']:.2f}-{ivw_t2dm['OR_uci']:.2f})"
        ),
        (
            "  MI: OR "
            f"{ivw_mi['OR']:.2f} "
            f"(95% CI: {ivw_mi['OR_lci']:.2f}-{ivw_mi['OR_uci']:.2f})"
        ),
        "",
        "Calibration Ratios (MR / Model Midpoint):",
        f"  T2DM: {ivw_t2dm['OR'] / model_t2dm_hr:.2f}",
        f"  CVD: {ivw_mi['OR'] / model_cvd_hr:.2f}",
        "",
        "Interpretation:",
        "- Ratio ~1.0: Model well-calibrated",
        "- Ratio > 1.0: Model may underestimate effect",
        "- Ratio < 1.0: Model may overestimate effect",
        "",
        "=" * 60,
        "Analysis Complete",
        "=" * 60,
    ]
    return "\n".join(lines)


def run_pan_ukb_mr_analysis(
    paths: PanUkbPaths,
    *,
    chunksize: int = 1_000_000,
) -> pd.DataFrame:
    import pandas as pd

    paths.results_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Pan-UKB MR Validation for Optiqal")
    print("=" * 60)

    print("\n--- Loading BMI exposure GWAS ---")
    bmi = read_panukb(paths, "bmi.tsv.bgz", chunksize=chunksize)
    bmi_instruments = clump_local(extract_instruments(bmi))
    del bmi

    print("\n--- MR: BMI -> Type 2 Diabetes ---")
    t2dm = read_panukb(paths, "t2dm.tsv.bgz", chunksize=chunksize)
    bmi_t2dm_harmonized = harmonize_data(bmi_instruments, t2dm)
    mr_bmi_t2dm = run_mr(bmi_t2dm_harmonized)
    print("\nResults:")
    print(
        mr_bmi_t2dm[
            ["method", "beta", "se", "OR", "OR_lci", "OR_uci", "pval", "nsnp"]
        ].to_string()
    )
    del t2dm

    print("\n--- MR: BMI -> Myocardial Infarction ---")
    mi = read_panukb(paths, "mi.tsv.bgz", chunksize=chunksize)
    bmi_mi_harmonized = harmonize_data(bmi_instruments, mi)
    mr_bmi_mi = run_mr(bmi_mi_harmonized)
    print("\nResults:")
    print(
        mr_bmi_mi[
            ["method", "beta", "se", "OR", "OR_lci", "OR_uci", "pval", "nsnp"]
        ].to_string()
    )
    del mi

    mr_bmi_t2dm["exposure"] = "BMI"
    mr_bmi_t2dm["outcome"] = "T2DM"
    mr_bmi_mi["exposure"] = "BMI"
    mr_bmi_mi["outcome"] = "MI"
    results_summary = pd.concat([mr_bmi_t2dm, mr_bmi_mi], ignore_index=True)
    output_path = paths.results_dir / "mr_results.csv"
    results_summary.to_csv(output_path, index=False)
    print(f"\nResults saved to: {output_path}")
    print("")
    print(render_validation_summary(results_summary))
    return results_summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help=(
            "Pan-UKB validation root directory. Defaults to "
            "$OPTIQAL_PAN_UKB_DATA_DIR or ~/.cache/optiqal/validation/pan-ukb."
        ),
    )

    parser = argparse.ArgumentParser(
        prog="optiqal-pan-ukb",
        description="Retrieve and analyze Pan-UKB validation data for Optiqal.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    describe_parser = subparsers.add_parser(
        "describe",
        parents=[parent],
        help="Show download instructions and current data-directory policy.",
    )
    describe_parser.add_argument(
        "phenotypes",
        nargs="*",
        choices=sorted(PAN_UKB_PHENOTYPES),
        help="Optional phenotype subset to describe.",
    )

    download_parser = subparsers.add_parser(
        "download",
        parents=[parent],
        help="Download the required Pan-UKB summary-stat files.",
    )
    download_parser.add_argument(
        "phenotypes",
        nargs="*",
        choices=sorted(PAN_UKB_PHENOTYPES),
        help="Optional phenotype subset to download.",
    )
    download_parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download files even if they already exist.",
    )

    wget_parser = subparsers.add_parser(
        "generate-wget-script",
        parents=[parent],
        help="Emit a shell script that downloads the selected files with wget.",
    )
    wget_parser.add_argument(
        "phenotypes",
        nargs="*",
        choices=sorted(PAN_UKB_PHENOTYPES),
        help="Optional phenotype subset to include.",
    )

    analyze_parser = subparsers.add_parser(
        "analyze",
        parents=[parent],
        help="Run the packaged BMI->T2DM / BMI->MI MR validation workflow.",
    )
    analyze_parser.add_argument(
        "--chunksize",
        type=int,
        default=1_000_000,
        help="Chunk size used when reading bgzip summary-stat files.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    paths = build_pan_ukb_paths(args.data_dir)

    if args.command == "describe":
        print(render_download_instructions(paths, args.phenotypes))
        return 0

    if args.command == "download":
        download_pan_ukb_files(
            paths,
            keys=args.phenotypes,
            force=args.force,
        )
        print("")
        print(f"Download complete. Files are under: {paths.sumstats_dir}")
        return 0

    if args.command == "generate-wget-script":
        print(generate_wget_script(paths, args.phenotypes))
        return 0

    if args.command == "analyze":
        run_pan_ukb_mr_analysis(paths, chunksize=args.chunksize)
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
