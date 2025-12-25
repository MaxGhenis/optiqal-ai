"use client";

import { useMemo } from "react";
import type { UserProfile } from "@/types";
import {
  calculateBaselineQALYs,
  type BaselineProjection,
} from "@/lib/evidence/baseline";
import { Card, CardContent } from "@/components/ui/card";
import { Heart, Clock, TrendingUp, Info } from "lucide-react";

interface BaselineCardProps {
  profile: UserProfile;
}

function formatYears(years: number): string {
  if (years >= 1) {
    return `${years.toFixed(1)} years`;
  }
  const months = years * 12;
  if (months >= 1) {
    return `${months.toFixed(0)} months`;
  }
  const days = years * 365;
  return `${days.toFixed(0)} days`;
}

export function BaselineCard({ profile }: BaselineCardProps) {
  const projection = useMemo(
    () => calculateBaselineQALYs(profile),
    [profile]
  );

  const bmi = profile.weight / Math.pow(profile.height / 100, 2);

  return (
    <Card className="mesh-gradient-card border-border/50 overflow-hidden">
      <CardContent className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent/10">
            <TrendingUp className="h-5 w-5 text-accent" />
          </div>
          <div>
            <h3 className="text-sm font-medium">Your Baseline Projection</h3>
            <p className="text-xs text-muted-foreground">
              Based on CDC life tables and GBD risk factors
            </p>
          </div>
        </div>

        {/* Main Stats */}
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center p-4 bg-muted/20 rounded-xl border border-border/30">
            <Clock className="w-5 h-5 mx-auto mb-2 text-primary" />
            <p className="text-2xl font-semibold text-primary">
              {projection.remainingLifeExpectancy.toFixed(1)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              years remaining
            </p>
          </div>
          <div className="text-center p-4 bg-muted/20 rounded-xl border border-border/30">
            <Heart className="w-5 h-5 mx-auto mb-2 text-accent" />
            <p className="text-2xl font-semibold text-accent">
              {projection.remainingQALYs.toFixed(1)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              QALYs remaining
            </p>
          </div>
          <div className="text-center p-4 bg-muted/20 rounded-xl border border-border/30">
            <div className="w-5 h-5 mx-auto mb-2 text-muted-foreground font-mono text-sm">
              ~{Math.round(projection.expectedDeathAge)}
            </div>
            <p className="text-2xl font-semibold">
              {(projection.currentQualityWeight * 100).toFixed(0)}%
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              current quality
            </p>
          </div>
        </div>

        {/* Risk Factor Summary */}
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-wider text-muted-foreground">
            Your Risk Profile
          </p>
          <div className="flex flex-wrap gap-2">
            <RiskBadge
              label={`BMI ${bmi.toFixed(1)}`}
              status={bmi < 25 ? "good" : bmi < 30 ? "warning" : "bad"}
            />
            <RiskBadge
              label={`${profile.exerciseHoursPerWeek}h exercise/wk`}
              status={
                profile.exerciseHoursPerWeek >= 2.5
                  ? "good"
                  : profile.exerciseHoursPerWeek > 0
                    ? "warning"
                    : "bad"
              }
            />
            <RiskBadge
              label={`${profile.sleepHoursPerNight}h sleep`}
              status={
                profile.sleepHoursPerNight >= 6 &&
                profile.sleepHoursPerNight <= 9
                  ? "good"
                  : "warning"
              }
            />
            {profile.smoker && <RiskBadge label="Smoker" status="bad" />}
          </div>
        </div>

        {/* Decade Breakdown */}
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-wider text-muted-foreground">
            Expected QALYs per Decade
          </p>
          <p className="text-xs text-muted-foreground -mt-1">
            Max 10 QALYs per decade (10 years × 100% quality)
          </p>
          <div className="space-y-1.5">
            {projection.breakdown.slice(0, 6).map((decade) => (
              <div key={decade.ageDecade} className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground w-10 shrink-0">
                  {decade.ageDecade}s
                </span>
                <div className="flex-1 h-3 bg-muted/30 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-primary/70 to-accent/70 rounded-full"
                    style={{
                      // Bar shows QALYs out of max 10 per decade
                      width: `${Math.min((decade.qalysInDecade / 10) * 100, 100).toFixed(0)}%`,
                    }}
                  />
                </div>
                <span className="text-xs text-muted-foreground w-24 shrink-0 text-right">
                  {decade.qalysInDecade.toFixed(1)} / 10
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Source note */}
        <div className="flex items-start gap-2 text-xs text-muted-foreground bg-muted/20 rounded-lg p-3">
          <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <p>
            Based on CDC 2022 Life Tables, GBD 2019 disability weights, and
            risk factor meta-analyses. Individual outcomes vary significantly.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function RiskBadge({
  label,
  status,
}: {
  label: string;
  status: "good" | "warning" | "bad";
}) {
  const styles = {
    good: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    warning: "bg-amber-500/10 text-amber-400 border-amber-500/30",
    bad: "bg-red-500/10 text-red-400 border-red-500/30",
  };

  return (
    <span
      className={`inline-flex items-center px-2.5 py-1 text-xs rounded-full border ${styles[status]}`}
    >
      {label}
    </span>
  );
}
