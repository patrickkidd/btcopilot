import { expect, test } from "@playwright/test";
import { need, sandboxOnly, walker } from "./sandbox";
import { placeCut } from "./setup";

// Patrick putting a conversation on the agenda from the agenda screen: the
// list of every family's sessions it opens picks the conversation to cut,
// never the chat. INVITE_TABLE must be an admin, and some session must have
// lines in it.

test.describe(() => {
  sandboxOnly("table");

  // R-0267, R-0346
  test("a session picked from the agenda's list goes on the agenda", async ({ page }, info) => {
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

    await page.locator(".tb-add").click();
    await page.locator(".tb-pick").first().click();
    await expect(page.locator("#cut-screen")).toBeVisible();
    const session = await page.locator("#title").innerText();
    await gates("placing the cut");
    await shot("1-cut");

    await placeCut(page);
    await expect(page.locator("#agenda-screen")).toBeVisible();
    await expect(page.locator(".tb-cut .sn-t", { hasText: session })).toBeVisible();
    check(stored.join() === "201", `one new cut was stored (${stored.join(", ")})`);
    await gates("the agenda");
    await shot("2-agenda");

    // Taken back off, so the fixtures can be installed again over this record.
    const row = page.locator(".tb-cut", { hasText: session });
    await row.locator(".pl-btn").click();
    await expect(row).toHaveCount(0);
    await quiet();
  });
});
