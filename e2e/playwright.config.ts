import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  timeout: 6 * 60_000,
  expect: { timeout: 20_000 },
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  outputDir: "resultados",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: "http://localhost:18088",
    // CANAL=msedge o chrome: usa el navegador instalado en lugar del que descarga Playwright.
    channel: process.env.CANAL || undefined,
    locale: "es-CO",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    // Sin service worker: cada corrida ve la versión recién construida.
    serviceWorkers: "block",
  },
});
