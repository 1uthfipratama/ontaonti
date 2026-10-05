import { expect, test, type Page } from "@playwright/test";

async function login(page: Page) {
  const email = process.env.E2E_EMAIL;
  const password = process.env.E2E_PASSWORD;
  test.skip(!email || !password, "set E2E_EMAIL / E2E_PASSWORD (or ADMIN_* in ../.env)");
  await page.goto("/login");
  await page.getByLabel("Email").fill(email!);
  await page.getByLabel("Kata sandi").fill(password!);
  await page.getByRole("button", { name: "Masuk" }).click();
  await expect(page).toHaveURL(/\/inbox/);
}

test("login lands on the inbox", async ({ page }) => {
  await login(page);
  await expect(page.getByTestId("page-title")).toHaveText("Kotak masuk");
  await expect(page.getByLabel("Kanal")).toBeVisible();
});

test("simulator message gets a bot reply and shows up in the inbox", async ({ page }) => {
  await login(page);
  await page.goto("/simulator");
  const user = `e2e${Date.now()}`;
  await page.getByTestId("sim-user").fill(user);
  await page.getByLabel("Nama tampilan").fill(`E2E ${user}`);
  await page.getByTestId("sim-input").fill("Halo kak, berapa lama pengobatan TBC?");
  await page.getByTestId("sim-send").click();

  await expect(page.getByTestId("sim-user-msg")).toHaveCount(1);
  // First contact: the consent notice, then the answer (or the fixed fallback
  // reply when no LLM is reachable). Both are bot messages, delivered live (SSE).
  await expect(page.getByTestId("sim-reply-bot")).toHaveCount(2);
  await expect(page.getByTestId("sim-reply-bot").first()).toContainText("Onti Erlina");

  await page.getByRole("link", { name: "Buka di kotak masuk →" }).click();
  await expect(page.getByTestId("thread-title")).toContainText(user);
  await expect(page.getByTestId("bubble-user")).toHaveCount(1);
  await expect(page.getByTestId("bubble-bot")).toHaveCount(2);
});

test("saved reply, internal note and label in a thread", async ({ page }) => {
  await login(page);

  // A saved reply (kept between runs; the shortcut is unique).
  await page.goto("/settings?tab=replies");
  const existing = page.getByTestId("saved-reply-item").filter({ hasText: "/e2e-salam" });
  await page.waitForLoadState("networkidle");
  if ((await existing.count()) === 0) {
    await page.locator("#sr-shortcut").fill("e2e-salam");
    await page.locator("#sr-title").fill("Salam e2e");
    await page.locator("#sr-body").fill("Halo {nama}, terima kasih sudah menghubungi kami.");
    await page.getByTestId("saved-reply-save").click();
    await expect(existing).toHaveCount(1);
  }

  // A conversation that needs no LLM call: the LANGGANAN keyword.
  await page.goto("/simulator");
  const user = `e2e-tools${Date.now()}`;
  await page.getByTestId("sim-user").fill(user);
  await page.getByLabel("Nama tampilan").fill(`E2E ${user}`);
  await page.getByTestId("sim-input").fill("LANGGANAN");
  await page.getByTestId("sim-send").click();
  await expect(page.getByTestId("sim-reply-bot")).toHaveCount(2);
  await page.getByRole("link", { name: "Buka di kotak masuk →" }).click();
  await expect(page.getByTestId("thread-title")).toContainText(user);

  // "/" opens the saved replies; Enter inserts one with the contact's name filled in.
  const box = page.getByTestId("reply-box");
  await box.fill("/e2e-sal");
  await expect(page.getByTestId("saved-reply-menu")).toBeVisible();
  await box.press("Enter");
  await expect(box).toHaveValue(`Halo E2E ${user}, terima kasih sudah menghubungi kami.`);

  // An internal note is shown in the thread but never sent.
  await page.getByTestId("tab-note").click();
  await box.fill("Catatan e2e: telepon besok pagi");
  await page.getByRole("button", { name: "Simpan catatan" }).click();
  await expect(page.getByTestId("staff-note")).toContainText("telepon besok pagi");

  // Labels: create from the tag menu, shown under the contact name.
  await page.getByTestId("label-button").click();
  await page.getByTestId("label-input").fill("Uji e2e");
  await page.getByTestId("label-input").press("Enter");
  await expect(page.getByTestId("thread-title").locator("..")).toContainText("Uji e2e");
});

test("an emergency message gets the fixed safety reply and opens a case", async ({ page }) => {
  await login(page);
  await page.goto("/simulator");
  await page.getByTestId("sim-user").fill(`e2e-sos${Date.now()}`);
  await page.getByTestId("sim-input").fill("Saya batuk darah banyak dan sesak napas berat");
  await page.getByTestId("sim-send").click();
  await expect(page.getByTestId("sim-reply-bot").last()).toContainText("hubungi 119");
  await page.goto("/cases");
  await expect(page.getByTestId("case-list")).toContainText(/darurat/i);
});
