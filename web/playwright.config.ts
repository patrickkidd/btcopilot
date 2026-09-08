import { defineConfig, devices } from "@playwright/test";

/** Visual goldens for the companion page. They run against a sandbox server the
 * developer starts (see web/tests/visual/README.md) and against the fixture
 * records `python -m btcopilot.companion.fixtures` installs, so a golden only
 * changes when the page changes.
 *
 * Headless Chromium at the two sizes the page is designed for: a phone at
 * 390x844 and a desktop window at 1280x800. */

export default defineConfig({
  testDir: "./tests/visual",
  globalSetup: "./tests/visual/setup.ts",
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  timeout: 60_000,
  expect: {
    toHaveScreenshot: {
      // fonts and antialiasing move a few pixels between machines
      maxDiffPixelRatio: 0.01,
      animations: "disabled",
    },
  },
  use: {
    baseURL: process.env.COMPANION_URL ?? "http://127.0.0.1:8889",
    colorScheme: "light",
    deviceScaleFactor: 2,
  },
  projects: [
    {
      name: "phone",
      use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 } },
    },
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
    },
  ],
});
