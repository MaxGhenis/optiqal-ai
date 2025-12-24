/**
 * Example: Using Precomputed Baselines in TypeScript
 *
 * This example demonstrates how to use precomputed baseline data
 * for fast QALY calculations in the browser/Next.js environment.
 */

import {
  loadPrecomputedBaselines,
  getPrecomputedLifeExpectancy,
  getPrecomputedRemainingQALYs,
  getPrecomputedQualityWeight,
  type PrecomputedBaselines,
} from "./precomputed";
import { getRemainingLifeExpectancy } from "./life-tables";
import { getAgeQualityWeight } from "./quality-weights";

/**
 * Example 1: Direct precomputed lookups
 */
export async function exampleDirectLookups() {
  // Load precomputed data (cached after first load)
  const baselines = await loadPrecomputedBaselines();

  console.log("Direct Precomputed Lookups (O(1) operations)");
  console.log("=" + "=".repeat(69));

  // Life expectancy lookups
  const ages = [0, 20, 40, 60, 80];
  console.log("\nLife Expectancy (remaining years):");
  console.log("Age    Male    Female");
  console.log("-".repeat(30));

  for (const age of ages) {
    const male = getPrecomputedLifeExpectancy(age, "male", baselines);
    const female = getPrecomputedLifeExpectancy(age, "female", baselines);
    console.log(`${age.toString().padStart(3)}    ${male?.toFixed(1).padStart(4)}    ${female?.toFixed(1).padStart(6)}`);
  }

  // QALY lookups
  console.log("\nRemaining QALYs (3% discount rate):");
  console.log("Age    Male    Female");
  console.log("-".repeat(30));

  for (const age of ages) {
    const male = getPrecomputedRemainingQALYs(age, "male", baselines);
    const female = getPrecomputedRemainingQALYs(age, "female", baselines);
    console.log(`${age.toString().padStart(3)}    ${male?.toFixed(1).padStart(4)}    ${female?.toFixed(1).padStart(6)}`);
  }

  return baselines;
}

/**
 * Example 2: Using precomputed data with existing functions
 */
export async function exampleWithExistingFunctions() {
  const baselines = await loadPrecomputedBaselines();

  console.log("\n\nUsing Precomputed with Existing Functions");
  console.log("=" + "=".repeat(69));

  const age = 45;
  const sex = "male";

  // Method 1: With precomputed (fast, O(1))
  const start1 = performance.now();
  const lifeExpFast = getRemainingLifeExpectancy(age, sex, baselines);
  const qualityFast = getAgeQualityWeight(age, baselines);
  const duration1 = performance.now() - start1;

  console.log(`\nWith precomputed baselines (O(1) lookup):`);
  console.log(`  Life expectancy: ${lifeExpFast.toFixed(2)} years`);
  console.log(`  Quality weight: ${qualityFast.toFixed(3)}`);
  console.log(`  Time: ${duration1.toFixed(3)}ms`);

  // Method 2: Without precomputed (slower, O(n) interpolation)
  const start2 = performance.now();
  const lifeExpSlow = getRemainingLifeExpectancy(age, sex);
  const qualitySlow = getAgeQualityWeight(age);
  const duration2 = performance.now() - start2;

  console.log(`\nWithout precomputed (interpolation):`);
  console.log(`  Life expectancy: ${lifeExpSlow.toFixed(2)} years`);
  console.log(`  Quality weight: ${qualitySlow.toFixed(3)}`);
  console.log(`  Time: ${duration2.toFixed(3)}ms`);

  console.log(`\nSpeedup: ${(duration2 / duration1).toFixed(2)}x faster`);

  return baselines;
}

/**
 * Example 3: Batch processing with precomputed data
 */
export async function exampleBatchProcessing() {
  const baselines = await loadPrecomputedBaselines();

  console.log("\n\nBatch Processing Example");
  console.log("=" + "=".repeat(69));

  // Simulate processing 1000 user profiles
  const profiles = Array.from({ length: 1000 }, (_, i) => ({
    age: 20 + Math.floor(i / 20), // Ages 20-69
    sex: i % 2 === 0 ? ("male" as const) : ("female" as const),
  }));

  // With precomputed
  const start1 = performance.now();
  const results1 = profiles.map((p) => ({
    lifeExp: getRemainingLifeExpectancy(p.age, p.sex, baselines),
    qalys: getPrecomputedRemainingQALYs(p.age, p.sex, baselines),
  }));
  const duration1 = performance.now() - start1;

  console.log(`\nProcessed ${profiles.length} profiles with precomputed:`);
  console.log(`  Total time: ${duration1.toFixed(2)}ms`);
  console.log(`  Per profile: ${(duration1 / profiles.length).toFixed(3)}ms`);
  console.log(`  Throughput: ${(profiles.length / duration1 * 1000).toFixed(0)} profiles/second`);

  // Without precomputed
  const start2 = performance.now();
  const results2 = profiles.map((p) => ({
    lifeExp: getRemainingLifeExpectancy(p.age, p.sex),
    qalys: null, // Would need to calculate manually
  }));
  const duration2 = performance.now() - start2;

  console.log(`\nProcessed ${profiles.length} profiles without precomputed:`);
  console.log(`  Total time: ${duration2.toFixed(2)}ms`);
  console.log(`  Per profile: ${(duration2 / profiles.length).toFixed(3)}ms`);
  console.log(`  Throughput: ${(profiles.length / duration2 * 1000).toFixed(0)} profiles/second`);

  console.log(`\nSpeedup: ${(duration2 / duration1).toFixed(2)}x faster`);

  return results1;
}

/**
 * Example 4: Quality weight lookups for age ranges
 */
export async function exampleQualityWeights() {
  const baselines = await loadPrecomputedBaselines();

  console.log("\n\nQuality Weights Across Lifespan");
  console.log("=" + "=".repeat(69));
  console.log("Age    Quality Weight");
  console.log("-".repeat(30));

  for (let age = 0; age <= 100; age += 10) {
    const quality = getPrecomputedQualityWeight(age, baselines);
    console.log(`${age.toString().padStart(3)}    ${quality?.toFixed(3)}`);
  }
}

/**
 * Run all examples
 */
export async function runAllExamples() {
  try {
    await exampleDirectLookups();
    await exampleWithExistingFunctions();
    await exampleBatchProcessing();
    await exampleQualityWeights();

    console.log("\n\n" + "=" + "=".repeat(69));
    console.log("Summary");
    console.log("=" + "=".repeat(69));
    console.log(`
Precomputed baselines provide:
1. O(1) lookups instead of O(n) interpolation
2. Significant performance improvement for batch operations
3. Identical results to interpolation (within rounding)
4. Easy integration: just pass baselines parameter

Usage:
  const baselines = await loadPrecomputedBaselines();
  const lifeExp = getRemainingLifeExpectancy(age, sex, baselines);
  const quality = getAgeQualityWeight(age, baselines);
    `);
  } catch (error) {
    console.error("Error running examples:", error);
  }
}

// For testing in Node.js environment
if (typeof window === "undefined" && require.main === module) {
  runAllExamples();
}
