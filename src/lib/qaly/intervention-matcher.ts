/**
 * Intervention ID Matcher
 *
 * Maps user queries to precomputed intervention IDs for instant profile-based results.
 */

interface InterventionMapping {
  id: string;
  keywords: string[];
  name: string;
}

const INTERVENTION_MAPPINGS: InterventionMapping[] = [
  {
    id: "walking_30min_daily",
    keywords: [
      "walking",
      "walk",
      "30 min",
      "30 minute",
      "daily walk",
      "brisk walk",
    ],
    name: "30 minutes daily walking",
  },
  {
    id: "strength_training",
    keywords: [
      "strength training",
      "weight lifting",
      "resistance training",
      "lift weights",
      "gym",
      "weightlifting",
    ],
    name: "Strength training",
  },
  {
    id: "daily_exercise_moderate",
    keywords: [
      "moderate exercise",
      "daily exercise",
      "150 min",
      "150 minutes",
      "exercise daily",
    ],
    name: "Daily moderate exercise",
  },
  {
    id: "quit_smoking",
    keywords: [
      "quit smoking",
      "stop smoking",
      "smoking cessation",
      "quit cigarettes",
      "stop cigarettes",
    ],
    name: "Quit smoking",
  },
  {
    id: "mediterranean_diet",
    keywords: [
      "mediterranean diet",
      "mediterranean",
      "med diet",
      "olive oil",
      "fish diet",
    ],
    name: "Mediterranean diet",
  },
  {
    id: "sleep_8_hours",
    keywords: [
      "sleep 8 hours",
      "8 hours sleep",
      "sleep eight hours",
      "adequate sleep",
      "sleep more",
    ],
    name: "Sleep 8 hours nightly",
  },
  {
    id: "meditation_daily",
    keywords: [
      "meditation",
      "meditate",
      "mindfulness",
      "daily meditation",
      "meditate daily",
    ],
    name: "Daily meditation",
  },
  {
    id: "moderate_alcohol",
    keywords: [
      "moderate alcohol",
      "moderate drinking",
      "1-2 drinks",
      "light drinking",
    ],
    name: "Moderate alcohol consumption",
  },
  {
    id: "fish_oil_supplement",
    keywords: [
      "fish oil",
      "omega-3",
      "omega 3",
      "fish oil supplement",
      "omega-3 supplement",
    ],
    name: "Fish oil supplement",
  },
  {
    id: "daily_sunscreen",
    keywords: [
      "sunscreen",
      "daily sunscreen",
      "sunscreen daily",
      "spf",
      "sun protection",
    ],
    name: "Daily sunscreen",
  },
];

/**
 * Match a user query to a precomputed intervention ID
 *
 * Returns the intervention ID if a match is found, null otherwise.
 */
export function matchInterventionId(query: string): {
  id: string;
  name: string;
} | null {
  const normalizedQuery = query.toLowerCase().trim();

  for (const mapping of INTERVENTION_MAPPINGS) {
    for (const keyword of mapping.keywords) {
      if (normalizedQuery.includes(keyword)) {
        return {
          id: mapping.id,
          name: mapping.name,
        };
      }
    }
  }

  return null;
}

/**
 * Get all available precomputed interventions
 */
export function getAvailableInterventions(): InterventionMapping[] {
  return INTERVENTION_MAPPINGS;
}
