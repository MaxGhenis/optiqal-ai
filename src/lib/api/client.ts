/**
 * Client utilities for calling OptiqAI API endpoints
 */

import type {
  CombinationsRequest,
  CombinationsResponse,
  PortfolioRequest,
  PortfolioResponse,
} from "@/app/api/types";

/**
 * Calculate combined QALY for selected interventions
 */
export async function calculateCombinations(
  request: CombinationsRequest
): Promise<CombinationsResponse> {
  const response = await fetch("/api/combinations", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || "Failed to calculate combinations");
  }

  return response.json();
}

/**
 * Find optimal intervention portfolio
 */
export async function findOptimalPortfolio(
  request: PortfolioRequest
): Promise<PortfolioResponse> {
  const response = await fetch("/api/portfolio", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || "Failed to find optimal portfolio");
  }

  return response.json();
}
