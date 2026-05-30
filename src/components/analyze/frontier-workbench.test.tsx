import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent, within } from "@testing-library/react";
import { FrontierWorkbench } from "@/components/analyze/frontier-workbench";
import type { FrontierItem, FrontierResponse } from "@/lib/frontier-types";

function makeItem(overrides: Partial<FrontierItem>): FrontierItem {
  return {
    id: "item",
    name: "Item",
    category: "sleep",
    display_category: "behavioral",
    public_lane: "consumer_public",
    annual_cost: 0,
    total_cost: 0,
    cost_per_qaly: null,
    total_qaly: 0.12,
    days: 43.8,
    p_benefit: 0.68,
    p_harm: 0.04,
    mort_qaly: 0.1,
    harm_qaly: 0,
    qol_qaly: 0.02,
    sleep_qol_qaly: 0.02,
    profile_effect_multiplier: 1,
    airway_effect_multiplier: 1,
    sleep_mortality_hr_multiplier: 1,
    sleep_mortality_relief_fraction: 0,
    interaction_tags: [],
    benefit_tags: ["sleep"],
    notes: "",
    sources: [],
    selected_in_frontier: false,
    pricing_status: "free",
    rankability_reason: null,
    access: {
      tier: "behavioral",
      coverage_outlook: "na",
      friction: "low",
      notes: "",
    },
    ...overrides,
  };
}

function makeResponse(items: FrontierItem[]): FrontierResponse {
  return {
    meta: {
      selection_mode: "ordered_by_marginal_cost_per_qaly",
      analyzed_count: items.length,
      positive_count: items.length,
      qaly_discount_rate: 0,
      cost_discount_rate: 0,
      n_simulations: 5000,
      rankable_count: items.length,
      profile: {
        age: 39,
        sex: "male",
        bmi_category: "normal",
        smoking_status: "never",
        has_diabetes: false,
        has_hypertension: false,
        activity_level: "active",
      },
    },
    sleep_estimate: null,
    public_policy: { lanes: [], conditions: [], items: [] },
    frontier: [],
    items,
    decision_states: [],
    decision_sequence: [],
  };
}

function mockFetchOnce(response: FrontierResponse) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => response,
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function runAndAwaitResults(response: FrontierResponse) {
  mockFetchOnce(response);
  render(<FrontierWorkbench />);
  fireEvent.click(screen.getByRole("button", { name: /run live analysis/i }));
  // Wait for the results region to appear (catalog results header).
  await screen.findByText(/standalone intervention library/i);
}

/** The catalog table is the one whose header row contains "Intervention". */
function getCatalogTable(): HTMLElement {
  const tables = screen.getAllByRole("table");
  const catalog = tables.find((table) =>
    within(table).queryByText("Intervention")
  );
  if (!catalog) {
    throw new Error("Catalog table not found");
  }
  return catalog;
}

function getCatalogRow(itemName: string): HTMLElement {
  const row = within(getCatalogTable()).getByText(itemName).closest("tr");
  if (!row) {
    throw new Error(`Catalog row for "${itemName}" not found`);
  }
  return row;
}

describe("FrontierWorkbench", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows the medical disclaimer", async () => {
    await runAndAwaitResults(makeResponse([makeItem({ id: "a", name: "Head elevation" })]));
    expect(
      screen.getAllByText(/statistical estimates, not medical advice/i).length
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/consult a healthcare professional before acting/i).length
    ).toBeGreaterThan(0);
  });

  it("renders the confidence interval next to the selected point estimate", async () => {
    const item = makeItem({
      id: "stat",
      name: "Low-dose statin",
      total_qaly: 0.12,
      net_qaly_ci: [0.02, 0.21],
      days: 84.2,
      net_days_ci: [78.4, 91.1],
      selected_in_frontier: true,
    });
    await runAndAwaitResults(makeResponse([item]));

    // Select the item (via the catalog row) to open the detail panel.
    fireEvent.click(within(getCatalogRow("Low-dose statin")).getByText("Low-dose statin"));

    // Standalone effect with a day-range, rounded to whole days (84, not 84.2).
    expect(screen.getByText(/84\s*\(range 78\s*[–-]\s*91\)/i)).toBeInTheDocument();
    // QALY point estimate with its range.
    expect(
      screen.getByText(/\+0\.12 QALYs\s*\(0\.02\s*[–-]\s*0\.21\)/i)
    ).toBeInTheDocument();
  });

  it("renders a prescription badge on rx rows and detail, but not on non-rx items", async () => {
    const rxItem = makeItem({
      id: "rx_statin",
      name: "Rosuvastatin",
      display_category: "rx",
      selected_in_frontier: true,
    });
    const otcItem = makeItem({
      id: "otc_melatonin",
      name: "Melatonin",
      display_category: "supplement",
    });
    await runAndAwaitResults(makeResponse([rxItem, otcItem]));

    // The catalog table row for the rx item carries the badge.
    const rxRow = getCatalogRow("Rosuvastatin");
    expect(
      within(rxRow).getByText(/prescription\s*[—-]\s*consult a clinician/i)
    ).toBeInTheDocument();

    // The non-rx row does not.
    const otcRow = getCatalogRow("Melatonin");
    expect(
      within(otcRow).queryByText(/prescription\s*[—-]\s*consult a clinician/i)
    ).toBeNull();

    // Selecting the rx item surfaces the badge in the detail panel too.
    fireEvent.click(within(rxRow).getByText("Rosuvastatin"));
    const badges = screen.getAllByText(/prescription\s*[—-]\s*consult a clinician/i);
    expect(badges.length).toBeGreaterThanOrEqual(2);
  });
});
