import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { colors, contrastPairs, type Hsl } from "../tokens";

/**
 * Convert an HSL triple (matching CSS `H S% L%`) to sRGB in [0, 1].
 *
 * @see https://www.w3.org/TR/css-color-3/#hsl-color
 */
function hslToRgb([h, s, l]: Hsl): [number, number, number] {
  const sat = s / 100;
  const lit = l / 100;
  const c = (1 - Math.abs(2 * lit - 1)) * sat;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = lit - c / 2;
  let rp = 0,
    gp = 0,
    bp = 0;
  if (h < 60) [rp, gp, bp] = [c, x, 0];
  else if (h < 120) [rp, gp, bp] = [x, c, 0];
  else if (h < 180) [rp, gp, bp] = [0, c, x];
  else if (h < 240) [rp, gp, bp] = [0, x, c];
  else if (h < 300) [rp, gp, bp] = [x, 0, c];
  else [rp, gp, bp] = [c, 0, x];
  return [rp + m, gp + m, bp + m];
}

/**
 * Compute WCAG 2.x relative luminance from sRGB in [0, 1].
 *
 * @see https://www.w3.org/TR/WCAG22/#dfn-relative-luminance
 */
function relativeLuminance(rgb: readonly [number, number, number]): number {
  const linear = rgb.map((c) =>
    c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4),
  );
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

/**
 * Compute the WCAG contrast ratio between two HSL colors.
 *
 * @see https://www.w3.org/TR/WCAG22/#dfn-contrast-ratio
 */
export function contrastRatio(fg: Hsl, bg: Hsl): number {
  const lFg = relativeLuminance(hslToRgb(fg));
  const lBg = relativeLuminance(hslToRgb(bg));
  const lighter = Math.max(lFg, lBg);
  const darker = Math.min(lFg, lBg);
  return (lighter + 0.05) / (darker + 0.05);
}

/** Parse `--token-name: H S% L%;` declarations from tokens.css. */
function parseTokensCss(css: string): Map<string, Hsl> {
  const out = new Map<string, Hsl>();
  const re = /--([a-z0-9-]+):\s*(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)%\s+(\d+(?:\.\d+)?)%\s*;/gi;
  let match: RegExpExecArray | null;
  while ((match = re.exec(css)) !== null) {
    out.set(match[1], [
      Number(match[2]),
      Number(match[3]),
      Number(match[4]),
    ] as const);
  }
  return out;
}

describe("token contrast", () => {
  it("each documented contrast pair clears its declared minimum", () => {
    const failures: string[] = [];
    for (const pair of contrastPairs) {
      const ratio = contrastRatio(pair.fg, pair.bg);
      if (ratio < pair.minRatio) {
        failures.push(
          `${pair.description}: ${ratio.toFixed(2)}:1 (need ${pair.minRatio.toFixed(1)}:1)`,
        );
      }
    }
    if (failures.length > 0) {
      throw new Error(
        `${failures.length} contrast pair(s) below WCAG minimum:\n  ${failures.join("\n  ")}`,
      );
    }
  });

  it("contrastRatio matches known WCAG values", () => {
    // White on black = 21:1 (the maximum).
    expect(contrastRatio([0, 0, 100], [0, 0, 0])).toBeCloseTo(21, 0);
    // Same color = 1:1.
    expect(contrastRatio([18, 77, 42], [18, 77, 42])).toBeCloseTo(1, 5);
  });

  it("tokens.css HSL values stay in sync with the JS token table", () => {
    const cssPath = resolve(__dirname, "../styles/tokens.css");
    const parsed = parseTokensCss(readFileSync(cssPath, "utf8"));
    const expected: Array<[string, Hsl]> = [
      ["paper-000", colors.paper000],
      ["paper-050", colors.paper050],
      ["paper-100", colors.paper100],
      ["ink-900", colors.ink900],
      ["ink-800", colors.ink800],
      ["ink-600", colors.ink600],
      ["ink-500", colors.ink500],
      ["sage-700", colors.sage700],
      ["sage-400", colors.sage400],
      ["rust-600", colors.rust600],
      ["rust-300", colors.rust300],
      ["sand-300", colors.sand300],
      ["sand-400", colors.sand400],
      ["danger-600", colors.danger600],
    ];
    const drift: string[] = [];
    for (const [name, expectedTuple] of expected) {
      const actual = parsed.get(name);
      if (!actual) {
        drift.push(`${name}: missing from tokens.css`);
        continue;
      }
      if (
        actual[0] !== expectedTuple[0] ||
        actual[1] !== expectedTuple[1] ||
        actual[2] !== expectedTuple[2]
      ) {
        drift.push(
          `${name}: tokens.css has ${actual.join(" ")} but JS table has ${expectedTuple.join(" ")}`,
        );
      }
    }
    if (drift.length > 0) {
      throw new Error(`Token drift between tokens.css and src/tokens:\n  ${drift.join("\n  ")}`);
    }
  });
});
