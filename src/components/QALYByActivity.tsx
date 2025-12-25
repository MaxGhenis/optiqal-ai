"use client";

import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  ResponsiveContainer,
  ErrorBar,
} from "recharts";
import type { ProfileData } from "@/lib/profile-data";
import {
  buildActivityLevelData,
  calculateBMICategory,
  mapSmokingStatus,
} from "@/lib/profile-data";
import type { UserProfile } from "@/types";
import { formatQALYs } from "@/lib/analyze-structured";

interface QALYByActivityProps {
  profileData: ProfileData;
  userProfile: UserProfile;
}

const ACTIVITY_LABELS: Record<string, string> = {
  sedentary: "Sedentary",
  light: "Light",
  moderate: "Moderate",
  active: "Active",
};

export function QALYByActivity({
  profileData,
  userProfile,
}: QALYByActivityProps) {
  const { activityData, userActivityLevel } = useMemo(() => {
    const sex = userProfile.sex === "other" ? "male" : userProfile.sex;
    const smokingStatus = mapSmokingStatus(userProfile.smoker);
    const bmiCategory = calculateBMICategory(
      userProfile.weight,
      userProfile.height
    );

    const activityData = buildActivityLevelData(
      profileData,
      userProfile.age,
      sex as "male" | "female",
      bmiCategory,
      smokingStatus,
      userProfile.hasDiabetes,
      userProfile.hasHypertension
    );

    return {
      activityData,
      userActivityLevel: userProfile.activityLevel,
    };
  }, [profileData, userProfile]);

  // If no data for this specific profile, show message
  if (activityData.length === 0) {
    return (
      <div className="space-y-4">
        <div>
          <h3 className="text-sm font-medium text-foreground">
            QALY Impact by Activity Level
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            For your demographics
          </p>
        </div>
        <div className="bg-muted/10 rounded-xl p-8 border border-border/30 text-center">
          <p className="text-sm text-muted-foreground">
            No activity-specific data available for this profile combination.
          </p>
        </div>
      </div>
    );
  }

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-card/95 backdrop-blur-sm border border-border rounded-lg p-3 shadow-xl">
          <p className="text-xs font-medium text-foreground mb-1">
            {ACTIVITY_LABELS[data.activity_level]}
          </p>
          <p className="text-sm font-semibold text-primary">
            {formatQALYs(data.qaly)} QALYs
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            95% CI: {formatQALYs(data.qaly_ci_low)} to{" "}
            {formatQALYs(data.qaly_ci_high)}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-medium text-foreground">
          QALY Impact by Activity Level
        </h3>
        <p className="text-xs text-muted-foreground mt-0.5">
          For age {userProfile.age}, {userProfile.sex},{" "}
          {calculateBMICategory(userProfile.weight, userProfile.height)} BMI
        </p>
      </div>

      <div className="bg-muted/10 rounded-xl p-4 border border-border/30">
        <ResponsiveContainer width="100%" height={250}>
          <BarChart
            data={activityData}
            margin={{ top: 20, right: 20, bottom: 40, left: 40 }}
          >
            <XAxis
              dataKey="activity_level"
              tickFormatter={(value) => ACTIVITY_LABELS[value] || value}
              tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
              tickLine={{ stroke: "hsl(var(--border))" }}
              angle={-30}
              textAnchor="end"
              height={60}
            />
            <YAxis
              tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
              tickLine={{ stroke: "hsl(var(--border))" }}
              label={{
                value: "QALYs",
                angle: -90,
                position: "insideLeft",
                style: {
                  fill: "hsl(var(--muted-foreground))",
                  fontSize: 12,
                },
              }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="qaly" radius={[8, 8, 0, 0]}>
              <ErrorBar
                dataKey="qaly_ci_low"
                width={4}
                strokeWidth={2}
                stroke="hsl(var(--muted-foreground))"
                direction="y"
              />
              <ErrorBar
                dataKey="qaly_ci_high"
                width={4}
                strokeWidth={2}
                stroke="hsl(var(--muted-foreground))"
                direction="y"
              />
              {activityData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={
                    entry.activity_level === userActivityLevel
                      ? "hsl(var(--primary))"
                      : "hsl(var(--accent))"
                  }
                  fillOpacity={
                    entry.activity_level === userActivityLevel ? 1 : 0.5
                  }
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="flex items-center gap-2 text-xs text-muted-foreground bg-primary/5 rounded-lg px-3 py-2 border border-primary/20">
        <div className="w-3 h-3 rounded bg-primary" />
        <span>
          Your current activity level ({ACTIVITY_LABELS[userActivityLevel]})
        </span>
      </div>
    </div>
  );
}
