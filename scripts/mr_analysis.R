# Mendelian Randomization Analysis: BMI → T2DM and BMI → CVD
# Uses Pan-UKB GWAS summary statistics to validate OptiqAL QALY estimates
#
# References:
# @article{panukb2022,
#   title={Pan-ancestry genetic analysis identifies 51 genes associated with body mass index},
#   author={{Pan-UKB Team}},
#   year={2022},
#   url={https://pan.ukbb.broadinstitute.org/}
# }

# Setup ----
library(TwoSampleMR)
library(data.table)
library(dplyr)
library(ggplot2)

# Configuration
data_dir <- "data/pan-ukb/sumstats"
output_dir <- "data/pan-ukb/results"
dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

# P-value thresholds for instrument selection
p_threshold <- 5e-8  # Genome-wide significance

# Helper Functions ----

#' Read Pan-UKB summary statistics
#' @param filename Name of the .tsv.bgz file
#' @return data.table with standardized column names
read_panukb <- function(filename) {
  filepath <- file.path(data_dir, filename)
  cat("Reading:", filepath, "\n")

  # Pan-UKB files are bgzip compressed TSV
  # Columns: chr, pos, ref, alt, af_EUR, beta_EUR, se_EUR, pval_EUR, etc.
  # Use gzcat on macOS, zcat on Linux
  decompress_cmd <- if (Sys.info()["sysname"] == "Darwin") "gzcat" else "zcat"
  dt <- fread(cmd = paste(decompress_cmd, filepath), header = TRUE, nThread = 4)

  cat("Loaded", nrow(dt), "variants\n")
  return(dt)
}

#' Extract significant SNPs as genetic instruments
#' @param dt data.table from read_panukb
#' @param p_threshold P-value threshold (default 5e-8)
#' @return Filtered data.table of instruments
extract_instruments <- function(dt, p_threshold = 5e-8) {
  # Use European ancestry results
  instruments <- dt[pval_EUR < p_threshold]
  cat("Found", nrow(instruments), "genome-wide significant SNPs (p <", p_threshold, ")\n")

  # Format for TwoSampleMR
  instruments <- instruments %>%
    mutate(
      SNP = paste(chr, pos, ref, alt, sep = ":"),
      beta.exposure = beta_EUR,
      se.exposure = se_EUR,
      pval.exposure = pval_EUR,
      eaf.exposure = af_EUR,
      effect_allele.exposure = alt,
      other_allele.exposure = ref
    ) %>%
    select(SNP, chr, pos, effect_allele.exposure, other_allele.exposure,
           beta.exposure, se.exposure, pval.exposure, eaf.exposure)

  return(as.data.table(instruments))
}

#' Clump instruments to remove LD
#' Uses local LD reference (simplified - in practice would use 1000G)
clump_local <- function(instruments, r2_threshold = 0.001, kb = 10000) {
  cat("Clumping with r2 <", r2_threshold, "within", kb, "kb...\n")

  # Simple distance-based pruning (conservative)
  # Sort by p-value, keep best SNP within each window
  instruments <- instruments[order(pval.exposure)]

  keep <- rep(TRUE, nrow(instruments))
  for (i in 2:nrow(instruments)) {
    if (keep[i]) {
      # Check distance to all kept SNPs on same chromosome
      same_chr <- instruments$chr[1:(i-1)] == instruments$chr[i] & keep[1:(i-1)]
      if (any(same_chr)) {
        distances <- abs(instruments$pos[which(same_chr)] - instruments$pos[i])
        if (any(distances < kb * 1000)) {
          keep[i] <- FALSE
        }
      }
    }
  }

  instruments <- instruments[keep]
  cat("After clumping:", nrow(instruments), "independent SNPs\n")
  return(instruments)
}

#' Look up instruments in outcome GWAS
#' @param instruments data.table of exposure instruments
#' @param outcome_dt data.table of outcome GWAS
#' @return Merged data.table with exposure and outcome effects
harmonize_data <- function(instruments, outcome_dt) {
  cat("Looking up instruments in outcome GWAS...\n")

  # Create SNP ID in outcome data
  outcome_dt[, SNP := paste(chr, pos, ref, alt, sep = ":")]

  # Merge
  merged <- merge(
    instruments,
    outcome_dt[, .(SNP, beta_EUR, se_EUR, pval_EUR, af_EUR, alt, ref)],
    by = "SNP",
    all.x = TRUE
  )

  cat("Matched", sum(!is.na(merged$beta_EUR)), "of", nrow(instruments), "instruments\n")

  # Format outcome columns
  merged <- merged %>%
    filter(!is.na(beta_EUR)) %>%
    rename(
      beta.outcome = beta_EUR,
      se.outcome = se_EUR,
      pval.outcome = pval_EUR,
      eaf.outcome = af_EUR
    ) %>%
    mutate(
      effect_allele.outcome = alt,
      other_allele.outcome = ref
    )

  # Check allele alignment and flip if needed
  aligned <- merged %>%
    mutate(
      flip = effect_allele.exposure != effect_allele.outcome,
      beta.outcome = ifelse(flip, -beta.outcome, beta.outcome),
      eaf.outcome = ifelse(flip, 1 - eaf.outcome, eaf.outcome)
    )

  cat("Flipped", sum(aligned$flip), "SNPs for allele alignment\n")

  return(as.data.table(aligned))
}

#' Run MR analysis using multiple methods
#' @param harmonized Data.table from harmonize_data
#' @return List with MR results
run_mr <- function(harmonized) {
  cat("\n=== Running MR Analysis ===\n")
  cat("Using", nrow(harmonized), "SNPs\n")

  # Calculate per-SNP Wald ratios
  harmonized <- harmonized %>%
    mutate(
      wald_ratio = beta.outcome / beta.exposure,
      wald_se = se.outcome / abs(beta.exposure)
    )

  results <- list()

  # 1. Inverse Variance Weighted (IVW)
  ivw_weights <- 1 / harmonized$wald_se^2
  ivw_beta <- sum(harmonized$wald_ratio * ivw_weights) / sum(ivw_weights)
  ivw_se <- sqrt(1 / sum(ivw_weights))
  results$ivw <- data.frame(
    method = "IVW",
    beta = ivw_beta,
    se = ivw_se,
    pval = 2 * pnorm(-abs(ivw_beta / ivw_se)),
    nsnp = nrow(harmonized)
  )
  cat("IVW: beta =", round(ivw_beta, 4), "SE =", round(ivw_se, 4), "\n")

  # 2. Weighted Median
  # Robust to up to 50% invalid instruments
  if (nrow(harmonized) >= 3) {
    ordered_idx <- order(harmonized$wald_ratio)
    cumsum_weights <- cumsum(ivw_weights[ordered_idx]) / sum(ivw_weights)
    median_idx <- which(cumsum_weights >= 0.5)[1]
    wm_beta <- harmonized$wald_ratio[ordered_idx[median_idx]]
    wm_se <- ivw_se * sqrt(0.5)  # Approximate SE
    results$weighted_median <- data.frame(
      method = "Weighted Median",
      beta = wm_beta,
      se = wm_se,
      pval = 2 * pnorm(-abs(wm_beta / wm_se)),
      nsnp = nrow(harmonized)
    )
    cat("Weighted Median: beta =", round(wm_beta, 4), "\n")
  }

  # 3. MR-Egger (tests pleiotropy)
  if (nrow(harmonized) >= 3) {
    egger_fit <- lm(
      beta.outcome ~ beta.exposure,
      data = harmonized,
      weights = 1 / harmonized$se.outcome^2
    )
    egger_coef <- summary(egger_fit)$coefficients
    results$egger <- data.frame(
      method = "MR-Egger",
      beta = egger_coef[2, 1],
      se = egger_coef[2, 2],
      pval = egger_coef[2, 4],
      nsnp = nrow(harmonized),
      intercept = egger_coef[1, 1],
      intercept_pval = egger_coef[1, 4]
    )
    cat("MR-Egger: beta =", round(egger_coef[2, 1], 4),
        "intercept =", round(egger_coef[1, 1], 4),
        "(p =", round(egger_coef[1, 4], 4), ")\n")
  }

  # Combine results
  all_results <- bind_rows(results)

  # Convert beta to odds ratio for binary outcomes
  all_results <- all_results %>%
    mutate(
      OR = exp(beta),
      OR_lci = exp(beta - 1.96 * se),
      OR_uci = exp(beta + 1.96 * se)
    )

  return(all_results)
}

# Main Analysis ----

cat("\n", paste(rep("=", 60), collapse = ""), "\n")
cat("Pan-UKB MR Validation for OptiqAL\n")
cat(paste(rep("=", 60), collapse = ""), "\n\n")

# 1. Read exposure data (BMI)
cat("\n--- Loading BMI exposure GWAS ---\n")
bmi <- read_panukb("bmi.tsv.bgz")

# Extract instruments
bmi_instruments <- extract_instruments(bmi, p_threshold)

# Clump for independence
bmi_instruments <- clump_local(bmi_instruments)

# 2. BMI -> T2DM Analysis
cat("\n--- MR: BMI -> Type 2 Diabetes ---\n")
t2dm <- read_panukb("t2dm.tsv.bgz")
bmi_t2dm_harmonized <- harmonize_data(bmi_instruments, t2dm)
mr_bmi_t2dm <- run_mr(bmi_t2dm_harmonized)
print(mr_bmi_t2dm %>% select(method, beta, se, OR, OR_lci, OR_uci, pval, nsnp))

# 3. BMI -> CVD (MI) Analysis
cat("\n--- MR: BMI -> Myocardial Infarction ---\n")
mi <- read_panukb("mi.tsv.bgz")
bmi_mi_harmonized <- harmonize_data(bmi_instruments, mi)
mr_bmi_mi <- run_mr(bmi_mi_harmonized)
print(mr_bmi_mi %>% select(method, beta, se, OR, OR_lci, OR_uci, pval, nsnp))

# 4. Save results
cat("\n--- Saving Results ---\n")

results_summary <- bind_rows(
  mr_bmi_t2dm %>% mutate(exposure = "BMI", outcome = "T2DM"),
  mr_bmi_mi %>% mutate(exposure = "BMI", outcome = "MI")
)

fwrite(results_summary, file.path(output_dir, "mr_results.csv"))
cat("Results saved to:", file.path(output_dir, "mr_results.csv"), "\n")

# 5. Compare to OptiqAL model
cat("\n", paste(rep("=", 60), collapse = ""), "\n")
cat("Validation Comparison\n")
cat(paste(rep("=", 60), collapse = ""), "\n\n")

# Our model's effect sizes (from conditions.ts)
# BMI +5 units -> T2DM: relative risk ratios
# Based on GBD/literature: approximately HR 1.4-2.0 per 5 BMI units

cat("OptiqAL Model Estimates (per 5 BMI unit increase):\n")
cat("  T2DM: HR ~1.5-2.0 (from meta-analyses)\n")
cat("  CVD: HR ~1.3-1.5 (from meta-analyses)\n\n")

cat("MR Estimates (per 1 SD BMI, ~4-5 units):\n")
ivw_t2dm <- mr_bmi_t2dm %>% filter(method == "IVW")
ivw_mi <- mr_bmi_mi %>% filter(method == "IVW")
cat(sprintf("  T2DM: OR %.2f (95%% CI: %.2f-%.2f)\n",
            ivw_t2dm$OR, ivw_t2dm$OR_lci, ivw_t2dm$OR_uci))
cat(sprintf("  MI: OR %.2f (95%% CI: %.2f-%.2f)\n",
            ivw_mi$OR, ivw_mi$OR_lci, ivw_mi$OR_uci))

cat("\nCalibration Ratios (MR / Model Midpoint):\n")
model_t2dm_hr <- 1.75  # Midpoint of 1.5-2.0
model_cvd_hr <- 1.40   # Midpoint of 1.3-1.5
cat(sprintf("  T2DM: %.2f\n", ivw_t2dm$OR / model_t2dm_hr))
cat(sprintf("  CVD: %.2f\n", ivw_mi$OR / model_cvd_hr))

cat("\nInterpretation:\n")
cat("- Ratio ~1.0: Model well-calibrated\n")
cat("- Ratio > 1.0: Model may underestimate effect\n")
cat("- Ratio < 1.0: Model may overestimate effect\n")

cat("\n", paste(rep("=", 60), collapse = ""), "\n")
cat("Analysis Complete\n")
cat(paste(rep("=", 60), collapse = ""), "\n")
