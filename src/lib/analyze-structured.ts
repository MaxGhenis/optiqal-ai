/**
 * Structured QALY analysis using mechanism-based approach
 *
 * Flow:
 * 1. Send intervention to Claude with mechanism elicitation prompt
 * 2. Parse mechanism effects from response
 * 3. Use mechanism→condition mappings to derive condition effects
 * 4. Run Monte Carlo simulation
 * 5. Return structured results with full uncertainty quantification
 */

import Anthropic from "@anthropic-ai/sdk";
import type { UserProfile } from "@/types";
import {
  type Distribution,
  type MechanismEffect,
  type InterventionEffect,
  type QALYSimulationResult,
  type Mechanism,
  MECHANISM_CONDITION_LINKS,
  simulateQALYImpact,
  qalyYearsToMinutes,
} from "@/lib/qaly";
import { calculateBaselineQALYs } from "@/lib/evidence/baseline";

/**
 * Response from Claude's mechanism elicitation
 */
interface ClaudeMechanismResponse {
  intervention: string;
  mechanismEffects: {
    mechanism: string;
    affected: boolean;
    direction: "increase" | "decrease";
    effectSize: {
      type: "normal" | "lognormal" | "uniform" | "point";
      mean?: number;
      sd?: number;
      logMean?: number;
      logSd?: number;
      min?: number;
      max?: number;
      value?: number;
    };
    units?: string;
    evidenceQuality: "strong" | "moderate" | "weak";
    source?: string;
    reasoning?: string;
  }[];
  directMortalityEffect?: {
    hasDirectEffect: boolean;
    hazardRatio?: {
      type: "lognormal";
      logMean: number;
      logSd: number;
    };
    source?: string;
  };
  overallEvidenceQuality: "high" | "moderate" | "low" | "very-low";
  caveats: string[];
  keyStudies: {
    citation: string;
    studyType: string;
    sampleSize?: number;
    relevance: string;
  }[];
}

/**
 * Full analysis result with mechanism details
 */
export interface StructuredAnalysisResult {
  // Original input
  intervention: string;
  profile: UserProfile;

  // Baseline projection
  baseline: {
    remainingLifeExpectancy: number;
    remainingQALYs: number;
  };

  // Mechanism-level effects from Claude
  mechanismEffects: MechanismEffect[];

  // Monte Carlo simulation results
  simulation: QALYSimulationResult;

  // Human-readable summary
  summary: {
    totalQALYs: { median: number; ci95Low: number; ci95High: number };
    totalMinutes: { median: number; ci95Low: number; ci95High: number };
    probPositive: number;
    confidenceLevel: "high" | "medium" | "low";
  };

  // Evidence details
  evidence: {
    quality: "high" | "moderate" | "low" | "very-low";
    keyStudies: { citation: string; studyType: string; relevance: string }[];
    caveats: string[];
  };

  // Affected mechanisms and conditions (for display)
  affectedMechanisms: {
    mechanism: string;
    direction: "increase" | "decrease";
    evidenceQuality: string;
    affectedConditions: string[];
  }[];
}

const MECHANISM_ELICITATION_SYSTEM = `You are a biomedical evidence synthesizer. Analyze interventions by estimating their effects on specific biological mechanisms.

For each AFFECTED mechanism, provide:
- Direction (increase/decrease)
- Effect size as a distribution (mean + SD for normal, or logMean + logSD for lognormal)
- Evidence quality (strong/moderate/weak)
- Key source

MECHANISMS TO CONSIDER:

Cardiovascular: blood_pressure, lipid_profile, endothelial_function, arterial_stiffness, heart_rate_variability, cardiac_output
Metabolic: insulin_sensitivity, glucose_regulation, adiposity, metabolic_rate, mitochondrial_function
Inflammatory: systemic_inflammation, oxidative_stress, immune_function, gut_microbiome
Neurological: neuroplasticity, bdnf_levels, neurotransmitter_balance, sleep_quality, stress_hormones, cognitive_reserve
Musculoskeletal: muscle_mass, bone_density, joint_health, balance_proprioception
Cellular: telomere_length, cellular_senescence, autophagy, dna_repair
Respiratory: lung_function, oxygen_delivery

EFFECT SIZE GUIDANCE:
- blood_pressure: express in mmHg (e.g., -5 mmHg with SD 2)
- lipid_profile, inflammation, etc.: express as % change (e.g., -15% with SD 8%)
- For other mechanisms: use standardized effect sizes (Cohen's d)
- Use CONSERVATIVE estimates - don't overstate evidence
- Larger SD when evidence is weak or heterogeneous

RESPONSE FORMAT (JSON only):
{
  "intervention": "description",
  "mechanismEffects": [
    {
      "mechanism": "blood_pressure",
      "affected": true,
      "direction": "decrease",
      "effectSize": { "type": "normal", "mean": -5.0, "sd": 2.0 },
      "units": "mmHg",
      "evidenceQuality": "strong",
      "source": "Cornelissen 2013 meta-analysis",
      "reasoning": "Why this effect size"
    }
  ],
  "directMortalityEffect": {
    "hasDirectEffect": true,
    "hazardRatio": { "type": "lognormal", "logMean": -0.15, "logSd": 0.08 },
    "source": "Source if direct mortality evidence exists"
  },
  "overallEvidenceQuality": "moderate",
  "caveats": ["Important limitations"],
  "keyStudies": [
    { "citation": "Author, Year", "studyType": "meta-analysis", "sampleSize": 10000, "relevance": "Why relevant" }
  ]
}

Only include mechanisms that ARE affected. Be Bayesian: conservative priors, update with evidence, wide uncertainty when evidence is weak.`;

/**
 * Call Claude to elicit mechanism effects
 */
async function elicitMechanismEffects(
  intervention: string,
  profile: UserProfile,
  apiKey: string
): Promise<ClaudeMechanismResponse> {
  const client = new Anthropic({ apiKey, dangerouslyAllowBrowser: true });

  const bmi = profile.weight / (profile.height / 100) ** 2;

  const userMessage = `USER CONTEXT:
- Age: ${profile.age}, Sex: ${profile.sex}
- BMI: ${bmi.toFixed(1)} (${profile.weight}kg, ${profile.height}cm)
- Exercise: ${profile.exerciseHoursPerWeek} hrs/week
- Sleep: ${profile.sleepHoursPerNight} hrs/night
- Diet: ${profile.diet}
- Smoker: ${profile.smoker ? "Yes" : "No"}

INTERVENTION TO ANALYZE:
"${intervention}"

Analyze which biological mechanisms this intervention affects. Consider the user's baseline when estimating marginal effects (e.g., someone already exercising 5hrs/week gets less benefit from more exercise).

Return ONLY valid JSON.`;

  const response = await client.messages.create({
    model: "claude-opus-4-5-20251101",
    max_tokens: 4096,
    messages: [{ role: "user", content: userMessage }],
    system: MECHANISM_ELICITATION_SYSTEM,
  });

  const textContent = response.content.find((block) => block.type === "text");
  if (!textContent || textContent.type !== "text") {
    throw new Error("No text response from API");
  }

  let jsonText = textContent.text;
  const jsonMatch = jsonText.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (jsonMatch) {
    jsonText = jsonMatch[1];
  }

  try {
    return JSON.parse(jsonText.trim()) as ClaudeMechanismResponse;
  } catch {
    console.error("Failed to parse mechanism response:", jsonText);
    throw new Error("Failed to parse mechanism response as JSON");
  }
}

/**
 * Convert Claude's effect size to our Distribution type
 */
function parseDistribution(
  effectSize: ClaudeMechanismResponse["mechanismEffects"][0]["effectSize"]
): Distribution {
  switch (effectSize.type) {
    case "normal":
      return {
        type: "normal",
        mean: effectSize.mean ?? 0,
        sd: effectSize.sd ?? 1,
      };
    case "lognormal":
      return {
        type: "lognormal",
        logMean: effectSize.logMean ?? 0,
        logSd: effectSize.logSd ?? 0.5,
      };
    case "uniform":
      return {
        type: "uniform",
        min: effectSize.min ?? 0,
        max: effectSize.max ?? 1,
      };
    case "point":
    default:
      return { type: "point", value: effectSize.value ?? effectSize.mean ?? 0 };
  }
}

/**
 * Convert Claude's mechanism response to our InterventionEffect type
 */
function convertToInterventionEffect(
  response: ClaudeMechanismResponse
): InterventionEffect {
  const mechanismEffects: MechanismEffect[] = response.mechanismEffects
    .filter((m) => m.affected)
    .map((m) => ({
      mechanism: m.mechanism as Mechanism,
      effectSize: parseDistribution(m.effectSize),
      direction: m.direction,
      units: m.units,
      evidenceQuality: m.evidenceQuality,
      source: m.source,
    }));

  // Build mortality effect if Claude provided direct evidence
  let mortality = null;
  if (response.directMortalityEffect?.hasDirectEffect && response.directMortalityEffect.hazardRatio) {
    mortality = {
      hazardRatio: {
        type: "lognormal" as const,
        logMean: response.directMortalityEffect.hazardRatio.logMean,
        logSd: response.directMortalityEffect.hazardRatio.logSd,
      },
      affectedCauses: undefined,
      onsetDelay: 0,
      rampUpPeriod: 1,
      persistenceAfterStopping: undefined,
      decayRate: 0,
    };
  }

  return {
    description: response.intervention,
    category: "other",
    mechanismEffects,
    mortality,
    quality: null, // Will be derived from mechanisms
    costs: null,
    evidenceQuality: response.overallEvidenceQuality,
    keySources: response.keyStudies.map((s) => ({
      citation: s.citation,
      studyType: s.studyType as "meta-analysis" | "rct" | "cohort" | "case-control" | "other",
      sampleSize: s.sampleSize,
      contribution: s.relevance,
    })),
    caveats: response.caveats,
    profileAdjustments: [],
  };
}

/**
 * Get conditions affected by mechanisms
 */
function getAffectedConditions(mechanisms: MechanismEffect[]): Map<string, string[]> {
  const mechanismToConditions = new Map<string, string[]>();

  for (const mech of mechanisms) {
    const links = MECHANISM_CONDITION_LINKS[mech.mechanism];
    if (links) {
      const conditions = links.map((l) => l.condition);
      mechanismToConditions.set(mech.mechanism, conditions);
    }
  }

  return mechanismToConditions;
}

/**
 * Main entry point: analyze an intervention with full mechanism decomposition
 */
export async function analyzeStructured(
  profile: UserProfile,
  intervention: string,
  apiKey: string
): Promise<StructuredAnalysisResult> {
  // 1. Get baseline projection
  const baseline = calculateBaselineQALYs(profile);

  // 2. Elicit mechanism effects from Claude
  const claudeResponse = await elicitMechanismEffects(intervention, profile, apiKey);

  // 3. Convert to our types
  const interventionEffect = convertToInterventionEffect(claudeResponse);

  // 4. Run Monte Carlo simulation
  const simulation = simulateQALYImpact(profile, interventionEffect, 10000);

  // 5. Get affected conditions for display
  const mechanismConditions = getAffectedConditions(interventionEffect.mechanismEffects);

  // 6. Determine confidence level
  let confidenceLevel: "high" | "medium" | "low" = "medium";
  if (claudeResponse.overallEvidenceQuality === "high") {
    confidenceLevel = "high";
  } else if (claudeResponse.overallEvidenceQuality === "low" || claudeResponse.overallEvidenceQuality === "very-low") {
    confidenceLevel = "low";
  }

  // 7. Build result
  return {
    intervention,
    profile,

    baseline: {
      remainingLifeExpectancy: baseline.remainingLifeExpectancy,
      remainingQALYs: baseline.remainingQALYs,
    },

    mechanismEffects: interventionEffect.mechanismEffects,

    simulation,

    summary: {
      totalQALYs: {
        median: simulation.median,
        ci95Low: simulation.ci95.low,
        ci95High: simulation.ci95.high,
      },
      totalMinutes: {
        median: qalyYearsToMinutes(simulation.median),
        ci95Low: qalyYearsToMinutes(simulation.ci95.low),
        ci95High: qalyYearsToMinutes(simulation.ci95.high),
      },
      probPositive: simulation.probPositive,
      confidenceLevel,
    },

    evidence: {
      quality: claudeResponse.overallEvidenceQuality,
      keyStudies: claudeResponse.keyStudies.map((s) => ({
        citation: s.citation,
        studyType: s.studyType,
        relevance: s.relevance,
      })),
      caveats: claudeResponse.caveats,
    },

    affectedMechanisms: interventionEffect.mechanismEffects.map((m) => ({
      mechanism: m.mechanism,
      direction: m.direction,
      evidenceQuality: m.evidenceQuality,
      affectedConditions: mechanismConditions.get(m.mechanism) || [],
    })),
  };
}

/**
 * Format QALY years for display
 */
export function formatQALYs(years: number): string {
  const absYears = Math.abs(years);
  const sign = years >= 0 ? "+" : "-";

  if (absYears < 1 / 365) {
    const minutes = absYears * 525600;
    return `${sign}${Math.round(minutes)} minutes`;
  } else if (absYears < 1 / 52) {
    const hours = absYears * 8760;
    return `${sign}${hours.toFixed(1)} hours`;
  } else if (absYears < 1 / 12) {
    const days = absYears * 365;
    return `${sign}${days.toFixed(1)} days`;
  } else if (absYears < 1) {
    const months = absYears * 12;
    return `${sign}${months.toFixed(1)} months`;
  } else {
    return `${sign}${absYears.toFixed(2)} years`;
  }
}
