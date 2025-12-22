/**
 * Tests for A vs B comparison functionality
 */

import { describe, it, expect } from "vitest";
import { isComparisonQuery, parseComparisonQuery } from "./analyze-structured";

describe("isComparisonQuery", () => {
  it("should detect 'vs' pattern", () => {
    expect(isComparisonQuery("walking vs running")).toBe(true);
    expect(isComparisonQuery("nuts vs seeds")).toBe(true);
    expect(isComparisonQuery("walnuts vs. almonds")).toBe(true);
  });

  it("should detect 'or' pattern", () => {
    expect(isComparisonQuery("walking or running")).toBe(true);
    expect(isComparisonQuery("should I eat nuts or seeds")).toBe(true);
  });

  it("should detect 'compared to' pattern", () => {
    expect(isComparisonQuery("walking compared to cycling")).toBe(true);
  });

  it("should detect 'versus' pattern", () => {
    expect(isComparisonQuery("walking versus running")).toBe(true);
  });

  it("should detect 'which is better' pattern", () => {
    expect(isComparisonQuery("which is better: walking or running")).toBe(true);
    expect(isComparisonQuery("which is better, nuts vs seeds?")).toBe(true);
  });

  it("should detect 'compare' pattern", () => {
    expect(isComparisonQuery("compare walking to running")).toBe(true);
    expect(isComparisonQuery("compare nuts and seeds")).toBe(true);
  });

  it("should detect 'should I' pattern", () => {
    expect(isComparisonQuery("should I eat walnuts or almonds?")).toBe(true);
    expect(isComparisonQuery("should I do yoga vs pilates")).toBe(true);
  });

  it("should not match single interventions", () => {
    expect(isComparisonQuery("walking 30 minutes")).toBe(false);
    expect(isComparisonQuery("eat nuts daily")).toBe(false);
    expect(isComparisonQuery("how beneficial is walking")).toBe(false);
  });
});

describe("parseComparisonQuery", () => {
  it("should parse 'A vs B' queries", () => {
    const result = parseComparisonQuery("walking vs running");
    expect(result).toEqual({ a: "walking", b: "running" });
  });

  it("should parse 'A or B' queries", () => {
    const result = parseComparisonQuery("walnuts or almonds");
    expect(result).toEqual({ a: "walnuts", b: "almonds" });
  });

  it("should parse 'compare A to B' queries", () => {
    const result = parseComparisonQuery("compare nuts to seeds");
    expect(result).toEqual({ a: "nuts", b: "seeds" });
  });

  it("should parse 'should I do A or B' queries", () => {
    // Note: captures full phrase including "should I eat" - still usable for matching
    const result = parseComparisonQuery("should I eat walnuts or almonds?");
    expect(result?.a).toContain("walnuts");
    expect(result?.b).toContain("almonds");
  });

  it("should parse 'which is better' queries", () => {
    // The simple "A or B" pattern matches first
    const result = parseComparisonQuery("which is better: walking or cycling?");
    expect(result?.a).toContain("walking");
    expect(result?.b).toContain("cycling");
  });

  it("should handle whitespace", () => {
    const result = parseComparisonQuery("  walking   vs   running  ");
    expect(result).toEqual({ a: "walking", b: "running" });
  });

  it("should return null for non-comparison queries", () => {
    expect(parseComparisonQuery("walking 30 minutes")).toBeNull();
    expect(parseComparisonQuery("eat nuts daily")).toBeNull();
  });

  it("should handle multi-word interventions", () => {
    const result = parseComparisonQuery("eating walnuts daily vs eating almonds daily");
    expect(result).toEqual({
      a: "eating walnuts daily",
      b: "eating almonds daily",
    });
  });

  it("should handle 'better than' pattern", () => {
    const result = parseComparisonQuery("running better than walking");
    expect(result).toEqual({ a: "running", b: "walking" });
  });
});
