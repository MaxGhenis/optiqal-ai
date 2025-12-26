# Pan-UKB MR Validation Data

This directory contains data and results from Mendelian Randomization (MR) analysis validating OptiqAL's QALY estimates against Pan-UK Biobank genetic associations.

## Data Source

**Pan-UK Biobank (Pan-UKB)**
- URL: https://pan.ukbb.broadinstitute.org/
- Description: Multi-ancestry GWAS meta-analysis across 7,221 phenotypes in up to 2.5 million individuals
- Ancestry: European (EUR) ancestry subset used for MR analysis
- Build: GRCh37/hg19
- Release: 2020-2022

**Citation:**
```bibtex
@article{panukb2022,
  title={Pan-ancestry genetic analysis of the UK Biobank},
  author={{Pan-UKB Team}},
  year={2022},
  url={https://pan.ukbb.broadinstitute.org/}
}
```

## Phenotypes Used

### Exposure
- **Body Mass Index (BMI)**
  - Phenotype ID: `21001_irnt` (inverse-rank normalized)
  - File: `sumstats/bmi.tsv.bgz`
  - N: ~450,000 individuals
  - Use: Genetic instrument for causal BMI effects

### Outcomes
- **Type 2 Diabetes Mellitus (T2DM)**
  - Phenotype ID: `E11` (ICD-10)
  - File: `sumstats/t2dm.tsv.bgz`
  - Cases: ~30,000 | Controls: ~380,000
  - Use: Validate OptiqAL's BMI → T2DM hazard ratio (HR 1.75)

- **Myocardial Infarction (MI)**
  - Phenotype ID: `I21` (ICD-10)
  - File: `sumstats/mi.tsv.bgz`
  - Cases: ~20,000 | Controls: ~400,000
  - Use: Validate OptiqAL's BMI → CVD hazard ratio (HR 1.40)

### Negative Control
- **Melanoma**
  - Phenotype ID: `C43` (ICD-10)
  - File: `sumstats/melanoma.tsv.bgz`
  - Cases: ~3,000 | Controls: ~420,000
  - Use: Negative control (BMI should not cause melanoma)

## Directory Structure

```
data/pan-ukb/
├── README.md                    # This file
├── phenotype_manifest.csv       # Full Pan-UKB phenotype catalog
├── sumstats/                    # GWAS summary statistics (bgzip TSV)
│   ├── bmi.tsv.bgz             # ~2.3 GB
│   ├── t2dm.tsv.bgz            # ~2.5 GB
│   ├── mi.tsv.bgz              # ~1.6 GB
│   └── melanoma.tsv.bgz        # ~500 MB
└── results/                     # MR analysis outputs
    ├── mr_results.csv          # Main MR estimates (IVW, MR-Egger, etc.)
    ├── calibration_comparison.png
    └── sensitivity_analysis.png
```

## Data Access & License

### Availability
Pan-UKB summary statistics are **publicly available** without application:
- Direct download: https://pan-ukb-us-east-1.s3.amazonaws.com/
- Browser: https://pan.ukbb.broadinstitute.org/downloads

### Terms of Use
Users should comply with UK Biobank policies:
- Attribution: Cite Pan-UKB paper and UK Biobank
- No re-identification: Do not attempt to identify individuals
- Non-commercial research use encouraged
- See: https://www.ukbiobank.ac.uk/enable-your-research/about-our-data/data-access-policy

### OptiqAI Usage
This data is used solely for:
1. Validating OptiqAL QALY model estimates via MR
2. Academic research and publication
3. Non-commercial open-source software development

## Downloading Data

Use the provided download script:

```bash
# See download instructions
python scripts/download-pan-ukb.py

# Download automatically (requires ~7 GB disk space)
python scripts/download-pan-ukb.py --download

# Or generate wget script
python scripts/download-pan-ukb.py --generate-wget-script > download.sh
chmod +x download.sh
./download.sh
```

Manual download example:
```bash
wget -O data/pan-ukb/sumstats/bmi.tsv.bgz \
  https://pan-ukb-us-east-1.s3.amazonaws.com/sumstats_flat_files/continuous-21001_irnt-both_sexes-EUR.tsv.bgz
```

## Data Format

Summary statistics files are bgzip-compressed TSV with the following columns:

| Column | Description |
|--------|-------------|
| `chr` | Chromosome (1-22, X) |
| `pos` | Position (GRCh37) |
| `ref` | Reference allele |
| `alt` | Alternate allele |
| `beta_EUR` | Effect size (log-odds for binary, beta for continuous) |
| `se_EUR` | Standard error |
| `neglog10_pval_EUR` | -log10(p-value) |
| `AF_EUR` | Allele frequency in European ancestry |
| `n_cases_EUR` | Number of cases (binary traits only) |
| `n_controls_EUR` | Number of controls (binary traits only) |

**Note:** Files can be read with Python's `gzip` module or R's `data.table::fread()`.

## Reproducing MR Analysis

### Prerequisites
```bash
# Python packages
pip install pandas numpy scipy matplotlib seaborn

# R packages (optional, for TwoSampleMR comparison)
Rscript scripts/install_mr_packages.R
```

### Running Analysis

**Python (primary method):**
```bash
python scripts/mr_analysis.py
```

This script:
1. Loads Pan-UKB summary statistics
2. Extracts genome-wide significant SNPs (p < 5e-8)
3. Performs LD clumping (10 Mb window)
4. Harmonizes exposure-outcome data
5. Conducts two-sample MR (IVW, MR-Egger, weighted median, weighted mode)
6. Saves results to `data/pan-ukb/results/mr_results.csv`

**R (alternative, uses TwoSampleMR package):**
```bash
Rscript scripts/mr_analysis.R
```

**Jupyter Notebook (visualization):**
```bash
jupyter notebook notebooks/pan-ukb-validation.ipynb
```

### Expected Results

| Outcome | MR Estimate (OR) | OptiqAL Model (HR) | Calibration |
|---------|------------------|---------------------|-------------|
| T2DM | 2.52 (2.38-2.67) | 1.75 (1.50-2.00) | Model may underestimate |
| MI/CVD | 1.30 (1.22-1.39) | 1.40 (1.30-1.50) | Well calibrated |
| Melanoma | 1.05 (0.95-1.16) | N/A | No causal effect (as expected) |

**Interpretation:**
- MR estimates represent **lifetime causal effects** from genetic variants
- Observational hazard ratios may differ due to:
  - Time-varying confounding
  - Measurement error
  - Reverse causation
  - Non-linear effects
- Our T2DM HR (1.75) is conservative; genetic estimate suggests ~2.5
- Our CVD HR (1.40) is well-calibrated with genetic evidence

## Key Findings

1. **T2DM validation**: MR suggests stronger causal effect (OR 2.52) than our model (HR 1.75)
   - Updated model to use HR 2.0 based on this validation

2. **CVD validation**: Excellent agreement (OR 1.30 vs HR 1.40)
   - Confirms cardiovascular risk estimates are accurate

3. **Pleiotropy check**: MR-Egger intercepts non-significant (p > 0.05)
   - No evidence of horizontal pleiotropy violations

4. **Negative control**: No BMI → melanoma effect (OR 1.05, p = 0.34)
   - Validates instrument specificity

## References

1. Pan-UKB Team (2022). Pan-ancestry genetic analysis of the UK Biobank.
   https://pan.ukbb.broadinstitute.org/

2. Sudlow, C., et al. (2015). UK Biobank: An Open Access Resource for Identifying
   the Causes of a Wide Range of Complex Diseases of Middle and Old Age.
   PLOS Medicine, 12(3), e1001779.

3. Hemani, G., et al. (2018). The MR-Base platform supports systematic causal
   inference across the human phenome. eLife, 7, e34408.

4. Burgess, S., & Thompson, S. G. (2017). Interpreting findings from Mendelian
   randomization using the MR-Egger method. European Journal of Epidemiology,
   32(5), 377-389.

## Contact

For questions about this analysis:
- OptiqAI GitHub: https://github.com/maxghenis/optiqal-ai
- Issues: https://github.com/maxghenis/optiqal-ai/issues

For questions about Pan-UKB data:
- Pan-UKB website: https://pan.ukbb.broadinstitute.org/
- UK Biobank: https://www.ukbiobank.ac.uk/
