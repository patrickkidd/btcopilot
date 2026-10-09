import { expect, test, type Page } from "./fixtures";
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

/** A new auditor, already told of their task the way dating a cut does: the
 * id of that notification, and their sign-in link as a path on whichever
 * address the run reaches the sandbox by. */
function newAuditor(): { path: string; notification: number } {
  const [told, link] = execSync(
    `. "${process.env.SANDBOX_ENV}" && uv run python ${ROOT}/btcopilot/tests/frontend/seedauditor.py`,
    { shell: "/bin/bash", cwd: process.env.FIXTURE_CWD ?? ROOT },
  )
    .toString()
    .trim()
    .split("\n")
    .slice(-2);
  return {
    path: new URL(link).pathname,
    notification: Number(told.split(" ")[1]),
  };
}

/** Sign in as a new auditor, and collect what the page threw so a test can
 * say there was none. */
async function signIn(
  page: Page,
): Promise<{ bad: string[]; notification: number }> {
  const bad: string[] = [];
  page.on("pageerror", (e) => bad.push(e.message));
  page.on("response", (r) => {
    if (r.status() >= 400) bad.push(`${r.status()} ${r.url()}`);
  });
  const { path, notification } = newAuditor();
  await page.goto(path, { waitUntil: "load" });
  await expect(page.locator("#task-screen")).toBeVisible();
  return { bad, notification };
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
    const { bad } = await signIn(page);
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
    const { bad } = await signIn(page);
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

  // R-0055, R-0265
  test("a tap on a coding task notification opens the task card", async ({
    page,
  }) => {
    const { bad, notification } = await signIn(page);
    await page.locator("#task-body .addbtn").click();
    await expect(page.locator("#coding-screen")).toBeVisible();
    // what the worker tells the app already open when its notification is tapped
    const opened = page.waitForResponse((r) =>
      r.url().endsWith(`/notifications/${notification}`),
    );
    await page.evaluate((id) => {
      navigator.serviceWorker.dispatchEvent(
        new MessageEvent("message", { data: { notification: id } }),
      );
    }, notification);
    expect((await opened).ok()).toBe(true);
    await expect(page.locator("#task-screen")).toBeVisible();
    await expect(page.locator("#coding-screen")).toBeHidden();
    expect(bad).toEqual([]);
  });
});
