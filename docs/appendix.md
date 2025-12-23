---
kernelspec:
  name: python3
  display_name: Python 3
---

# Technical Appendix

```{code-cell} python
:tags: [remove-cell]

import sys
sys.path.insert(0, '.')
from optiqal_results import r
```

## A. State Schema

The complete `PersonState` schema in TypeScript:

```typescript
interface PersonState {
  demographics: {
    birthYear: number;
    sex: "male" | "female";
    ethnicity?: string;
  };

  conditions: Condition[];  // Diagnosed conditions with severity

  biomarkers: {
    systolicBP?: number;     // mmHg
    diastolicBP?: number;
    bmi?: number;
    ldlCholesterol?: number; // mg/dL
    hdlCholesterol?: number;
    fastingGlucose?: number;
    hba1c?: number;          // %
  };

  behaviors: {
    exercise: {
      aerobicMinutesPerWeek: number;
      strengthSessionsPerWeek: number;
    };
    diet: {
      mediterraneanAdherence: number;  // 0-1
      processedFoodPercent: number;
      vegetableServingsPerDay: number;
    };
    smoking: {
      status: "never" | "former" | "current";
      packYears?: number;
      yearsQuit?: number;
    };
    alcohol: {
      drinksPerWeek: number;
      bingeFrequency: "never" | "monthly" | "weekly";
    };
    sleep: {
      hoursPerNight: number;
      quality: "poor" | "fair" | "good" | "excellent";
    };
    social: {
      closeRelationships: number;
      livesAlone: boolean;
    };
  };

  environment: {
    airQualityAQI?: number;
    walkabilityScore?: number;
    healthcareAccess?: "poor" | "moderate" | "good";
  };
}
```

## B. Causal DAG Specification

The complete causal DAG mapping interventions to downstream effects:

```typescript
const CAUSAL_DAG = {
  exercise: [
    { downstream: "bmi", effectSize: -0.5, perUnit: "per 150 min/week" },
    { downstream: "systolicBP", effectSize: -4, perUnit: "per 150 min/week" },
    { downstream: "hdlCholesterol", effectSize: +3, perUnit: "per 150 min/week" },
    { downstream: "sleepHours", effectSize: +0.2, perUnit: "per 150 min/week" },
    { downstream: "depression", effectSize: -0.3, perUnit: "SD per 150 min/week" },
  ],

  diet: [
    { downstream: "bmi", effectSize: -1.0, perUnit: "per 0.5 adherence" },
    { downstream: "ldlCholesterol", effectSize: -10, perUnit: "per 0.5 adherence" },
    { downstream: "systolicBP", effectSize: -3, perUnit: "per 0.5 adherence" },
  ],

  smoking_cessation: [
    { downstream: "bmi", effectSize: +2.0, perUnit: "after quitting" },
    { downstream: "systolicBP", effectSize: -5, perUnit: "after cessation" },
    { downstream: "lungFunction", effectSize: +5, perUnit: "% FEV1" },
  ],

  alcohol_reduction: [
    { downstream: "bmi", effectSize: -0.3, perUnit: "per 7 drinks/week" },
    { downstream: "systolicBP", effectSize: -3, perUnit: "per 50% reduction" },
  ],

  sleep: [
    { downstream: "bmi", effectSize: -0.2, perUnit: "per 1 hour" },
    { downstream: "depression", effectSize: -0.2, perUnit: "SD per hour" },
  ],
};
```

Sources for effect sizes:
- Exercise → BMI: DPP trial lifestyle intervention arm
- Exercise → BP: Cornelissen 2013 meta-analysis of 93 trials
- Exercise → HDL: Kodama 2007 meta-analysis
- Diet → LDL: PREDIMED trial
- Diet → BP: DASH trial
- Smoking → weight: Aubin 2012 meta-analysis

## C. Imputation Model

Behavior imputation from demographics:

```typescript
function imputeBehaviors(input: { age, sex, bmi?, smokingStatus?, education? }) {
  // Exercise: Base 150 min/week, adjusted by BMI, age, sex
  const exerciseBase = 150;
  const bmiEffect = (bmi - 25) * -8;        // Higher BMI → less exercise
  const ageEffect = max(0, (age - 40) * -2); // Older → less exercise
  const sexEffect = sex === "male" ? 20 : 0;
  const exerciseMean = max(0, exerciseBase + bmiEffect + ageEffect + sexEffect);

  // Diet: Base 0.45 Mediterranean adherence
  const dietBase = 0.45;
  const dietBmiEffect = (bmi - 25) * -0.02;
  const dietAgeEffect = age > 60 ? 0.05 : 0;
  const dietEducationEffect = education in ["college", "graduate"] ? 0.10 : 0;
  const dietMean = clamp(0, 1, dietBase + dietBmiEffect + dietAgeEffect + dietEducationEffect);

  // ... similar for alcohol, sleep, social
}
```

These equations are calibrated to NHANES 2017-2020 population distributions.

## D. Hazard Ratio Database

Complete hazard ratios used for risk factor → mortality:

| Risk Factor | Comparison | HR | 95% CI | Source |
|-------------|------------|-----|--------|--------|
| **Smoking** | | | | |
| Current vs never | 20 pack-years | 2.80 | [2.45, 3.20] | Jha 2013 |
| Former vs never | Quit 5+ years | 1.34 | [1.25, 1.44] | Jha 2013 |
| **BMI** | | | | |
| Obese (30-35) vs normal | Per 5 kg/m² | 1.29 | [1.22, 1.36] | GSCB 2009 |
| Severely obese (35+) | Per 5 kg/m² | 1.91 | [1.67, 2.18] | GSCB 2009 |
| **Exercise** | | | | |
| 150+ min/week vs sedentary | | 0.70 | [0.64, 0.77] | Arem 2015 |
| 75-150 min/week | | 0.80 | [0.74, 0.87] | Arem 2015 |
| **Blood Pressure** | | | | |
| Stage 1 HTN (130-139) | vs <120 | 1.20 | [1.12, 1.29] | PSC 2002 |
| Stage 2 HTN (140+) | vs <120 | 1.56 | [1.44, 1.69] | PSC 2002 |
| **Diet** | | | | |
| Mediterranean high | vs low | 0.79 | [0.73, 0.85] | PREDIMED |
| **Alcohol** | | | | |
| Heavy (>14/week) | vs moderate | 1.24 | [1.15, 1.34] | Wood 2018 |
| **Sleep** | | | | |
| <6 hours | vs 7-8 hours | 1.13 | [1.06, 1.21] | Cappuccio 2010 |
| **Social** | | | | |
| Social isolation | vs connected | 1.50 | [1.35, 1.67] | Holt-Lunstad 2010 |

## E. Confounding Calibration

The confounding prior Beta({eval}`r.confounding.alpha`, {eval}`r.confounding.beta`) was calibrated using:

### E.1 RCT vs Observational Comparison

| Intervention | RCT Effect | Observational Effect | Ratio |
|--------------|------------|---------------------|-------|
| Exercise → CVD | HR 0.86 | HR 0.70 | 0.48 |
| Diet → mortality | HR 0.91 | HR 0.79 | 0.67 |
| Omega-3 supplements | HR 0.97 | HR 0.82 | 0.17 |

Weighted average: ~0.33 of observational effect is causal.

### E.2 E-value Analysis

For observed HR = 0.70, the E-value is 2.22—meaning unmeasured confounding would need HR ≥ 2.22 with both exposure AND outcome to fully explain the association. Given typical confounder strengths of 1.3-1.8, substantial causal effect likely remains.

### E.3 Within-Sibling Designs

Sibling-comparison studies typically find 30-50% attenuation versus unpaired estimates, consistent with our prior.

## F. Monte Carlo Simulation

The simulation proceeds as follows:

```python
def simulate_qaly_impact(baseline_state, counterfactual_state, n_simulations=10000):
    results = []
    for i in range(n_simulations):
        # Sample hazard ratios with uncertainty
        baseline_hr = sample_hazard_ratio(baseline_state)
        counter_hr = sample_hazard_ratio(counterfactual_state)

        # Sample confounding adjustment
        causal_fraction = sample_beta(alpha=2.5, beta=5.0)

        # Adjust for confounding
        adjusted_hr = 1 + causal_fraction * (counter_hr - 1)

        # Compute lifecycle QALYs
        baseline_qaly = integrate_lifecycle(baseline_state, baseline_hr)
        counter_qaly = integrate_lifecycle(counterfactual_state, adjusted_hr)

        results.append(counter_qaly - baseline_qaly)

    return {
        'mean': np.mean(results),
        'ci_lower': np.percentile(results, 2.5),
        'ci_upper': np.percentile(results, 97.5),
    }
```

## G. Precomputed Interventions

The full list of {eval}`r.intervention_count` precomputed interventions by category:

### Exercise
- Walking 30 min daily
- Running (moderate)
- Strength training 2x/week
- Swimming
- Cycling
- Yoga
- HIIT training
- Standing desk

### Diet
- Mediterranean diet
- Reduce processed food
- Increase vegetables
- Reduce sugar
- Daily nut consumption
- Fish twice weekly
- Olive oil daily
- Berry consumption
- Intermittent fasting
- Caloric restriction
- Increase fiber
- Reduce red meat
- Adequate hydration

### Substance
- Quit smoking
- Reduce alcohol (moderate)
- Quit alcohol
- Coffee (moderate)
- Green tea

### Sleep
- Consistent bedtime
- Blue light blocking
- Sleep apnea treatment (CPAP)

### Social/Stress
- Regular social interaction
- Marriage/partnership
- Volunteering
- Therapy/counseling
- Gratitude practice
- Nature exposure
- Meditation daily

### Medical
- Blood pressure medication
- Statin therapy
- Vitamin D supplement
- Magnesium supplement
- Creatine supplement
- Probiotic supplement
- B vitamin complex
- CoQ10 supplement
- Curcumin supplement

### Environment
- Air purifier
- Move to walkable city
- Reduce noise pollution
