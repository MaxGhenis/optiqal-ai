"use client";

import type { ComparisonAnalysisResult } from "@/lib/analyze-structured";
import { formatQALYs } from "@/lib/analyze-structured";
import { Card, CardContent } from "@/components/ui/card";
import {
  ArrowRight,
  Check,
  Equal,
  TrendingUp,
  Lightbulb,
} from "lucide-react";

interface ComparisonResultCardProps {
  result: ComparisonAnalysisResult;
}

function InterventionSummary({
  name,
  median,
  ci95Low,
  ci95High,
  isWinner,
}: {
  name: string;
  median: number;
  ci95Low: number;
  ci95High: number;
  isWinner: boolean;
}) {
  return (
    <div
      className={`flex-1 rounded-xl p-5 border ${
        isWinner
          ? "bg-primary/10 border-primary/30"
          : "bg-muted/20 border-border/30"
      }`}
    >
      <div className="flex items-start justify-between mb-3">
        <h3 className="font-medium text-sm truncate pr-2">{name}</h3>
        {isWinner && (
          <span className="flex items-center gap-1 text-xs text-primary bg-primary/20 px-2 py-0.5 rounded-full shrink-0">
            <Check className="w-3 h-3" />
            Better
          </span>
        )}
      </div>
      <div
        className={`text-2xl font-semibold ${
          median >= 0 ? "text-primary" : "text-destructive"
        }`}
      >
        {formatQALYs(median)}
      </div>
      <p className="text-xs text-muted-foreground mt-1">
        95% CI: {formatQALYs(ci95Low)} to {formatQALYs(ci95High)}
      </p>
    </div>
  );
}

export function ComparisonResultCard({ result }: ComparisonResultCardProps) {
  const { interventionA, interventionB, comparison, bothBeneficial } = result;

  const aMedian = interventionA.result.summary.totalQALYs.median;
  const bMedian = interventionB.result.summary.totalQALYs.median;

  return (
    <Card className="mesh-gradient-card border-border/50 card-highlight overflow-hidden">
      <CardContent className="p-8 space-y-8">
        {/* Header */}
        <div className="text-center space-y-2">
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
            Comparison Analysis
          </p>
          <h2 className="font-serif text-2xl font-medium">
            {interventionA.name} vs {interventionB.name}
          </h2>
        </div>

        {/* Side by side comparison */}
        <div className="flex gap-4 items-stretch">
          <InterventionSummary
            name={interventionA.name}
            median={aMedian}
            ci95Low={interventionA.result.summary.totalQALYs.ci95Low}
            ci95High={interventionA.result.summary.totalQALYs.ci95High}
            isWinner={comparison.winner === "A"}
          />

          <div className="flex items-center">
            {comparison.winner === "similar" ? (
              <div className="w-10 h-10 rounded-full bg-muted/30 flex items-center justify-center">
                <Equal className="w-5 h-5 text-muted-foreground" />
              </div>
            ) : (
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                <ArrowRight
                  className={`w-5 h-5 text-primary ${
                    comparison.winner === "A" ? "rotate-180" : ""
                  }`}
                />
              </div>
            )}
          </div>

          <InterventionSummary
            name={interventionB.name}
            median={bMedian}
            ci95Low={interventionB.result.summary.totalQALYs.ci95Low}
            ci95High={interventionB.result.summary.totalQALYs.ci95High}
            isWinner={comparison.winner === "B"}
          />
        </div>

        {/* Difference */}
        <div className="bg-muted/20 rounded-xl p-5 border border-border/30">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">
              Difference between options
            </span>
            <span className={`text-lg font-semibold ${
              comparison.practicallySignificant ? "text-primary" : "text-muted-foreground"
            }`}>
              {formatQALYs(comparison.differenceQALYs)}
            </span>
          </div>
          {!comparison.practicallySignificant && (
            <p className="text-xs text-muted-foreground mt-2">
              This difference is small (less than ~26 days) and may not be practically significant.
            </p>
          )}
        </div>

        {/* Key insight */}
        <div className={`rounded-xl p-5 border ${
          bothBeneficial
            ? "bg-emerald-500/10 border-emerald-500/20"
            : "bg-amber-500/10 border-amber-500/20"
        }`}>
          <div className="flex items-start gap-3">
            <div className={`p-2 rounded-lg ${
              bothBeneficial ? "bg-emerald-500/20" : "bg-amber-500/20"
            }`}>
              <Lightbulb className={`w-4 h-4 ${
                bothBeneficial ? "text-emerald-400" : "text-amber-400"
              }`} />
            </div>
            <div className="flex-1">
              <h4 className={`text-sm font-medium mb-1 ${
                bothBeneficial ? "text-emerald-400" : "text-amber-400"
              }`}>
                Key Insight
              </h4>
              <p className="text-sm text-foreground/80">
                {comparison.insight}
              </p>
            </div>
          </div>
        </div>

        {/* Both beneficial badge */}
        {bothBeneficial && (
          <div className="flex items-center justify-center gap-2 text-emerald-400">
            <TrendingUp className="w-4 h-4" />
            <span className="text-sm font-medium">
              Both options are beneficial
            </span>
          </div>
        )}

        {/* Note about confidence */}
        <p className="text-xs text-muted-foreground text-center">
          Estimates include confounding adjustment. Individual results may vary based on baseline health,
          adherence, and other factors.
        </p>
      </CardContent>
    </Card>
  );
}
