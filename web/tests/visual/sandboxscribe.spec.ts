import { test } from "@playwright/test";
import { need, sandboxOnly, walker } from "./sandbox";

// A coder's own sentence about a marriage and about a parent: the scribe adds
// the people and the bond, and writes what it did under the coder's words.

test.describe(() => {
  sandboxOnly("coder");
  test.describe.configure({ timeout: 600_000 });

  test("a coder's sentence adds a person and a bond", async ({ page }, info) => {
    const { say, check, shot, text, visible, gates, changed, quiet } = walker(
      page,
      info,
    );
    const invite = need("coder");

    /** Tap a line of the frozen thread, type what it tells you happened, and
     * read back what the scribe wrote under your words. */
    const code = async (turn: number, sentence: string) => {
      await page.locator("#coding-chat .bub.line").nth(turn).click();
      await page.waitForTimeout(400);
      await page.locator("#coding-composer").click();
      await page.keyboard.type(sentence);
      say(
        `typed into the box: "${await page.locator("#coding-composer").innerText()}"` +
          ` send enabled=${await page.locator("#coding-send").isEnabled()}`,
      );
      await page.locator("#coding-send").click();
      await page.waitForTimeout(25000);
      return page.locator("#coding-chat .did").allInnerTexts();
    };

    await page.goto(invite, { waitUntil: "networkidle" });
    await page.waitForTimeout(1200);
    if (await visible("#task-screen")) {
      say(`the one card says: ${(await text("#task-body")).replace(/\s+/g, " ")}`);
      await page.locator("#task-screen .addbtn").first().click();
      await page.waitForTimeout(2500);
    } else {
      await page.locator("#sessions-open").click();
      await page.waitForTimeout(800);
      const card = page.locator(".fs-task").first();
      say(`the card says: ${(await card.innerText()).replace(/\s+/g, " ")}`);
      await card.click();
      await page.waitForTimeout(2000);
    }
    await shot("1-thread");
    // The coder's one card is the vote once Patrick has opened it, and there is
    // no coding to do; that state is the ballot walk's, not this one's.
    test.skip(
      !(await visible("#coding-screen")),
      "the coder's task on this fixture is the vote, not a coding",
    );
    check(await visible("#coding-screen"), "the coding thread opens");

    const married = await code(6, "Marcus and Delphine married in 1970.");
    say(`after the marriage sentence: ${JSON.stringify(married.slice(-3))}`);
    check(
      married.some((l) => /Marcus & Delphine/.test(l) && /married/.test(l)),
      "a sentence about a marriage is written as a bond line",
    );

    const born = await code(7, "Corinne is the daughter of Marcus and Delphine.");
    say(`after the parent sentence: ${JSON.stringify(born.slice(-3))}`);
    check(
      born.some((l) => /Corinne/.test(l) && /Marcus & Delphine/.test(l)),
      "a sentence about a parent is written as a birth line",
    );
    check(
      (await page.locator("#coding-chat .bub.said").count()) >= 2,
      "the coder's own words stay in the thread under the line",
    );
    await shot("2-written");


    await quiet();
  });
});
