import { expect, test } from "@playwright/test";
import { need, sandboxOnly, walker } from "./sandbox";
import { backToMine, placeCut, toTheirDiagram, username } from "./setup";

// Patrick putting a cut on the agenda from the agenda screen: its button goes
// to the Diagrams page, someone's diagram opens with selecting a cut on, and
// placing it returns to the agenda. INVITE_TABLE must be an admin, and the
// sandbox must hold the many-sittings fixture family.

test.describe(() => {
  sandboxOnly("table");

  // R-0629, R-0631
  test("a cut selected in someone's chat goes on the agenda", async ({ page }, info) => {
    const { check, shot, gates, quiet } = walker(page, info);
    const stored: number[] = [];
    page.on("response", (r) => {
      if (r.request().method() === "POST" && /\/cuts$/.test(r.url()))
        stored.push(r.status());
    });

    await page.goto(need("table"), { waitUntil: "networkidle" });
    await page.locator("#account").click();
    await page.locator(".sn-pane.in .sn-row", { hasText: "Next meeting" }).click();
    await expect(page.locator("#agenda-screen")).toBeVisible();

    const before = await page.locator(".tb-cut").count();
    await toTheirDiagram(page, username("sittings"));
    await gates("selecting the cut");
    await shot("1-cut");

    await placeCut(page);
    await expect(page.locator("#agenda-screen")).toBeVisible();
    await expect(page.locator(".tb-cut")).toHaveCount(before + 1);
    check(stored.join() === "201", `one new cut was stored (${stored.join(", ")})`);
    await expect(page.locator(".tb-when").first()).toBeVisible();
    check(
      (await page.locator(".tb-when").first().evaluate((el) => el.nextElementSibling?.className)) === "sn-hd",
      "the meeting date is a field above the list, not a row in it",
    );
    check(
      (await page.locator(".tb-cut ~ .tb-when, .tb-cut .tb-when").count()) === 0,
      "the list holds cuts only",
    );
    await gates("the agenda");
    await shot("2-agenda");

    // Taken back off, so the fixtures can be installed again over this record.
    await page.locator(".tb-cut").last().locator(".pl-btn").click();
    await page.locator(".ag.cf-sheet button", { hasText: "Take it off" }).click();
    await expect(page.locator(".tb-cut")).toHaveCount(before);
    await backToMine(page);
    await quiet();
  });
});
