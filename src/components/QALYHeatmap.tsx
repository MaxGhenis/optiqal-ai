"use client";

import { useMemo } from "react";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  Tooltip,
  Cell,
  ResponsiveContainer,
  ReferenceArea,
} from "recharts";
import type { ProfileData, ProfileResult } from "@/lib/profile-data";
import {
  buildAgeByBMIGrid,
  calculateBMICategory,
  mapSmokingStatus,
} from "@/lib/profile-data";
import type { UserProfile } from "@/types";
import { formatQALYs } from "@/lib/analyze-structured";

interface QALYHeatmapProps {
  profileData: ProfileData;
  userProfile: UserProfile;
}

const BMI_ORDER = ["underweight", "normal", "overweight", "obese"];

// Color scale from low to high QALY impact
function getColorForQALY(qaly: number, min: number, max: number): string {
  const normalized = (qaly - min) / (max - min);

  // Gradient from dark blue (low) -> cyan -> green -> yellow (high)
  if (normalized < 0.25) {
    const t = normalized / 0.25;
    return `rgb(${Math.round(30 + t * 30)}, ${Math.round(60 + t * 140)}, ${Math.round(114 + t * 86)})`;
  } else if (normalized < 0.5) {
    const t = (normalized - 0.25) / 0.25;
    return `rgb(${Math.round(60 + t * 20)}, ${Math.round(200 - t * 140)}, ${Math.round(200 - t * 100)})`;
  } else if (normalized < 0.75) {
    const t = (normalized - 0.5) / 0.25;
    return `rgb(${Math.round(80 + t * 100)}, ${Math.round(60 + t * 130)}, ${Math.round(100 - t * 100)})`;
  } else {
    const t = (normalized - 0.75) / 0.25;
    return `rgb(${Math.round(180 + t * 75)}, ${Math.round(190 + t * 65)}, ${Math.round(0)})`;
  }
}

export function QALYHeatmap({ profileData, userProfile }: QALYHeatmapProps) {
  const { gridData, minQALY, maxQALY, userBMI, userAge } = useMemo(() => {
    const sex = userProfile.sex === "other" ? "male" : userProfile.sex;
    const smokingStatus = mapSmokingStatus(userProfile.smoker);
    const userBMI = calculateBMICategory(
      userProfile.weight,
      userProfile.height
    );

    const gridData = buildAgeByBMIGrid(
      profileData,
      sex as "male" | "female",
      smokingStatus,
      userProfile.hasDiabetes,
      userProfile.hasHypertension
    );

    // Find min/max for color scale
    const qalyValues = gridData.map((d) => d.qaly);
    const minQALY = Math.min(...qalyValues);
    const maxQALY = Math.max(...qalyValues);

    return {
      gridData,
      minQALY,
      maxQALY,
      userBMI,
      userAge: userProfile.age,
    };
  }, [profileData, userProfile]);

  // Transform data for scatter plot (heatmap style)
  const scatterData = gridData.map((d) => ({
    x: d.age,
    y: BMI_ORDER.indexOf(d.bmi_category),
    z: d.qaly,
    bmi: d.bmi_category,
    age: d.age,
  }));

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-card/95 backdrop-blur-sm border border-border rounded-lg p-3 shadow-xl">
          <p className="text-xs font-medium text-foreground mb-1">
            Age {data.age}, {data.bmi}
          </p>
          <p className="text-sm font-semibold text-primary">
            {formatQALYs(data.z)} QALYs
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium text-foreground">
            QALY Impact by Age and BMI
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Holding sex, smoking, diabetes, and hypertension constant
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted-foreground">Lower</span>
          <div className="w-24 h-3 rounded-full bg-gradient-to-r from-[rgb(30,60,114)] via-[rgb(80,190,0)] to-[rgb(255,255,0)]" />
          <span className="text-muted-foreground">Higher</span>
        </div>
      </div>

      <div className="bg-muted/10 rounded-xl p-4 border border-border/30">
        <ResponsiveContainer width="100%" height={300}>
          <ScatterChart
            margin={{ top: 20, right: 20, bottom: 20, left: 60 }}
          >
            <XAxis
              type="number"
              dataKey="x"
              name="Age"
              domain={["dataMin", "dataMax"]}
              tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
              tickLine={{ stroke: "hsl(var(--border))" }}
              label={{
                value: "Age",
                position: "insideBottom",
                offset: -10,
                style: {
                  fill: "hsl(var(--muted-foreground))",
                  fontSize: 12,
                },
              }}
            />
            <YAxis
              type="number"
              dataKey="y"
              name="BMI Category"
              domain={[0, 3]}
              ticks={[0, 1, 2, 3]}
              tickFormatter={(value) => BMI_ORDER[value] || ""}
              tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
              tickLine={{ stroke: "hsl(var(--border))" }}
              width={80}
            />
            <ZAxis type="number" dataKey="z" range={[400, 400]} />
            <Tooltip content={<CustomTooltip />} />

            {/* Highlight user's position */}
            <ReferenceArea
              x1={userAge - 2.5}
              x2={userAge + 2.5}
              y1={BMI_ORDER.indexOf(userBMI) - 0.4}
              y2={BMI_ORDER.indexOf(userBMI) + 0.4}
              fill="hsl(var(--primary))"
              fillOpacity={0.15}
              stroke="hsl(var(--primary))"
              strokeWidth={2}
              strokeDasharray="4 4"
            />

            <Scatter data={scatterData} shape="square">
              {scatterData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={getColorForQALY(entry.z, minQALY, maxQALY)}
                  stroke={
                    entry.age === userAge &&
                    entry.bmi === userBMI
                      ? "hsl(var(--primary))"
                      : "transparent"
                  }
                  strokeWidth={
                    entry.age === userAge && entry.bmi === userBMI ? 3 : 0
                  }
                />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      <div className="flex items-center gap-2 text-xs text-muted-foreground bg-primary/5 rounded-lg px-3 py-2 border border-primary/20">
        <div className="w-2 h-2 rounded-sm border-2 border-primary border-dashed" />
        <span>
          Your position (age {userAge}, {userBMI})
        </span>
      </div>
    </div>
  );
}
