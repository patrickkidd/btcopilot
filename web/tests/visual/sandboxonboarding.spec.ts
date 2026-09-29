import { expect, test, type Page } from "@playwright/test";
import { execSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// A new auditor is walked through the work by the app itself: the task card
// says how it works until they tap Got it, and the first line they tap says
// what to do with it. Each test signs in as a new auditor seedauditor.py makes,
// so it always meets one who has seen nothing. SANDBOX_ENV names a shell file
// with the sandbox's Flask settings, and FIXTURE_CWD where its Python is.

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const HOW = "How this works";
const HINT = "Type what this line tells you happened, then send.";

/** The new auditor's sign-in link, as a path on whichever address the run
 * reaches the sandbox by. */
function newAuditor(): string {
  const link = execSync(
    `. "${process.env.SANDBOX_ENV}" && uv run python ${ROOT}/btcopilot/tests/frontend/seedauditor.py`,
    { shell: "/bin/bash", cwd: process.env.FIXTURE_CWD ?? ROOT },
  )
    .toString()
    .trim()
    .split("\n")
    .at(-1)!;
  return new URL(link).pathname;
}

/** Sign in, and collect what the page threw so a test can say there was none. */
async function signIn(page: Page): Promise<string[]> {
  const bad: string[] = [];
  page.on("pageerror", (e) => bad.push(e.message));
  page.on("response", (r) => {
    if (r.status() >= 400) bad.push(`${r.status()} ${r.url()}`);
  });
  await page.goto(newAuditor(), { waitUntil: "load" });
  await expect(page.locator("#task-screen")).toBeVisible();
  return bad;
}

const saved = (page: Page) =>
  page.waitForResponse(
    (r) => r.request().method() === "PATCH" && r.url().endsWith("/preferences"),
  );

test.describe(() => {
  test.skip(
    !process.env.SANDBOX_URL || !process.env.SANDBOX_ENV,
    "needs SANDBOX_URL and SANDBOX_ENV, the sandbox's Flask settings",
  );

  // R-0265
  test("a new auditor reads how the task works until Got it", async ({
    page,
  }) => {
    const bad = await signIn(page);
    const card = page.locator("#task-body .tkcard");
    await expect(card.getByText(HOW)).toBeVisible();
    await expect(card.locator(".cta-p")).toHaveCount(4);
    const patched = saved(page);
    await card.getByRole("button", { name: "Got it" }).click();
    await patched;
    await expect(card.getByText(HOW)).toHaveCount(0);

    await page.reload({ waitUntil: "load" });
    await expect(card.locator(".addbtn")).toBeVisible();
    await expect(card.getByText(HOW)).toHaveCount(0);
    expect(bad).toEqual([]);
  });

  // R-0270
  test("the first line a new auditor taps says what to do with it", async ({
    page,
  }) => {
    const bad = await signIn(page);
    const lines = page.locator("#coding-chat .bub.line");
    const hint = page.locator("#coding-chat .abv");
    await page.locator("#task-body .addbtn").click();
    const patched = saved(page);
    await lines.first().click();
    await patched;
    await expect(hint).toHaveText(HINT);
    await lines.nth(1).click();
    await expect(hint).toHaveCount(0);

    await page.reload({ waitUntil: "load" });
    await page.locator("#task-body .addbtn").click();
    await lines.first().click();
    await expect(lines.first()).toHaveClass(/sel/);
    await expect(hint).toHaveCount(0);
    expect(bad).toEqual([]);
  });
});
