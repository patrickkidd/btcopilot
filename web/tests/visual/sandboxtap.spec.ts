import { test } from "@playwright/test";
import { need, sandboxOnly, walker } from "./sandbox";

// Tapping on the coding thread: a tap above the agreed line shows its notice
// where the tap was and does not throw the thread to the bottom; a tap on a
// codable line outlines it; what the coder says and what the scribe wrote both
// stay in view under the tapped turn.

test.describe(() => {
  sandboxOnly("coder");
  test.describe.configure({ timeout: 600_000 });

  test("a tap on the thread keeps its place", async ({ page }, info) => {
    const { say, check, shot, visible, gates, quiet } = walker(page, info);
    const invite = need("coder");

    /** Where something sits against the thread's own window. */
    const inView = (sel: string) =>
      page.evaluate((one) => {
        const list = document
          .getElementById("coding-chat")!
          .getBoundingClientRect();
        const el = document.querySelector(one);
        if (!el) return { found: false, visible: false };
        const r = el.getBoundingClientRect();
        return {
          found: true,
          visible: r.top >= list.top - 1 && r.bottom <= list.bottom + 1,
        };
      }, sel);
    const scrolled = () =>
      page.evaluate(() => {
        const c = document.getElementById("coding-chat")!;
        return {
          top: Math.round(c.scrollTop),
          max: Math.round(c.scrollHeight - c.clientHeight),
        };
      });

    await page.goto(invite, { waitUntil: "networkidle" });
    await page.waitForTimeout(1200);
    if (await visible("#task-screen"))
      await page.locator("#task-screen .addbtn").first().click();
    else {
      await page.locator("#sessions-open").click();
      await page.waitForTimeout(800);
      await page.locator(".fs-task").first().click();
    }
    await page.waitForTimeout(2500);
    test.skip(
      !(await visible("#coding-screen")),
      "the coder's task on this fixture is the vote, not a coding",
    );
    await gates("the coding thread");

    // ── 1. a tap above the agreed line ────────────────────────────────────
    await page.evaluate(() => {
      document.getElementById("coding-chat")!.scrollTop = 0;
    });
    await page.waitForTimeout(200);
    const above = page.locator("#coding-chat .bub.line").first();
    await above.click();
    await page.waitForTimeout(400);
    const place = await scrolled();
    const notice = await inView("#coding-chat .abv");
    say(`after the tap above the line: ${JSON.stringify({ place, notice })}`);
    check(
      notice.found && notice.visible,
      "the agreed-line notice is in view under the tapped turn",
    );
    check(
      place.top < place.max - 40,
      "the thread did not jump to the bottom",
    );
    await shot("1-above");

    // ── 2. a tap on a codable line ────────────────────────────────────────
    const codable = page.locator("#coding-chat .bub.line").nth(6);
    await codable.scrollIntoViewIfNeeded();
    await codable.click();
    await page.waitForTimeout(400);
    const turn = await codable.getAttribute("data-turn");
    const chosen = await inView(`#coding-chat .bub.line[data-turn="${turn}"].sel`);
    const outline = await page.evaluate(
      (id) =>
        getComputedStyle(
          document.querySelector(`#coding-chat .bub.line[data-turn="${id}"]`)!,
        ).outlineWidth,
      turn,
    );
    say(`the tapped line: ${JSON.stringify(chosen)} outline ${outline}`);
    check(
      chosen.found && chosen.visible && outline !== "0px",
      "the tapped codable line is outlined and in view",
    );

    // ── 3. saying something on that line ──────────────────────────────────
    await page.locator("#coding-composer").click();
    await page.keyboard.type(
      "Marcus's father drove to Arizona alone in March 1969",
    );
    await page.locator("#coding-send").click();
    await page.waitForSelector(
      `#coding-chat .bub.coach[data-turn="${turn}"] .did`,
      { timeout: 120_000 },
    );
    await page.waitForTimeout(1200);
    const words = await inView(`#coding-chat .bub.said[data-turn="${turn}"]`);
    const written = await inView(
      `#coding-chat .bub.coach[data-turn="${turn}"] .did`,
    );
    say(`words ${JSON.stringify(words)} line ${JSON.stringify(written)}`);
    check(
      words.found && words.visible,
      "the coder's words are in view under the tapped turn",
    );
    check(
      written.found && written.visible,
      "the scribe's line is in view under the coder's words",
    );
    await gates("the thread after saying something");
    await shot("2-said");
    await quiet();
  });
});
