# API Routes

This directory contains Next.js API routes for the OptiqAI application.

## Endpoints

### POST /api/combinations

Calculate combined QALY impact of multiple interventions with overlap and diminishing returns corrections.

**Request Body:**

```typescript
{
  profile: {
    age: number;              // 0-120
    sex: "male" | "female";
    bmiCategory: "normal" | "overweight" | "obese" | "severely_obese";
    smokingStatus: "never" | "former" | "current";
    hasDiabetes: boolean;
    hasHypertension?: boolean;    // Optional, defaults to false
    activityLevel?: "sedentary" | "light" | "moderate" | "active";  // Optional, defaults to "light"
  },
  selectedInterventions: string[];  // Array of intervention IDs
  options?: {
    applyOverlap?: boolean;              // Optional, defaults to true
    applyDiminishingReturns?: boolean;   // Optional, defaults to true
  }
}
```

**Response:**

```typescript
{
  totalQaly: number;                          // Combined QALY after all adjustments
  individualQalys: Record<string, number>;    // QALY for each intervention before adjustments
  overlapAdjustments: Record<string, number>; // Overlap penalty factors applied (< 1.0)
  diminishingReturnsFactor: number;           // Global diminishing returns factor
  interventionIds: string[];                  // Interventions included in calculation
}
```

**Example:**

```bash
curl -X POST http://localhost:3000/api/combinations \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {
      "age": 35,
      "sex": "male",
      "bmiCategory": "normal",
      "smokingStatus": "never",
      "hasDiabetes": false
    },
    "selectedInterventions": ["walking_30min_daily", "sleep_8_hours"]
  }'
```

**Response:**

```json
{
  "totalQaly": 0.52,
  "individualQalys": {
    "walking_30min_daily": 0.3,
    "sleep_8_hours": 0.25
  },
  "overlapAdjustments": {
    "sleep_8_hours": 0.9
  },
  "diminishingReturnsFactor": 0.95,
  "interventionIds": ["walking_30min_daily", "sleep_8_hours"]
}
```

### POST /api/portfolio

Find optimal intervention portfolio using greedy selection. Returns ranked list showing which interventions to add at each step to maximize QALY gain.

**Request Body:**

```typescript
{
  profile: {
    age: number;              // 0-120
    sex: "male" | "female";
    bmiCategory: "normal" | "overweight" | "obese" | "severely_obese";
    smokingStatus: "never" | "former" | "current";
    hasDiabetes: boolean;
    hasHypertension?: boolean;    // Optional, defaults to false
    activityLevel?: "sedentary" | "light" | "moderate" | "active";  // Optional, defaults to "light"
  },
  excludedInterventions?: string[];  // Optional, interventions to exclude from consideration
  maxInterventions?: number;         // Optional, max portfolio size (defaults to 5, capped at 10)
}
```

**Response:**

```typescript
{
  portfolio: Array<{
    interventionIds: string[];     // Interventions in portfolio at this step
    totalQaly: number;             // Cumulative QALY at this step
    marginalQaly: number;          // QALY gained by adding this intervention
    addedIntervention: string;     // Intervention added at this step
  }>,
  availableInterventions: string[];  // All interventions considered (after exclusions)
}
```

**Example:**

```bash
curl -X POST http://localhost:3000/api/portfolio \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {
      "age": 35,
      "sex": "male",
      "bmiCategory": "normal",
      "smokingStatus": "never",
      "hasDiabetes": false
    },
    "maxInterventions": 3
  }'
```

**Response:**

```json
{
  "portfolio": [
    {
      "interventionIds": ["walking_30min_daily"],
      "totalQaly": 0.3,
      "marginalQaly": 0.3,
      "addedIntervention": "walking_30min_daily"
    },
    {
      "interventionIds": ["walking_30min_daily", "sleep_8_hours"],
      "totalQaly": 0.52,
      "marginalQaly": 0.22,
      "addedIntervention": "sleep_8_hours"
    },
    {
      "interventionIds": ["walking_30min_daily", "sleep_8_hours", "mediterranean_diet"],
      "totalQaly": 0.68,
      "marginalQaly": 0.16,
      "addedIntervention": "mediterranean_diet"
    }
  ],
  "availableInterventions": [
    "walking_30min_daily",
    "daily_exercise_moderate",
    "strength_training",
    "mediterranean_diet",
    "fish_oil_supplement",
    "quit_smoking",
    "moderate_alcohol",
    "meditation_daily",
    "sleep_8_hours",
    "daily_sunscreen"
  ]
}
```

## Available Interventions

The following interventions are currently supported (must have precomputed data):

- `walking_30min_daily` - 30 minutes of walking daily
- `daily_exercise_moderate` - Moderate exercise daily
- `strength_training` - Regular strength training
- `mediterranean_diet` - Mediterranean diet
- `fish_oil_supplement` - Fish oil supplementation
- `quit_smoking` - Smoking cessation
- `moderate_alcohol` - Moderate alcohol consumption
- `meditation_daily` - Daily meditation practice
- `sleep_8_hours` - 8 hours of sleep per night
- `daily_sunscreen` - Daily sunscreen use

## Error Responses

All endpoints return appropriate HTTP status codes:

- `200` - Success
- `400` - Invalid request (missing/invalid parameters)
- `500` - Server error (missing precomputed data, calculation failure)

Error response format:

```json
{
  "error": "Description of the error"
}
```

## TypeScript Types

Import types from the API module:

```typescript
import type {
  CombinationsRequest,
  CombinationsResponse,
  PortfolioRequest,
  PortfolioResponse,
  PortfolioStep,
} from "@/app/api/types";
```

## Implementation Details

Both endpoints:

1. Validate the profile and intervention parameters
2. Fetch precomputed single-intervention QALYs from JSON files
3. Apply overlap corrections based on intervention similarity
4. Apply global diminishing returns for stacking multiple interventions
5. Return results with detailed breakdowns

The `/api/portfolio` endpoint uses a greedy algorithm to build the optimal portfolio step-by-step, selecting the intervention with the highest marginal QALY gain at each step.
