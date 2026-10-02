import { expect, test } from "@playwright/test";
import { need, sandboxOnly, walker } from "./sandbox";
import { backToMine, placeCut, toTheirDiagram, username } from "./setup";

// Patrick selecting a cut inside the chat of someone else's diagram: Next
// meeting's button lands on the Diagrams page, the diagram opens read-only
// with selecting already on, the first tap rings one line, the second rings
// every line between across the line between sittings and fades what comes
// after, and placing it returns to Next meeting with the row naming the days
// and sittings it spans. INVITE_TABLE must be an admin, and the sandbox must
// hold the many-sittings fixture family.

test.describe(() => {
  sandboxOnly("table");

  // R-0629, R-0631
  test("a cut selected in the chat runs across a line between sittings", async ({ page }, info) => {
    const { check, gates, quiet } = walker(page, info);

    await page.goto(need("table"), { waitUntil: "networkidle" });
    await page.locator("#account").click();
    await page.locator(".sn-pane.in .sn-row", { hasText: "Next meeting" }).click();
    await expect(page.locator(".tb-add")).toHaveText("Select a cut for the agenda");
    await toTheirDiagram(page, username("sittings"));

    const say = page.locator("#cut-say");
    const go = page.locator(".ct-go");
    const dividers = page.locator("#chat .sitting");
    const lit = page.locator("#chat .bub.lit");
    await expect(say).toHaveText("Selecting a cut · tap the first line, then the last");
    await expect(go).toHaveText("Place this cut");
    await expect(go).toBeDisabled();
    await expect(lit).toHaveCount(0);
    check((await dividers.count()) >= 2, "the thread shows more than one sitting");

    // The last line of the sitting before the last, then the newest line.
    const second = dividers.last();
    await second.scrollIntoViewIfNeeded();
    await second.locator("xpath=preceding-sibling::div[contains(@class,'bub')][1]").click();
    await expect(lit).toHaveCount(1);
    await expect(say).toHaveText("Selecting a cut · now tap the last line");
    await expect(go).toBeDisabled();
    await second.locator("xpath=following-sibling::div[contains(@class,'bub')][1]").click();
    await expect(lit).toHaveCount(2);
    await expect(say).toHaveText(/^Selecting a cut · .+, 2 sittings$/);
    await expect(go).toBeEnabled();
    const across = await page.evaluate(() => {
      const ringed = [...document.querySelectorAll("#chat .bub.lit")];
      const line = [...document.querySelectorAll("#chat .sitting")].at(-1)!;
      return (
        !!(ringed[0].compareDocumentPosition(line) & Node.DOCUMENT_POSITION_FOLLOWING) &&
        !!(line.compareDocumentPosition(ringed[1]) & Node.DOCUMENT_POSITION_FOLLOWING)
      );
    });
    check(across, "the ringed lines sit on both sides of the line between sittings");
    await gates("a cut across sittings");
    if (info.project.name === "sandbox-phone" && process.env.CUT_SHOT)
      await page.screenshot({ path: process.env.CUT_SHOT });

    const [stored] = await Promise.all([
      page.waitForResponse((r) => r.request().method() === "POST" && /\/cuts$/.test(r.url())),
      go.click(),
    ]);
    check(stored.status() === 201, `the cut was stored (${stored.status()})`);
    const cut = await stored.json();
    const row = page.locator(`.tb-cut[data-cut="${cut.id}"]`);
    await expect(row.locator(".sn-s")).toHaveText(/ · 2 sittings$/);

    // Back in from the row: the same thread, the cut ringed where it stands.
    await row.locator(".sn-m").click();
    await expect(page.locator("#cut-strip")).toBeVisible();
    await expect(lit).toHaveCount(2);
    await page.locator("#cut-strip .cs-cancel").click();
    await expect(lit).toHaveCount(0);

    // Taken back off, so the fixtures can be installed again over this record.
    await page.locator("#account").click();
    await page.locator(".sn-pane.in .sn-row", { hasText: "Next meeting" }).click();
    await row.locator(".pl-btn").click();
    await page.locator(".ag.cf-sheet button", { hasText: "Take it off" }).click();
    await expect(row).toHaveCount(0);
    await backToMine(page);
    await quiet();
  });

  // R-0632
  test("a cut selected on the admin's own diagram from Next meeting", async ({ page }, info) => {
    const { check, gates, quiet } = walker(page, info);

    await page.goto(need("table"), { waitUntil: "networkidle" });
    await page.locator("#account").click();
    await page.locator(".sn-pane.in .sn-row", { hasText: "Next meeting" }).click();
    await page.locator(".tb-add").click();
    const pane = page.locator('.sn-pane[data-page="diagrams"]');
    await pane.locator(".sn-row[data-diagram]").first().click();

    await expect(page.locator("#viewing")).toBeHidden();
    await expect(page.locator("#cut-say")).toHaveText("Selecting a cut · tap the first line, then the last");
    await expect(page.locator("#inbar")).toBeHidden();
    await gates("selecting on the admin's own diagram");
    if (info.project.name === "sandbox-phone" && process.env.OWN_CUT_SHOT)
      await page.screenshot({ path: process.env.OWN_CUT_SHOT });

    const [stored] = await Promise.all([
      page.waitForResponse((r) => r.request().method() === "POST" && /\/cuts$/.test(r.url())),
      placeCut(page),
    ]);
    check(stored.status() === 201, `the cut was stored (${stored.status()})`);
    const cut = await stored.json();
    const row = page.locator(`.tb-cut[data-cut="${cut.id}"]`);
    await expect(row).toContainText(cut.owner);
    await expect(page.locator("#inbar")).toBeVisible();

    await row.locator(".pl-btn").click();
    await page.locator(".ag.cf-sheet button", { hasText: "Take it off" }).click();
    await expect(row).toHaveCount(0);
    await quiet();
  });
});
