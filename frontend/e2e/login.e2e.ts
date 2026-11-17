import { expect, test } from "@playwright/test";

import { registerInUi } from "./helpers";

// docs/spec.md "Login copy": a first visit opens Register and says what you get and what the email is for.
const VALUE_LINE =
  "Find the risky clauses in a client's contract, with exact quotes, suggested wording and a ready email to your client. Free to try.";
const EMAIL_NOTE =
  "Your email is used only to sign in, and to tell you about Pro if you join its waitlist. No newsletter.";

const selected = (name: string) => ({ name, selected: true });

test("a first visit opens Register with the value line and the email note", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("tab", selected("Register"))).toBeVisible();
  await expect(page.getByTestId("login-value")).toHaveText(VALUE_LINE);
  await expect(page.getByTestId("email-note")).toHaveText(EMAIL_NOTE);
  await expect(page.getByRole("link", { name: "See a sample analysis" })).toBeVisible();
});

test("?tab=login and the sample's Log in link open the Login tab", async ({ page }) => {
  await page.goto("/login?tab=login");
  await expect(page.getByRole("tab", selected("Login"))).toBeVisible();
  await expect(page.getByTestId("email-note")).toHaveCount(0);

  await page.goto("/sample/net-90");
  await page.getByRole("link", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/login\?tab=login$/);
  await expect(page.getByRole("tab", selected("Login"))).toBeVisible();
});

test("a signed-in user is not shown the login page", async ({ page }) => {
  await registerInUi(page);
  await page.goto("/login");
  await expect(page).toHaveURL(/\/history$/);
});
