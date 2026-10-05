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
