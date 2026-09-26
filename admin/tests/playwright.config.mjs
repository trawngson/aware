import { defineConfig } from "@playwright/test";

// Serves admin/ as static files and runs the tests in Chromium. The page's
// config and data come from the local Supabase stack (see admin.spec.mjs).
// CHROMIUM_PATH picks a preinstalled browser instead of Playwright's own.
export default defineConfig({
  testDir: ".",
  timeout: 60_000,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4173",
    launchOptions: process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
  },
  webServer: {
    command: "python3 -m http.server 4173 --bind 127.0.0.1 --directory ..",
    url: "http://127.0.0.1:4173/index.html",
    reuseExistingServer: true,
  },
});
