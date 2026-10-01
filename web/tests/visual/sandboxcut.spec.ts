import { expect, test } from "@playwright/test";
import { need, sandboxOnly, walker } from "./sandbox";

// Patrick placing a cut on a family's whole thread: every sitting in one
// scroll with the chat's line between sittings, a row of the sittings that
// jumps to each, and a cut whose first and last lines sit on either side of a
// line between sittings. INVITE_TABLE must be an admin, and the sandbox must
// hold the many-sittings fixture family, whose sittings each open with "I keep
// coming back to".

test.describe(() => {
  sandboxOnly("table");

  // R-0267, R-0296
  test("a cut runs across a line between sittings of one thread", async ({ page }, info) => {
    const { check, gates, quiet } = walker(page, info);

    await page.goto(need("table"), { waitUntil: "networkidle" });
    await page.locator("#account").click();
    await page.locator(".sn-pane.in .sn-row", { hasText: "Next meeting" }).click();
    await page.locator(".tb-add").click();
    await page.locator(".tb-words").fill("keep coming back to Dad's drinking");
    await page.locator(".tb-pick", { hasText: "FD-362 visual fixture" }).first().click();
    await expect(page.locator("#cut-screen")).toBeVisible();

    const dividers = page.locator("#cut-chat .sitting");
    const jumps = page.locator("#cut-jump .ct-to");
    const many = await dividers.count();
    check(many > 2, `the whole thread is one scroll with a line per sitting (${many})`);
    check((await jumps.count()) === many, "one jump per sitting");

    await jumps.nth(3).click();
    const gap = await page.evaluate(
      (at) => {
        const list = document.getElementById("cut-chat")!;
        const line = list.querySelectorAll(".sitting")[at];
        return line.getBoundingClientRect().top - list.getBoundingClientRect().top;
      },
      3,
    );
    check(Math.abs(gap) < 4, `the jump brings that sitting's line to the top (${gap}px)`);

    // The last line of the second sitting, then the second line of the third.
    const third = dividers.nth(2);
    await third.scrollIntoViewIfNeeded();
    await third.locator("xpath=preceding-sibling::div[contains(@class,'bub')][1]").click();
    await third.locator("xpath=following-sibling::div[contains(@class,'bub')][2]").click();
    const lit = page.locator("#cut-chat .bub.line.lit");
    await expect(lit).toHaveCount(3);
    const across = await page.evaluate(() => {
      const lit = [...document.querySelectorAll("#cut-chat .bub.line.lit")];
      const line = document.querySelectorAll("#cut-chat .sitting")[2];
      return (
        !!(lit[0].compareDocumentPosition(line) & Node.DOCUMENT_POSITION_FOLLOWING) &&
        !!(line.compareDocumentPosition(lit[1]) & Node.DOCUMENT_POSITION_FOLLOWING)
      );
    });
    check(across, "the lit lines sit on both sides of the line between sittings");
    await gates("a cut across sittings");
    if (info.project.name === "sandbox-phone" && process.env.CUT_SHOT)
      await page.screenshot({ path: process.env.CUT_SHOT });

    const [stored] = await Promise.all([
      page.waitForResponse((r) => r.request().method() === "POST" && /\/cuts$/.test(r.url())),
      page.locator(".ct-go").click(),
    ]);
    check(stored.status() === 201, `the cut was stored (${stored.status()})`);
    const cut = await stored.json();
    check(cut.start_statement_id !== cut.end_statement_id, "the cut holds both ends");
    await expect(page.locator(`.tb-cut[data-discussion="${cut.sitting_id}"]`)).toBeVisible();

    // Taken back off, so the fixtures can be installed again over this record.
    const row = page.locator(`.tb-cut[data-discussion="${cut.sitting_id}"]`);
    await row.locator(".pl-btn").click();
    await quiet();
  });
});
