/**
 * Life expectancy data from CDC/NCHS National Vital Statistics
 * Source: https://www.cdc.gov/nchs/data/nvsr/nvsr74/nvsr74-04.pdf
 * Data: United States Life Tables, 2022
 *
 * e(x) = remaining life expectancy at age x
 */

export interface LifeTableEntry {
  age: number;
  male: number; // remaining life expectancy in years
  female: number;
}

// CDC 2022 Period Life Table (Table 1)
// Selected ages - we interpolate for others
export const US_LIFE_TABLE_2022: LifeTableEntry[] = [
  { age: 0, male: 74.8, female: 80.2 },
  { age: 1, male: 74.3, female: 79.6 },
  { age: 5, male: 70.4, female: 75.7 },
  { age: 10, male: 65.5, female: 70.7 },
  { age: 15, male: 60.5, female: 65.8 },
  { age: 20, male: 55.8, female: 60.9 },
  { age: 25, male: 51.1, female: 56.0 },
  { age: 30, male: 46.5, female: 51.2 },
  { age: 35, male: 41.8, female: 46.4 },
  { age: 40, male: 37.2, female: 41.6 },
  { age: 45, male: 32.7, female: 36.9 },
  { age: 50, male: 28.4, female: 32.3 },
  { age: 55, male: 24.2, female: 27.9 },
  { age: 60, male: 20.3, female: 23.6 },
  { age: 65, male: 16.7, female: 19.5 },
  { age: 70, male: 13.4, female: 15.7 },
  { age: 75, male: 10.5, female: 12.3 },
  { age: 80, male: 7.9, female: 9.2 },
  { age: 85, male: 5.7, female: 6.6 },
  { age: 90, male: 4.0, female: 4.6 },
  { age: 95, male: 2.8, female: 3.1 },
  { age: 100, male: 2.0, female: 2.1 },
];

/**
 * Get remaining life expectancy for a given age and sex
 * Uses linear interpolation between table entries
 */
export function getRemainingLifeExpectancy(
  age: number,
  sex: "male" | "female" | "other"
): number {
  // Use average for "other"
  const sexKey = sex === "other" ? null : sex;

  // Clamp age to table range
  const clampedAge = Math.max(0, Math.min(100, age));

  // Find surrounding entries
  let lower = US_LIFE_TABLE_2022[0];
  let upper = US_LIFE_TABLE_2022[US_LIFE_TABLE_2022.length - 1];

  for (let i = 0; i < US_LIFE_TABLE_2022.length - 1; i++) {
    if (
      US_LIFE_TABLE_2022[i].age <= clampedAge &&
      US_LIFE_TABLE_2022[i + 1].age > clampedAge
    ) {
      lower = US_LIFE_TABLE_2022[i];
      upper = US_LIFE_TABLE_2022[i + 1];
      break;
    }
  }

  // Linear interpolation
  const t = (clampedAge - lower.age) / (upper.age - lower.age || 1);

  if (sexKey) {
    return lower[sexKey] + t * (upper[sexKey] - lower[sexKey]);
  } else {
    // Average of male and female
    const maleLE = lower.male + t * (upper.male - lower.male);
    const femaleLE = lower.female + t * (upper.female - lower.female);
    return (maleLE + femaleLE) / 2;
  }
}

/**
 * Get expected age at death
 */
export function getLifeExpectancy(
  currentAge: number,
  sex: "male" | "female" | "other"
): number {
  return currentAge + getRemainingLifeExpectancy(currentAge, sex);
}
