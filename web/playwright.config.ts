import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig, devices } from "@playwright/test";

// Runs against the running stack (docker compose up). Credentials come from
// E2E_EMAIL / E2E_PASSWORD, else from ADMIN_EMAIL / ADMIN_PASSWORD in ../.env.
function fromDotEnv(key: string): string {
  try {
    const line = readFileSync(resolve(__dirname, "../.env"), "utf8")
      .split(/\r?\n/)
      .find((l) => l.startsWith(`${key}=`));
    return line ? line.slice(key.length + 1).trim() : "";
  } catch {
    return "";
  }
}
process.env.E2E_EMAIL ||= fromDotEnv("ADMIN_EMAIL");
process.env.E2E_PASSWORD ||= fromDotEnv("ADMIN_PASSWORD");

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
