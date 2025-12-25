/**
 * Example: Using the OptiqAI API endpoints in a React component
 *
 * This demonstrates how to use both the combinations and portfolio endpoints
 * with the provided React hooks.
 */

"use client";

import { useState } from "react";
import { useCombinations, usePortfolio } from "@/lib/api/hooks";
import type { ProfileQuery } from "@/lib/qaly/precomputed-profiles";

export default function InterventionCalculator() {
  const [profile] = useState<ProfileQuery>({
    age: 35,
    sex: "male",
    bmiCategory: "normal",
    smokingStatus: "never",
    hasDiabetes: false,
    hasHypertension: false,
    activityLevel: "light",
  });

  const [selectedInterventions, setSelectedInterventions] = useState<string[]>([
    "walking_30min_daily",
    "sleep_8_hours",
  ]);

  const { calculate, data: combinationData, loading: loadingCombination } = useCombinations();
  const { findPortfolio, data: portfolioData, loading: loadingPortfolio } = usePortfolio();

  const handleCalculateCombination = async () => {
    try {
      await calculate({
        profile,
        selectedInterventions,
      });
    } catch (error) {
      console.error("Failed to calculate combinations:", error);
    }
  };

  const handleFindPortfolio = async () => {
    try {
      await findPortfolio({
        profile,
        maxInterventions: 5,
      });
    } catch (error) {
      console.error("Failed to find portfolio:", error);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold">Intervention Calculator</h1>

      {/* Profile Display */}
      <div className="bg-gray-50 p-4 rounded-lg">
        <h2 className="text-xl font-semibold mb-2">Your Profile</h2>
        <dl className="grid grid-cols-2 gap-2 text-sm">
          <dt className="font-medium">Age:</dt>
          <dd>{profile.age}</dd>
          <dt className="font-medium">Sex:</dt>
          <dd>{profile.sex}</dd>
          <dt className="font-medium">BMI Category:</dt>
          <dd>{profile.bmiCategory}</dd>
          <dt className="font-medium">Smoking Status:</dt>
          <dd>{profile.smokingStatus}</dd>
        </dl>
      </div>

      {/* Combination Calculator */}
      <div className="border rounded-lg p-4">
        <h2 className="text-xl font-semibold mb-4">Calculate Combination</h2>

        <div className="mb-4">
          <label className="block text-sm font-medium mb-2">
            Selected Interventions:
          </label>
          <div className="space-y-2">
            {selectedInterventions.map((id) => (
              <div key={id} className="flex items-center">
                <input
                  type="checkbox"
                  checked
                  onChange={() =>
                    setSelectedInterventions((prev) => prev.filter((i) => i !== id))
                  }
                  className="mr-2"
                />
                <span className="text-sm">{id.replace(/_/g, " ")}</span>
              </div>
            ))}
          </div>
        </div>

        <button
          onClick={handleCalculateCombination}
          disabled={loadingCombination}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:bg-gray-400"
        >
          {loadingCombination ? "Calculating..." : "Calculate Combination"}
        </button>

        {combinationData && (
          <div className="mt-4 bg-green-50 p-4 rounded">
            <h3 className="font-semibold mb-2">Results:</h3>
            <p className="text-lg">
              Total QALY: <span className="font-bold">{combinationData.totalQaly.toFixed(3)}</span>
            </p>
            <p className="text-sm text-gray-600">
              Diminishing returns factor: {combinationData.diminishingReturnsFactor.toFixed(2)}
            </p>

            <div className="mt-2">
              <p className="text-sm font-medium">Individual QALYs:</p>
              <ul className="text-sm space-y-1">
                {Object.entries(combinationData.individualQalys).map(([id, qaly]) => (
                  <li key={id}>
                    {id.replace(/_/g, " ")}: {qaly.toFixed(3)}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>

      {/* Portfolio Finder */}
      <div className="border rounded-lg p-4">
        <h2 className="text-xl font-semibold mb-4">Find Optimal Portfolio</h2>

        <button
          onClick={handleFindPortfolio}
          disabled={loadingPortfolio}
          className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700 disabled:bg-gray-400"
        >
          {loadingPortfolio ? "Finding..." : "Find Optimal Portfolio"}
        </button>

        {portfolioData && (
          <div className="mt-4 bg-purple-50 p-4 rounded">
            <h3 className="font-semibold mb-2">Optimal Portfolio Path:</h3>
            <div className="space-y-3">
              {portfolioData.portfolio.map((step, index) => (
                <div key={index} className="border-l-4 border-purple-600 pl-3">
                  <p className="font-medium">
                    Step {index + 1}: Add {step.addedIntervention.replace(/_/g, " ")}
                  </p>
                  <p className="text-sm text-gray-600">
                    Marginal QALY: +{step.marginalQaly.toFixed(3)} | Total: {step.totalQaly.toFixed(3)}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
