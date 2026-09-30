# Methodology

This document describes the technical methodology underlying the Optiqal Quality-Adjusted Life Year (QALY) framework for estimating health intervention impacts.

## Overview

Optiqal estimates the lifetime QALY gains from health interventions using a lifecycle simulation model with Monte Carlo uncertainty quantification. The framework incorporates:

1. CDC life tables adjusted for individual risk profiles
2. Pathway-specific hazard ratios (cardiovascular disease, cancer, other causes)
3. Evidence-calibrated confounding adjustment
4. Profile-specific intervention effect modifiers
5. Combination effects with overlap and diminishing returns

## QALY Calculation Framework

### Lifecycle Integration

QALYs are calculated by integrating the discounted quality-weighted survival curve over the remaining lifetime:

$$
\text{QALY} = \sum_{t=0}^{T_{\max} - \text{age}_0} S(t) \times Q(t) \times D(t)
$$

where:
- $S(t)$ is the survival probability at time $t$ years from baseline
- $Q(t)$ is the quality-of-life weight at age $\text{age}_0 + t$
- $D(t) = (1 + r)^{-t}$ is the discount factor with rate $r$ (default 3% for QALYs)
- $T_{\max} = 100$ is the maximum age in the life table

### Survival Probability

Survival at time $t$ is calculated recursively from age-specific mortality rates:

$$
S(t) = \prod_{i=0}^{t-1} \left(1 - q_{\text{age}_0 + i}\right)
$$

where $q_a$ is the annual mortality rate (probability of death) for age $a$: the single-year $q_x$ from the CDC's *United States Life Tables, 2021* (NVSR 72-12, Table 2 for males and Table 3 for females) for ages 0-99. From age 100 the model uses the constant annual rate $1 - e^{-l_{100}/T_{100}}$, which reproduces the published life expectancy of the open-ended "100 and older" row.

### Quality-of-Life Weights

Age-specific quality weights $Q(t)$ are based on Sullivan et al. (2006) and Global Burden of Disease (GBD) 2019 estimates:

| Age | Quality Weight |
|-----|----------------|
| 25  | 0.92           |
| 35  | 0.90           |
| 45  | 0.88           |
| 55  | 0.85           |
| 65  | 0.82           |
| 75  | 0.78           |
| 85  | 0.72           |
| 95  | 0.65           |

Values are linearly interpolated between age points.

### Discount Rate

Future QALYs are discounted at 3% annually in the default Optiqal configuration, matching the engine's reference-case default. Alternative rates from 0% to 10% are supported for sensitivity analysis.

## Pathway Decomposition

### Cause-Specific Mortality

Total mortality is decomposed into three pathways based on CDC WONDER (2021) data:

$$
q_a = f_{\text{CVD}}(a) \times q_a + f_{\text{cancer}}(a) \times q_a + f_{\text{other}}(a) \times q_a
$$

where $f_{\text{CVD}}(a)$, $f_{\text{cancer}}(a)$, and $f_{\text{other}}(a)$ are age-dependent fractions summing to 1:

| Age | CVD  | Cancer | Other |
|-----|------|--------|-------|
| 40  | 0.20 | 0.25   | 0.55  |
| 50  | 0.25 | 0.35   | 0.40  |
| 60  | 0.30 | 0.35   | 0.35  |
| 70  | 0.35 | 0.30   | 0.35  |
| 80  | 0.40 | 0.20   | 0.40  |
| 90  | 0.45 | 0.12   | 0.43  |

### Pathway-Specific Hazard Ratios

Interventions affect mortality through pathway-specific hazard ratios. The intervention mortality rate is:

$$
q_a^{\text{int}} = q_a \times \left(f_{\text{CVD}} \times \text{HR}_{\text{CVD}} + f_{\text{cancer}} \times \text{HR}_{\text{cancer}} + f_{\text{other}} \times \text{HR}_{\text{other}}\right)
$$

For most interventions, the observed hazard ratio $\text{HR}_{\text{obs}}$ is distributed across pathways with differential weighting. The framework uses:

$$
\log(\text{HR}_{\text{pathway}}) = w_{\text{pathway}} \times \log(\text{HR}_{\text{obs}})
$$

where default weights are:
- CVD: $w_{\text{CVD}} = 1.3$ (stronger effect on cardiovascular mortality)
- Cancer: $w_{\text{cancer}} = 0.8$
- Other: $w_{\text{other}} = 0.6$

These weights are calibrated to meta-analytic evidence on cause-specific mortality effects (Aune et al., 2016).

## Causal Inference: Confounding Adjustment

### Causal Fraction Model

Observational studies often overestimate causal effects due to healthy user bias and residual confounding. Optiqal adjusts hazard ratios using evidence-calibrated causal fractions:

$$
\log(\text{HR}_{\text{causal}}) = \theta \times \log(\text{HR}_{\text{obs}})
$$

where $\theta \in [0,1]$ is the causal fraction:
- $\theta = 1$: fully causal (no confounding)
- $\theta = 0$: fully spurious (entirely confounded)

### Beta Prior Distributions

The causal fraction $\theta$ is uncertain and varies by intervention category. Optiqal uses Beta distributions calibrated to RCT vs. observational discrepancies:

$$
\theta \sim \text{Beta}(\alpha, \beta)
$$

**Exercise interventions** (walking, moderate exercise):
- Prior: $\text{Beta}(1.2, 6.0)$
- Mean causal fraction: 17%
- 95% CI: [0.8%, 49.0%]
- **Rationale**: RCTs show minimal causal effect on mortality (Ballin et al., 2021, n=50,000). Finnish Twin Cohort study of identical twins discordant for physical activity found no mortality difference (2024). Mendelian randomization studies show null effects. Strong healthy user bias in observational studies.
- **Calibration sources**: Ballin et al. 2021 (RCT critical review, n=50,000); Finnish Twin Cohort 2024 (twin discordance); Mendelian randomization studies (null for mortality)

**Diet interventions** (Mediterranean diet):
- Prior: $\text{Beta}(3.0, 3.0)$
- Mean causal fraction: 50%
- 95% CI: [15%, 85%]
- **Rationale**: PREDIMED RCT confirms substantial causal effects on CVD (30% reduction, Estruch et al., 2018). Mendelian randomization supports causality (Larsson et al., 2020). Much stronger causal evidence than exercise.
- **Calibration sources**: PREDIMED Trial 2018 (RCT, n=7,447, 30% CVD reduction); Aune et al. 2016 (nut meta-analysis)

**Substance interventions** (smoking cessation, alcohol changes):
- Prior: $\text{Beta}(2.0, 4.0)$
- Mean causal fraction: 33%
- 95% CI: [6%, 68%]
- **Rationale**: Smoking cessation has strong RCT backing (~56% causal fraction, Taylor et al. 2014), but the alcohol J-curve is essentially entirely confounded (Mendelian randomization shows no benefit), so the pooled substance prior sits between them.
- **Calibration sources**: Taylor et al. 2014 (cessation RCTs); Stockwell et al. 2016 (alcohol J-curve as bias)

**Sleep interventions**:
- Prior: $\text{Beta}(1.5, 4.5)$
- Mean causal fraction: 25%
- 95% CI: [3%, 58%]
- **Rationale**: No RCTs for sleep duration and mortality. High reverse causation risk (illness affects sleep). CBT-I shows quality-of-life effects but mortality effects uncertain.
- **Calibration sources**: Cappuccio et al. 2010 (observational only); no mortality RCTs available

**Stress/meditation**:
- Prior: $\text{Beta}(1.2, 5.0)$
- Mean causal fraction: 19%
- 95% CI: [2%, 50%]
- **Rationale**: Meditation RCTs show much smaller effects than observational studies. Stress heavily confounded with SES and health behaviors.
- **Calibration sources**: Goyal et al. 2014 (meditation RCT meta-analysis); Khoury et al. 2015

**Medical interventions**:
- Prior: $\text{Beta}(2.5, 4.0)$
- Mean causal fraction: 38%
- 95% CI: [8%, 73%]
- **Rationale**: Even RCT-based drugs show observational inflation. Statins: HR 0.54 observational vs. 0.84 RCT (causal fraction ~28%, Danaei et al., 2012).
- **Calibration sources**: Danaei et al. 2012 (statin comparison); ARRIVE/ASPREE trials

**Social interventions**:
- Prior: $\text{Beta}(1.0, 5.5)$
- Mean causal fraction: 15%
- 95% CI: [1%, 42%]
- **Rationale**: Social relationships heavily confounded with SES, mental health, physical health. No RCT evidence possible for mortality.
- **Calibration sources**: Holt-Lunstad et al. 2010 (observational only)

**Other interventions**:
- Prior: $\text{Beta}(1.2, 4.8)$
- Mean causal fraction: 20%
- 95% CI: [2%, 50%]
- **Rationale**: Unknown intervention types use a conservative prior reflecting general observational bias in the calibration data.

### Monte Carlo Sampling

For each intervention, the framework samples from both the hazard ratio distribution and the causal fraction prior:

1. Sample $\text{HR}_{\text{obs}} \sim \text{LogNormal}(\mu, \sigma)$ from intervention definition
2. Sample $\theta \sim \text{Beta}(\alpha, \beta)$ from confounding prior
3. Calculate adjusted HR: $\text{HR}_{\text{causal}} = \exp(\theta \times \log(\text{HR}_{\text{obs}}))$
4. Run lifecycle simulation with adjusted HR
5. Repeat 5,000-10,000 times to estimate median, mean, and credible intervals

This propagates both epistemic uncertainty (parameter uncertainty) and causal uncertainty (confounding) into final estimates.

Note: the Beta parameters in this section are the live values in
`python/optiqal/data/priors.yaml`. That file is canonical; if the two ever
disagree, the registry wins and this document is stale.

## Quality-of-Life Evidence Guarding

Mortality effects have always passed through the guard stack above, but most
of the modeled protocol value flows through quality-of-life overlays (symptom
relief, wellbeing, sleep quality). These claims now pass through a parallel
guard (`optiqal/qol_evidence.py`), composed on the claimed annual effect:

$$
\text{QALY}_{\text{effective}} = \text{QALY}_{\text{claimed}} \times (1 - s) \times \theta
$$

1. **Study-quality shrinkage** $s$: reporting/publication inflation for
   patient-reported endpoints, tiered from 10% (objective-endpoint RCTs) to
   70% (mechanistic or self-experiment only). Subjective endpoints get
   harsher weak-end tiers than the mortality table because they are easier to
   p-hack and selectively report.
2. **Transport prior** $\theta \sim \text{Beta}(\alpha, \beta)$: the fraction
   of the claimed benefit expected to survive placebo/expectancy stripping and
   transport to an already-healthy, already-treated user. Category priors are
   calibrated to published placebo-adjusted versus open-label discrepancies
   (e.g. placebo response averages roughly two-thirds of drug response for
   subjective insomnia outcomes, Winkler & Rief 2015; commercial adaptogen
   trials shrink in better designs, Speers 2021; sham-controlled CPAP trials
   show roughly halved subjective gains versus open-label, Jenkinson 1999).

Two anchor modes prevent double-shrinking:

- **authored_shaded**: the authored mean already embeds a private severity
  judgment, so only study-quality shrinkage plus a mild residual-optimism
  prior ($\text{Beta}(6, 2)$, mean 75%) applies. Re-anchoring such an item to
  a published placebo-adjusted delta requires a user severity input.
- **published_delta**: the claim is a published delta or is applied to a
  measured personal burden, so the full category transport prior applies.
  Sleep-relief fractions use this mode: personal severity is measured
  (wearables plus a home sleep study), making the relief fraction a pure
  evidence claim. Guarded relief feeds **both** the sleep-QoL leg and the
  sleep-derived mortality hazard multiplier, closing a previous bypass where
  relief-derived mortality benefit skipped every evidence adjustment.

Claimed **harms** (negative QoL overlays) are never shrunk: conservatism cuts
against the intervention on both sides. Per-item annotations with study
quality, category, and rationale live in `optiqal/qol_annotations.py`; a test
fails if any positive claim lacks one.

### Predeclared range freeze

Per-item predeclared total-QALY ranges are frozen in
`optiqal/data/predeclared_ranges_v1.json` (stamped 2026-08-07, pre-guard).
The pipeline reports items outside their frozen range and any ranges edited
since the freeze, and the ranges are deliberately **not** rewritten to match
guarded outputs — a claim landing below its pre-guard authored expectation is
information, not an error to be tuned away.

## Baseline Mortality Adjustments by Profile

### Risk Factor Model

Baseline mortality rates are adjusted for individual risk profiles using multiplicative relative risks:

$$
q_a^{\text{profile}} = q_a \times \text{RR}_{\text{BMI}} \times \text{RR}_{\text{smoking}} \times \text{RR}_{\text{diabetes}} \times \text{RR}_{\text{HTN}} \times \text{RR}_{\text{activity}}
$$

This multiplicative model is conservative (may overestimate combined risk) but computationally tractable.

### BMI Relative Risks

**Source**: Global BMI Mortality Collaboration, 2016 (Lancet)

| BMI Category       | BMI Range | Relative Risk | 95% CI        |
|--------------------|-----------|---------------|---------------|
| Normal             | 18.5-25   | 1.00          | Reference     |
| Overweight         | 25-30     | 1.11          | 1.10-1.11     |
| Obese              | 30-35     | 1.44          | 1.38-1.50     |
| Severely obese     | 35+       | 2.06          | 1.90-2.23     |

### Smoking Relative Risks

**Source**: Jha et al. 2013 (NEJM); CDC mortality data

| Smoking Status | Relative Risk | Description                              |
|----------------|---------------|------------------------------------------|
| Never          | 1.00          | Reference                                |
| Former         | 1.34          | Former smokers retain ~34% excess risk   |
| Current        | 2.80          | Current smokers: 2.8× all-cause mortality|

### Diabetes Relative Risk

**Source**: Emerging Risk Factors Collaboration, 2011 (NEJM)

- Diabetes: RR = 1.80 (95% CI: 1.71-1.90)
- Adjusted for age, sex, smoking, BMI

### Hypertension Relative Risk

**Source**: Lewington et al. 2002 (Lancet, Prospective Studies Collaboration)

- Hypertension: RR = 1.50 (conservative for treated hypertension)
- Note: Each 20 mmHg SBP increase doubles CVD mortality in ages 40-69
- Untreated/uncontrolled hypertension would be higher (~2.0×)

### Physical Activity Relative Risks

**Source**: Lear et al. 2017 (PURE study); Ekelund et al. 2016

| Activity Level | Relative Risk | Description                    |
|----------------|---------------|--------------------------------|
| Sedentary      | 1.40          | Sitting >8h/day, no exercise   |
| Light          | 1.15          | Some walking, <150 min/week    |
| Moderate       | 1.00          | Meets guidelines (150 min/week)|
| Active         | 0.90          | Exceeds guidelines (300+ min)  |

### Profile Grid

The precomputation system uses a factorial grid of profiles:

- **Ages**: 25, 30, 35, ..., 80 (12 points)
- **Sex**: male, female (2)
- **BMI categories**: normal, overweight, obese, severely_obese (4)
- **Smoking status**: never, former, current (3)
- **Diabetes**: no, yes (2)
- **Hypertension**: no, yes (2)
- **Activity level**: light (default; varies via effect modifiers)

Total: 12 × 2 × 4 × 3 × 2 × 2 = **1,152 profiles** per intervention.

## Intervention Effect Modifiers

Effect modifiers adjust intervention effectiveness based on baseline characteristics. The adjusted hazard ratio is:

$$
\log(\text{HR}_{\text{modified}}) = m(\text{profile}) \times \log(\text{HR}_{\text{base}})
$$

where $m(\text{profile})$ is a multiplicative modifier:
- $m > 1$: intervention more effective (HR moves further from 1)
- $m < 1$: diminishing returns (HR moves closer to 1)

### Exercise Interventions

**Activity level modifiers** (baseline dependency):

| Baseline Activity | Modifier | Rationale                                          |
|-------------------|----------|---------------------------------------------------|
| Sedentary         | 1.20     | Largest gains from starting exercise              |
| Light             | 1.00     | Baseline effect                                   |
| Moderate          | 0.60     | Already meeting guidelines, smaller marginal gain |
| Active            | 0.30     | Already exceeding guidelines, minimal benefit     |

**Source**: Ekelund et al. 2016; Kodama et al. 2009

**Obesity modifier**: +15% effect for obese/severely obese (larger metabolic improvements)

**Age modifier**: -10% effect for age >70 (smaller mortality effect, though functional benefits remain)

**Hypertension modifier**: +10% effect for hypertensive individuals (larger BP reduction from exercise)

### Diet Interventions

**Obesity modifier**: +20% effect for obese/severely obese (greater room for metabolic improvement)

**Diabetes modifier**: +15% effect for diabetics (larger metabolic improvements)

**Hypertension modifier**: +10% effect for hypertensives (DASH/Mediterranean patterns reduce BP)

**Source**: Estruch et al. 2018 (PREDIMED); Grosso et al. 2017

### Smoking Cessation

**Age-dependent effectiveness** (younger quitters benefit more):

| Quit Age | Modifier | Rationale                                |
|----------|----------|------------------------------------------|
| <35      | 1.30     | Nearly eliminate excess mortality risk   |
| 35-44    | 1.15     | Large benefit                            |
| 45-54    | 1.00     | Baseline                                 |
| 55-64    | 0.85     | Moderate benefit                         |
| 65+      | 0.70     | Still beneficial but reduced             |

**Source**: Doll et al. 2004 (British Doctors Study); Jha et al. 2013

### Supplement Interventions

**Modifier for poor baseline health**: +20% effect for sedentary + obese individuals (more likely to have nutritional deficiencies)

### Stress/Sleep Interventions

**Sedentary modifier**: +10-15% effect (worse baseline sleep/stress management)

## Combination Effects

### Overlap Matrix

When combining multiple interventions, some pairs share mechanisms and exhibit less-than-additive effects. The overlap factor represents the fraction of the second intervention's effect retained when the first is already applied:

$$
\log(\text{HR}_{\text{combined}}) = \log(\text{HR}_1) + \sum_{i=2}^{n} O_{1...i-1,i} \times \log(\text{HR}_i)
$$

where $O_{1...i-1,i} \in [0,1]$ is the cumulative overlap factor.

**Key overlap relationships**:

| Intervention A           | Intervention B           | Overlap Factor | Rationale                              |
|--------------------------|--------------------------|----------------|----------------------------------------|
| Walking                  | Moderate exercise        | 0.40           | Walking is subset of moderate exercise |
| Walking                  | Strength training        | 0.80           | Different mechanisms (cardio vs. muscle)|
| Moderate exercise        | Strength training        | 0.70           | Some overlap in fitness benefits       |
| Mediterranean diet       | Fish oil supplement      | 0.50           | Mediterranean diet includes fish       |
| Meditation               | Sleep optimization       | 0.80           | Both affect stress, some overlap       |
| Exercise (moderate)      | Sleep optimization       | 0.85           | Exercise improves sleep                |

For pairs not in the matrix, the default overlap factor is 1.0 (fully additive).

### Diminishing Returns Formula

As more interventions are stacked, adherence decreases and marginal benefits shrink:

$$
\text{DR}(n) = \max(0.95^{n-1}, 0.80)
$$

where $n$ is the number of interventions. The final combined log hazard ratio is:

$$
\log(\text{HR}_{\text{final}}) = \text{DR}(n) \times \sum_{i=1}^{n} O_{1...i-1,i} \times \log(\text{HR}_i)
$$

**Diminishing returns schedule**:

| Number of Interventions | Multiplier |
|-------------------------|------------|
| 1                       | 1.00       |
| 2                       | 0.95       |
| 3                       | 0.90       |
| 4                       | 0.85       |
| 5+                      | 0.80 (floor)|

**Rationale**:
- As baseline risk decreases, additional interventions have less absolute room to provide benefit
- Adherence burden increases with intervention complexity
- Biological redundancy: multiple interventions may target overlapping pathways

The combined hazard ratio is capped at HR = 0.10 (maximum 90% mortality reduction).

## Evidence Quality and Sources

### Intervention Definitions

Each intervention is defined in YAML format with:

1. **Mortality effect**: LogNormal distribution for hazard ratio
   - Example: `LogNormal(-0.18, 0.08)` for walking (median HR = 0.84, 95% CI: 0.72-0.97)

2. **Mechanism effects**: Changes in biomarkers/pathways
   - Blood pressure: `Normal(-4, 2)` mmHg
   - Insulin sensitivity: `Normal(15, 8)` %
   - Inflammation (CRP): `Normal(-15, 8)` %

3. **Evidence quality**: high, moderate, low, very-low

4. **Primary sources**: Citations to meta-analyses and RCTs

5. **Confounding prior**: Beta distribution for causal fraction

### Example: Mediterranean Diet

```yaml
mortality:
  hazard_ratio: LogNormal(-0.25, 0.10)
  # Median HR = 0.78, 95% CI: 0.64-0.95
  # Source: Sofi et al. 2014 (meta-analysis, n=1.5M)

confounding:
  prior:
    type: beta
    alpha: 3.0
    beta: 3.0
  # Mean causal fraction: 50%
  # Serves the diet category prior (PREDIMED 2018, Aune 2016)
```

### Example: Walking 30 Minutes Daily

```yaml
mortality:
  hazard_ratio: LogNormal(-0.18, 0.08)
  # Median HR = 0.84, 95% CI: 0.72-0.97
  # Source: Hamer & Chida 2008 (meta-analysis, n=460K)

confounding:
  prior:
    type: beta
    alpha: 1.2
    beta: 6.0
  # Mean causal fraction: 17%
  # Serves the exercise category prior (Ballin 2021, Finnish Twin Cohort 2024)
```

## Time Horizon and Temporal Effects

### Onset Delay

Some interventions have delayed benefits (e.g., smoking cessation takes years to fully reduce cancer risk). The onset delay parameter $t_{\text{onset}}$ delays the start of HR application.

### Ramp-Up Period

Effects gradually increase over time with ramp-up period $t_{\text{ramp}}$:

$$
\text{HR}_{\text{effective}}(t) = \begin{cases}
1 & \text{if } t < t_{\text{onset}} \\
1 - \frac{t - t_{\text{onset}}}{t_{\text{ramp}}} \times (1 - \text{HR}) & \text{if } t_{\text{onset}} \le t < t_{\text{onset}} + t_{\text{ramp}} \\
\text{HR} & \text{if } t \ge t_{\text{onset}} + t_{\text{ramp}}
\end{cases}
$$

### Decay Rate

For interventions with adherence decay, the effect diminishes over time:

$$
\text{HR}(t) = 1 - (1 - \text{HR}_0) \times e^{-\lambda t}
$$

where $\lambda$ is the decay rate. Most interventions assume $\lambda = 0$ (persistent effects with perfect adherence).

## Limitations

### Model Structure

1. **Multiplicative mortality assumption**: The model assumes risk factors combine multiplicatively, which may overestimate combined effects. Additive or intermediate models may be more accurate for some combinations.

2. **Pathway independence**: CVD, cancer, and other mortality pathways are assumed to be conditionally independent given the intervention. Shared biological mechanisms may induce correlations.

3. **Life table limitations**: CDC life tables represent population averages and may not fully capture heterogeneity within demographic groups.

### Causal Inference

4. **Confounding priors**: Beta priors are calibrated to limited RCT vs. observational comparisons. Evidence continues to evolve (e.g., the Finnish Twin Cohort 2024 exercise study strengthens skepticism).

5. **Unmeasured effect modifiers**: The model includes age, sex, BMI, smoking, diabetes, hypertension, and activity level, but does not account for genetics, detailed medical history, medication use, or socioeconomic factors.

6. **Selection effects**: Individuals who adopt interventions may differ from those who don't in unmeasured ways (motivation, health literacy, resources).

### Intervention Specifics

7. **Adherence**: The model assumes perfect, sustained adherence. Real-world adherence is typically 30-70% for lifestyle interventions, substantially reducing benefits.

8. **Intervention quality**: Effects assume high-quality implementation (e.g., "Mediterranean diet" assumes authentic adherence to the PREDIMED protocol, not just "eating more vegetables").

9. **Context dependency**: Benefits may vary by food environment, built environment, social support, and cultural context.

### Uncertainty

10. **Parameter uncertainty**: Hazard ratio distributions capture study uncertainty but may not fully reflect unknown unknowns or publication bias.

11. **Model uncertainty**: The functional form (exponential survival, log-linear hazard ratios) is conventional but not uniquely justified.

12. **Extrapolation**: Long-term effects (20+ years) are extrapolated from shorter studies. Benefits may diminish or accumulate differently than assumed.

### Combination Effects

13. **Overlap matrix subjectivity**: Overlap factors are informed estimates based on mechanistic reasoning, not direct empirical measurements of combined interventions.

14. **Limited RCT evidence**: Very few RCTs test combinations of 3+ interventions, so combination effects rely on modeling assumptions.

15. **Non-linear interactions**: Some intervention pairs may have synergistic (super-additive) or antagonistic (sub-additive) effects not captured by the overlap model.

### Quality of Life

16. **Quality weights**: Age-specific quality weights are population averages and do not account for individual variation in disability, pain, or functional status.

17. **Intervention-specific QoL**: The model does not yet incorporate intervention-specific quality-of-life effects beyond mortality (e.g., improved energy, reduced pain, cognitive benefits).

### Generalizability

18. **Population differences**: Most evidence comes from high-income countries (US, Europe). Effects may differ in other populations.

19. **Secular trends**: Mortality rates and disease patterns are changing over time. Historical life tables may not perfectly predict future longevity.

20. **Competing risks**: The model does not explicitly model competing risks (e.g., someone who avoids CVD death may die of cancer instead), though pathway decomposition partially addresses this.

## References

Aune D, et al. Fruit and vegetable intake and the risk of cardiovascular disease, total cancer and all-cause mortality. Int J Epidemiol. 2017;46(3):1029-1056.

Ballin M, et al. Effects of interval training on visceral adipose tissue in centrally obese older adults. Int J Obes. 2021;45:1934-1943.

Cappuccio FP, et al. Sleep duration and all-cause mortality: a systematic review and meta-analysis. Sleep. 2010;33(5):585-592.

Danaei G, et al. Observational data and randomized trial estimates of statin effects. Circulation. 2012;125:2015-2026.

Doll R, et al. Mortality in relation to smoking: 50 years' observations on male British doctors. BMJ. 2004;328:1519.

Ekelund U, et al. Does physical activity attenuate, or even eliminate, the detrimental association of sitting time with mortality? Lancet. 2016;388:1389-1396.

Emerging Risk Factors Collaboration. Diabetes mellitus, fasting blood glucose concentration, and risk of vascular disease. NEJM. 2011;364:829-841.

Estruch R, et al. Primary prevention of cardiovascular disease with a Mediterranean diet supplemented with extra-virgin olive oil or nuts. NEJM. 2018;378:e34.

Global BMI Mortality Collaboration. Body-mass index and all-cause mortality. Lancet. 2016;388:776-786.

Goyal M, et al. Meditation programs for psychological stress and well-being. JAMA Intern Med. 2014;174(3):357-368.

Grosso G, et al. A comprehensive meta-analysis on dietary flavonoid and lignan intake and cancer risk. Nutr Cancer. 2017;69(8):1119-1130.

Hamer M, Chida Y. Walking and primary prevention: a meta-analysis of prospective cohort studies. Br J Sports Med. 2008;42(4):238-243.

Holt-Lunstad J, et al. Social relationships and mortality risk: a meta-analytic review. PLoS Med. 2010;7(7):e1000316.

Jha P, et al. 21st-century hazards of smoking and benefits of cessation in the United States. NEJM. 2013;368:341-350.

Kodama S, et al. Effect of aerobic exercise training on serum levels of high-density lipoprotein cholesterol. Arch Intern Med. 2007;167(10):999-1008.

Larsson SC, et al. Modifiable pathways in Alzheimer's disease: Mendelian randomisation analysis. BMJ. 2020;368:l6820.

Lear SA, et al. The effect of physical activity on mortality and cardiovascular disease in 130,000 people from 17 high-income, middle-income, and low-income countries. Lancet. 2017;390:2643-2654.

Lewington S, et al. Age-specific relevance of usual blood pressure to vascular mortality. Lancet. 2002;360:1903-1913.

Sanders GD, et al. Recommendations for conduct, methodological practices, and reporting of cost-effectiveness analyses: Second Panel on Cost-Effectiveness in Health and Medicine. JAMA. 2016;316(10):1093-1103.

Sofi F, et al. Adherence to Mediterranean diet and health status: meta-analysis. BMJ. 2008;337:a1344.

Sullivan PW, et al. Catalog of preference scores from published cost-utility analyses. Med Decis Making. 2006;26(4):342-362.

Taylor FC, et al. Mortality reductions in patients receiving exercise-based cardiac rehabilitation: how much can be attributed to cardiovascular risk factor improvements? Eur J Cardiovasc Prev Rehabil. 2014;13(3):369-374.

VanderWeele TJ, Ding P. Sensitivity analysis in observational research: introducing the E-value. Ann Intern Med. 2017;167(4):268-274.
