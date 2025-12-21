/**
 * OptiqAL DSL Parser
 *
 * Converts YAML intervention definitions to TypeScript InterventionEffect objects.
 * Supports both verbose object syntax and shorthand string syntax for distributions.
 */

import type {
  Distribution,
  InterventionEffect,
  MechanismEffect,
  MortalityEffect,
  QualityEffect,
  ConditionEffect,
  DimensionEffect,
  EQ5DDimension,
  HealthCondition,
} from "./types";
import type { Mechanism } from "./mechanisms";
import type { ConfoundingConfig } from "./confounding";

/**
 * Raw YAML intervention structure (matches schema)
 */
export interface YAMLIntervention {
  id: string;
  name: string;
  description?: string;
  category: "exercise" | "diet" | "sleep" | "stress" | "substance" | "medical" | "social" | "other";
  keywords?: string[];

  evidence?: {
    quality?: "high" | "moderate" | "low" | "very-low";
    primary_study_type?: "meta-analysis" | "rct" | "cohort" | "case-control" | "review" | "expert";
    sources?: Array<{
      citation: string;
      year?: number;
      sample_size?: number;
      contribution?: string;
    }>;
  };

  confounding?: {
    prior?: YAMLDistribution;
    calibration_sources?: string[];
    rationale?: string;
  };

  mechanisms?: Record<string, {
    effect: YAMLDistribution;
    direction: "increase" | "decrease";
    units?: string;
    evidence: "strong" | "moderate" | "weak";
    source?: string;
  }>;

  mortality?: {
    hazard_ratio: YAMLDistribution;
    affected_causes?: string[];
    onset_delay?: number;
    ramp_up?: number;
    decay_rate?: number;
  };

  quality?: {
    subjective_wellbeing?: YAMLDistribution;
    condition_effects?: Array<{
      condition: string;
      incidence_rr?: YAMLDistribution;
      severity_change?: YAMLDistribution;
    }>;
    dimension_effects?: Array<{
      dimension: string;
      change: YAMLDistribution;
    }>;
  };

  costs?: {
    hours_per_week?: YAMLDistribution;
    annual_cost_usd?: YAMLDistribution;
    activity_disutility?: YAMLDistribution;
  };

  caveats?: string[];
  profile_adjustments?: Array<{
    condition: string;
    adjustment: string;
  }>;
}

/**
 * Distribution can be object or shorthand string
 */
type YAMLDistribution =
  | string // Shorthand: "Normal(-4, 2)" or "LogNormal(-0.18, 0.08)"
  | { type: "point"; value: number }
  | { type: "normal"; mean: number; sd: number }
  | { type: "lognormal"; log_mean: number; log_sd: number }
  | { type: "beta"; alpha: number; beta: number }
  | { type: "uniform"; min: number; max: number };

/**
 * Parse shorthand distribution string to Distribution object
 *
 * Supported formats:
 * - Normal(mean, sd)
 * - LogNormal(logMean, logSd)
 * - Beta(alpha, beta)
 * - Uniform(min, max)
 * - Point(value)
 */
export function parseDistribution(input: YAMLDistribution): Distribution {
  if (typeof input === "string") {
    return parseShorthandDistribution(input);
  }

  // Already an object - convert snake_case to camelCase
  switch (input.type) {
    case "point":
      return { type: "point", value: input.value };

    case "normal":
      return { type: "normal", mean: input.mean, sd: input.sd };

    case "lognormal":
      return { type: "lognormal", logMean: input.log_mean, logSd: input.log_sd };

    case "beta":
      return { type: "beta", alpha: input.alpha, beta: input.beta };

    case "uniform":
      return { type: "uniform", min: input.min, max: input.max };

    default:
      throw new Error(`Unknown distribution type: ${JSON.stringify(input)}`);
  }
}

/**
 * Parse shorthand string like "Normal(-4, 2)"
 */
function parseShorthandDistribution(s: string): Distribution {
  const match = s.match(/^(Normal|LogNormal|Beta|Uniform|Point)\(([^)]+)\)$/i);
  if (!match) {
    throw new Error(`Invalid distribution shorthand: ${s}`);
  }

  const [, type, argsStr] = match;
  const args = argsStr.split(",").map((a) => parseFloat(a.trim()));

  switch (type.toLowerCase()) {
    case "normal":
      if (args.length !== 2) throw new Error(`Normal requires 2 args: ${s}`);
      return { type: "normal", mean: args[0], sd: args[1] };

    case "lognormal":
      if (args.length !== 2) throw new Error(`LogNormal requires 2 args: ${s}`);
      return { type: "lognormal", logMean: args[0], logSd: args[1] };

    case "beta":
      if (args.length !== 2) throw new Error(`Beta requires 2 args: ${s}`);
      return { type: "beta", alpha: args[0], beta: args[1] };

    case "uniform":
      if (args.length !== 2) throw new Error(`Uniform requires 2 args: ${s}`);
      return { type: "uniform", min: args[0], max: args[1] };

    case "point":
      if (args.length !== 1) throw new Error(`Point requires 1 arg: ${s}`);
      return { type: "point", value: args[0] };

    default:
      throw new Error(`Unknown distribution type: ${type}`);
  }
}

/**
 * Parse YAML intervention to InterventionEffect
 */
export function parseIntervention(yaml: YAMLIntervention): InterventionEffect {
  // Parse mechanism effects
  const mechanismEffects: MechanismEffect[] = [];
  if (yaml.mechanisms) {
    for (const [mechName, mechData] of Object.entries(yaml.mechanisms)) {
      mechanismEffects.push({
        mechanism: mechName as Mechanism,
        effectSize: parseDistribution(mechData.effect),
        direction: mechData.direction,
        units: mechData.units,
        evidenceQuality: mechData.evidence,
        source: mechData.source,
      });
    }
  }

  // Parse mortality effect
  let mortality: MortalityEffect | null = null;
  if (yaml.mortality) {
    mortality = {
      hazardRatio: parseDistribution(yaml.mortality.hazard_ratio),
      affectedCauses: yaml.mortality.affected_causes,
      onsetDelay: yaml.mortality.onset_delay ?? 0,
      rampUpPeriod: yaml.mortality.ramp_up ?? 0.5,
      decayRate: yaml.mortality.decay_rate ?? 0,
    };
  }

  // Parse quality effect
  let quality: QualityEffect | null = null;
  if (yaml.quality) {
    const conditionEffects: ConditionEffect[] = [];
    if (yaml.quality.condition_effects) {
      for (const ce of yaml.quality.condition_effects) {
        conditionEffects.push({
          condition: ce.condition as HealthCondition,
          incidenceRR: ce.incidence_rr ? parseDistribution(ce.incidence_rr) : undefined,
          severityChange: ce.severity_change ? parseDistribution(ce.severity_change) : undefined,
        });
      }
    }

    const dimensionEffects: DimensionEffect[] = [];
    if (yaml.quality.dimension_effects) {
      for (const de of yaml.quality.dimension_effects) {
        dimensionEffects.push({
          dimension: de.dimension.replace("_", "") as EQ5DDimension,
          change: parseDistribution(de.change),
        });
      }
    }

    quality = {
      conditionEffects,
      directDimensionEffects: dimensionEffects,
      subjectiveWellbeing: yaml.quality.subjective_wellbeing
        ? parseDistribution(yaml.quality.subjective_wellbeing)
        : undefined,
      onsetDelay: 0,
      decayRate: 0,
    };
  }

  // Parse evidence sources
  const keySources = yaml.evidence?.sources?.map((s) => ({
    citation: s.citation,
    studyType: (yaml.evidence?.primary_study_type as "meta-analysis" | "rct" | "cohort" | "case-control" | "other") || "other",
    sampleSize: s.sample_size,
    contribution: s.contribution || "",
  })) ?? [];

  return {
    description: yaml.description || yaml.name,
    category: yaml.category,
    mechanismEffects,
    mortality,
    quality,
    costs: yaml.costs ? {
      hoursPerWeek: yaml.costs.hours_per_week
        ? parseDistribution(yaml.costs.hours_per_week)
        : { type: "point", value: 0 },
      annualCost: yaml.costs.annual_cost_usd
        ? parseDistribution(yaml.costs.annual_cost_usd)
        : { type: "point", value: 0 },
      activityDisutility: yaml.costs.activity_disutility
        ? parseDistribution(yaml.costs.activity_disutility)
        : { type: "point", value: 0 },
    } : null,
    evidenceQuality: yaml.evidence?.quality || "moderate",
    keySources,
    caveats: yaml.caveats || [],
    profileAdjustments: yaml.profile_adjustments?.map((p) => p.adjustment) || [],
  };
}

/**
 * Parse confounding configuration from YAML
 */
export function parseConfounding(yaml: YAMLIntervention): ConfoundingConfig | null {
  if (!yaml.confounding?.prior) {
    return null;
  }

  const prior = parseDistribution(yaml.confounding.prior);
  if (prior.type !== "beta") {
    throw new Error("Confounding prior must be a Beta distribution");
  }

  return {
    causalFraction: {
      alpha: prior.alpha,
      beta: prior.beta,
    },
    rationale: yaml.confounding.rationale || "",
    calibrationSources: yaml.confounding.calibration_sources || [],
  };
}

/**
 * Format distribution for display (inverse of parsing)
 */
export function formatDistribution(dist: Distribution): string {
  switch (dist.type) {
    case "point":
      return `${dist.value.toFixed(2)}`;
    case "normal":
      return `Normal(${dist.mean.toFixed(2)}, ${dist.sd.toFixed(2)})`;
    case "lognormal":
      return `LogNormal(${dist.logMean.toFixed(2)}, ${dist.logSd.toFixed(2)})`;
    case "beta":
      return `Beta(${dist.alpha.toFixed(1)}, ${dist.beta.toFixed(1)})`;
    case "uniform":
      return `Uniform(${dist.min.toFixed(2)}, ${dist.max.toFixed(2)})`;
  }
}

/**
 * Get mean/expected value of a distribution
 */
export function getDistributionMean(dist: Distribution): number {
  switch (dist.type) {
    case "point":
      return dist.value;
    case "normal":
      return dist.mean;
    case "lognormal":
      return Math.exp(dist.logMean + (dist.logSd * dist.logSd) / 2);
    case "beta":
      return dist.alpha / (dist.alpha + dist.beta);
    case "uniform":
      return (dist.min + dist.max) / 2;
  }
}

/**
 * Get standard deviation of a distribution
 */
export function getDistributionSD(dist: Distribution): number {
  switch (dist.type) {
    case "point":
      return 0;
    case "normal":
      return dist.sd;
    case "lognormal": {
      const variance =
        (Math.exp(dist.logSd * dist.logSd) - 1) *
        Math.exp(2 * dist.logMean + dist.logSd * dist.logSd);
      return Math.sqrt(variance);
    }
    case "beta": {
      const a = dist.alpha;
      const b = dist.beta;
      return Math.sqrt((a * b) / ((a + b) ** 2 * (a + b + 1)));
    }
    case "uniform":
      return (dist.max - dist.min) / Math.sqrt(12);
  }
}
