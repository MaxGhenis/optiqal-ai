import { test, expect } from "@playwright/test";

// These cover the current server-rendered analyze/predict workbenches. The
// previous version asserted a removed bring-your-own-API-key flow (#apiKey /
// localStorage "optiqal-api-key") and an older "Analyze a lifestyle choice"
// UI; both no longer exist — estimates are computed server-side from the
// profile, with no key entry.

test.describe("Analyze page (frontier ranking)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/analyze");
    await page.waitForLoadState("networkidle");
  });

  test("loads with the ranking heading", async ({ page }) => {
    await expect(page).toHaveTitle(/Optiqal/);
    await expect(page.locator("h1")).toContainText(/Rank interventions/i);
  });

  test("does not show a bring-your-own API key input", async ({ page }) => {
    await expect(page.locator("#apiKey")).toHaveCount(0);
  });

  test("exposes the profile inputs", async ({ page }) => {
    await expect(page.locator("#age")).toBeAttached();
    await expect(page.locator("#sex")).toBeAttached();
  });

  test("accepts a profile age", async ({ page }) => {
    const age = page.locator("#age");
    await age.fill("45");
    await expect(age).toHaveValue("45");
  });
});

test.describe("Predict page (baseline projection)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/predict");
    await page.waitForLoadState("networkidle");
  });

  test("loads with the projection heading", async ({ page }) => {
    await expect(page).toHaveTitle(/Optiqal/);
    await expect(page.locator("h1")).toContainText(/Project remaining life years/i);
  });

  test("exposes profile and risk-factor inputs", async ({ page }) => {
    await expect(page.locator("#age")).toBeAttached();
    await expect(page.locator("#smoker")).toBeAttached();
    await expect(page.locator("#diabetes")).toBeAttached();
  });

  test("accepts a profile age", async ({ page }) => {
    const age = page.locator("#age");
    await age.fill("50");
    await expect(age).toHaveValue("50");
  });
});

test.describe("Landing page", () => {
  test("loads", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveTitle(/Optiqal/);
  });

  test("has a hero heading", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("h1").first()).toBeVisible();
  });

  test("links to the analyze page", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    const analyzeLink = page
      .getByRole("link", { name: /Analyze|Start analysis|Try/i })
      .first();
    await analyzeLink.click();
    await expect(page).toHaveURL(/analyze/);
  });
});

test.describe("Footer (legal discoverability)", () => {
  test("exposes Privacy and Terms on every page", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    const footer = page.getByRole("navigation", { name: /footer/i });
    await expect(footer.getByRole("link", { name: "Privacy" })).toBeVisible();
    await expect(footer.getByRole("link", { name: "Terms" })).toBeVisible();
  });
});
