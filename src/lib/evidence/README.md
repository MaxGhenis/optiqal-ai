# Evidence Library

Curated research evidence for QALY impact estimation.

## Structure

```
evidence/
  baseline/           # Life tables, baseline QALY projections
    life-tables.ts    # Age/sex-specific mortality rates
    hale.ts           # Health-adjusted life expectancy

  risk-factors/       # Modifiable risk factors
    smoking.ts        # Smoking cessation/initiation
    exercise.ts       # Physical activity levels
    diet.ts           # Dietary patterns
    alcohol.ts        # Alcohol consumption
    sleep.ts          # Sleep duration/quality
    bmi.ts            # Body mass index

  interventions/      # Specific interventions
    medications.ts    # Statins, metformin, etc.
    screening.ts      # Cancer screening, checkups
    supplements.ts    # Vitamins, etc.
```

## Data Sources (Priority Order)

1. **GBD Study (IHME)** - Risk factor quantification, disability weights
2. **Cochrane Reviews** - Meta-analyses of RCTs
3. **CDC/NCHS Life Tables** - US mortality data
4. **WHO Global Health Observatory** - HALE, global data
5. **USPSTF** - Preventive service evidence reviews
6. **Individual meta-analyses** - Published in high-impact journals

## Evidence Format

Each evidence entry includes:
- `source`: Full citation
- `type`: meta-analysis | rct | cohort | case-control | cross-sectional
- `sampleSize`: Total participants
- `effectSize`: Relative risk, hazard ratio, or absolute effect
- `confidenceInterval`: 95% CI
- `population`: Who was studied
- `applicability`: How generalizable

## Baseline Calculation

For a given user profile (age, sex, health status):

1. Look up remaining life expectancy from life tables
2. Apply disability weight based on existing conditions
3. Calculate baseline QALYs = life expectancy × quality weight
4. Adjust for modifiable risk factors (smoking, BMI, etc.)

## Intervention Calculation

For a lifestyle change:

1. Find matching evidence in library
2. Apply effect size to baseline mortality/morbidity
3. Adjust for user-specific factors (age modifies most effects)
4. Calculate confidence interval from evidence uncertainty
