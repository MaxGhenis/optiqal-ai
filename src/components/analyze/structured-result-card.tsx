"use client";

import { useState } from "react";
import type { StructuredAnalysisResult } from "@/lib/analyze-structured";
import { formatQALYs } from "@/lib/analyze-structured";
import { Card, CardContent } from "@/components/ui/card";
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
      <span
        className={`text-[10px] ${
          quality === "strong"
            ? "text-emerald-400"
            : quality === "moderate"
              ? "text-primary"
              : "text-amber-400"
        }`}
      >
        ({quality})
      </span>
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

export function StructuredResultCard({ result }: StructuredResultCardProps) {
  const [showMechanisms, setShowMechanisms] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);

  const { summary, simulation, affectedMechanisms, evidence, baseline, source } = result;
  const isPositive = summary.totalQALYs.median >= 0;

  return (
    <Card className="mesh-gradient-card border-border/50 card-highlight overflow-hidden">
      <CardContent className="p-8 space-y-8">
        {/* Source indicator */}
        <SourceBadge source={source} />

        {/* Main Impact */}
        <div className="text-center space-y-3">
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
            Estimated QALY Impact
          </p>
          <div
            className={`text-5xl md:text-6xl font-serif font-semibold ${
              isPositive ? "gradient-text text-glow" : "text-destructive"
            }`}
          >
            {formatQALYs(summary.totalQALYs.median)}
          </div>
          <p className="text-sm text-muted-foreground">
            of quality-adjusted life
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
              label="P(> 1 year QALY gain)"
            />
          </div>
        </div>

        {/* Breakdown */}
        <div className="grid grid-cols-2 gap-4">
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
          </div>
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
          </div>
        </div>

        {/* Baseline context */}
        <div className="bg-muted/20 rounded-xl p-4 border border-border/30">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm font-medium">Your Baseline</span>
          </div>
          <p className="text-xs text-muted-foreground">
            {baseline.remainingLifeExpectancy.toFixed(1)} years remaining life expectancy,{" "}
            {baseline.remainingQALYs.toFixed(1)} QALYs. This intervention would change your QALYs by{" "}
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
            Results computed via {simulation.nSimulations.toLocaleString()}-iteration Monte Carlo
            simulation, propagating uncertainty through biological mechanism pathways.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
