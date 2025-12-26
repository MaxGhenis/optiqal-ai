# API Implementation Summary

This document summarizes the new API endpoints for intervention combination calculations.

## Files Created

### API Routes

1. **`src/app/api/combinations/route.ts`**
   - POST endpoint for calculating combined QALY impact
   - Accepts profile + selected interventions
   - Returns total QALY with breakdown by intervention and overlap penalties
   - Comprehensive input validation
   - Error handling with appropriate HTTP status codes

2. **`src/app/api/portfolio/route.ts`**
   - POST endpoint for finding optimal intervention portfolio
   - Accepts profile + optional exclusions and max size
   - Returns ranked list showing which interventions to add at each step
   - Uses greedy algorithm for optimization

3. **`src/app/api/types.ts`**
   - Centralized type exports for both API routes
   - Makes it easy to import request/response types in client code

### Tests

4. **`src/app/api/combinations/route.test.ts`**
   - 11 comprehensive tests covering:
     - Input validation (invalid body, missing/invalid fields)
     - Error handling (null results)
     - Successful responses
     - Optional parameters
     - Default values

5. **`src/app/api/portfolio/route.test.ts`**
   - 11 comprehensive tests covering:
     - Input validation
     - Exclusion handling
     - Max interventions parameter
     - Missing data scenarios
     - Default values

### Client Utilities

6. **`src/lib/api/client.ts`**
   - Typed fetch wrappers for both endpoints
   - Error handling with helpful messages
   - Easy to use in any client-side code

7. **`src/lib/api/hooks.ts`**
   - React hooks for both endpoints: `useCombinations()` and `usePortfolio()`
   - Manage loading, error, and data states
   - Reset functionality

### Documentation

8. **`src/app/api/README.md`**
   - Complete API documentation
   - Request/response schemas
   - Example curl commands
   - Available interventions list
   - Error response formats

9. **`examples/api-usage.tsx`**
   - Full React component example
   - Demonstrates both endpoints
   - Shows hook usage patterns
   - Interactive UI example

## Test Results

All tests pass:

```
✓ src/app/api/combinations/route.test.ts (11 tests) 8ms
✓ src/app/api/portfolio/route.test.ts (11 tests) 8ms

Test Files  2 passed (2)
Tests  22 passed (22)
```

## Key Features

### Combinations Endpoint (`/api/combinations`)

- **Input Validation**: Age range (0-120), valid enum values for all categorical fields
- **Overlap Corrections**: Applies intervention-specific overlap penalties
- **Diminishing Returns**: Global factor for stacking many interventions
- **Flexible Options**: Can disable overlap or diminishing returns for testing
- **Detailed Breakdown**: Returns individual QALYs before adjustments + penalty factors

### Portfolio Endpoint (`/api/portfolio`)

- **Greedy Optimization**: Iteratively selects intervention with highest marginal gain
- **Exclusion Support**: Can exclude interventions from consideration
- **Configurable Size**: Max portfolio size (defaults to 5, capped at 10)
- **Step-by-Step Path**: Shows which intervention to add at each step with marginal gains
- **Handles Missing Data**: Gracefully excludes interventions without precomputed data

## Usage Example

```typescript
import { useCombinations, usePortfolio } from "@/lib/api/hooks";

function MyComponent() {
  const { calculate, data, loading, error } = useCombinations();

  const handleCalculate = async () => {
    await calculate({
      profile: {
        age: 35,
        sex: "male",
        bmiCategory: "normal",
        smokingStatus: "never",
        hasDiabetes: false,
      },
      selectedInterventions: ["walking_30min_daily", "sleep_8_hours"],
    });
  };

  return (
    <div>
      <button onClick={handleCalculate} disabled={loading}>
        Calculate
      </button>
      {data && <div>Total QALY: {data.totalQaly}</div>}
    </div>
  );
}
```

## Technical Implementation

- **TypeScript**: Full type safety throughout
- **Next.js 15**: Uses App Router API route handlers
- **Validation**: Runtime validation with helpful error messages
- **Testing**: Vitest with comprehensive mocking
- **Error Handling**: Appropriate HTTP status codes (400, 500)
- **Type Safety**: Validates enums and ranges before type assertions

## Available Interventions

The endpoints currently support 10 interventions:

- walking_30min_daily
- daily_exercise_moderate
- strength_training
- mediterranean_diet
- fish_oil_supplement
- quit_smoking
- moderate_alcohol
- meditation_daily
- sleep_8_hours
- daily_sunscreen

Each requires precomputed profile data in `/public/precomputed/[intervention_id]_profiles.json`.

## Next Steps

Potential enhancements:

1. **Caching**: Add response caching for common profile queries
2. **Batch Operations**: Support multiple profiles in one request
3. **More Algorithms**: Add alternative optimization strategies (e.g., integer programming)
4. **Cost Integration**: Factor in intervention costs for cost-effectiveness analysis
5. **Personalization**: Use effect modifiers from precomputed data
6. **Rate Limiting**: Add rate limiting for production deployment
