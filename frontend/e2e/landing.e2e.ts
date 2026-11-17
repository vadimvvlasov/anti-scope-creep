import { expect, test, type Page } from "@playwright/test";

import { pasteContract, registerInUi } from "./helpers";

// The landing page at `/` (docs/spec.md "Landing page"): static HTML with the text, no API call for a
// guest, a stored session goes to Contract History, and deep links still get the app.
const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000";
const HEADING = "Find the risky clauses before you sign.";
const CONTRACT = [
  "This Services Agreement is entered into between the Client and the Contractor.",
  "Invoices are payable within 60 days of receipt.",
].join(" ");

function recordApiCalls(page: Page): string[] {
  const paths: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.origin === new URL(API_URL).origin) paths.push(url.pathname);
  });
  return paths;
}

test("the HTML of / carries the landing text and the link preview", async ({ request }) => {
  const html = await (await request.get("/")).text();
  expect(html).toContain(HEADING);
  expect(html).toContain("Six common traps in freelance contracts");
  expect(html).toMatch(/<meta property="og:image" content="[^"]*\/og-image\.png"/);
  const image = await request.get("/og-image.png");
  expect(image.ok()).toBe(true);
});

for (const viewport of [
  { name: "desktop", width: 1280, height: 900 },
  { name: "390 px", width: 390, height: 844 },
]) {
  test(`a guest sees the landing page without an API call (${viewport.name})`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    const apiCalls = recordApiCalls(page);

    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1, name: HEADING })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Your contract stays private" })).toBeVisible();
    // The list follows the analyzer (the local stack runs the stub); this line is in every variant.
    await expect(page.getByTestId("landing-privacy")).toContainText("is never stored");
    await expect(page.getByText("does not constitute professional legal advice")).toBeVisible();
    // No horizontal scroll at phone width.
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);

    await page
      .getByRole("main")
      .getByRole("link", { name: "See a sample analysis", exact: true })
      .click();
    await expect(page).toHaveURL(/\/sample\/net-90$/);
    expect(apiCalls.filter((path) => path !== "/events")).toEqual([]);
  });
}

test("the call to action opens Register", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("banner").getByRole("link", { name: "Create a free account" }).click();
  await expect(page).toHaveURL(/\/login\?tab=register$/);
  await expect(page.getByRole("tab", { name: "Register" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
});

test("a stored session goes from / to Contract History", async ({ page }) => {
  await registerInUi(page);
  await page.goto("/");
  await expect(page).toHaveURL(/\/history$/);
});

test("deep links still load the app on reload", async ({ page }) => {
  await registerInUi(page);
  await pasteContract(page, CONTRACT, "E2E deep link");
  await page.reload();
  await expect(page.getByRole("heading", { name: "Findings" })).toBeVisible();

  for (const path of ["/history", "/sample/net-90", "/login?tab=login"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: HEADING })).toHaveCount(0);
    await expect(page.locator("main, [role=tabpanel]").first()).toBeVisible();
  }
});

test("an unknown path shows Not Found, not the landing page", async ({ page }) => {
  await page.goto("/no-such-page");
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
});
