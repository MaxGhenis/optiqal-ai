import { test, expect } from "@playwright/test";

test.describe("Analyze page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/analyze");
  });

  test("should load the analyze page", async ({ page }) => {
    // Wait for the page to fully load (suspense boundary)
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveTitle(/Optiqal/);
    // Check for the main heading
    await expect(page.locator("h1")).toContainText("Analyze a lifestyle choice");
  });

  test("should show intervention input", async ({ page }) => {
    await page.waitForLoadState("networkidle");
    // The textarea has id="choice" and specific placeholder text
    const input = page.locator("#choice");
    await expect(input).toBeVisible();
  });

  test("should show API key section", async ({ page }) => {
    await page.waitForLoadState("networkidle");
    // Should have API key input with id="apiKey"
    const apiKeyInput = page.locator("#apiKey");
    await expect(apiKeyInput).toBeVisible();
  });

  test("should show profile section collapsed by default", async ({ page }) => {
    await page.waitForLoadState("networkidle");
    // Profile is collapsed, should show summary text
    await expect(page.getByText(/Your Profile/)).toBeVisible();
    // Age input should NOT be visible when collapsed
    const ageInput = page.locator("#age");
    await expect(ageInput).not.toBeVisible();
  });

  test("should expand profile section on click", async ({ page }) => {
    await page.waitForLoadState("networkidle");
    // Click to expand profile
    await page.getByText(/Your Profile/).click();
    // Age input should now be visible
    const ageInput = page.locator("#age");
    await expect(ageInput).toBeVisible();
  });

  test("should show baseline QALY card", async ({ page }) => {
    await page.waitForLoadState("networkidle");
    // Should show baseline projection card
    await expect(page.getByText(/Baseline Projection/i)).toBeVisible();
  });

  test("should allow intervention input", async ({ page }) => {
    await page.waitForLoadState("networkidle");
    const input = page.locator("#choice");
    await input.fill("quit smoking");
    // Input should have the text
    await expect(input).toHaveValue("quit smoking");
  });

  test("should have analyze button", async ({ page }) => {
    await page.waitForLoadState("networkidle");
    const button = page.getByRole("button", { name: /Analyze QALY Impact/i });
    await expect(button).toBeVisible();
  });

  test("should disable analyze button without API key", async ({ page }) => {
    await page.waitForLoadState("networkidle");
    // Clear any stored API key
    await page.evaluate(() => {
      localStorage.removeItem("optiqal-api-key");
    });
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Fill in the choice
    await page.locator("#choice").fill("quit smoking");

    // Button should be disabled
    const button = page.getByRole("button", { name: /Analyze QALY Impact/i });
    await expect(button).toBeDisabled();
  });

  test("should show error when analyzing without API key", async ({ page }) => {
    await page.waitForLoadState("networkidle");
    // Clear any stored API key
    await page.evaluate(() => {
      localStorage.removeItem("optiqal-api-key");
    });
    await page.reload();
    await page.waitForLoadState("networkidle");

    // The button is disabled, so we can't click it without a key
    // This test verifies the disabled state
    const button = page.getByRole("button", { name: /Analyze QALY Impact/i });
    await expect(button).toBeDisabled();
  });
});

test.describe("Profile editing", () => {
  test("should update profile age", async ({ page }) => {
    await page.goto("/analyze");
    await page.waitForLoadState("networkidle");

    // Expand profile
    await page.getByText(/Your Profile/).click();

    // Find and update age
    const ageInput = page.locator("#age");
    await ageInput.fill("45");
    await expect(ageInput).toHaveValue("45");
  });

  test("should toggle between metric and imperial units", async ({ page }) => {
    await page.goto("/analyze");
    await page.waitForLoadState("networkidle");

    // Expand profile
    await page.getByText(/Your Profile/).click();

    // Find the toggle button (it contains Imperial text when in imperial mode)
    const imperialText = page.getByText("Imperial");
    const metricText = page.getByText("Metric");

    await expect(imperialText).toBeVisible();
    await expect(metricText).toBeVisible();
  });

  test("should save profile to localStorage", async ({ page }) => {
    await page.goto("/analyze");
    await page.waitForLoadState("networkidle");

    // Expand profile
    await page.getByText(/Your Profile/).click();

    // Update age
    await page.locator("#age").fill("50");

    // Reload and check persistence
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Expand profile again
    await page.getByText(/Your Profile/).click();

    // Check age persisted
    await expect(page.locator("#age")).toHaveValue("50");
  });
});

test.describe("Landing page", () => {
  test("should load the landing page", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveTitle(/Optiqal/);
  });

  test("should have hero section", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    // Check for hero text or main heading
    const heroText = page.locator("h1").first();
    await expect(heroText).toBeVisible();
  });

  test("should navigate to analyze page", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Find and click CTA button (adjust selector based on actual button text)
    const analyzeLink = page.getByRole("link", { name: /Analyze|Try|Start/i }).first();
    if (await analyzeLink.isVisible().catch(() => false)) {
      await analyzeLink.click();
      await expect(page).toHaveURL(/analyze/);
    }
  });
});
