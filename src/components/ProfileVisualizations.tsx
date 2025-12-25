"use client";

import { useEffect, useState } from "react";
import { QALYHeatmap } from "./QALYHeatmap";
import { QALYByActivity } from "./QALYByActivity";
import type { StructuredAnalysisResult } from "@/lib/analyze-structured";
import type { ProfileData } from "@/lib/profile-data";
import { loadProfileData } from "@/lib/profile-data";
import { Loader2, TrendingUp } from "lucide-react";

interface ProfileVisualizationsProps {
  result: StructuredAnalysisResult;
}

export function ProfileVisualizations({
  result,
}: ProfileVisualizationsProps) {
  const [profileData, setProfileData] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      // Only load if we have a precomputed intervention ID
      if (result.source.type !== "precomputed" || !result.source.precomputedId) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const data = await loadProfileData(result.source.precomputedId);

        if (!data) {
          setError("Profile data not available for this intervention");
        } else {
          setProfileData(data);
        }
      } catch (err) {
        console.error("Error loading profile data:", err);
        setError("Failed to load profile data");
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [result.source.type, result.source.precomputedId]);

  // Don't show anything if not a precomputed intervention
  if (result.source.type !== "precomputed") {
    return null;
  }

  // Loading state
  if (loading) {
    return (
      <div className="bg-muted/20 rounded-xl p-8 border border-border/30 text-center">
        <Loader2 className="h-6 w-6 animate-spin text-primary mx-auto mb-2" />
        <p className="text-sm text-muted-foreground">
          Loading demographic visualizations...
        </p>
      </div>
    );
  }

  // Error state
  if (error || !profileData) {
    return (
      <div className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-4">
        <p className="text-xs text-amber-400">
          {error || "Profile visualizations not available for this intervention"}
        </p>
      </div>
    );
  }

  // Success - show visualizations
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-2">
        <TrendingUp className="w-5 h-5 text-primary" />
        <h3 className="text-lg font-medium text-foreground">
          Impact by Demographics
        </h3>
      </div>
      <p className="text-sm text-muted-foreground -mt-4">
        Explore how this intervention's impact varies across different demographic profiles
      </p>

      {/* Heatmap */}
      <QALYHeatmap profileData={profileData} userProfile={result.profile} />

      {/* Footer note */}
      <div className="text-xs text-muted-foreground bg-muted/10 rounded-lg p-3 border border-border/20">
        <p>
          These visualizations are based on precomputed simulations across
          {" "}{Object.keys(profileData.results).length.toLocaleString()} demographic profiles.
          Each point represents the median QALY impact from 1,500 Monte Carlo simulations.
        </p>
      </div>
    </div>
  );
}
