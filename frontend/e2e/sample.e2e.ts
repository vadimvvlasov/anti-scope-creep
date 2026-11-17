import { expect, test, type Page } from "@playwright/test";

// The guest sample (docs/spec.md "Guest sample"): a signed-out visitor sees a real analysis, downloads its
// reports, and the page calls no API except the analytics endpoint.
const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000";
const LABEL = "Sample: synthetic contract, analysed by openai/gpt-oss-120b, prompt v6, 2026-10-16";

/** Paths of every request the page sends to the API origin. */
function recordApiCalls(page: Page): string[] {
  const paths: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.origin === new URL(API_URL).origin) paths.push(url.pathname);
  });
  return paths;
}

for (const viewport of [
  { name: "desktop", width: 1280, height: 900 },
  { name: "390 px", width: 390, height: 844 },
]) {
  test(`a guest opens the sample without an API call (${viewport.name})`, async ({
    page,
    request,
  }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    const apiCalls = recordApiCalls(page);

    await page.goto("/login");
    await page.getByRole("link", { name: "See a sample analysis" }).click();
    await expect(page).toHaveURL(/\/sample\/net-90$/);

    await expect(page.getByTestId("sample-label")).toHaveText(LABEL);
    await expect(
      page.getByRole("heading", { name: "Software development agreement" }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: "Findings" })).toBeVisible();
    // Both Net 90 findings are highlighted in the contract text.
    await expect(
      page.getByRole("region", { name: "Contract text" }).getByRole("button", {
        name: "Long / unfavorable payment terms, high risk",
      }),
    ).toHaveCount(2);
    await expect(page.getByText("Anti-Scope Creep uses automated AI analysis")).toBeVisible();
    await expect(page.getByRole("button", { name: "Retry Analysis" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Delete/ })).toHaveCount(0);

    for (const extension of ["pdf", "docx"]) {
      const link = page.getByRole("link", { name: `Download ${extension.toUpperCase()}` });
      const href = await link.getAttribute("href");
      const file = await request.get(href!);
      expect(file.ok()).toBe(true);
      const magic = extension === "pdf" ? "%PDF" : "PK";
      expect((await file.body()).subarray(0, magic.length).toString("latin1")).toBe(magic);
    }

    await page
      .getByTestId("sample-cta")
      .getByRole("link", { name: "Create a free account" })
      .click();
    await expect(page).toHaveURL(/\/login\?tab=register$/);
    await expect(page.getByRole("tab", { name: "Register" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    expect(apiCalls.filter((path) => path !== "/events")).toEqual([]);
  });
}

test("the clean sample has no findings and an unknown sample says so", async ({ page }) => {
  await page.goto("/sample/clean");
  await expect(page.getByTestId("sample-label")).toBeVisible();
  await expect(page.getByText("No high-risk clauses detected")).toBeVisible();

  await page.goto("/sample/nope");
  await expect(page.getByText("This sample does not exist.")).toBeVisible();
});
