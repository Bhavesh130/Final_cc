import { expect, test } from "@playwright/test";

// These run against a live FinAlly instance (see test/README.md). The app
// should be started with LLM_MOCK=true for the deterministic chat scenario.

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("FinAlly", { exact: false }).first()).toBeVisible();
});

test("fresh start shows the default watchlist, cash, and streaming prices", async ({
  page,
}) => {
  // Default watchlist of 10 tickers.
  await expect(page.getByRole("cell", { name: "AAPL", exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "NVDA", exact: true })).toBeVisible();

  // Starting cash.
  await expect(page.getByText("$10,000.00").first()).toBeVisible();

  // Prices stream in: connection indicator reaches "Live".
  await expect(page.getByText("Live", { exact: true })).toBeVisible({ timeout: 15_000 });
});

test("add and remove a ticker", async ({ page }) => {
  await page.getByLabel("Add ticker").fill("PYPL");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await expect(page.getByRole("cell", { name: "PYPL", exact: true })).toBeVisible();

  const row = page.getByRole("row", { name: /PYPL/ });
  await row.hover();
  await row.getByRole("button", { name: "Remove PYPL" }).click();
  await expect(page.getByRole("cell", { name: "PYPL", exact: true })).toHaveCount(0);
});

test("buying shares updates cash and creates a position", async ({ page }) => {
  await page.getByLabel("Trade ticker").fill("AAPL");
  await page.getByLabel("Trade quantity").fill("3");
  await page.getByRole("button", { name: "Buy", exact: true }).click();

  // Position appears in the positions table.
  await expect(
    page.getByRole("cell", { name: "AAPL", exact: true }).last()
  ).toBeVisible();
  // Cash is no longer the full starting balance somewhere in the header.
  await expect(page.getByText(/Bought 3 AAPL/)).toBeVisible();
});

test("AI chat (mock) responds and executes an inline trade", async ({ page }) => {
  await page.getByLabel("Chat message").fill("buy 2 MSFT");
  await page.getByRole("button", { name: "Send" }).click();

  // Assistant reply bubble.
  await expect(page.getByText(/\[mock\]/).first()).toBeVisible({ timeout: 15_000 });
  // Inline trade confirmation (the ✓ confirmation line, not the echoed message).
  await expect(page.getByText(/✓ buy 2 MSFT/i)).toBeVisible();
  // Position shows up.
  await expect(
    page.getByRole("cell", { name: "MSFT", exact: true }).last()
  ).toBeVisible();
});
