/** Optiqal design tokens as JS constants.
 *
 * Mirrors the canonical HSL values declared in `src/styles/tokens.css`. Keep
 * the two in sync — the contrast test in `__tests__/contrast.test.ts` reads
 * from this module and asserts every documented foreground / surface pair
 * clears its WCAG minimum, so token edits that drop below threshold fail CI.
 */

/** An HSL color tuple matching the `H S% L%` form used in tokens.css. */
export type Hsl = readonly [h: number, s: number, l: number];

export const colors = {
  // Surfaces
  paper000: [42, 52, 99] as const,
  paper050: [42, 46, 96] as const,
  paper100: [42, 42, 94] as const,

  // Ink
  ink900: [166, 24, 14] as const,
  ink800: [166, 20, 18] as const,
  ink600: [166, 16, 28] as const,
  ink500: [166, 11, 38] as const,

  // Brand sage
  sage700: [167, 43, 31] as const,
  sage400: [168, 30, 68] as const,

  // Highlight rust. `rust600` is the AA text/icon color (4.5:1 on paper);
  // `rust300` is for low-contrast decorative tints only.
  rust600: [18, 77, 42] as const,
  rust300: [23, 70, 74] as const,

  // Borders. `sand300` is the decorative `--border-subtle` (no SC 1.4.11
  // contract). `sand400` is `--border-strong` / `--input` and clears 3:1
  // against paper for form input boundaries (SC 1.4.11 non-text).
  sand300: [38, 28, 82] as const,
  sand400: [38, 24, 50] as const,

  danger600: [3, 70, 46] as const,
} as const satisfies Record<string, Hsl>;

/** Documented WCAG contrast guarantees. Asserted in
 * `__tests__/contrast.test.ts`; drift fails CI. */
export type ContrastPair = {
  description: string;
  fg: Hsl;
  bg: Hsl;
  /** WCAG SC 1.4.3 normal-text minimum is 4.5; 1.4.11 non-text is 3.0. */
  minRatio: number;
};

export const contrastPairs: readonly ContrastPair[] = [
  // Body text on the canvas surface
  {
    description: "ink-900 on paper-050 (body text)",
    fg: colors.ink900,
    bg: colors.paper050,
    minRatio: 4.5,
  },
  {
    description: "ink-800 on paper-050 (text-base)",
    fg: colors.ink800,
    bg: colors.paper050,
    minRatio: 4.5,
  },
  {
    description: "ink-600 on paper-050 (text-soft)",
    fg: colors.ink600,
    bg: colors.paper050,
    minRatio: 4.5,
  },
  {
    description: "ink-500 on paper-050 (text-muted, smallest legible)",
    fg: colors.ink500,
    bg: colors.paper050,
    minRatio: 4.5,
  },
  // Same body text against the elevated paper-100 surface
  {
    description: "ink-900 on paper-100",
    fg: colors.ink900,
    bg: colors.paper100,
    minRatio: 4.5,
  },
  {
    description: "ink-500 on paper-100 (text-muted floor)",
    fg: colors.ink500,
    bg: colors.paper100,
    minRatio: 4.5,
  },
  // And against the panel surface that cards use
  {
    description: "ink-900 on paper-000 (cards)",
    fg: colors.ink900,
    bg: colors.paper000,
    minRatio: 4.5,
  },
  {
    description: "ink-500 on paper-000 (text-muted in cards)",
    fg: colors.ink500,
    bg: colors.paper000,
    minRatio: 4.5,
  },
  // Brand sage as text — buttons, links, headings
  {
    description: "sage-700 on paper-050 (brand text)",
    fg: colors.sage700,
    bg: colors.paper050,
    minRatio: 4.5,
  },
  {
    description: "sage-700 on paper-000 (brand text on cards)",
    fg: colors.sage700,
    bg: colors.paper000,
    minRatio: 4.5,
  },
  // Highlight rust as text — accent badges, icons used as text accents,
  // small-text disclaimers (text-accent in brand/writing)
  {
    description: "rust-600 on paper-050 (accent text)",
    fg: colors.rust600,
    bg: colors.paper050,
    minRatio: 4.5,
  },
  {
    description: "rust-600 on paper-000 (accent text on cards)",
    fg: colors.rust600,
    bg: colors.paper000,
    minRatio: 4.5,
  },
  {
    description: "rust-600 on paper-100 (accent text on elevated)",
    fg: colors.rust600,
    bg: colors.paper100,
    minRatio: 4.5,
  },
  // Danger as text
  {
    description: "danger-600 on paper-050 (status text)",
    fg: colors.danger600,
    bg: colors.paper050,
    minRatio: 4.5,
  },
  // SC 1.4.11 non-text — form input borders
  {
    description: "sand-400 on paper-050 (input border, SC 1.4.11)",
    fg: colors.sand400,
    bg: colors.paper050,
    minRatio: 3,
  },
  {
    description: "sand-400 on paper-000 (input border on cards, SC 1.4.11)",
    fg: colors.sand400,
    bg: colors.paper000,
    minRatio: 3,
  },
  // Focus ring (sage-700 doubles as `--ring-strong`)
  {
    description: "sage-700 on paper-050 (focus ring, SC 1.4.11)",
    fg: colors.sage700,
    bg: colors.paper050,
    minRatio: 3,
  },
];
