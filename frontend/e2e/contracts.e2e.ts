import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000";
const PASSWORD = "password123";

// English, so language detection accepts it; the stub analyzer finds several risks in it.
const CONTRACT_TEXT = [
  "This Statement of Work is between Client and Freelancer.",
  "The Freelancer will design and build a marketing website.",
  "The Client may request additional revisions at any time at no extra cost.",
  "Payment is due within 90 days after final acceptance.",
  "The Freelancer assigns all intellectual property upon delivery.",
  "Either party may terminate this agreement with seven days written notice.",
].join(" ");

function uniqueEmail(): string {
  return `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function registerInUi(page: Page): Promise<string> {
  const email = uniqueEmail();
  await page.goto("/login");
  await page.getByRole("tab", { name: "Register" }).click();
  await page.locator("#register-email").fill(email);
  await page.locator("#register-password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/history$/);
  return email;
}

async function contractOfAnotherUser(request: APIRequestContext): Promise<string> {
  const auth = await request.post(`${API_URL}/auth/register`, {
    data: { email: uniqueEmail(), password: PASSWORD },
  });
  expect(auth.ok()).toBeTruthy();
  const { access_token } = await auth.json();
  const created = await request.post(`${API_URL}/contracts`, {
    headers: { Authorization: `Bearer ${access_token}` },
    multipart: { text: CONTRACT_TEXT, title: "Someone else's contract" },
  });
  expect(created.status()).toBe(202);
  return (await created.json()).id;
}

test("a new user pastes a contract and gets findings and a client email", async ({ page }) => {
  await registerInUi(page);

  await page.getByRole("navigation").getByRole("link", { name: "New Analysis" }).click();
  await page.getByRole("tab", { name: "Paste text" }).click();
  await page.getByPlaceholder("Paste the contract text here…").fill(CONTRACT_TEXT);
  await page.locator("#title").fill("E2E website SOW");
  await page.getByRole("button", { name: "Analyze contract" }).click();

  await expect(page).toHaveURL(/\/contracts\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { name: "E2E website SOW" })).toBeVisible();
  // The page polls every 2 s while the analysis runs.
  await expect(page.getByRole("heading", { name: "Findings" })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("heading", { name: "Client email" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Copy to Clipboard" })).toBeVisible();

  // A deep link survives a full reload (SPA fallback on the static host).
  await page.reload();
  await expect(page.getByRole("heading", { name: "Findings" })).toBeVisible();
});

test("another user's contract shows the not-found state", async ({ page, request }) => {
  const contractId = await contractOfAnotherUser(request);
  await registerInUi(page);

  await page.goto(`/contracts/${contractId}`);
  await expect(page.getByText("Contract not found.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Back to history" })).toBeVisible();
});

test("logout clears the session", async ({ page }) => {
  await registerInUi(page);

  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect(await page.evaluate(() => window.localStorage.getItem("asc_access_token"))).toBeNull();

  await page.goto("/history");
  await expect(page).toHaveURL(/\/login$/);
});
