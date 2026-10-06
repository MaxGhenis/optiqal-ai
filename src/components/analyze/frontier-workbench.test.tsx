import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { StrictMode } from "react";
import {
  cleanup,
  render,
  screen,
  fireEvent,
  act,
  waitFor,
  within,
} from "@testing-library/react";
import { FrontierWorkbench } from "@/components/analyze/frontier-workbench";
import type {
  FrontierItem,
  FrontierResponse,
  FrontierStep,
} from "@/lib/frontier-types";
import { DEFAULT_PROFILE } from "@/types";

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

function makeResponse(
  items: FrontierItem[],
  frontier: FrontierStep[] = []
): FrontierResponse {
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
    frontier,
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
  fireEvent.click(screen.getByRole("button", { name: /rank my options/i }));
  await screen.findByText(/marginal cost-effectiveness order/i);
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
    expect(screen.getByRole("status")).toHaveTextContent(/ranking complete/i);
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

    expect(screen.getAllByText(/\+84 days/i).length).toBeGreaterThan(0);
    expect(
      screen.getByText(/80% model interval 78 days\s*[–-]\s*91 days/i)
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
      within(rxRow).getByText(/prescription\s*[—-]\s*ask a clinician/i)
    ).toBeInTheDocument();

    // The non-rx row does not.
    const otcRow = getCatalogRow("Melatonin");
    expect(
      within(otcRow).queryByText(/prescription\s*[—-]\s*ask a clinician/i)
    ).toBeNull();

    // Selecting the rx item surfaces the badge in the detail panel too.
    fireEvent.click(within(rxRow).getByText("Rosuvastatin"));
    const badges = screen.getAllByText(/prescription\s*[—-]\s*ask a clinician/i);
    expect(badges.length).toBeGreaterThanOrEqual(2);
  });

  it("reranks around an intervention the user already does", async () => {
    const item = makeItem({
      id: "hiit_2x_week",
      name: "HIIT 2x/week",
      selected_in_frontier: true,
    });
    const step: FrontierStep = {
      step: 1,
      added_intervention: item.id,
      added_name: item.name,
      marginal_qaly: 0.02,
      marginal_days: 7.3,
      marginal_cost_per_qaly: 0,
      marginal_cost_value: 0,
      marginal_interaction_qaly: 0,
      total_qaly: 0.02,
      total_days: 7.3,
      interaction_penalty_qaly: 0,
      interaction_penalty_days: 0,
      total_cost_value: 0,
      total_annual_cost: 0,
      selected_interventions: [item.id],
    };
    const fetchMock = mockFetchOnce(makeResponse([item], [step]));
    render(<FrontierWorkbench />);

    fireEvent.click(screen.getByRole("button", { name: /rank my options/i }));
    await screen.findByRole("button", { name: /already in my routine/i });
    fireEvent.click(screen.getByRole("button", { name: /already in my routine/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const secondRequest = fetchMock.mock.calls[1]?.[1] as RequestInit;
    expect(JSON.parse(String(secondRequest.body))).toMatchObject({
      current_stack_ids: ["hiit_2x_week"],
    });
  });

  it("replaces a mutually exclusive routine variant", async () => {
    const onceWeekly = makeItem({
      id: "hiit_1x_week",
      name: "HIIT 1x/week",
      exclusive_group: "cardio_mode",
    });
    const twiceWeekly = makeItem({
      id: "hiit_2x_week",
      name: "HIIT 2x/week",
      exclusive_group: "cardio_mode",
    });
    localStorage.setItem(
      "optiqal-current-stack-v1",
      JSON.stringify([onceWeekly.id])
    );
    const fetchMock = mockFetchOnce(makeResponse([onceWeekly, twiceWeekly]));
    render(<FrontierWorkbench />);

    fireEvent.click(screen.getByRole("button", { name: /rank my options/i }));
    await screen.findByText(/marginal cost-effectiveness order/i);
    fireEvent.click(within(getCatalogRow(twiceWeekly.name)).getByText(twiceWeekly.name));
    fireEvent.click(screen.getByRole("button", { name: /already in my routine/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const secondRequest = fetchMock.mock.calls[1]?.[1] as RequestInit;
    expect(JSON.parse(String(secondRequest.body))).toMatchObject({
      current_stack_ids: [twiceWeekly.id],
    });
  });

  it("restores the analyzed profile and sleep inputs when draft edits are closed", async () => {
    await runAndAwaitResults(makeResponse([makeItem({ id: "walk", name: "Walk daily" })]));

    fireEvent.click(screen.getByRole("button", { name: /edit profile/i }));
    fireEvent.change(screen.getByRole("spinbutton", { name: "Age" }), {
      target: { value: "45" },
    });
    fireEvent.click(screen.getByRole("button", { name: /add wearable sleep details/i }));
    fireEvent.change(screen.getByRole("spinbutton", { name: /sleep quality/i }), {
      target: { value: "80" },
    });
    fireEvent.click(screen.getByRole("button", { name: /close/i }));

    expect(screen.getByText(/ranked for a 35-year-old/i)).toBeInTheDocument();
    expect(screen.queryByText(/ranked for a 45-year-old/i)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /edit profile/i }));
    expect(screen.getByRole("spinbutton", { name: "Age" })).toHaveValue(35);
    expect(screen.getByRole("spinbutton", { name: /sleep quality/i })).toHaveValue(null);
  });

  it("prevents closing the editor while an updated ranking is in flight", async () => {
    const response = makeResponse([makeItem({ id: "walk", name: "Walk daily" })]);
    let resolveUpdate!: (value: {
      ok: boolean;
      json: () => Promise<FrontierResponse>;
    }) => void;
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => response })
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveUpdate = resolve;
          })
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<FrontierWorkbench />);

    fireEvent.click(screen.getByRole("button", { name: /rank my options/i }));
    await screen.findByText(/marginal cost-effectiveness order/i);
    fireEvent.click(screen.getByRole("button", { name: /edit profile/i }));
    fireEvent.change(screen.getByRole("spinbutton", { name: "Age" }), {
      target: { value: "45" },
    });
    fireEvent.click(screen.getByRole("button", { name: /update my ranking/i }));

    expect(screen.getByRole("button", { name: /close/i })).toBeDisabled();

    await act(async () => {
      resolveUpdate({ ok: true, json: async () => response });
    });
    await screen.findByText(/ranked for a 45-year-old/i);
  });

  it("does not commit a routine change when reranking fails", async () => {
    const item = makeItem({ id: "walk", name: "Walk daily" });
    const fetchMock = mockFetchOnce(makeResponse([item]));
    render(<FrontierWorkbench />);
    fireEvent.click(screen.getByRole("button", { name: /rank my options/i }));
    await screen.findByRole("button", { name: /already in my routine/i });

    fetchMock.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ error: "Unable to rerank" }),
    });
    fireEvent.click(screen.getByRole("button", { name: /already in my routine/i }));

    await screen.findByRole("alert");
    expect(screen.getByRole("button", { name: /already in my routine/i })).toBeInTheDocument();
    expect(localStorage.getItem("optiqal-current-stack-v1")).toBe("[]");
  });

  it("restores persisted profile and routine state in StrictMode", async () => {
    localStorage.setItem(
      "optiqal-frontier-profile-v1",
      JSON.stringify({ ...DEFAULT_PROFILE, age: 48 })
    );
    localStorage.setItem(
      "optiqal-current-stack-v1",
      JSON.stringify([" hiit_2x_week "])
    );
    localStorage.setItem(
      "optiqal-frontier-sleep-v1",
      JSON.stringify({ breathing_score: 80, duration_hours: 99, sleep_quality_score: 900 })
    );

    render(
      <StrictMode>
        <FrontierWorkbench />
      </StrictMode>
    );

    await waitFor(() =>
      expect(screen.getByRole("spinbutton", { name: "Age" })).toHaveValue(48)
    );
    expect(JSON.parse(localStorage.getItem("optiqal-frontier-profile-v1")!)).toMatchObject({
      age: 48,
    });
    expect(localStorage.getItem("optiqal-current-stack-v1")).toBe(
      '["hiit_2x_week"]'
    );
    await waitFor(() =>
      expect(JSON.parse(localStorage.getItem("optiqal-frontier-sleep-v1")!)).toEqual({
        breathing_score: 0.8,
      })
    );
  });

  it("lets the user clear a stale saved routine before analysis", async () => {
    localStorage.setItem(
      "optiqal-current-stack-v1",
      JSON.stringify(["removed_catalog_item"])
    );
    render(<FrontierWorkbench />);

    const clearButton = await screen.findByRole("button", { name: /clear routine/i });
    fireEvent.click(clearButton);

    await waitFor(() =>
      expect(localStorage.getItem("optiqal-current-stack-v1")).toBe("[]")
    );
    expect(screen.queryByRole("button", { name: /clear routine/i })).toBeNull();
  });
});
