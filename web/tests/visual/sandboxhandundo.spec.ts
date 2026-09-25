import { expect, test } from "@playwright/test";
import { execSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { need, sandboxOnly } from "./sandbox";

// A hand edit made on the page, then the coach's own read of recent changes and
// its undo, run as the coach would, then the page again: the event reads as it
// did before the edit. INVITE_TURNS is the link seedturns.py prints;
// SANDBOX_ENV names a shell file that points Flask at the sandbox's database,
// and FIXTURE_CWD where the sandbox's Python environment is.

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const EVENT = 10;

test.describe(() => {
  sandboxOnly("turns");
  test.skip(!process.env.SANDBOX_ENV, "needs SANDBOX_ENV, the sandbox's Flask settings");

  // R-0084
  test("the coach sees and undoes a hand edit", async ({ page }, info) => {
    const bad: string[] = [];
    page.on("pageerror", (e) => bad.push(e.message));
    const open = page.locator("#menu-open");
    const row = page.locator(`#menu-body .row[data-event="${EVENT}"]`);
    const words = async () => (await row.innerText()).split("\n")[0].trim();

    await page.goto(need("turns"), { waitUntil: "load" });
    await page.waitForTimeout(1000);
    if (await open.isVisible().catch(() => false)) await open.click();
    const old = await words();
    await row.click();
    await page
      .locator("#menu-body .editor [data-name=description]")
      .fill(`Undo me ${info.project.name}`);
    const patch = page.waitForResponse((r) => r.request().method() === "PATCH");
    await page.locator("#menu-body .editor .save").click();
    await patch;
    await page.waitForTimeout(800);
    const out = execSync(
      `. "${process.env.SANDBOX_ENV}" && uv run python ${ROOT}/btcopilot/tests/frontend/handundo.py undo ${EVENT}`,
      // run where the sandbox's own Python environment is, as setup.ts does
      { shell: "/bin/bash", cwd: process.env.FIXTURE_CWD ?? ROOT },
    ).toString();
    console.log(`[${info.project.name}] before the edit "${old}"\n${out.trim()}`);

    await page.reload({ waitUntil: "load" });
    await page.waitForTimeout(1000);
    if (await open.isVisible().catch(() => false)) await open.click();
    expect(await words()).toBe(old);
    expect(bad).toEqual([]);
  });
});
