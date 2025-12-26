# Pan-UK Biobank Validation Plan

## Overview

Use freely available Pan-UKB GWAS summary statistics to validate OptiqAL's QALY estimates without UK Biobank data access fees.

## What's Available (Free)

[Pan-UKB](https://pan.ukbb.broadinstitute.org/) provides:
- **7,228 phenotypes** across 6 ancestry groups
- GWAS summary statistics for each phenotype
- No application, no fees, no restrictions

### Relevant Phenotype Categories

| Category | Examples | Use for Validation |
|----------|----------|-------------------|
| Biomarkers | BMI, BP, cholesterol, HbA1c | Verify mechanism effect sizes |
| ICD-10 codes | E11 (T2DM), I25 (CHD), C43 (melanoma) | Validate condition incidence |
| Phecodes | Grouped disease categories | Cross-check disease associations |
| Continuous traits | Walking pace, sleep duration | Validate lifestyle→outcome links |

## Validation Strategy

### 1. Genetic Instrument Validation

**Concept**: Use genetic variants as instrumental variables to estimate causal effects (Mendelian Randomization).

**Why this works**: Genetic variants are assigned at conception (no confounding) and flow one-way (genotype → phenotype).

**What we can validate**:
- BMI → T2DM causal effect
- BMI → CVD causal effect
- Physical activity genetic scores → mortality
- Compare MR estimates to our confounding-adjusted estimates

### 2. Phenotype Correlation Structure

**Concept**: Check if our modeled relationships match observed genetic correlations.

**Available data**: Pan-UKB provides genetic correlations between phenotypes via LD score regression.

**What we can validate**:
- Exercise phenotypes correlate with cardiovascular outcomes
- BMI correlates with diabetes, hypertension, mortality
- Depression correlates with lifestyle factors

### 3. Effect Size Benchmarking

**Concept**: Compare our hazard ratios to published Pan-UKB associations.

**Example workflow**:
```python
# Our model says: BMI +5 → T2DM HR 1.87
# Pan-UKB genetic association: BMI PGS → T2DM odds ratio
# If MR estimate ≈ 1.8-2.0, our model is calibrated
```

## Specific Phenotypes to Download

### From Phenotype Manifest

Search the [manifest](https://docs.google.com/spreadsheets/d/1AeeADtT0U1AukliiNyiVzVRdLYPkTbruQSk38DeutU8/) for:

1. **BMI** (continuous, Field 21001)
2. **Walking pace** (categorical, Field 924)
3. **Moderate physical activity** (continuous, Field 894)
4. **Type 2 diabetes** (ICD-10 E11, Phecode 250.2)
5. **Coronary heart disease** (ICD-10 I25, Phecode 411)
6. **Melanoma** (ICD-10 C43, Phecode 172)
7. **All-cause mortality** (derived phenotype if available)
8. **Systolic blood pressure** (Field 4080)
9. **Depression** (ICD-10 F32-F33, Phecode 296.2)

### Download Locations

Per-phenotype files on AWS:
```
s3://pan-ukb-us-east-1/sumstats_flat_files/
```

Or use GWAS Catalog for curated versions.

## Implementation Plan

### Phase 1: Data Collection (1-2 days)

1. Download phenotype manifest
2. Identify all relevant phenotypes
3. Download summary statistics for:
   - 10 lifestyle/biomarker phenotypes
   - 10 disease outcome phenotypes
4. Store in `data/pan-ukb/`

### Phase 2: MR Analysis Setup (2-3 days)

1. Install MR tools: `TwoSampleMR`, `MendelianRandomization` R packages
2. Identify genetic instruments for:
   - BMI (from GIANT consortium or Pan-UKB)
   - Physical activity (from published GWAS)
   - Smoking (from GSCAN)
3. Run MR for:
   - BMI → T2DM
   - BMI → CVD
   - Physical activity → CVD
   - Smoking → lung cancer

### Phase 3: Comparison & Calibration (2-3 days)

1. Compare MR causal estimates to our model's hazard ratios
2. Calculate calibration metrics:
   ```
   calibration_ratio = MR_estimate / our_estimate
   ```
3. If ratio ≠ 1.0, adjust confounding priors
4. Document discrepancies and their sources

### Phase 4: Integration (1-2 days)

1. Create validation notebook: `notebooks/pan-ukb-validation.ipynb`
2. Add to CI: automated comparison when model changes
3. Update paper with validation results

## Key Limitations

1. **GWAS ≠ individual data**: Can't run our exact simulations
2. **Ancestry**: Pan-UKB is multi-ancestry but UK-centric
3. **Phenotype definitions**: May differ from our condition definitions
4. **No direct mortality GWAS**: Use disease outcomes as proxies

## Resources

- [Pan-UKB Downloads](https://pan.ukbb.broadinstitute.org/downloads/index.html)
- [Phenotype Manifest](https://docs.google.com/spreadsheets/d/1AeeADtT0U1AukliiNyiVzVRdLYPkTbruQSk38DeutU8/)
- [Per-phenotype file docs](https://pan.ukbb.broadinstitute.org/docs/per-phenotype-files/index.html)
- [AWS Open Data Registry](https://registry.opendata.aws/broad-pan-ukb/)
- [TwoSampleMR R package](https://mrcieu.github.io/TwoSampleMR/)

## Expected Outcomes

1. **Calibration report**: How well do our estimates match MR causal estimates?
2. **Adjusted confounding priors**: If needed, update Beta priors based on MR
3. **Validation badge**: "Validated against Pan-UKB genetic associations"
4. **Paper section**: Add validation methodology and results

## Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Data collection | 2 days | Raw summary stats in `data/pan-ukb/` |
| MR setup | 3 days | Working MR pipeline |
| Comparison | 3 days | Calibration metrics |
| Integration | 2 days | Validation notebook + CI |
| **Total** | **~10 days** | Full validation suite |
