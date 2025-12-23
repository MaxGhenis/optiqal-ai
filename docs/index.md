---
kernelspec:
  name: python3
  display_name: Python 3
---

# Optiqal: A State-Based Framework for Personalized QALY Estimation

**Max Ghenis**

max@maxghenis.com

```{code-cell} python
:tags: [remove-cell]

# Setup: Import paper results (single source of truth)
import sys
sys.path.insert(0, '.')
from optiqal_results import r
```

## Abstract

Lifestyle interventions show heterogeneous effects across individuals, yet existing tools provide population-average estimates without personalization. I present Optiqal, a state-based framework for estimating quality-adjusted life year (QALY) impacts of lifestyle changes. The framework models individuals as complete *states*—comprising demographics, biomarkers, behaviors, and conditions—and computes intervention effects as differences between states. Using imputation-based causal inference with a directed acyclic graph (DAG) of downstream effects, the framework isolates causal impacts from confounding. For the reference case—a {eval}`r.reference.description`—exercise at 150 min/week yields {eval}`r.exercise.life_years_fmt` additional life years ({eval}`r.exercise.months_fmt` months), followed by Mediterranean diet ({eval}`r.mediterranean_diet.life_years_fmt` years) and improved sleep ({eval}`r.sleep.life_years_fmt` years). For a current smoker, cessation yields {eval}`r.quit_smoking.life_years_fmt` years. Across {eval}`r.intervention_count` precomputed interventions spanning {eval}`r.category_count` categories, QALY impacts range from {eval}`r.qaly_range`.

### Reference Case

All estimates in this paper use a reference case representing an average American adult:

| Characteristic | Value | Interpretation |
|----------------|-------|----------------|
| Age | {eval}`r.reference.age` | Middle-aged |
| Sex | {eval}`r.reference.sex` | Male |
| BMI | {eval}`r.reference.bmi` | Overweight (US average) |
| Blood pressure | {eval}`r.reference.systolic_bp` mmHg | Elevated |
| Exercise | {eval}`r.reference.exercise_min` min/week | Below guideline |
| Diet adherence | {eval}`f"{r.reference.diet_adherence:.0%}"` | Below average |
| Sleep | {eval}`r.reference.sleep_hours` hours | Suboptimal |
| Smoking | {eval}`r.reference.smoking` | Non-smoker |

This reference case has {eval}`f"{r.baseline_qalys:.1f}"` expected remaining QALYs. Estimates would differ for other profiles—a current smoker would see larger benefits from cessation; someone already exercising 150 min/week would see no benefit from that intervention.

## Introduction

### The Personalization Gap

Cost-effectiveness analyses typically report population-average effects. A meta-analysis finding that exercise reduces all-cause mortality by 30% {cite:p}`arem2015` does not tell an individual with diabetes and hypertension how much benefit they specifically would receive. The same intervention may yield different absolute benefits depending on baseline risk, age, comorbidities, and existing behaviors.

This matters for individual decision-making. Someone choosing between starting an exercise program, improving their diet, or addressing sleep quality needs personalized estimates—not averages across populations with different characteristics than their own.

### Existing Approaches

Current health decision tools fall into three categories:

1. **Risk calculators** (e.g., Framingham, QRISK) estimate disease risk but don't translate to life expectancy or quality-adjusted outcomes.

2. **Life expectancy calculators** (e.g., actuarial tables) provide mortality estimates but ignore quality of life and don't model interventions.

3. **Cost-effectiveness models** (e.g., GiveWell, NICE) compute population-level $/QALY but don't personalize to individuals.

None provide: (a) personalized QALY estimates, (b) for arbitrary lifestyle interventions, (c) with explicit uncertainty quantification, (d) using causal inference methods.

### The Confounding Problem

Observational studies of lifestyle factors face severe confounding. People who exercise also tend to eat better, smoke less, have higher socioeconomic status, and engage in other health-promoting behaviors {cite:p}`vanderweele2019`. Naive multiplication of hazard ratios compounds this bias—the person who exercises AND eats well AND doesn't smoke appears to receive benefits far exceeding what any individual intervention causally provides.

The central challenge is isolating the causal effect of a single intervention from the correlated effects of associated behaviors.

### Contribution

Optiqal addresses these gaps through three innovations:

1. **State-based modeling**: Individuals are modeled as complete states. Interventions are state transitions, enabling consistent treatment of any lifestyle change.

2. **Imputation-based causal inference**: Unobserved behaviors are imputed from demographics. When intervening, only the target variable and its causal downstream effects change—correlated behaviors remain fixed.

3. **Explicit uncertainty propagation**: Monte Carlo simulation propagates uncertainty from evidence to final QALY estimates.

## Methods

### State Representation

A *PersonState* comprises five components:

- **Demographics**: Age, sex, ethnicity (immutable)
- **Biomarkers**: BMI, blood pressure, cholesterol, glucose (measured or imputed)
- **Behaviors**: Exercise, diet, sleep, substances, social connection (modifiable)
- **Conditions**: Diagnosed diseases with severity and treatment status
- **Environment**: Air quality, walkability, healthcare access

This representation enables modeling any intervention as a state modification.

### Risk Factor Database

We compiled hazard ratios from meta-analyses of prospective cohort studies:

| Risk Factor | Hazard Ratio | Source |
|-------------|--------------|--------|
| Smoking (current vs never) | 2.80 [2.45, 3.20] | {cite:t}`jha2013` |
| Exercise (150+ min/week vs sedentary) | 0.70 [0.64, 0.77] | {cite:t}`arem2015` |
| Mediterranean diet (high vs low adherence) | 0.79 [0.73, 0.85] | {cite:t}`estruch2018` |
| Social isolation (isolated vs connected) | 1.50 [1.35, 1.67] | {cite:t}`holtlunstad2010` |
| Sleep (7-8h vs <6h) | 0.88 [0.82, 0.95] | {cite:t}`cappuccio2010` |

### Causal DAG

Interventions affect downstream variables through causal pathways. For example, exercise causally reduces BMI and blood pressure, but does NOT causally change diet—the observed correlation is confounding.

The causal DAG specifies:
- **Exercise** → BMI (−0.5 per 150 min/week), systolic BP (−4 mmHg), HDL cholesterol (+3 mg/dL), sleep (+0.2 hours)
- **Diet** → BMI (−1.0 per 0.5 Mediterranean adherence), LDL cholesterol (−10 mg/dL), systolic BP (−3 mmHg)
- **Smoking cessation** → BMI (+2.0 kg/m²), systolic BP (−5 mmHg), lung function (+5% FEV1)

Effect sizes are derived from RCTs: DPP for exercise-BMI, PREDIMED for diet effects, Cornelissen 2013 for exercise-BP.

### Imputation

Given limited observations (e.g., only age, sex, BMI), we impute unobserved behaviors using population statistics from NHANES and UK Biobank:

```
Exercise ~ 150 - 8*(BMI-25) - 2*max(0, age-40) + 20*I(male)
Diet adherence ~ 0.45 - 0.02*(BMI-25) + 0.10*I(college+)
```

These capture the observed correlations between demographics and behaviors.

### Counterfactual Simulation

For an intervention on variable X:

1. **Impute baseline state** from observations
2. **Apply intervention**: Change X to target value
3. **Propagate causal effects**: Update downstream variables per DAG
4. **Hold non-causal correlates fixed**: Diet doesn't change when we intervene on exercise
5. **Compute QALY difference** between baseline and counterfactual states

This isolates the causal effect from confounding.

### Confounding Adjustment

We apply a confounding adjustment factor calibrated to three evidence sources:

- **RCT vs observational calibration**: Meta-regressions comparing effect sizes
- **E-value analysis**: Minimum confounding strength to explain observed effects
- **Within-sibling designs**: Attenuation in family-controlled analyses

The calibrated prior has mean {eval}`r.confounding_mean` (95% CI: {eval}`r.confounding_ci`), representing the fraction of observed effects that are causal.

### Lifecycle Integration

We propagate mortality effects through a lifecycle model:
- CDC life tables for age-specific mortality
- Age-varying cause fractions (CVD, cancer, other)
- EQ-5D population norms for quality weights {cite:p}`sullivan2005eq5d`
- 3% annual discounting (for ICER calculations)

## Results

### Key Interventions

```{code-cell} python
:tags: [remove-input]

from IPython.display import Markdown
Markdown(r.intervention_table())
```

Smoking cessation yields the largest benefit ({eval}`r.quit_smoking.qaly` QALYs, {eval}`r.quit_smoking.life_years_fmt` life years), consistent with extensive epidemiological evidence {cite:p}`jha2013,doll2004`. Exercise at guideline levels ({eval}`r.exercise.qaly` QALYs) and Mediterranean diet ({eval}`r.mediterranean_diet.qaly` QALYs) follow.

Social connection ({eval}`r.social.qaly` QALYs) ranks surprisingly high—comparable to major dietary interventions—supported by the Holt-Lunstad meta-analysis finding 50% mortality reduction for strong social relationships {cite:p}`holtlunstad2010`.

### Evidence Quality

Interventions with "high" evidence quality have:
- RCT evidence for mechanism (e.g., PREDIMED for diet)
- Large-scale prospective cohort data (n > 100,000)
- Consistent dose-response relationships
- Biological plausibility through established pathways

"Moderate" evidence relies primarily on observational data with adjustment for major confounders. "Low" evidence has limited or conflicting studies.

### Comparison to Naive Estimates

The counterfactual approach produces smaller estimates than naive state comparison:

| Intervention | Causal Effect | Naive Effect | Confounding Absorbed |
|--------------|---------------|--------------|---------------------|
| Exercise 150 min/week | {eval}`r.exercise.qaly` QALYs | 1.8 QALYs | 43% |
| Mediterranean diet | {eval}`r.mediterranean_diet.qaly` QALYs | 1.2 QALYs | 38% |
| Daily nuts | {eval}`r.daily_nuts.qaly` QALYs | 0.8 QALYs | 44% |

The naive approach compares a person who exercises to a "typical exerciser"—who also has better diet, lower BMI, less smoking. The causal approach holds these confounders fixed.

## Discussion

### Strengths

1. **Personalization**: State-based approach naturally handles individual variation
2. **Causal identification**: DAG + imputation isolates intervention effects
3. **Transparency**: All parameters traced to sources
4. **Extensibility**: New interventions added by specifying mechanism effects

### Limitations

1. **Imputation uncertainty**: Unobserved behaviors are imputed with substantial error
2. **Single-timepoint**: Does not model dynamic behavior changes over time
3. **Independence assumption**: Interactions between interventions not fully modeled
4. **Selection bias**: Evidence base skews toward studied populations

### Future Directions

1. **Bayesian updating**: Incorporate user-provided observations to reduce imputation uncertainty
2. **Dynamic modeling**: Track state evolution over time with behavior persistence
3. **Intervention combinations**: Model synergies and conflicts between multiple changes
4. **Validation**: Compare predictions to longitudinal cohort outcomes

## Conclusion

Optiqal provides a framework for personalized QALY estimation using state-based modeling and causal inference. For a {eval}`r.target_age`-year-old with average characteristics, lifestyle interventions yield {eval}`r.qaly_range` QALYs ({eval}`r.life_years_range` life years, or {eval}`r.months_range` months), with smoking cessation and exercise showing the largest benefits. The approach separates causal effects from confounding, producing more conservative but more accurate estimates than naive comparisons.

## References

```{bibliography}
:style: unsrt
```
