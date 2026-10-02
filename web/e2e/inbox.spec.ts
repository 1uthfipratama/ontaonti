import { expect, test, type Page } from "@playwright/test";

async function login(page: Page) {
  const email = process.env.E2E_EMAIL;
  const password = process.env.E2E_PASSWORD;
  test.skip(!email || !password, "set E2E_EMAIL / E2E_PASSWORD (or ADMIN_* in ../.env)");
  await page.goto("/login");
  await page.getByLabel("Email").fill(email!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/inbox/);
}

test("login lands on the inbox with the prototype banner", async ({ page }) => {
  await login(page);
  await expect(page.getByTestId("prototype-banner")).toContainText("Prototype — test data only");
  await expect(page.getByLabel("Channel")).toBeVisible();
});

test("simulator message gets a bot reply and shows up in the inbox", async ({ page }) => {
  await login(page);
  await page.goto("/simulator");
  const user = `e2e${Date.now()}`;
  await page.getByTestId("sim-user").fill(user);
  await page.getByLabel("Display name").fill(`E2E ${user}`);
  await page.getByTestId("sim-input").fill("Halo kak, berapa lama pengobatan TBC?");
  await page.getByTestId("sim-send").click();

  await expect(page.getByTestId("sim-user-msg")).toHaveCount(1);
  // First contact: the consent notice, then the answer (or the fixed fallback
  // reply when no LLM is reachable). Both are bot messages, delivered live (SSE).
  await expect(page.getByTestId("sim-reply-bot")).toHaveCount(2);
  await expect(page.getByTestId("sim-reply-bot").first()).toContainText("Onti Erlani");

  await page.getByRole("link", { name: "Open in inbox →" }).click();
  await expect(page.getByTestId("thread-title")).toContainText(user);
  await expect(page.getByTestId("bubble-user")).toHaveCount(1);
  await expect(page.getByTestId("bubble-bot")).toHaveCount(2);
});

test("an emergency message gets the fixed safety reply and opens a case", async ({ page }) => {
  await login(page);
  await page.goto("/simulator");
  await page.getByTestId("sim-user").fill(`e2e-sos${Date.now()}`);
  await page.getByTestId("sim-input").fill("Saya batuk darah banyak dan sesak napas berat");
  await page.getByTestId("sim-send").click();
  await expect(page.getByTestId("sim-reply-bot").last()).toContainText("hubungi 119");
  await page.goto("/cases");
  await expect(page.getByTestId("case-list")).toContainText(/emergency/i);
});
