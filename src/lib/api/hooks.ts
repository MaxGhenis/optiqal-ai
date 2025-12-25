/**
 * React hooks for OptiqAI API endpoints
 */

import { useState, useCallback } from "react";
import type {
  CombinationsRequest,
  CombinationsResponse,
  PortfolioRequest,
  PortfolioResponse,
} from "@/app/api/types";
import { calculateCombinations, findOptimalPortfolio } from "./client";

/**
 * Hook for calculating intervention combinations
 *
 * @example
 * const { calculate, data, loading, error } = useCombinations();
 *
 * const handleCalculate = async () => {
 *   await calculate({
 *     profile: { age: 35, sex: "male", ... },
 *     selectedInterventions: ["walking_30min_daily", "sleep_8_hours"]
 *   });
 * };
 */
export function useCombinations() {
  const [data, setData] = useState<CombinationsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const calculate = useCallback(async (request: CombinationsRequest) => {
    setLoading(true);
    setError(null);
    try {
      const result = await calculateCombinations(request);
      setData(result);
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
  }, []);

  return { calculate, data, loading, error, reset };
}

/**
 * Hook for finding optimal intervention portfolio
 *
 * @example
 * const { findPortfolio, data, loading, error } = usePortfolio();
 *
 * const handleFindPortfolio = async () => {
 *   await findPortfolio({
 *     profile: { age: 35, sex: "male", ... },
 *     maxInterventions: 5
 *   });
 * };
 */
export function usePortfolio() {
  const [data, setData] = useState<PortfolioResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const findPortfolio = useCallback(async (request: PortfolioRequest) => {
    setLoading(true);
    setError(null);
    try {
      const result = await findOptimalPortfolio(request);
      setData(result);
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
  }, []);

  return { findPortfolio, data, loading, error, reset };
}
