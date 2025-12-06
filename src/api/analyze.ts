import Anthropic from '@anthropic-ai/sdk';
import type { UserProfile, AnalysisResponse } from '../types';

const SYSTEM_PROMPT = `You are OptiqAL, an expert system that estimates the Quality-Adjusted Life Year (QALY) impact of lifestyle choices. Your role is to:

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

  const userMessage = `
USER PROFILE:
- Age: ${profile.age}
- Sex: ${profile.sex}
- Height: ${profile.height} cm
- Weight: ${profile.weight} kg (BMI: ${(profile.weight / ((profile.height / 100) ** 2)).toFixed(1)})
- Exercise: ${profile.exerciseHoursPerWeek} hours/week
- Sleep: ${profile.sleepHoursPerNight} hours/night
- Diet: ${profile.diet}
- Smoker: ${profile.smoker ? 'Yes' : 'No'}
- Existing conditions: ${profile.existingConditions.length > 0 ? profile.existingConditions.join(', ') : 'None reported'}

CHOICE TO ANALYZE:
"${choice}"

Please estimate the QALY impact of this choice for this specific person. Consider their baseline health behaviors and conditions when estimating marginal benefits. Respond with the JSON object only.`;

  const response = await client.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 4096,
    messages: [{ role: 'user', content: userMessage }],
    system: SYSTEM_PROMPT,
  });

  const textContent = response.content.find(block => block.type === 'text');
  if (!textContent || textContent.type !== 'text') {
    throw new Error('No text response from API');
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
  } catch (e) {
    console.error('Failed to parse response:', jsonText);
    throw new Error('Failed to parse AI response as JSON');
  }
}
