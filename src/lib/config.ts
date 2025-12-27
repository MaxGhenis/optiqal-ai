/**
 * Feature flags for the Optiqal app.
 *
 * These control what features are visible to users while keeping
 * the underlying engine functionality intact.
 */

export const FEATURES = {
  /**
   * Whether to show quality-of-life adjustments (QALYs).
   *
   * When false:
   * - UI shows "life years" instead of "QALYs"
   * - Quality breakdown panel is hidden
   * - Only longevity impacts are displayed
   *
   * The engine still calculates quality adjustments internally,
   * but they're not exposed in the user interface.
   */
  SHOW_QUALITY_ADJUSTMENTS: false,

  /**
   * Whether to show the detailed mechanism breakdown.
   */
  SHOW_MECHANISM_DETAILS: true,

  /**
   * Whether to show confounding adjustment details.
   */
  SHOW_CONFOUNDING_DETAILS: true,
} as const;

/**
 * Labels that change based on feature flags.
 */
export function getLabels() {
  if (FEATURES.SHOW_QUALITY_ADJUSTMENTS) {
    return {
      mainMetric: "QALY Impact",
      mainMetricUnit: "of quality-adjusted life",
      shortUnit: "QALYs",
      probabilityLabel: "P(> 1 year QALY gain)",
    };
  } else {
    return {
      mainMetric: "Life Years Impact",
      mainMetricUnit: "of additional life expectancy",
      shortUnit: "years",
      probabilityLabel: "P(> 1 year life gained)",
    };
  }
}
