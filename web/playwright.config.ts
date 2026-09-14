import { defineConfig, devices } from "@playwright/test";

/** Visual goldens for the chat page. They run against a sandbox server the
 * developer starts (see web/tests/visual/README.md) and against the fixture
 * records `python -m btcopilot.personal.routes.fixtures` installs, so a golden only
 * changes when the page changes.
 *
 * Headless Chromium at the two sizes the page is designed for: a phone at
 * 390x844 and a desktop window at 1280x800. */

/** The review walks live beside the goldens but run as their own projects. */
const SANDBOX = "**/sandbox*.spec.ts";

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
    baseURL: process.env.SANDBOX_URL ?? "http://127.0.0.1:8889",
    // A call that waits on something that never comes is a failed step, not a
    // run that sits there until the whole test's budget is gone.
    actionTimeout: 30_000,
    colorScheme: "light",
    deviceScaleFactor: 2,
  },
  projects: [
    {
      name: "phone",
      testIgnore: SANDBOX,
      use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 } },
    },
    {
      name: "desktop",
      testIgnore: SANDBOX,
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
    },
    // The review walks: journeys against a running review sandbox, in both
    // engines at phone size and in Chromium at desktop size. They skip unless
    // the sandbox and its sign-in links are named in the environment, so a
    // plain golden run never waits on them (tests/visual/sandbox.ts).
    {
      name: "sandbox-phone",
      testMatch: SANDBOX,
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 393, height: 852 },
        ignoreHTTPSErrors: true,
      },
    },
    {
      name: "sandbox-webkit",
      testMatch: SANDBOX,
      use: {
        ...devices["Desktop Safari"],
        viewport: { width: 393, height: 852 },
        ignoreHTTPSErrors: true,
      },
    },
    {
      name: "sandbox-desktop",
      testMatch: SANDBOX,
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 800 },
        ignoreHTTPSErrors: true,
      },
    },
  ],
});
