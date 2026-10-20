import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

// Demo happy path over the synthetic fixture (Screen 1 → Screen 5).
// Three of the four fixture clauses arrive pre-verified against the PDF text;
// the apportionment clause is deliberately left unresolved, so Screen 3 must
// show the ₹14,000–₹38,667 range (point estimate ₹14,000 / insurer ₹1,06,000).
// The clause expressly exempts medicines from the deduction, so an
// all-medical-expenses reading (which would give ₹49,500) must not
// appear as the ceiling — the range only spans readings the wording
// supports.

async function startDemo(page: Page): Promise<void> {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "What are you planning for?" })).toBeVisible();
  // Sample-data mode is on by default; the banner must say so.
  await expect(page.getByText(/sample data/i).first()).toBeVisible();
  await page.getByRole("button", { name: "Start →" }).click();
  await page.waitForURL(/\/evidence\//);
}

async function confirmAllClauses(page: Page): Promise<void> {
  const rows = page.locator(".clause-row");
  await expect(rows).toHaveCount(4);
  for (let i = 0; i < 4; i++) {
    const row = rows.nth(i);
    await row.locator(".row-head").click();
    await row.getByRole("button", { name: "Confirm", exact: true }).click();
    // Status dot flips to user-confirmed; wait for the PATCH to settle.
    await page.waitForTimeout(250);
  }
  const cont = page.getByRole("button", { name: /See what you'll pay/ });
  await expect(cont).toBeEnabled({ timeout: 15_000 });
  await cont.click();
  await page.waitForURL(/\/simulate\//);
}

test("full demo flow S1→S5", async ({ page }) => {
  await startDemo(page);
  await confirmAllClauses(page);

  // Unresolved apportionment → range headline, never a single promised number.
  await expect(page.getByText("₹14,000 – ₹38,667")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("conservation-check")).toContainText("= ₹1,20,000");

  // One change at a time: room within cap → OOP ₹9,500 (non-payables only).
  await page.getByTestId("room-at-cap").click();
  await expect(page.getByText("₹9,500").first()).toBeVisible({ timeout: 15_000 });

  // The delta chip attributes the change and deep-links to the clause.
  const chip = page.getByTestId("delta-chip");
  await expect(chip).toBeVisible({ timeout: 15_000 });
  await expect(chip).toContainText("₹4,500");
  await chip.click();
  await page.waitForURL(/\/evidence\//);
  await expect(page.locator("mark").first()).toBeVisible({ timeout: 15_000 });

  await page.goBack();
  await page.waitForURL(/\/simulate\//);
  await page.getByRole("link", { name: /What to do next/ }).click();
  await page.waitForURL(/\/plan\//);

  await expect(page.getByText("Confirm your continuity credit")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/24 months/).first()).toBeVisible();
  await expect(page.getByText("₹81,333").first()).toBeVisible();

  await page.getByRole("link", { name: /View your data and delete/ }).click();
  await page.waitForURL(/\/audit\//);
  await expect(page.getByRole("heading", { name: "Clause statuses" })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("1.4.2")).toBeVisible();

  await page.getByRole("button", { name: "Delete my data" }).click();
  await page.locator("#delete-confirm").fill("DELETE");
  await page.getByRole("button", { name: "Delete permanently" }).click();
  await expect(page.getByRole("heading", { name: "Deleted" })).toBeVisible({ timeout: 15_000 });
});

test("multi-change shows message instead of delta", async ({ page }) => {
  await startDemo(page);
  await confirmAllClauses(page);
  await expect(page.getByText("₹14,000 – ₹38,667")).toBeVisible({ timeout: 15_000 });

  await page.getByTestId("room-at-cap").click();
  await page.getByTestId("continuity-off").click();
  await expect(page.getByTestId("multi-change")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("delta-chip")).toHaveCount(0);
});
