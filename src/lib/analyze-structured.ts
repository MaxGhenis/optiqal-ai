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
  simulateQALYImpactRigorous,
  type RigorousSimulationResult,
  qalyYearsToMinutes,
  matchIntervention,
  getPrecomputedEffect,
  deriveMortalityFromMechanisms,
  deriveQualityFromMechanisms,
} from "@/lib/qaly";
import { calculateBaselineQALYs } from "@/lib/evidence/baseline";
import { getCachedResult, setCachedResult } from "./cache";

/**
 * Response from Claude's mechanism elicitation
 */
interface ClaudeMechanismResponse {
  intervention: string;
  counterfactual: string;
  mechanismEffects: {
    mechanism: string;
    affected?: boolean; // optional - if present, mechanism is affected
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
  }[];
  directMortalityEffect?: {
    hasDirectEffect: boolean;
    hazardRatio?: {
      type: "lognormal";
      logMean: number;
      logSd: number;
    };
  };
  overallEvidenceQuality: "high" | "moderate" | "low" | "very-low";
  caveats: string[];
  keyStudies: {
    citation: string;
    studyType: string;
  }[];
}

/**
 * Full analysis result with mechanism details
 */
export interface StructuredAnalysisResult {
  // Original input
  intervention: string;
  counterfactual: string; // What this is being compared against
  profile: UserProfile;

  // Data source
  source: {
    type: "precomputed" | "claude" | "cache";
    precomputedId?: string;
    precomputedName?: string;
    confidence?: number; // 0-1 for precomputed match confidence
    cacheHit?: boolean; // True if result came from cache
  };

  // Baseline projection
  baseline: {
    remainingLifeExpectancy: number;
    remainingQALYs: number;
  };

  // Mechanism-level effects from Claude
  mechanismEffects: MechanismEffect[];

  // Monte Carlo simulation results (with lifecycle model)
  simulation: RigorousSimulationResult;

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
    effectSize?: { type: "normal"; mean: number; sd: number };
    units?: string;
  }[];
}

const MECHANISM_ELICITATION_SYSTEM = `You are a biomedical evidence synthesizer. Return COMPACT JSON only.

COUNTERFACTUAL: State what this is compared against (be specific, e.g., "no coffee" not "baseline").

MECHANISMS (include TOP 5 most affected):
blood_pressure, lipid_profile, insulin_sensitivity, systemic_inflammation, adiposity, sleep_quality, muscle_mass, bone_density, stress_hormones, neuroplasticity, cardiac_output, lung_function

EFFECT SIZES: blood_pressure in mmHg, others as % or Cohen's d. Conservative estimates, wider SD for weak evidence.

JSON FORMAT:
{"intervention":"brief","counterfactual":"vs what","mechanismEffects":[{"mechanism":"blood_pressure","direction":"decrease","effectSize":{"type":"normal","mean":5,"sd":2},"evidenceQuality":"strong"}],"directMortalityEffect":{"hasDirectEffect":false},"overallEvidenceQuality":"moderate","caveats":["caveat1","caveat2"],"keyStudies":[{"citation":"Author Year","studyType":"meta-analysis"}]}

RULES:
- Max 5 mechanisms, 3 caveats, 2 studies
- effectSize.mean is MAGNITUDE (positive), direction indicates sign
- Only include mechanisms actually affected
- Be Bayesian: conservative estimates`;

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
    max_tokens: 1500,
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
    .filter((m) => m.affected !== false) // include if affected is true or undefined
    .map((m) => ({
      mechanism: m.mechanism as Mechanism,
      effectSize: parseDistribution(m.effectSize),
      direction: m.direction,
      units: m.units,
      evidenceQuality: m.evidenceQuality,
    }));

  // Build mortality effect:
  // 1. Use Claude's direct mortality estimate if provided
  // 2. Otherwise derive from mechanism effects
  let mortality = null;
  if (response.directMortalityEffect?.hasDirectEffect && response.directMortalityEffect.hazardRatio) {
    // Claude provided direct mortality evidence (e.g., from RCTs)
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
  } else if (mechanismEffects.length > 0) {
    // Derive mortality from mechanism effects
    mortality = deriveMortalityFromMechanisms(mechanismEffects);
  }

  // Derive quality of life effects from mechanism effects
  const quality = mechanismEffects.length > 0
    ? deriveQualityFromMechanisms(mechanismEffects)
    : null;

  return {
    description: response.intervention,
    category: "other",
    mechanismEffects,
    mortality,
    quality,
    costs: null,
    evidenceQuality: response.overallEvidenceQuality,
    keySources: response.keyStudies.map((s) => ({
      citation: s.citation,
      studyType: s.studyType as "meta-analysis" | "rct" | "cohort" | "case-control" | "other",
      contribution: "Key evidence source",
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
 * Analyze using precomputed intervention data (instant, no API call)
 */
function analyzePrecomputed(
  profile: UserProfile,
  intervention: string,
  matchId: string,
  matchConfidence: number
): StructuredAnalysisResult {
  const precomputedEffect = getPrecomputedEffect(matchId);
  if (!precomputedEffect) {
    throw new Error(`Precomputed effect not found for ${matchId}`);
  }

  // Get the full intervention data for metadata
  const match = matchIntervention(intervention);
  const precomputedIntervention = match?.intervention;

  // 1. Get baseline projection
  const baseline = calculateBaselineQALYs(profile);

  // 2. Run Monte Carlo simulation with precomputed effect
  // Use primary study type from sources for confounding adjustment
  const primaryStudyType = precomputedIntervention?.sources?.[0]?.studyType as
    | "meta-analysis" | "rct" | "cohort" | "case-control" | "review" | "other"
    | undefined;

  const simulation = simulateQALYImpactRigorous(profile, precomputedEffect, {
    nSimulations: 10000,
    applyConfounding: true,
    evidenceType: primaryStudyType,
    useLifecycleModel: true,
    discountRate: 0.03,
  });

  // 3. Get affected conditions for display
  const mechanismConditions = getAffectedConditions(precomputedEffect.mechanismEffects);

  // 4. Determine confidence level from evidence quality
  let confidenceLevel: "high" | "medium" | "low" = "medium";
  if (precomputedEffect.evidenceQuality === "high") {
    confidenceLevel = "high";
  } else if (precomputedEffect.evidenceQuality === "low" || precomputedEffect.evidenceQuality === "very-low") {
    confidenceLevel = "low";
  }

  // Derive counterfactual: use explicit if available, otherwise generate from category
  const counterfactual = precomputedIntervention?.counterfactual ||
    (precomputedIntervention?.category === "exercise"
      ? "not doing this exercise / sedentary behavior"
      : precomputedIntervention?.category === "diet"
      ? "typical diet without this food/change"
      : precomputedIntervention?.category === "substance"
      ? "not using this substance"
      : "not making this change");

  return {
    intervention,
    counterfactual,
    profile,

    source: {
      type: "precomputed",
      precomputedId: matchId,
      precomputedName: precomputedIntervention?.name,
      confidence: matchConfidence,
    },

    baseline: {
      remainingLifeExpectancy: baseline.remainingLifeExpectancy,
      remainingQALYs: baseline.remainingQALYs,
    },

    mechanismEffects: precomputedEffect.mechanismEffects,

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
      quality: precomputedEffect.evidenceQuality as "high" | "moderate" | "low" | "very-low",
      keyStudies: precomputedEffect.keySources?.map((s) => ({
        citation: s.citation,
        studyType: s.studyType,
        relevance: s.contribution || "Key evidence source",
      })) || [],
      caveats: precomputedEffect.caveats || [],
    },

    affectedMechanisms: precomputedEffect.mechanismEffects.map((m) => ({
      mechanism: m.mechanism,
      direction: m.direction,
      evidenceQuality: m.evidenceQuality,
      affectedConditions: mechanismConditions.get(m.mechanism) || [],
      effectSize: m.effectSize.type === "normal" ? { type: "normal" as const, mean: m.effectSize.mean, sd: m.effectSize.sd } : undefined,
      units: m.units,
    })),
  };
}

/**
 * Analyze using Claude API (more flexible, but costs money and takes time)
 */
async function analyzeWithClaude(
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

  // 4. Run Monte Carlo simulation with confounding adjustment
  // For Claude-generated estimates, use the evidence quality to infer study type
  const evidenceType = claudeResponse.overallEvidenceQuality === "high"
    ? "meta-analysis"
    : claudeResponse.overallEvidenceQuality === "moderate"
    ? "cohort"
    : "other";

  const simulation = simulateQALYImpactRigorous(profile, interventionEffect, {
    nSimulations: 10000,
    applyConfounding: true,
    evidenceType: evidenceType as "meta-analysis" | "cohort" | "other",
    useLifecycleModel: true,
    discountRate: 0.03,
  });

  // 5. Get affected conditions for display
  const mechanismConditions = getAffectedConditions(interventionEffect.mechanismEffects);

  // 6. Determine confidence level
  let confidenceLevel: "high" | "medium" | "low" = "medium";
  if (claudeResponse.overallEvidenceQuality === "high") {
    confidenceLevel = "high";
  } else if (claudeResponse.overallEvidenceQuality === "low" || claudeResponse.overallEvidenceQuality === "very-low") {
    confidenceLevel = "low";
  }

  return {
    intervention,
    counterfactual: claudeResponse.counterfactual || "current behavior / not doing this intervention",
    profile,

    source: {
      type: "claude",
    },

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
        relevance: "Key evidence source",
      })),
      caveats: claudeResponse.caveats,
    },

    affectedMechanisms: interventionEffect.mechanismEffects.map((m) => ({
      mechanism: m.mechanism,
      direction: m.direction,
      evidenceQuality: m.evidenceQuality,
      affectedConditions: mechanismConditions.get(m.mechanism) || [],
      effectSize: m.effectSize.type === "normal" ? { type: "normal" as const, mean: m.effectSize.mean, sd: m.effectSize.sd } : undefined,
      units: m.units,
    })),
  };
}

/** Confidence threshold for using precomputed data */
const PRECOMPUTED_CONFIDENCE_THRESHOLD = 0.5;

/**
 * Main entry point: analyze an intervention with full mechanism decomposition
 *
 * Flow:
 * 1. Check cache for existing result
 * 2. Try precomputed interventions for instant results
 * 3. Fall back to Claude for novel queries
 * 4. Cache the result
 */
export async function analyzeStructured(
  profile: UserProfile,
  intervention: string,
  apiKey: string,
  options?: { forceSource?: "precomputed" | "claude"; skipCache?: boolean }
): Promise<StructuredAnalysisResult> {
  // Check cache first (unless skipCache is true)
  if (!options?.skipCache) {
    const cached = getCachedResult(intervention, profile);
    if (cached) {
      console.log(`[Optiqal] Cache hit for "${intervention}"`);
      // Mark as cache hit
      return {
        ...cached,
        source: {
          ...cached.source,
          cacheHit: true,
        },
      };
    }
  }

  // Option to force a specific source (useful for testing)
  if (options?.forceSource === "claude") {
    const result = await analyzeWithClaude(profile, intervention, apiKey);
    setCachedResult(intervention, profile, result);
    return result;
  }

  // Try to match against precomputed interventions
  const match = matchIntervention(intervention);

  // Use precomputed if:
  // 1. Match found with sufficient confidence
  // 2. Not forcing Claude
  if (match && match.confidence >= PRECOMPUTED_CONFIDENCE_THRESHOLD) {
    console.log(`[Optiqal] Using precomputed data for "${match.intervention.name}" (confidence: ${(match.confidence * 100).toFixed(0)}%)`);
    const result = analyzePrecomputed(profile, intervention, match.id, match.confidence);
    setCachedResult(intervention, profile, result);
    return result;
  }

  // Fall back to Claude for novel queries
  if (match) {
    console.log(`[Optiqal] Low confidence match (${(match.confidence * 100).toFixed(0)}%), using Claude instead`);
  } else {
    console.log(`[Optiqal] No precomputed match found, using Claude`);
  }

  const result = await analyzeWithClaude(profile, intervention, apiKey);
  setCachedResult(intervention, profile, result);
  return result;
}

/**
 * Result for comparing two interventions (A vs B)
 */
export interface ComparisonAnalysisResult {
  // The original query
  query: string;

  // Both interventions analyzed
  interventionA: {
    name: string;
    result: StructuredAnalysisResult;
  };
  interventionB: {
    name: string;
    result: StructuredAnalysisResult;
  };

  // Comparison summary
  comparison: {
    // Which is better (or "similar" if difference < threshold)
    winner: "A" | "B" | "similar";
    // Absolute difference in median QALYs
    differenceQALYs: number;
    // Difference in minutes
    differenceMinutes: number;
    // Is the difference practically significant? (> 0.1 QALYs)
    practicallySignificant: boolean;
    // Key insight for user
    insight: string;
  };

  // Whether both interventions are beneficial
  bothBeneficial: boolean;
}

/**
 * Patterns that indicate a comparison query
 */
const COMPARISON_PATTERNS = [
  /^(.+?)\s+(?:vs\.?|versus|or|compared to|against)\s+(.+?)$/i,
  /^(?:should i (?:do|eat|take|use|try))\s+(.+?)\s+(?:or|vs\.?)\s+(.+?)\??$/i,
  /^(.+?)\s+(?:better than|worse than)\s+(.+?)$/i,
  /^(?:which is better[,:]?)\s*(.+?)\s+(?:or|vs\.?)\s+(.+?)\??$/i,
  /^(?:compare)\s+(.+?)\s+(?:to|with|and|vs\.?)\s+(.+?)$/i,
];

/**
 * Check if a query is asking for a comparison
 */
export function isComparisonQuery(query: string): boolean {
  return COMPARISON_PATTERNS.some((pattern) => pattern.test(query.trim()));
}

/**
 * Parse comparison query into two interventions
 */
export function parseComparisonQuery(query: string): { a: string; b: string } | null {
  const trimmed = query.trim();

  for (const pattern of COMPARISON_PATTERNS) {
    const match = trimmed.match(pattern);
    if (match) {
      return {
        a: match[1].trim(),
        b: match[2].trim(),
      };
    }
  }

  return null;
}

/**
 * Generate insight message for comparison
 */
function generateComparisonInsight(
  aName: string,
  bName: string,
  aMedian: number,
  bMedian: number,
  bothBeneficial: boolean,
  practicallySignificant: boolean
): string {
  const diffMinutes = Math.abs(qalyYearsToMinutes(aMedian) - qalyYearsToMinutes(bMedian));
  const diffDays = diffMinutes / (24 * 60);

  if (!bothBeneficial) {
    if (aMedian > 0 && bMedian <= 0) {
      return `${aName} is beneficial while ${bName} appears neutral or harmful.`;
    } else if (bMedian > 0 && aMedian <= 0) {
      return `${bName} is beneficial while ${aName} appears neutral or harmful.`;
    } else {
      return `Neither intervention shows clear benefit in this analysis.`;
    }
  }

  if (!practicallySignificant) {
    return `Both are beneficial with similar effects (~${diffDays.toFixed(0)} days difference). ` +
      `Choose based on preference and what you'll actually stick with - consistency matters more than the marginal difference.`;
  }

  const better = aMedian > bMedian ? aName : bName;
  const worse = aMedian > bMedian ? bName : aName;
  return `${better} shows a larger benefit (~${diffDays.toFixed(0)} days more), ` +
    `but both are worthwhile. If you prefer ${worse}, it's still a good choice.`;
}

/**
 * Compare two interventions (A vs B)
 *
 * Useful when user asks "X vs Y" or "should I do X or Y"
 */
export async function analyzeComparison(
  profile: UserProfile,
  query: string,
  apiKey: string
): Promise<ComparisonAnalysisResult> {
  const parsed = parseComparisonQuery(query);
  if (!parsed) {
    throw new Error(`Could not parse comparison query: "${query}"`);
  }

  // Analyze both interventions in parallel
  const [resultA, resultB] = await Promise.all([
    analyzeStructured(profile, parsed.a, apiKey),
    analyzeStructured(profile, parsed.b, apiKey),
  ]);

  const medianA = resultA.summary.totalQALYs.median;
  const medianB = resultB.summary.totalQALYs.median;
  const differenceQALYs = medianA - medianB;
  const differenceMinutes = qalyYearsToMinutes(Math.abs(differenceQALYs));

  // Practical significance threshold: 0.05 QALYs (~26 days)
  const PRACTICAL_THRESHOLD = 0.05;
  const practicallySignificant = Math.abs(differenceQALYs) > PRACTICAL_THRESHOLD;

  const bothBeneficial = medianA > 0 && medianB > 0;

  let winner: "A" | "B" | "similar";
  if (!practicallySignificant) {
    winner = "similar";
  } else {
    winner = differenceQALYs > 0 ? "A" : "B";
  }

  const insight = generateComparisonInsight(
    parsed.a,
    parsed.b,
    medianA,
    medianB,
    bothBeneficial,
    practicallySignificant
  );

  return {
    query,
    interventionA: { name: parsed.a, result: resultA },
    interventionB: { name: parsed.b, result: resultB },
    comparison: {
      winner,
      differenceQALYs: Math.abs(differenceQALYs),
      differenceMinutes,
      practicallySignificant,
      insight,
    },
    bothBeneficial,
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
