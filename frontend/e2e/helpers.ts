import { expect, type Page } from "@playwright/test";

export const PASSWORD = "password123";

export function uniqueEmail(): string {
  return `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

export async function registerInUi(page: Page): Promise<string> {
  const email = uniqueEmail();
  await page.goto("/login");
  await page.getByRole("tab", { name: "Register" }).click();
  await page.locator("#register-email").fill(email);
  await page.locator("#register-password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/history$/);
  return email;
}

/** Pastes a contract on New Analysis and waits for the analysis to finish. */
export async function pasteContract(page: Page, text: string, title: string) {
  await page.getByRole("navigation").getByRole("link", { name: "New Analysis" }).click();
  await page.getByRole("tab", { name: "Paste text" }).click();
  await page.getByPlaceholder("Paste the contract text here…").fill(text);
  await page.locator("#title").fill(title);
  await page.getByRole("button", { name: "Analyze contract" }).click();
  await expect(page).toHaveURL(/\/contracts\/[0-9a-f-]{36}$/);
  // The page polls every 2 s while the analysis runs.
  await expect(page.getByRole("heading", { name: "Findings" })).toBeVisible({ timeout: 60_000 });
}
