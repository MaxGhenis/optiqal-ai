"use client";

import { useState } from "react";
import type { ChoiceAnalysis } from "@/types";
import { formatTime } from "@/lib/analyze";
import { Card, CardContent } from "@/components/ui/card";
import {
  Clock,
  Heart,
  TrendingUp,
  AlertTriangle,
  BookOpen,
  Lightbulb,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

interface ResultCardProps {
  analysis: ChoiceAnalysis;
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

function EvidenceTypeBadge({ type }: { type: string }) {
  const styles: Record<string, string> = {
    "meta-analysis": "bg-purple-500/20 text-purple-400",
    rct: "bg-emerald-500/20 text-emerald-400",
    cohort: "bg-blue-500/20 text-blue-400",
    "case-control": "bg-cyan-500/20 text-cyan-400",
    "cross-sectional": "bg-amber-500/20 text-amber-400",
    "expert-opinion": "bg-muted text-muted-foreground",
  };

  return (
    <span
      className={`px-2 py-0.5 text-xs rounded ${styles[type] || styles["expert-opinion"]}`}
    >
      {type.replace("-", " ")}
    </span>
  );
}

export function ResultCard({ analysis }: ResultCardProps) {
  const [showEvidence, setShowEvidence] = useState(false);
  const {
    impact,
    evidence,
    mechanismExplanation,
    caveats,
    personalizedFactors,
  } = analysis;
  const isPositive = impact.totalMinutes >= 0;

  return (
    <Card className="mesh-gradient-card border-border/50 card-highlight overflow-hidden">
      <CardContent className="p-8 space-y-8">
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
            {formatTime(impact.totalMinutes)}
          </div>
          <p className="text-sm text-muted-foreground">
            of quality-adjusted life
          </p>
          <ConfidenceBadge level={impact.confidenceLevel} />
        </div>

        {/* Confidence Interval */}
        <div className="bg-muted/30 rounded-xl p-5">
          <p className="text-xs text-muted-foreground mb-3 uppercase tracking-wider">
            95% Confidence Interval
          </p>
          <div className="relative h-10">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-primary/50 via-primary to-primary/50 rounded-full"
                  style={{
                    marginLeft: `${Math.max(0, 50 + (impact.confidenceInterval.low / (Math.abs(impact.confidenceInterval.high) + Math.abs(impact.confidenceInterval.low) + 1)) * 50)}%`,
                    width: `${Math.min(100, ((impact.confidenceInterval.high - impact.confidenceInterval.low) / (Math.abs(impact.confidenceInterval.high) + Math.abs(impact.confidenceInterval.low) + 1)) * 50)}%`,
                  }}
                />
              </div>
            </div>
            <div className="absolute inset-0 flex items-center justify-between text-sm text-muted-foreground px-1">
              <span className="bg-background/80 px-2 py-0.5 rounded">
                {formatTime(impact.confidenceInterval.low)}
              </span>
              <span className="bg-background/80 px-2 py-0.5 rounded">
                {formatTime(impact.confidenceInterval.high)}
              </span>
            </div>
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
                impact.longevityMinutes >= 0 ? "text-primary" : "text-destructive"
              }`}
            >
              {formatTime(impact.longevityMinutes)}
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
                impact.qualityMinutes >= 0 ? "text-accent" : "text-destructive"
              }`}
            >
              {formatTime(impact.qualityMinutes)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Equivalent quality gain
            </p>
          </div>
        </div>

        {/* Mechanism */}
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Lightbulb className="w-4 h-4 text-amber-400" />
            <span className="text-sm font-medium">How it works</span>
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed">
            {mechanismExplanation}
          </p>
        </div>

        {/* Personalized Factors */}
        {personalizedFactors.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-primary" />
              <span className="text-sm font-medium">Personalized to you</span>
            </div>
            <ul className="space-y-2">
              {personalizedFactors.map((factor, i) => (
                <li
                  key={i}
                  className="text-sm text-muted-foreground flex items-start gap-2"
                >
                  <span className="text-primary mt-1.5 text-xs">●</span>
                  {factor}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Caveats */}
        {caveats.length > 0 && (
          <div className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-5 space-y-3">
            <div className="flex items-center gap-2 text-amber-400">
              <AlertTriangle className="w-4 h-4" />
              <span className="text-sm font-medium">Important caveats</span>
            </div>
            <ul className="space-y-2">
              {caveats.map((caveat, i) => (
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
                Evidence sources ({evidence.length})
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
              {evidence.map((source, i) => (
                <div
                  key={i}
                  className="bg-muted/20 rounded-xl p-5 space-y-3 border border-border/20"
                >
                  <div className="flex items-start justify-between gap-3">
                    <h4 className="text-sm font-medium">{source.title}</h4>
                    <span className="text-xs text-muted-foreground shrink-0">
                      {source.year}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <EvidenceTypeBadge type={source.type} />
                    {source.sampleSize && (
                      <span className="text-xs text-muted-foreground">
                        n={source.sampleSize.toLocaleString()}
                      </span>
                    )}
                    {source.effectSize && (
                      <span className="text-xs text-primary">
                        {source.effectSize}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {source.summary}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
