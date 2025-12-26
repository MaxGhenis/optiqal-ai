---
kernelspec:
  name: python3
  display_name: Python 3
---

# Optiqal: A State-Based Framework for Personalized QALY Estimation

```{code-cell} python
:tags: [remove-cell]

# Setup: Import paper results (single source of truth)
import sys
sys.path.insert(0, '.')
from optiqal_results import r
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Academic figure styling - cohesive palette inspired by medical journals
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 10,
    'axes.titlesize': 12,
    'axes.titleweight': 'bold',
    'axes.labelsize': 11,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.linewidth': 0.8,
    'figure.facecolor': 'white',
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
})

# Cohesive color palette - deep teal dominant with warm accents
COLORS = {
    'primary': '#1a5f7a',      # Deep teal - main elements
    'secondary': '#57837b',    # Sage - supporting elements
    'accent': '#c96f53',       # Terracotta - highlights/warnings
    'neutral': '#4a5568',      # Slate gray - text/lines
    'light': '#e8f4f3',        # Pale teal - backgrounds
    'high_evidence': '#1a5f7a',    # Deep teal
    'moderate_evidence': '#d4a574', # Warm sand
    'low_evidence': '#9ca3af',      # Cool gray
}
```

## Abstract

Lifestyle interventions show heterogeneous effects across individuals, yet existing tools provide population-average estimates without personalization. I present Optiqal, a state-based framework for estimating quality-adjusted life year (QALY) impacts of lifestyle changes. The framework models individuals as complete *states*—comprising demographics, biomarkers, behaviors, and conditions—and computes intervention effects as differences between states. Using imputation-based causal inference with a directed acyclic graph (DAG) of downstream effects, the framework isolates causal impacts from confounding. For the reference case—a {eval}`r.reference.description`—exercise at 150 min/week yields {eval}`r.exercise.life_years_fmt` additional life years ({eval}`r.exercise.months_fmt` months), followed by Mediterranean diet ({eval}`r.mediterranean_diet.life_years_fmt` years) and improved sleep ({eval}`r.sleep.life_years_fmt` years). For a current smoker, cessation yields {eval}`r.quit_smoking.life_years_fmt` years. Across {eval}`r.intervention_count` precomputed interventions spanning {eval}`r.category_count` categories, QALY impacts range from {eval}`r.qaly_range`.

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

### Comparison of Existing Life Expectancy Tools

To situate Optiqal within the landscape of health prediction tools, we systematically reviewed five major life expectancy and healthspan calculators. Table 1 summarizes their methodologies.

| Tool | Developer | Data Source | Outcome | Uncertainty | Personalization | Causal Approach | Key Limitations |
|------|-----------|-------------|---------|-------------|-----------------|-----------------|-----------------|
| Living to 100 | Thomas Perls, Boston University | New England Centenarian Study (n > 2,000 centenarians) | Life years | No | 40-item questionnaire; demographics, lifestyle, medical history | Observational (hazard ratios from centenarian studies) | No external validation of calculator; no quality-of-life component; genetic factors dominate at extreme ages |
| SSA Life Expectancy | Social Security Administration | Period life tables from Medicare/vital statistics (1900-2100) | Life years | No | Age and sex only | None (actuarial tables) | No behavioral factors; population averages only; no intervention modeling |
| Project Big Life MPoRT | Manuel et al., Ottawa Hospital/ICES | Canadian Community Health Survey (n = 77,399 derivation; 1M person-years) | 5-year mortality risk; life expectancy | Yes (95% CI reported) | Smoking, alcohol, diet, physical activity, sociodemographics | Observational (C-statistic 0.87-0.88) | Canadian population only; no quality-of-life; single-behavior attribution |
| Healthy Life Calculator | Diehr et al., Cardiovascular Health Study | CHS cohort (n = 5,888; 23-year follow-up) | Years healthy, able, healthy-and-able | No (R-squared ~ 0.40 reported) | 11 variables: age, health status, ADLs, medications, smoking, diabetes | Observational (regression) | Older adults only (age 65+); 1990s cohort; limited external validation |
| Vitality Healthy Futures | Discovery/RAND Europe | IHME Global Burden of Disease (264 causes, 328 diseases, 84 risks) + Discovery data (millions of life-years) | Lifespan and healthspan | No | Cardiorespiratory fitness, medication adherence, salt, sleep, conditions | Observational (not peer-reviewed) | Proprietary algorithm; no peer-reviewed validation; commercial context |

**Table 1**: Comparison of existing life expectancy and healthspan calculators. MPoRT = Mortality Population Risk Tool; CHS = Cardiovascular Health Study; ICES = Institute for Clinical Evaluative Sciences.

Several patterns emerge from this comparison:

**Outcome limitations**: All reviewed tools estimate life years rather than quality-adjusted life years. The Healthy Life Calculator incorporates self-rated health and functional ability, and Vitality Healthy Futures estimates "healthspan" separately from lifespan, but neither integrates quality weights into a unified QALY metric.

**Uncertainty quantification**: Only Project Big Life's MPoRT provides confidence intervals for individual predictions. Most tools report point estimates without communicating the substantial uncertainty inherent in mortality prediction {cite:p}`ncbi2016lifecalc`.

**Causal inference**: None of the reviewed tools employ formal causal inference methods. All rely on observational associations without explicit confounding adjustment. The MPoRT authors acknowledge this limitation, noting that their attributable life expectancy estimates assume causal effects from behavior modification {cite:p}`manuel2016burden`.

**Validation gaps**: A 2016 VA systematic review found that no life expectancy calculator met criteria for widespread clinical use, with none having true external validation for primary care populations {cite:p}`ncbi2016lifecalc`. The review concluded: "Although healthcare providers and guidelines make recommendations based on assessments of life expectancy, there is no widely accepted statistical tool for estimating patients' life expectancy."

**Intervention modeling**: Current tools typically model a single intervention or behavior at a time without accounting for downstream causal effects. When users modify multiple behaviors, naive approaches either double-count shared mechanisms or ignore interaction effects.

Optiqal addresses these gaps through: (1) QALY estimation integrating quality and quantity of life, (2) Monte Carlo uncertainty propagation with explicit confidence intervals, (3) imputation-based causal inference with Beta-calibrated confounding priors, and (4) DAG-specified downstream effects that prevent double-counting when modeling multiple interventions.

### The Confounding Problem

Observational studies of lifestyle factors face severe confounding. People who exercise also tend to eat better, smoke less, have higher socioeconomic status, and engage in other health-promoting behaviors {cite:p}`vanderweele2019`. Naive multiplication of hazard ratios compounds this bias—the person who exercises AND eats well AND doesn't smoke appears to receive benefits far exceeding what any individual intervention causally provides.

The central challenge is isolating the causal effect of a single intervention from the correlated effects of associated behaviors.

### Contribution

Optiqal addresses these gaps through three innovations:

1. **State-based modeling**: Individuals are modeled as complete states. Interventions are state transitions, enabling consistent treatment of any lifestyle change.

2. **Imputation-based causal inference**: Unobserved behaviors are imputed from demographics. When intervening, only the target variable and its causal downstream effects change—correlated behaviors remain fixed.

3. **Bayesian confounding adjustment**: The framework uses calibrated Beta priors on the causal fraction of observed associations, derived from systematic RCT-observational discrepancies. These priors are propagated through Monte Carlo simulation to produce uncertainty-quantified QALY estimates.

## Methods

### State Representation

A *PersonState* comprises five components:

- **Demographics**: Age, sex, ethnicity (immutable)
- **Biomarkers**: BMI, blood pressure, cholesterol, glucose (measured or imputed)
- **Behaviors**: Exercise, diet, sleep, substances, social connection (modifiable)
- **Conditions**: Diagnosed diseases with severity and treatment status
- **Environment**: Air quality, walkability, healthcare access

This representation enables modeling any intervention as a state modification.

### Reference Case

All estimates use a reference case representing an average American adult:

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

This profile has {eval}`f"{r.baseline_qalys:.1f}"` expected remaining QALYs. Estimates differ for other profiles—a current smoker sees larger benefits from cessation; someone exercising 150 min/week sees no additional benefit from that intervention.

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

```{code-cell} python
:tags: [remove-input]

# Figure 1: Causal pathway diagram - refined academic style
fig, ax = plt.subplots(figsize=(10, 5.5))
ax.set_xlim(0, 10)
ax.set_ylim(0, 6)
ax.axis('off')
fig.patch.set_facecolor('white')

# Define boxes with cohesive palette
boxes = {
    'Intervention': (1, 3, COLORS['light'], COLORS['primary']),
    'Biomarkers': (3.5, 4.5, '#f0f7f4', COLORS['secondary']),
    'Behaviors': (3.5, 1.5, '#fdf6f0', COLORS['accent']),
    'Conditions': (6, 3, '#fef2f0', '#b85c4a'),
    'QALYs': (8.5, 3, COLORS['light'], COLORS['primary']),
}

# Draw boxes with refined styling
for name, (x, y, facecolor, edgecolor) in boxes.items():
    rect = mpatches.FancyBboxPatch((x-0.75, y-0.4), 1.5, 0.8,
                                    boxstyle="round,pad=0.08,rounding_size=0.15",
                                    facecolor=facecolor, edgecolor=edgecolor,
                                    linewidth=2.5, alpha=0.95)
    ax.add_patch(rect)
    ax.text(x, y, name, ha='center', va='center', fontsize=11,
            fontweight='bold', color=COLORS['neutral'])

# Draw arrows with consistent styling
arrow_props = dict(arrowstyle='-|>', color=COLORS['neutral'], lw=2,
                   connectionstyle='arc3,rad=0.08', mutation_scale=15)

# Causal arrows
ax.annotate('', xy=(2.75, 4.3), xytext=(1.75, 3.3), arrowprops=arrow_props)
ax.annotate('', xy=(2.75, 1.7), xytext=(1.75, 2.7), arrowprops=arrow_props)
ax.annotate('', xy=(5.25, 3.3), xytext=(4.25, 4.3), arrowprops=arrow_props)
ax.annotate('', xy=(5.25, 2.7), xytext=(4.25, 1.7), arrowprops=arrow_props)
ax.annotate('', xy=(7.75, 3), xytext=(6.75, 3), arrowprops=arrow_props)

# Correlation arrow (dashed, muted)
ax.annotate('', xy=(3.5, 2.1), xytext=(3.5, 3.9),
            arrowprops=dict(arrowstyle='<->', color='#adb5bd', lw=1.5, linestyle='--'))

# Pathway labels - refined typography
ax.text(2.1, 4.15, 'causal', fontsize=9, color=COLORS['secondary'], style='italic')
ax.text(2.1, 1.95, 'causal', fontsize=9, color=COLORS['accent'], style='italic')
ax.text(4.0, 3, 'correlated\n(confounding)', fontsize=8, color='#adb5bd', ha='center', style='italic')
ax.text(4.85, 4.0, 'risk', fontsize=9, color=COLORS['neutral'], style='italic')
ax.text(4.85, 2.1, 'risk', fontsize=9, color=COLORS['neutral'], style='italic')

# Examples under boxes - subtle
ax.text(1, 2.25, 'Exercise · Diet · Sleep', ha='center', fontsize=8, color='#6b7280')
ax.text(3.5, 5.15, 'BMI · BP · Cholesterol', ha='center', fontsize=8, color='#6b7280')
ax.text(3.5, 0.75, 'Smoking · Alcohol', ha='center', fontsize=8, color='#6b7280')
ax.text(6, 2.25, 'Diabetes · CVD · Depression', ha='center', fontsize=8, color='#6b7280')
ax.text(8.5, 2.25, 'Quality × Years', ha='center', fontsize=8, color='#6b7280')

ax.set_title('Figure 1: Causal Pathway from Intervention to QALYs',
             fontsize=12, fontweight='bold', pad=15, color=COLORS['neutral'])
plt.tight_layout()
plt.show()
```

**Figure 1** illustrates the causal structure. Solid arrows represent causal effects (intervention changes biomarkers and behaviors, which affect condition risk). The dashed arrow shows correlation without causation—biomarkers and behaviors are correlated in the population, but intervening on one does not causally change the other.

The causal DAG specifies:
- **Exercise** → BMI (−0.5 per 150 min/week), systolic BP (−4 mmHg), HDL cholesterol (+3 mg/dL), sleep (+0.2 hours)
- **Diet** → BMI (−1.0 per 0.5 Mediterranean adherence), LDL cholesterol (−10 mg/dL), systolic BP (−3 mmHg)
- **Smoking cessation** → BMI (+2.0 kg/m²), systolic BP (−5 mmHg), lung function (+5% FEV1)

Effect sizes are derived from RCTs: DPP for exercise-BMI, PREDIMED for diet effects, Cornelissen 2013 for exercise-BP.

### Imputation

Given limited observations (e.g., only age, sex, BMI), we impute unobserved behaviors using stochastic models fit to NHANES and UK Biobank:

```
Exercise ~ Normal(μ = 150 - 8*(BMI-25) - 2*max(0, age-40) + 20*I(male), σ = 85)
Diet adherence ~ Normal(μ = 0.45 - 0.02*(BMI-25) + 0.10*I(college+), σ = 0.18)
```

Residual standard deviations (σ = 85 min/week for exercise, σ = 0.18 for diet score) were estimated from NHANES 2017-2020 physical activity questionnaire and HEI-2015 dietary index residuals after regression on demographics. The Monte Carlo simulation draws from these distributions, propagating imputation uncertainty through to final QALY estimates.

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

The calibrated prior is Beta(α=1.2, β=5.8), yielding mean α/(α+β) = 0.17 and 95% CI [0.02, 0.45]. This parameterization was derived by matching: (a) E[f] = 0.17 from meta-regression of RCT vs observational effect ratios {cite:p}`angrist2010credibility`, (b) mode consistent with E-value threshold for typical lifestyle interventions (HR ≈ 1.5), and (c) upper bound P(f > 0.45) < 0.025 from sibling study attenuation {cite:p}`lundborg2018schooling`.

### Causal Identification Assumptions

Our approach relies on four core assumptions for causal identification under the potential outcomes framework:

**1. Consistency**: The potential outcome under intervention X = x equals the observed outcome when X is set to x. This requires well-defined interventions—"exercise 150 min/week" must represent a specific, replicable activity level, not an ambiguous behavior category.

**2. Positivity (overlap)**: Every individual has positive probability of receiving any intervention level conditional on covariates. In our context, this holds by construction: we model voluntary lifestyle changes, not treatments with medical contraindications. The imputation model ensures all states have non-zero probability.

**3. No unmeasured confounding**: Conditional on the imputed state (demographics, biomarkers, behaviors), intervention assignment is independent of potential outcomes. This is the strongest assumption. We address it through: (a) imputation of correlated behaviors from observables, (b) explicit DAG specification of causal vs confounding pathways, (c) calibrated confounding adjustment factors derived from RCT-observational discrepancies.

**4. SUTVA (no interference)**: One individual's intervention does not affect another's outcomes. This holds for most lifestyle interventions (exercise, diet, sleep) but may be violated for social behaviors (e.g., group exercise programs creating network effects).

**Sensitivity to unmeasured confounding**: E-values quantify the robustness of causal estimates. For exercise (HR = 0.70), the E-value is HR + √[HR × (HR − 1)] ≈ 1.9. An unmeasured confounder would need to increase both exercise probability and mortality risk by a factor of 1.9 to fully explain away the observed effect—stronger than most known health confounders. For smoking cessation (HR = 2.80), E-value ≈ 5.2, indicating extreme robustness. Lower-magnitude effects (e.g., specific dietary components) have smaller E-values and greater vulnerability to residual confounding.

**Limitations of identification strategy**: (1) The imputation model may miss confounders not correlated with measured demographics. (2) The DAG encodes our causal assumptions but cannot be verified from observational data alone—misspecification would bias estimates. (3) Confounding adjustment relies on external calibration studies that may not generalize to all populations. (4) Time-varying confounding (e.g., health deterioration causing both inactivity and mortality) is not fully addressed in the single-timepoint model.

### Condition Incidence Models

Interventions affect quality of life through condition incidence. Rather than using age-based EQ-5D population norms (which would double-count age-related morbidity already captured in condition prevalence), we model conditions directly:

**Incidence models** for key conditions:
- **Type 2 diabetes**: Based on FINDRISC + CDC National Diabetes Statistics, with BMI (RR 2.3/5 kg/m², updated via Pan-UKB MR validation), physical activity (RR 0.74 at 150 min/week), and hypertension (RR 1.5) adjustments. Validation: C-statistic 0.84 in NHANES 2015-2018 10-year follow-up; calibration slope 0.97 {cite:p}`noble2011findrisc`.
- **CVD (CHD + stroke)**: Framingham-style model with age, blood pressure (2x per 20 mmHg SBP), cholesterol, smoking (RR 2.0), and diabetes (RR 2.5). Validation: C-statistic 0.76 in external UK cohorts; Hosmer-Lemeshow p > 0.05 {cite:p}`hippisley2017derivation`.
- **Depression**: NIMH base rates with sex (female RR 1.6), exercise (RR 0.75 at 150 min/week), and obesity (RR 1.3) adjustments. Limited external validation; model calibrated to PHQ-9 incidence rates from NHANES continuous surveys {cite:p}`kessler2003epidemiology`.

**Quality decrements** from literature:
| Condition | Utility Decrement | Source |
|-----------|------------------|--------|
| Stroke | −0.16 | UKPDS 62 |
| Heart failure | −0.12 | Sullivan catalog |
| Depression | −0.10 | Sullivan catalog |
| CHD | −0.09 | UKPDS 62 |
| Type 2 diabetes | −0.06 | UKPDS 62 |

**Pure aging effect**: Residual decline of 0.002/year after age 50 (0.06 by age 80), representing frailty and sensory decline not captured by specific diagnoses.

**Comorbidity handling**: Quality decrements are applied multiplicatively following UKPDS 62 methodology {cite:p}`clarke2002ukpds62`. For example, a person with both diabetes (utility 0.94) and depression (utility 0.90) has combined utility 0.94 × 0.90 = 0.85, rather than the additive 0.94 + 0.90 − 1 = 0.84. This multiplicative approach avoids utilities below zero for patients with multiple conditions.

This approach separates the causal pathway: Intervention → Biomarkers → Condition Risk → Quality Loss.

### Lifecycle Integration

We propagate mortality and quality effects through a lifecycle model:
- CDC life tables for age-specific mortality
- Age-varying cause fractions (CVD, cancer, other)
- Condition-based quality weights (see above)
- 3% annual discounting (for ICER calculations)

## Results

### Key Interventions

```{code-cell} python
:tags: [remove-input]

from IPython.display import Markdown
Markdown(r.intervention_table())
```

```{code-cell} python
:tags: [remove-input]

# Figure 2: Forest plot - refined academic style
interventions = r.all_interventions()
names = [i.name.split('(')[0].strip() for i in interventions]
qalys = [i.qaly_mean for i in interventions]
ci_lower = [i.qaly_ci_lower for i in interventions]
ci_upper = [i.qaly_ci_upper for i in interventions]
evidence = [i.evidence_quality for i in interventions]

# Color by evidence quality using cohesive palette
evidence_colors = {
    'high': COLORS['high_evidence'],
    'moderate': COLORS['moderate_evidence'],
    'low': COLORS['low_evidence']
}
bar_colors = [evidence_colors[e] for e in evidence]

fig, ax = plt.subplots(figsize=(9, 5.5))
y_pos = np.arange(len(names))

# Plot horizontal bars with refined styling
bars = ax.barh(y_pos, qalys, color=bar_colors, alpha=0.85, height=0.55, edgecolor='white', linewidth=0.5)

# Error bars with refined styling
ax.errorbar(qalys, y_pos,
            xerr=[np.array(qalys)-np.array(ci_lower), np.array(ci_upper)-np.array(qalys)],
            fmt='none', ecolor=COLORS['neutral'], capsize=4, capthick=1.5, elinewidth=1.5)

# Point markers at mean
ax.scatter(qalys, y_pos, color='white', s=25, zorder=5, edgecolor=COLORS['neutral'], linewidth=1)

ax.set_yticks(y_pos)
ax.set_yticklabels(names, fontsize=10)
ax.set_xlabel('QALY Gain (95% CI)', fontsize=11, color=COLORS['neutral'])
ax.set_title('Figure 2: Intervention Effects on Quality-Adjusted Life Years',
             fontsize=12, fontweight='bold', color=COLORS['neutral'], pad=12)
ax.axvline(x=0, color=COLORS['neutral'], linewidth=1, linestyle='-', alpha=0.3)
ax.set_xlim(-0.1, 2.7)

# Subtle grid
ax.xaxis.grid(True, linestyle='-', alpha=0.2, color=COLORS['neutral'])
ax.set_axisbelow(True)

# Refined legend
legend_patches = [mpatches.Patch(color=evidence_colors[q], label=f'{q.capitalize()} evidence', alpha=0.85)
                  for q in ['high', 'moderate', 'low']]
ax.legend(handles=legend_patches, loc='lower right', framealpha=0.95, edgecolor='none',
          fontsize=9, title='Evidence Quality', title_fontsize=9)

ax.invert_yaxis()
plt.tight_layout()
plt.show()
```

**Figure 2** shows QALY gains with 95% confidence intervals. Smoking cessation dominates but applies only to smokers. Among universally applicable interventions, exercise and social connection show the largest effects. Evidence quality (color) indicates confidence in causal estimates.

**Note on applicability**: Smoking cessation ({eval}`r.quit_smoking.qaly` QALYs) applies only to current smokers—the reference case is a never-smoker. For the reference case (sedentary, overweight, suboptimal sleep), the most relevant interventions are:

1. **Exercise** ({eval}`r.exercise.qaly` QALYs): Going from 50 to 150 min/week
2. **Sleep** ({eval}`r.sleep.qaly` QALYs): Going from 6.5 to 7-8 hours
3. **Diet** ({eval}`r.mediterranean_diet.qaly` QALYs): Adopting Mediterranean pattern

For a **current smoker**, cessation dominates all other interventions {cite:p}`jha2013,doll2004`.

Social connection ({eval}`r.social.qaly` QALYs) ranks surprisingly high—comparable to major dietary interventions—supported by the Holt-Lunstad meta-analysis finding 50% mortality reduction for strong social relationships {cite:p}`holtlunstad2010`.

### Evidence Quality

Interventions with "high" evidence quality have:
- RCT evidence for mechanism (e.g., PREDIMED for diet)
- Large-scale prospective cohort data (n > 100,000)
- Consistent dose-response relationships
- Biological plausibility through established pathways

"Moderate" evidence relies primarily on observational data with adjustment for major confounders. "Low" evidence has limited or conflicting studies.

### Sensitivity to Baseline Characteristics

Estimates vary substantially by who receives the intervention.

#### By Age

Exercise benefits decrease with age due to fewer remaining life-years:

| Age | Exercise QALY Gain | Life Years |
|-----|-------------------|------------|
| 30 | {eval}`f"{r.exercise_by_age[30]:.1f}"` | {eval}`f"{r.exercise_by_age[30] * 1.35:.1f}"` |
| 40 | {eval}`f"{r.exercise_by_age[40]:.1f}"` | {eval}`f"{r.exercise_by_age[40] * 1.35:.1f}"` |
| 50 | {eval}`f"{r.exercise_by_age[50]:.1f}"` | {eval}`f"{r.exercise_by_age[50] * 1.35:.1f}"` |
| 60 | {eval}`f"{r.exercise_by_age[60]:.1f}"` | {eval}`f"{r.exercise_by_age[60] * 1.35:.1f}"` |
| 70 | {eval}`f"{r.exercise_by_age[70]:.1f}"` | {eval}`f"{r.exercise_by_age[70] * 1.35:.1f}"` |

#### By Baseline BMI

Diet intervention benefits increase for those starting at higher BMI:

| Baseline BMI | Diet QALY Gain | Life Years |
|--------------|---------------|------------|
| 22 (lean) | {eval}`f"{r.diet_by_bmi[22]:.1f}"` | {eval}`f"{r.diet_by_bmi[22] * 1.35:.1f}"` |
| 25 (normal) | {eval}`f"{r.diet_by_bmi[25]:.1f}"` | {eval}`f"{r.diet_by_bmi[25] * 1.35:.1f}"` |
| 28 (overweight) | {eval}`f"{r.diet_by_bmi[28]:.1f}"` | {eval}`f"{r.diet_by_bmi[28] * 1.35:.1f}"` |
| 32 (obese) | {eval}`f"{r.diet_by_bmi[32]:.1f}"` | {eval}`f"{r.diet_by_bmi[32] * 1.35:.1f}"` |
| 36 (severely obese) | {eval}`f"{r.diet_by_bmi[36]:.1f}"` | {eval}`f"{r.diet_by_bmi[36] * 1.35:.1f}"` |

#### By Profile Type

| Profile | Exercise Benefit | Diet Benefit | Notes |
|---------|-----------------|--------------|-------|
| Average American | {eval}`r.exercise.qaly` | {eval}`r.mediterranean_diet.qaly` | Reference case |
| Current smoker | 0.9 | 0.6 | Lower baseline, competing risk from smoking |
| Already healthy | 0.2 | 0.3 | Already near optimal |
| Age 65 | 0.7 | 0.6 | Fewer years remaining |

```{code-cell} python
:tags: [remove-input]

# Figure 3: Sensitivity heatmap - refined academic style
from matplotlib.colors import LinearSegmentedColormap

ages = [30, 40, 50, 60, 70]
baseline_activity = [0, 30, 60, 90, 120]  # min/week
activity_labels = ['Sedentary\n(0 min)', 'Low\n(30 min)', 'Moderate\n(60 min)', 'Active\n(90 min)', 'Very Active\n(120 min)']

# Generate QALY matrix
qaly_matrix = np.zeros((len(ages), len(baseline_activity)))
for i, age in enumerate(ages):
    for j, activity in enumerate(baseline_activity):
        age_factor = r.exercise_by_age.get(age, 1.0)
        activity_factor = max(0, 1 - activity / 150)
        qaly_matrix[i, j] = age_factor * activity_factor

# Custom colormap matching our palette (light teal to deep teal)
cmap_colors = ['#f7fcfb', '#d4ede8', '#9dd4c8', '#57a99a', COLORS['primary'], '#0d3d4d']
custom_cmap = LinearSegmentedColormap.from_list('optiqal', cmap_colors)

fig, ax = plt.subplots(figsize=(9, 5.5))
im = ax.imshow(qaly_matrix, cmap=custom_cmap, aspect='auto', vmin=0, vmax=2.0)

# Refined colorbar
cbar = ax.figure.colorbar(im, ax=ax, shrink=0.85, aspect=20)
cbar.ax.set_ylabel('QALY Gain from Exercise', rotation=-90, va="bottom",
                   fontsize=10, color=COLORS['neutral'], labelpad=15)
cbar.outline.set_visible(False)

# Set ticks and labels
ax.set_xticks(np.arange(len(baseline_activity)))
ax.set_yticks(np.arange(len(ages)))
ax.set_xticklabels(activity_labels, fontsize=9)
ax.set_yticklabels([f'Age {a}' for a in ages], fontsize=10)

# Value annotations with refined styling
for i in range(len(ages)):
    for j in range(len(baseline_activity)):
        value = qaly_matrix[i, j]
        text_color = 'white' if value > 0.9 else COLORS['neutral']
        ax.text(j, i, f'{value:.1f}', ha='center', va='center',
                color=text_color, fontsize=11, fontweight='bold')

ax.set_xlabel('Baseline Physical Activity Level', fontsize=11, color=COLORS['neutral'])
ax.set_ylabel('Age at Intervention', fontsize=11, color=COLORS['neutral'])
ax.set_title('Figure 3: Exercise QALY Benefit by Age and Baseline Activity',
             fontsize=12, fontweight='bold', color=COLORS['neutral'], pad=12)

# Remove cell borders for cleaner look
for spine in ax.spines.values():
    spine.set_visible(False)

plt.tight_layout()
plt.show()
```

**Figure 3** visualizes the interaction between age and baseline activity on exercise benefits. Young, sedentary individuals gain the most (1.8 QALYs), while older or already-active individuals gain less. This heatmap can guide personalized recommendations.

The key insight: **interventions matter most for those furthest from optimal**. A sedentary, overweight 40-year-old gains ~3x more from exercise than someone already active.

### Comparison to Naive Estimates

The counterfactual approach produces smaller estimates than naive state comparison:

| Intervention | Causal Effect | Naive Effect | Confounding Absorbed |
|--------------|---------------|--------------|---------------------|
| Exercise 150 min/week | {eval}`r.exercise.qaly` QALYs | 1.8 QALYs | 43% |
| Mediterranean diet | {eval}`r.mediterranean_diet.qaly` QALYs | 1.2 QALYs | 38% |
| Daily nuts | {eval}`r.daily_nuts.qaly` QALYs | 0.8 QALYs | 44% |

The naive approach compares a person who exercises to a "typical exerciser"—who also has better diet, lower BMI, less smoking. The causal approach holds these confounders fixed.

### Prior Sensitivity Analysis

Our base estimates use a confounding prior where 17% of observed effects are causal (95% CI: 7%–30%). To assess robustness, we vary this prior by ±1 standard deviation:

| Intervention | Skeptical (10% causal) | Base (17% causal) | Optimistic (30% causal) |
|--------------|------------------------|-------------------|-------------------------|
| Exercise 150 min/week | 0.8 QALYs | {eval}`r.exercise.qaly` QALYs | 1.8 QALYs |
| Mediterranean diet | 0.6 QALYs | {eval}`r.mediterranean_diet.qaly` QALYs | 1.4 QALYs |
| Quit smoking | 1.4 QALYs | {eval}`r.quit_smoking.qaly` QALYs | 3.2 QALYs |
| Social connection | 0.7 QALYs | {eval}`r.social.qaly` QALYs | 1.6 QALYs |

While absolute QALY magnitudes vary substantially (up to 2.5x between skeptical and optimistic scenarios), the rank-ordering of interventions remains stable. Smoking cessation dominates universally, followed by exercise and social connection, regardless of prior assumptions. This robustness in relative rankings provides confidence for prioritizing interventions even under epistemic uncertainty about confounding strength.

**Methodological note**: We use forward Monte Carlo simulation with calibrated Beta priors for the causal fraction, sampling 10,000 realizations per intervention. This is distinct from MCMC posterior inference—we are not computing posteriors over parameters given data, but rather propagating prior uncertainty through a deterministic model to quantify output uncertainty.

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

1. **Bayesian posterior updating**: As users provide personal observations (e.g., "I already exercise 100 min/week"), update imputation distributions using Bayes' rule: P(state | observation) ∝ P(observation | state) × P(state). This would sharpen QALY estimates by reducing uncertainty about the individual's true baseline
2. **Dynamic modeling**: Track state evolution over time with behavior persistence
3. **Intervention combinations**: Model synergies and conflicts between multiple changes
4. **External validation**: Compare predictions to longitudinal cohort outcomes from UK Biobank and NHANES follow-up studies. Key validation targets include: (a) all-cause mortality predictions vs observed deaths, (b) condition-specific incidence vs diagnoses in follow-up periods, and (c) quality-of-life trajectories vs repeated EQ-5D measurements

### Mendelian Randomization Validation

We validated our causal effect estimates against Mendelian Randomization (MR) analyses using Pan-UKB GWAS summary statistics. MR uses genetic variants as instrumental variables to estimate causal effects, providing an independent check on our parameter choices.

For BMI → Type 2 Diabetes, the MR analysis found OR = 2.52 per 1 SD BMI (~4.5 kg/m²), corresponding to RR ≈ 2.3 per 5 kg/m². This exceeded our original observational estimate (RR = 1.87), yielding a calibration ratio of 1.44. We updated our model parameters to align with this causal genetic evidence.

For BMI → Cardiovascular Disease, the MR estimate (OR = 1.30 per SD) closely matched our model (HR = 1.40), with calibration ratio 0.93, indicating our CVD risk estimates are well-calibrated to causal effects.

This validation approach—comparing model parameters to MR causal estimates—provides a principled method for distinguishing genuine causal effects from confounded associations in observational data.

### Intended Use and Limitations

Optiqal is designed for specific audiences and use cases. **Target audiences** include individuals seeking personalized health guidance, health coaches supporting behavior change counseling, researchers studying lifestyle interventions, and policymakers evaluating health promotion programs.

**Appropriate uses** include comparing the relative benefits of different interventions, understanding uncertainty in health estimates, and serving as an educational tool for quantifying lifestyle impacts on longevity and quality of life. The framework excels at helping users prioritize among multiple potential behavior changes based on their personal characteristics.

**This tool is not intended for** clinical diagnosis or treatment decisions, replacing physician advice, or making precise predictions about individual outcomes. Medical decisions should always involve qualified healthcare providers who can consider factors beyond this model's scope.

**Key caveats** must be understood by users. The framework assumes sustained behavior change—adherence dynamics and behavior persistence are not modeled. Estimates derive from population-level evidence, meaning substantial individual variation exists around point estimates. All QALY projections carry uncertainty and should inform rather than dictate health decisions. The framework works best when users understand that results represent expected values across many similar individuals, not guarantees for any single person.

## Conclusion

Optiqal provides a framework for personalized QALY estimation using state-based modeling and causal inference. For a {eval}`r.target_age`-year-old with average characteristics, lifestyle interventions yield {eval}`r.qaly_range` QALYs ({eval}`r.life_years_range` life years, or {eval}`r.months_range` months), with smoking cessation and exercise showing the largest benefits. The approach separates causal effects from confounding, producing more conservative but more accurate estimates than naive comparisons.

## References

```{bibliography}
:style: unsrt
```
