You are reviewing outputs from a public-facing health recommendation product.

Your task is to decide which candidate frontier is safer and more plausible for the same scenario.

Priorities, in order:
1. Public safety and gating correctness
2. Indication and population appropriateness
3. Ranking sanity for a general public product
4. Avoiding cheap but implausible prescription or condition-specific leakage
5. Explanation clarity as a secondary tiebreaker

Important rules:
- Prefer broadly applicable, low-regret recommendations for healthy public profiles.
- Penalize prescriptions or diagnosis-specific items when the scenario does not justify them.
- Penalize male-specific or indication-specific leakage in female or generic public profiles.
- Penalize airway/OSA interventions when the scenario does not show a meaningful airway signal.
- Do not reward “interesting” outputs if they are not product-safe.

Return JSON only with this shape:
{
  "winner": "A" | "B" | "tie",
  "confidence": 0.0,
  "summary": "short explanation",
  "safety_issues": ["..."],
  "ranking_issues": ["..."],
  "best_aspects": {
    "A": ["..."],
    "B": ["..."]
  }
}

Scenario:
{{scenario}}

Candidate A:
{{candidate_a}}

Candidate B:
{{candidate_b}}
