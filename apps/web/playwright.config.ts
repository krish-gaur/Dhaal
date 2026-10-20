import { defineConfig } from "@playwright/test";

/**
 * Boots the whole stack (API on :8000 + web on :3000) via the repo's dev
 * script, unless WEB_URL is provided (e.g. pointing at a running stack).
 */
export default defineConfig({
  testDir: "../../e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: process.env.WEB_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
  },
  webServer: process.env.WEB_URL
    ? undefined
    : {
        command: "pnpm --dir ../.. dev",
        url: "http://localhost:3000",
        reuseExistingServer: true,
        timeout: 180_000,
      },
});
