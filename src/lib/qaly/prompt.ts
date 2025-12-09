/**
 * Structured prompt for eliciting mechanism-level intervention effects
 */

import type { Mechanism } from "./mechanisms";

/**
 * All mechanisms Claude can report on
 */
export const ALL_MECHANISMS: Mechanism[] = [
  // Cardiovascular
  "blood_pressure",
  "lipid_profile",
  "endothelial_function",
  "arterial_stiffness",
  "heart_rate_variability",
  "cardiac_output",
  // Metabolic
  "insulin_sensitivity",
  "glucose_regulation",
  "adiposity",
  "metabolic_rate",
  "mitochondrial_function",
  // Inflammatory/Immune
  "systemic_inflammation",
  "oxidative_stress",
  "immune_function",
  "gut_microbiome",
  // Neurological
  "neuroplasticity",
  "bdnf_levels",
  "neurotransmitter_balance",
  "sleep_quality",
  "stress_hormones",
  "cognitive_reserve",
  // Musculoskeletal
  "muscle_mass",
  "bone_density",
  "joint_health",
  "balance_proprioception",
  // Cellular
  "telomere_length",
  "cellular_senescence",
  "autophagy",
  "dna_repair",
  // Respiratory
  "lung_function",
  "oxygen_delivery",
];

export const MECHANISM_ELICITATION_PROMPT = `You are a biomedical evidence synthesizer. Your task is to estimate how an intervention affects specific biological mechanisms, based on your knowledge of the scientific literature.

For each mechanism, you will estimate:
1. Whether the intervention affects it (yes/no)
2. Direction of effect (increase/decrease)
3. Effect size as a distribution (mean and standard deviation)
4. Evidence quality (strong/moderate/weak)
5. Key source(s)

MECHANISMS TO EVALUATE:

**Cardiovascular:**
- blood_pressure: Systolic/diastolic BP in mmHg
- lipid_profile: LDL, HDL, triglycerides (express as % change)
- endothelial_function: Flow-mediated dilation (% change)
- arterial_stiffness: Pulse wave velocity (% change)
- heart_rate_variability: HRV metrics (% change)
- cardiac_output: Cardiac output/stroke volume (% change)

**Metabolic:**
- insulin_sensitivity: HOMA-IR, glucose disposal (% change)
- glucose_regulation: HbA1c, fasting glucose (% change)
- adiposity: Body fat %, visceral fat (% change or kg)
- metabolic_rate: Resting metabolic rate (% change)
- mitochondrial_function: Mitochondrial markers (standardized effect)

**Inflammatory/Immune:**
- systemic_inflammation: CRP, IL-6, TNF-α (% change)
- oxidative_stress: Oxidative markers (% change)
- immune_function: Immune cell counts/function (standardized effect)
- gut_microbiome: Diversity, beneficial bacteria (standardized effect)

**Neurological:**
- neuroplasticity: Hippocampal volume, neurogenesis markers (standardized effect)
- bdnf_levels: Serum/plasma BDNF (% change)
- neurotransmitter_balance: Serotonin, dopamine markers (standardized effect)
- sleep_quality: Sleep efficiency, duration, architecture (standardized effect)
- stress_hormones: Cortisol, catecholamines (% change)
- cognitive_reserve: Cognitive test performance (standardized effect)

**Musculoskeletal:**
- muscle_mass: Lean mass, strength (% change or kg)
- bone_density: BMD (% change)
- joint_health: Cartilage markers (standardized effect)
- balance_proprioception: Balance test performance (standardized effect)

**Cellular:**
- telomere_length: Telomere length (% change)
- cellular_senescence: Senescence markers (standardized effect)
- autophagy: Autophagy markers (standardized effect)
- dna_repair: DNA repair markers (standardized effect)

**Respiratory:**
- lung_function: FEV1, VO2max (% change)
- oxygen_delivery: Oxygen extraction (% change)

RESPONSE FORMAT:
Return a JSON object with this structure:

{
  "intervention": "description of what was analyzed",
  "mechanismEffects": [
    {
      "mechanism": "blood_pressure",
      "affected": true,
      "direction": "decrease",
      "effectSize": {
        "type": "normal",
        "mean": -5.0,
        "sd": 2.0
      },
      "units": "mmHg",
      "evidenceQuality": "strong",
      "source": "Cornelissen & Smart 2013 meta-analysis",
      "reasoning": "Brief explanation of why this effect size"
    }
  ],
  "directMortalityEffect": {
    "hasDirectEffect": true,
    "hazardRatio": {
      "type": "lognormal",
      "logMean": -0.15,
      "logSd": 0.08
    },
    "source": "If there's direct mortality evidence beyond mechanisms"
  },
  "overallEvidenceQuality": "moderate",
  "caveats": ["Important limitations"],
  "keyStudies": [
    {
      "citation": "Author et al., Journal, Year",
      "studyType": "meta-analysis",
      "sampleSize": 10000,
      "relevance": "What this study contributes"
    }
  ]
}

IMPORTANT GUIDELINES:
- Only include mechanisms that are actually affected (don't list all mechanisms with "affected: false")
- Use conservative effect sizes - don't overstate evidence
- For weak evidence, use larger standard deviations
- Express uncertainty honestly
- Distinguish between direct evidence (RCTs on this intervention) and mechanistic extrapolation
- Consider dose-response: effect sizes should be calibrated to the specific intervention dose/intensity
- Account for the user's baseline when relevant (e.g., effect of exercise depends on current fitness)`;

/**
 * Generate the full prompt for Claude
 */
export function generateElicitationPrompt(
  intervention: string,
  userContext: string
): string {
  return `${MECHANISM_ELICITATION_PROMPT}

---

USER CONTEXT:
${userContext}

INTERVENTION TO ANALYZE:
"${intervention}"

Please analyze this intervention's effects on biological mechanisms. Only include mechanisms that are likely affected. Use Bayesian reasoning: start with mechanistic priors, update with empirical evidence, and express appropriate uncertainty.

Return ONLY the JSON object, no other text.`;
}
