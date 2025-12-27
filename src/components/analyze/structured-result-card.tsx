"use client";

import { useState } from "react";
import type { StructuredAnalysisResult } from "@/lib/analyze-structured";
import { formatQALYs } from "@/lib/analyze-structured";
import {
  deriveMortalityWithBreakdown,
  deriveQualityWithBreakdown,
  type MechanismMortalityBreakdown,
  type MechanismQualityBreakdown,
} from "@/lib/qaly";
import type { MechanismEffect } from "@/lib/qaly/types";
import { FEATURES, getLabels } from "@/lib/config";
import { Card, CardContent } from "@/components/ui/card";
import { ShareButtons } from "./share-buttons";
import { ProfileVisualizations } from "@/components/ProfileVisualizations";
import {
  Clock,
  Heart,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  BookOpen,
  Activity,
  ChevronDown,
  ChevronUp,
  Beaker,
  Target,
  BarChart3,
  Zap,
  Sparkles,
  Database,
  GitCompare,
} from "lucide-react";

interface StructuredResultCardProps {
  result: StructuredAnalysisResult;
}

function ConfidenceBadge({ level }: { level: "low" | "medium" | "high" }) {
  const styles = {
    low: "bg-amber-500/10 text-amber-400 border-amber-500/30",
    medium: "bg-primary/10 text-primary border-primary/30",
    high: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full border ${styles[level]}`}
    >
      <div
        className={`w-1.5 h-1.5 rounded-full animate-pulse ${
          level === "high"
            ? "bg-emerald-400"
            : level === "medium"
              ? "bg-primary"
              : "bg-amber-400"
        }`}
      />
      {level} confidence
    </span>
  );
}

function SourceBadge({ source }: { source: StructuredAnalysisResult["source"] }) {
  // Show cache hit indicator
  if (source.cacheHit) {
    return (
      <div className="flex items-center justify-center gap-1.5 text-xs text-blue-400 bg-blue-500/10 border border-blue-500/20 rounded-full px-3 py-1">
        <Database className="w-3 h-3" />
        <span>Cached result</span>
        <span className="text-blue-400/70">• No API cost</span>
      </div>
    );
  }

  if (source.type === "precomputed") {
    return (
      <div className="flex items-center justify-center gap-1.5 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-full px-3 py-1">
        <Zap className="w-3 h-3" />
        <span>Instant result</span>
        {source.precomputedName && (
          <span className="text-emerald-400/70">• {source.precomputedName}</span>
        )}
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center gap-1.5 text-xs text-primary bg-primary/10 border border-primary/20 rounded-full px-3 py-1">
      <Sparkles className="w-3 h-3" />
      <span>AI-synthesized analysis</span>
    </div>
  );
}

// Map evidence quality to estimated causal fraction
function getEvidenceCausalFraction(quality: string): number {
  switch (quality) {
    case "strong":
      return 0.8; // RCT-level evidence
    case "moderate":
      return 0.5; // Cohort studies
    case "weak":
    default:
      return 0.2; // Observational/cross-sectional
  }
}

function MechanismBadge({
  mechanism,
  direction,
  quality,
}: {
  mechanism: string;
  direction: "increase" | "decrease";
  quality: string;
}) {
  const isPositive =
    (direction === "decrease" &&
      ["blood_pressure", "systemic_inflammation", "stress_hormones", "adiposity", "oxidative_stress"].includes(
        mechanism
      )) ||
    (direction === "increase" &&
      !["blood_pressure", "systemic_inflammation", "stress_hormones", "adiposity", "oxidative_stress"].includes(
        mechanism
      ));

  const causalPct = Math.round(getEvidenceCausalFraction(quality) * 100);

  const qualityColor =
    quality === "strong"
      ? "border-emerald-500/30"
      : quality === "moderate"
        ? "border-primary/30"
        : "border-amber-500/30";

  return (
    <div
      className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg border bg-muted/20 ${qualityColor}`}
    >
      {isPositive ? (
        <TrendingUp className="w-3 h-3 text-emerald-400" />
      ) : (
        <TrendingDown className="w-3 h-3 text-red-400" />
      )}
      <span className="text-foreground/80">
        {mechanism.replace(/_/g, " ")}
      </span>
      <span className="text-[10px] text-muted-foreground">
        {quality} · {causalPct}% causal
      </span>
    </div>
  );
}

function ConfoundingSection({
  confounding,
}: {
  confounding: NonNullable<StructuredAnalysisResult["simulation"]["confounding"]>;
}) {
  const [expanded, setExpanded] = useState(false);

  const causalPct = Math.round(confounding.expectedCausalFraction * 100);
  const ciLow = Math.round(confounding.causalFractionCI.low * 100);
  const ciHigh = Math.round(confounding.causalFractionCI.high * 100);

  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between text-foreground bg-amber-500/10 hover:bg-amber-500/20 transition-colors rounded-xl px-5 py-4 border border-amber-500/20"
      >
        <span className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          <span className="text-sm font-medium">
            Confounding adjustment applied
          </span>
          <span className="text-xs px-2 py-0.5 rounded bg-amber-500/20 text-amber-400">
            ~{causalPct}% causal
          </span>
        </span>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-amber-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-amber-400" />
        )}
      </button>

      {expanded && (
        <div className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-5 space-y-4">
          {/* Causal fraction */}
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium text-foreground">
                Estimated causal fraction
              </span>
              <span className="text-lg font-semibold text-amber-400">
                {causalPct}%
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              Of the observed association, ~{causalPct}% is estimated to be causal
              (95% CI: {ciLow}–{ciHigh}%). The rest may be due to confounding.
            </p>
            <div className="h-2 bg-muted/30 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-amber-500/70 to-amber-400/70 rounded-full"
                style={{ width: `${causalPct}%` }}
              />
            </div>
          </div>

          {/* Comparison */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-muted/20 rounded-lg p-3">
              <div className="text-xs text-muted-foreground mb-1">
                Unadjusted estimate
              </div>
              <div className="text-sm font-medium line-through opacity-60">
                {formatQALYs(confounding.comparison.unadjustedMedian)}
              </div>
            </div>
            <div className="bg-amber-500/10 rounded-lg p-3 border border-amber-500/20">
              <div className="text-xs text-amber-400 mb-1">
                After confounding adjustment
              </div>
              <div className="text-sm font-medium text-amber-400">
                {formatQALYs(confounding.comparison.adjustedMedian)}
              </div>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Estimate reduced by {confounding.comparison.reductionPercent.toFixed(0)}%
            to account for potential confounding.
          </p>

          {/* E-value */}
          <div className="bg-muted/10 rounded-lg p-3 space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-xs font-medium text-muted-foreground">
                E-value (robustness to unmeasured confounding)
              </span>
              <span className="text-sm font-semibold">
                {confounding.eValue.point.toFixed(2)}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              {confounding.eValue.interpretation}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function ProbabilityBar({ probability, label }: { probability: number; label: string }) {
  const pct = Math.round(probability * 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="text-foreground font-medium">{pct}%</span>
      </div>
      <div className="h-2 bg-muted/30 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-primary/70 to-accent/70 rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/**
 * Convert logHR to QALY contribution (approximate)
 * Uses baseline life expectancy to scale log-HR to years
 */
function logHRToQALY(logHR: number, baselineLE: number): number {
  // HR < 1 (negative logHR) means mortality reduction = QALY gain
  // Approximate: years gained ≈ -logHR * baselineLE * discount_factor
  // With 3% discounting over ~40 years, effective multiplier ~20
  const discountedYears = baselineLE * 0.5; // rough approximation
  return -logHR * discountedYears;
}

/**
 * Display a single mechanism's contribution to longevity or quality
 */
function MechanismContributionRow({
  mechanism,
  contribution,
  sd,
  causalFraction,
  isLongevity,
  baselineLE,
}: {
  mechanism: string;
  contribution: number; // logHR for longevity, utilityDelta for quality
  sd: number;
  causalFraction: number;
  isLongevity: boolean;
  baselineLE: number;
}) {
  // Convert to QALYs
  let qalyContribution: number;
  let qalySd: number;

  if (isLongevity) {
    qalyContribution = logHRToQALY(contribution, baselineLE) * causalFraction;
    qalySd = logHRToQALY(sd, baselineLE) * causalFraction;
  } else {
    // Quality: utility delta * remaining years
    qalyContribution = contribution * baselineLE * 0.5 * causalFraction;
    qalySd = sd * baselineLE * 0.5 * causalFraction;
  }

  // Calculate 95% CI
  const ciLow = qalyContribution - 1.96 * Math.abs(qalySd);
  const ciHigh = qalyContribution + 1.96 * Math.abs(qalySd);

  const isPositive = qalyContribution >= 0;

  return (
    <div className="flex items-center justify-between py-1.5 text-xs border-b border-border/10 last:border-0">
      <div className="flex items-center gap-2">
        {isPositive ? (
          <TrendingUp className="w-3 h-3 text-emerald-400" />
        ) : (
          <TrendingDown className="w-3 h-3 text-red-400" />
        )}
        <span className="text-muted-foreground">
          {mechanism.replace(/_/g, " ")}
        </span>
        <span className="text-[10px] text-muted-foreground/60">
          {Math.round(causalFraction * 100)}% causal
        </span>
      </div>
      <div className="text-right">
        <span className={isPositive ? "text-emerald-400" : "text-red-400"}>
          {formatQALYs(qalyContribution)}
        </span>
        <span className="text-muted-foreground/50 ml-1">
          ({formatQALYs(ciLow)} to {formatQALYs(ciHigh)})
        </span>
      </div>
    </div>
  );
}

/**
 * Display mechanism breakdown for longevity or quality
 */
function MechanismBreakdownPanel({
  title,
  icon,
  iconColor,
  breakdown,
  isLongevity,
  baselineLE,
}: {
  title: string;
  icon: React.ReactNode;
  iconColor: string;
  breakdown: MechanismMortalityBreakdown[] | MechanismQualityBreakdown[];
  isLongevity: boolean;
  baselineLE: number;
}) {
  if (breakdown.length === 0) return null;

  return (
    <div className="mt-3 pt-3 border-t border-border/30">
      <div className={`flex items-center gap-1.5 text-[10px] uppercase tracking-wider ${iconColor} mb-2`}>
        {icon}
        <span>By Mechanism (95% CI)</span>
      </div>
      <div className="space-y-0">
        {breakdown.map((b) => {
          const contribution = isLongevity
            ? (b as MechanismMortalityBreakdown).logHR
            : (b as MechanismQualityBreakdown).utilityDelta;
          const sd = isLongevity
            ? (b as MechanismMortalityBreakdown).logSD
            : (b as MechanismQualityBreakdown).sd;

          return (
            <MechanismContributionRow
              key={b.mechanism}
              mechanism={b.mechanism}
              contribution={contribution}
              sd={sd}
              causalFraction={b.causalFraction}
              isLongevity={isLongevity}
              baselineLE={baselineLE}
            />
          );
        })}
      </div>
    </div>
  );
}

export function StructuredResultCard({ result }: StructuredResultCardProps) {
  const [showMechanisms, setShowMechanisms] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);

  const { summary, simulation, affectedMechanisms, evidence, baseline, source } = result;
  const isPositive = summary.totalQALYs.median >= 0;
  const labels = getLabels();

  // Convert affectedMechanisms to MechanismEffect[] for breakdown calculation
  const mechanismEffects: MechanismEffect[] = affectedMechanisms.map((m) => ({
    mechanism: m.mechanism as MechanismEffect["mechanism"],
    direction: m.direction,
    effectSize: m.effectSize || { type: "normal" as const, mean: 1, sd: 0.5 },
    evidenceQuality: m.evidenceQuality as MechanismEffect["evidenceQuality"],
    units: m.units,
  }));

  // Compute breakdowns
  const mortalityBreakdown = deriveMortalityWithBreakdown(mechanismEffects);
  const qualityBreakdown = deriveQualityWithBreakdown(mechanismEffects);

  return (
    <Card className="mesh-gradient-card border-border/50 card-highlight overflow-hidden">
      <CardContent className="p-8 space-y-8">
        {/* Source indicator & Share buttons */}
        <div className="flex items-center justify-between flex-wrap gap-4">
          <SourceBadge source={source} />
          <ShareButtons result={result} />
        </div>

        {/* Counterfactual */}
        <div className="flex items-center gap-2 text-xs text-muted-foreground bg-muted/20 rounded-lg px-4 py-2.5">
          <GitCompare className="w-3.5 h-3.5 shrink-0 text-primary" />
          <span>
            <span className="text-foreground/70">Compared to:</span>{" "}
            {result.counterfactual}
          </span>
        </div>

        {/* Main Impact */}
        <div className="text-center space-y-3">
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
            Estimated {labels.mainMetric}
          </p>
          <div
            className={`text-5xl md:text-6xl font-serif font-semibold ${
              isPositive ? "gradient-text text-glow" : "text-destructive"
            }`}
          >
            {formatQALYs(summary.totalQALYs.median)}
          </div>
          <p className="text-sm text-muted-foreground">
            {labels.mainMetricUnit}
          </p>
          <ConfidenceBadge level={summary.confidenceLevel} />
        </div>

        {/* 95% Credible Interval */}
        <div className="bg-muted/30 rounded-xl p-5">
          <p className="text-xs text-muted-foreground mb-3 uppercase tracking-wider">
            95% Credible Interval (Monte Carlo, n={simulation.nSimulations.toLocaleString()})
          </p>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              {formatQALYs(summary.totalQALYs.ci95Low)}
            </span>
            <div className="flex-1 mx-4 h-2 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-primary/50 via-primary to-primary/50 rounded-full"
                style={{
                  marginLeft: "10%",
                  width: "80%",
                }}
              />
            </div>
            <span className="text-muted-foreground">
              {formatQALYs(summary.totalQALYs.ci95High)}
            </span>
          </div>
        </div>

        {/* Probability metrics */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-muted/20 rounded-xl p-5 border border-border/30">
            <ProbabilityBar
              probability={simulation.probPositive}
              label="Probability of benefit"
            />
          </div>
          <div className="bg-muted/20 rounded-xl p-5 border border-border/30">
            <ProbabilityBar
              probability={simulation.probMoreThanOneYear}
              label={labels.probabilityLabel}
            />
          </div>
        </div>

        {/* Pathway Breakdown (from rigorous lifecycle model) */}
        {simulation.lifecycle?.used && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Activity className="w-4 h-4" />
              <span className="text-xs uppercase tracking-wider">Mortality Pathway Contributions</span>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-rose-500/10 rounded-xl p-4 border border-rose-500/20">
                <div className="text-xs text-rose-400 mb-1">Cardiovascular</div>
                <p className="text-lg font-semibold text-rose-400">
                  {formatQALYs(simulation.lifecycle.pathwayContributions.cvd.median)}
                </p>
              </div>
              <div className="bg-purple-500/10 rounded-xl p-4 border border-purple-500/20">
                <div className="text-xs text-purple-400 mb-1">Cancer</div>
                <p className="text-lg font-semibold text-purple-400">
                  {formatQALYs(simulation.lifecycle.pathwayContributions.cancer.median)}
                </p>
              </div>
              <div className="bg-blue-500/10 rounded-xl p-4 border border-blue-500/20">
                <div className="text-xs text-blue-400 mb-1">Other</div>
                <p className="text-lg font-semibold text-blue-400">
                  {formatQALYs(simulation.lifecycle.pathwayContributions.other.median)}
                </p>
              </div>
            </div>
            <div className="bg-muted/20 rounded-lg p-3 flex items-center justify-between text-xs">
              <span className="text-muted-foreground">
                Life years gained (undiscounted):
              </span>
              <span className="font-medium">
                {simulation.lifecycle.lifeYearsGained.median.toFixed(2)} years
              </span>
            </div>
          </div>
        )}

        {/* Breakdown */}
        <div className={FEATURES.SHOW_QUALITY_ADJUSTMENTS ? "grid grid-cols-2 gap-4" : ""}>
          <div className="bg-muted/20 rounded-xl p-5 border border-border/30 hover-lift">
            <div className="flex items-center gap-2 text-primary mb-3">
              <Clock className="w-4 h-4" />
              <span className="text-sm font-medium">Longevity</span>
            </div>
            <p
              className={`text-2xl font-semibold ${
                simulation.breakdown.mortalityQALYs.median >= 0
                  ? "text-primary"
                  : "text-destructive"
              }`}
            >
              {formatQALYs(simulation.breakdown.mortalityQALYs.median)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Impact on lifespan
            </p>
            {mortalityBreakdown && mortalityBreakdown.breakdown.length > 0 && (
              <MechanismBreakdownPanel
                title="By Mechanism"
                icon={<Activity className="w-3 h-3" />}
                iconColor="text-primary/70"
                breakdown={mortalityBreakdown.breakdown}
                isLongevity={true}
                baselineLE={baseline.remainingLifeExpectancy}
              />
            )}
          </div>
          {FEATURES.SHOW_QUALITY_ADJUSTMENTS && (
            <div className="bg-muted/20 rounded-xl p-5 border border-border/30 hover-lift">
              <div className="flex items-center gap-2 text-accent mb-3">
                <Heart className="w-4 h-4" />
                <span className="text-sm font-medium">Quality</span>
              </div>
              <p
                className={`text-2xl font-semibold ${
                  simulation.breakdown.qualityQALYs.median >= 0
                    ? "text-accent"
                    : "text-destructive"
                }`}
              >
                {formatQALYs(simulation.breakdown.qualityQALYs.median)}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Quality improvement
              </p>
              {qualityBreakdown && qualityBreakdown.breakdown.length > 0 && (
                <MechanismBreakdownPanel
                  title="By Mechanism"
                  icon={<Activity className="w-3 h-3" />}
                  iconColor="text-accent/70"
                  breakdown={qualityBreakdown.breakdown}
                  isLongevity={false}
                  baselineLE={baseline.remainingLifeExpectancy}
                />
              )}
            </div>
          )}
        </div>

        {/* Baseline context */}
        <div className="bg-muted/20 rounded-xl p-4 border border-border/30">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm font-medium">Your Baseline</span>
          </div>
          <p className="text-xs text-muted-foreground">
            {baseline.remainingLifeExpectancy.toFixed(1)} years remaining life expectancy
            {FEATURES.SHOW_QUALITY_ADJUSTMENTS && (
              <>, {baseline.remainingQALYs.toFixed(1)} QALYs</>
            )}
            . This intervention would change your {labels.shortUnit} by{" "}
            {((summary.totalQALYs.median / baseline.remainingQALYs) * 100).toFixed(2)}%.
          </p>
        </div>

        {/* Mechanisms */}
        <div className="space-y-3">
          <button
            type="button"
            onClick={() => setShowMechanisms(!showMechanisms)}
            className="w-full flex items-center justify-between text-foreground bg-muted/30 hover:bg-muted/50 transition-colors rounded-xl px-5 py-4"
          >
            <span className="flex items-center gap-2">
              <Beaker className="w-4 h-4 text-primary" />
              <span className="text-sm font-medium">
                Biological mechanisms ({affectedMechanisms.length})
              </span>
            </span>
            {showMechanisms ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </button>

          {showMechanisms && (
            <div className="space-y-4 pt-2">
              <div className="flex flex-wrap gap-2">
                {affectedMechanisms.map((m) => (
                  <MechanismBadge
                    key={m.mechanism}
                    mechanism={m.mechanism}
                    direction={m.direction}
                    quality={m.evidenceQuality}
                  />
                ))}
              </div>

              <div className="space-y-3">
                {affectedMechanisms.map((m) => (
                  <div
                    key={m.mechanism}
                    className="bg-muted/10 rounded-lg p-3 text-xs"
                  >
                    <div className="font-medium text-foreground mb-1">
                      {m.mechanism.replace(/_/g, " ")} →{" "}
                      <span className="text-muted-foreground">
                        affects: {m.affectedConditions.join(", ") || "general health"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Caveats */}
        {evidence.caveats.length > 0 && (
          <div className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-5 space-y-3">
            <div className="flex items-center gap-2 text-amber-400">
              <AlertTriangle className="w-4 h-4" />
              <span className="text-sm font-medium">Important caveats</span>
            </div>
            <ul className="space-y-2">
              {evidence.caveats.map((caveat, i) => (
                <li
                  key={i}
                  className="text-sm text-amber-200/70 flex items-start gap-2"
                >
                  <span className="text-amber-400 mt-1.5 text-xs">●</span>
                  {caveat}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Demographic visualizations */}
        <ProfileVisualizations result={result} />

        {/* Evidence */}
        <div className="space-y-3">
          <button
            type="button"
            onClick={() => setShowEvidence(!showEvidence)}
            className="w-full flex items-center justify-between text-foreground bg-muted/30 hover:bg-muted/50 transition-colors rounded-xl px-5 py-4"
          >
            <span className="flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-primary" />
              <span className="text-sm font-medium">
                Evidence sources ({evidence.keyStudies.length})
              </span>
              <span
                className={`text-xs px-2 py-0.5 rounded ${
                  evidence.quality === "high"
                    ? "bg-emerald-500/20 text-emerald-400"
                    : evidence.quality === "moderate"
                      ? "bg-primary/20 text-primary"
                      : "bg-amber-500/20 text-amber-400"
                }`}
              >
                {evidence.quality} quality
              </span>
            </span>
            {showEvidence ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </button>

          {showEvidence && (
            <div className="space-y-3 pt-2">
              {evidence.keyStudies.map((study, i) => (
                <div
                  key={i}
                  className="bg-muted/20 rounded-xl p-4 space-y-2 border border-border/20"
                >
                  <div className="flex items-start justify-between gap-3">
                    <h4 className="text-sm font-medium">{study.citation}</h4>
                    <span className="text-xs text-muted-foreground shrink-0 bg-muted/30 px-2 py-0.5 rounded">
                      {study.studyType}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {study.relevance}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Monte Carlo note */}
        <div className="flex items-center gap-2 text-xs text-muted-foreground bg-muted/20 rounded-lg p-3">
          <BarChart3 className="w-3.5 h-3.5 shrink-0" />
          <p>
            {simulation.lifecycle?.used ? (
              <>
                Rigorous lifecycle model with CDC life tables, pathway decomposition,
                {simulation.lifecycle.discountRate > 0 && ` ${(simulation.lifecycle.discountRate * 100).toFixed(0)}% annual discounting,`}
                {" "}and confounding adjustment.
                {" "}{simulation.nSimulations.toLocaleString()} Monte Carlo iterations.
              </>
            ) : (
              <>
                Results computed via {simulation.nSimulations.toLocaleString()}-iteration Monte Carlo
                simulation, propagating uncertainty through biological mechanism pathways.
              </>
            )}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
