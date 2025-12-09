import Anthropic from "@anthropic-ai/sdk";
import type { UserProfile, AnalysisResponse } from "@/types";

const SYSTEM_PROMPT = `You are Optiqal, an expert system that estimates the Quality-Adjusted Life Year (QALY) impact of lifestyle choices. Your role is to:

1. Analyze the proposed lifestyle change
2. Search your knowledge for the best available causal evidence (meta-analyses, RCTs, cohort studies)
3. Estimate the QALY impact with appropriate uncertainty
4. Personalize the estimate based on the user's profile

IMPORTANT PRINCIPLES:
- Be honest about uncertainty. Use wide confidence intervals when evidence is weak.
- Distinguish between quality-of-life effects and longevity effects
- Express impacts in MINUTES of quality-adjusted life (not years) for intuitive understanding
- Consider both direct effects (e.g., exercise → cardiovascular health) and indirect effects (e.g., exercise → better sleep → better cognition)
- Account for the user's baseline: if they already do something, the marginal benefit is lower
- Flag when causal evidence is weak or when studies may not generalize to the user

RESPONSE FORMAT:
You must respond with a valid JSON object matching this schema:
{
  "analysis": {
    "id": "unique-id",
    "choice": "the choice analyzed",
    "category": "health|environment|lifestyle|diet|sleep|exercise|other",
    "impact": {
      "totalMinutes": number,
      "longevityMinutes": number,
      "qualityMinutes": number,
      "confidenceLevel": "low|medium|high",
      "confidenceInterval": { "low": number, "high": number }
    },
    "evidence": [
      {
        "title": "Study or source name",
        "year": number,
        "type": "meta-analysis|rct|cohort|case-control|cross-sectional|expert-opinion",
        "sampleSize": number (optional),
        "effectSize": "e.g., HR 0.85" (optional),
        "summary": "Brief summary of findings"
      }
    ],
    "mechanismExplanation": "How this choice affects health/longevity",
    "caveats": ["Important limitations or considerations"],
    "personalizedFactors": ["How the user's profile affects this estimate"]
  },
  "disclaimer": "Standard health disclaimer"
}

ESTIMATION GUIDANCE:
- 1 QALY = 1 year of perfect health = 525,600 minutes
- For recurring activities, calculate cumulative lifetime impact
- Example: Walking 30 min/day might add ~3 years of life (based on meta-analyses), so ~1.6 million minutes
- Quality effects: Convert to time-equivalent. E.g., 10% quality improvement for 20 years = 2 QALY-years
- Use remaining life expectancy based on age to bound estimates

Be specific, evidence-based, and appropriately uncertain.`;

export async function analyzeChoice(
  profile: UserProfile,
  choice: string,
  apiKey: string
): Promise<AnalysisResponse> {
  const client = new Anthropic({ apiKey, dangerouslyAllowBrowser: true });

  const bmi = profile.weight / (profile.height / 100) ** 2;

  const userMessage = `
USER PROFILE:
- Age: ${profile.age}
- Sex: ${profile.sex}
- Height: ${profile.height} cm
- Weight: ${profile.weight} kg (BMI: ${bmi.toFixed(1)})
- Exercise: ${profile.exerciseHoursPerWeek} hours/week
- Sleep: ${profile.sleepHoursPerNight} hours/night
- Diet: ${profile.diet}
- Smoker: ${profile.smoker ? "Yes" : "No"}
- Existing conditions: ${profile.existingConditions.length > 0 ? profile.existingConditions.join(", ") : "None reported"}

CHOICE TO ANALYZE:
"${choice}"

Please estimate the QALY impact of this choice for this specific person. Consider their baseline health behaviors and conditions when estimating marginal benefits. Respond with the JSON object only.`;

  const response = await client.messages.create({
    model: "claude-opus-4-5-20251101",
    max_tokens: 4096,
    messages: [{ role: "user", content: userMessage }],
    system: SYSTEM_PROMPT,
  });

  const textContent = response.content.find((block) => block.type === "text");
  if (!textContent || textContent.type !== "text") {
    throw new Error("No text response from API");
  }

  // Extract JSON from the response (handle markdown code blocks)
  let jsonText = textContent.text;
  const jsonMatch = jsonText.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (jsonMatch) {
    jsonText = jsonMatch[1];
  }

  try {
    const parsed = JSON.parse(jsonText.trim());
    return parsed as AnalysisResponse;
  } catch {
    console.error("Failed to parse response:", jsonText);
    throw new Error("Failed to parse AI response as JSON");
  }
}

export function formatTime(minutes: number): string {
  const absMinutes = Math.abs(minutes);
  const sign = minutes < 0 ? "-" : "+";

  if (absMinutes < 60) {
    return `${sign}${Math.round(absMinutes)} minutes`;
  } else if (absMinutes < 1440) {
    const hours = Math.floor(absMinutes / 60);
    const mins = Math.round(absMinutes % 60);
    return mins > 0
      ? `${sign}${hours} hour${hours > 1 ? "s" : ""} ${mins} min`
      : `${sign}${hours} hour${hours > 1 ? "s" : ""}`;
  } else if (absMinutes < 10080) {
    const days = Math.floor(absMinutes / 1440);
    const hours = Math.round((absMinutes % 1440) / 60);
    return hours > 0
      ? `${sign}${days} day${days > 1 ? "s" : ""} ${hours} hr`
      : `${sign}${days} day${days > 1 ? "s" : ""}`;
  } else if (absMinutes < 43800) {
    const weeks = Math.floor(absMinutes / 10080);
    const days = Math.round((absMinutes % 10080) / 1440);
    return days > 0
      ? `${sign}${weeks} week${weeks > 1 ? "s" : ""} ${days} day${days > 1 ? "s" : ""}`
      : `${sign}${weeks} week${weeks > 1 ? "s" : ""}`;
  } else if (absMinutes < 525600) {
    const months = absMinutes / 43800;
    return `${sign}${months.toFixed(1)} months`;
  } else {
    const years = absMinutes / 525600;
    const remainingMonths = (absMinutes % 525600) / 43800;
    if (remainingMonths >= 1) {
      return `${sign}${Math.floor(years)} year${Math.floor(years) > 1 ? "s" : ""}, ${Math.round(remainingMonths)} month${Math.round(remainingMonths) > 1 ? "s" : ""}`;
    }
    return `${sign}${years.toFixed(1)} years`;
  }
}
