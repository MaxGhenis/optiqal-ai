/**
 * Seedable Random Number Generator
 *
 * This module provides deterministic random number generation for reproducibility.
 * All QALY simulation code should use this instead of Math.random().
 *
 * Usage:
 *   import { random, setSeed } from './random';
 *
 *   setSeed(42);  // Set seed for reproducibility
 *   const value = random();  // Get random number [0, 1)
 */

import seedrandom from "seedrandom";

/**
 * Current PRNG instance
 */
let prng: seedrandom.PRNG = seedrandom();

/**
 * Set the random seed for reproducibility
 *
 * @param seed - Seed value (number or string)
 */
export function setSeed(seed: number | string): void {
  prng = seedrandom(String(seed));
}

/**
 * Get a random number in [0, 1)
 *
 * This is a drop-in replacement for Math.random()
 */
export function random(): number {
  return prng();
}

/**
 * Reset to unseeded (truly random) state
 */
export function resetRandom(): void {
  prng = seedrandom();
}
