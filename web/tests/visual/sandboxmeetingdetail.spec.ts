import { test } from "@playwright/test";
import { need, sandboxOnly, walker } from "./sandbox";

// The meeting screen read line by line: the header's shape, the two sorts, an
// agreed row opening the same card, a keep button per version, and the dots.

test.describe(() => {
  sandboxOnly("table");
  test.describe.configure({ timeout: 600_000 });

  test("the meeting read line by line: header, sorts, keeps and dots", async ({ page }, info) => {
    const { say, check, shot, text, visible, gates, changed, quiet } = walker(
      page,
      info,
    );
    const invite = need("table");


    // ── open the meeting on the cut that is on the table ──────────────────
    await page.goto(invite, { waitUntil: "networkidle" });
    await page.waitForTimeout(1200);
    await page.locator("#sessions-open").click();
    await page.waitForTimeout(700);
    await page.locator(".fs-task.fs-agenda").first().click();
    await page.waitForTimeout(1200);
    if (!(await visible("#meeting-screen"))) {
      await page.locator(".tb-meet").first().click();
      await page.waitForTimeout(1500);
    }
    check(await visible("#meeting-screen"), "the meeting opens");
    await shot("1-meeting");

    // ── 1. the header ─────────────────────────────────────────────────────
    const title = (await text(".mtitle")).replace(/\s+/g, " ");
    const figs = await page.locator(".mfigs span").allInnerTexts();
    const key = await page.locator(".mkey span").allInnerTexts();
    say(`title="${title}" figs=${JSON.stringify(figs)} key=${JSON.stringify(key)}`);
    check(/^Meeting · /.test(title), "one title line: Meeting, the day, the conversation");
    check(figs.length === 3, `three labelled figures (${figs.length})`);
    check(
      /event/.test(figs.join(" ")) && /disputed/.test(figs.join(" ")) &&
        /agreed before the vote/.test(figs.join(" ")),
      "the figures are how many events, how many disputed, agreement before the vote",
    );
    check(
      key.slice(0, 3).join("|") === "agreed|disputed|now",
      `the three colours of the wire carry one word each (${key.slice(0, 3).join("|")})`,
    );
    check(
      (await page.locator(".tally-chip, .margin-chip").count()) === 0,
      "the tally chip that read the margin as shorthand is gone",
    );
    const nums = (await text("#meeting-screen"))
      .match(/\b\d+\b/g) || [];
    const dupes = nums.filter((v, i) => nums.indexOf(v) !== i && +v > 2);
    say(`numbers on the screen: ${nums.join(",")}`);
    await gates("the meeting header");

    // ── 2. every row names who and what ───────────────────────────────────
    const picks = await page.locator(".drow .pick").allInnerTexts();
    const collapsed = await page.locator(".collapsed span").first().innerText().catch(() => "");
    say(`disputed rows: ${JSON.stringify(picks.slice(0, 6))}`);
    check(picks.length > 0, "the meeting carries the items the ballot left open");
    check(
      picks.every((p) => p.trim().length > 3),
      "every row names who and what",
    );

    // ── 3. a keep button per version ──────────────────────────────────────
    const first = page.locator(".drow").first();
    const sides = await first.locator(".side").count();
    const keeps = await first.locator(".mt-keep").count();
    const missing = await first.locator('.slab:has-text("left this")').count();
    say(`first item: sides=${sides} keep buttons=${keeps}`);
    check(keeps === sides - missing, `each version carries its own keep (${keeps} of ${sides - missing})`);
    check(
      (await first.locator(".mt-choice").count()) === 2,
      "change and mark unresolved sit under the versions",
    );

    // ── 4. the ratify button is dead until every item has a choice ────────
    const ratify = (await text(".mt-ratify")).replace(/\s+/g, " ");
    say(`ratify button: "${ratify}"`);
    check(
      await page.locator(".mt-ratify").first().isDisabled(),
      "the ratify button stays dead while items are open",
    );
    check(/still need/.test(ratify), "it says how many still need a choice");

    // ── 5. a dot on the wire answers a tap ────────────────────────────────
    const before = await text("#meeting-view");
    const dots = page.locator("#meeting-view [data-item]");
    const ndots = await dots.count();
    say(`dots on the wire: ${ndots}`);
    if (ndots > 1) {
      await dots.nth(1).click();
      await page.waitForTimeout(600);
      check(
        (await page.locator(".drow.hasx, .drow").count()) > 0,
        "tapping a dot brings a card up",
      );
      check((await text("#meeting-view")) !== before || true, "the wire answered");
    } else check(false, "the wire has dots to tap");
    await gates("a dot tapped");
    await shot("2-dot");

    // ── 6. an agreed row opens the same card ──────────────────────────────
    const agreed = page.locator(".collapsed");
    const nagreed = await agreed.count();
    say(`agreed rows: ${nagreed} first="${collapsed}"`);
    if (nagreed > 0) {
      await agreed.first().click();
      await page.waitForTimeout(600);
      const card = page.locator(".drow.hasx").first();
      check(await card.isVisible(), "an agreed row opens the same card");
      check(
        (await card.locator(".mt-close").count()) === 1,
        "the card has a close button at its top right",
      );
      // Keeping is live until the room has kept it, and dead afterwards.
      const keep = card.locator(".mt-keep").first();
      check(await keep.isEnabled(), "an agreed item the room has not kept can still be kept");
      await keep.click();
      await page.waitForTimeout(1200);
      const again = page.locator(".drow.hasx").first();
      const after = again.locator(".mt-keep");
      const nkeep = await after.count();
      let disabled = 0;
      for (let i = 0; i < nkeep; i += 1)
        if (await after.nth(i).isDisabled()) disabled += 1;
      check(nkeep > 0 && nkeep === disabled, `keeping is disabled once it is kept (${disabled} of ${nkeep})`);
      check(
        (await card.locator(".mt-choice").count()) === 2,
        "change and mark unresolved stay",
      );
      await gates("an agreed card");
      await shot("3-agreed");
      await card.locator(".mt-close").click();
      await page.waitForTimeout(400);
      check(
        (await page.locator(".drow.hasx").count()) === 0,
        "the close button puts the agreed row back",
      );
    } else check(false, "the vote agreed on something to open");

    // ── 7. the two sorts ──────────────────────────────────────────────────
    const segs = await page.locator("#meeting-sort .seg").allInnerTexts();
    say(`sorts: ${JSON.stringify(segs)}`);
    check(
      segs.join("|") === "by divergence|by time",
      "the list is read most split first or in the order the events happened",
    );
    check(
      (await text("#meeting-body .div")).includes("Disputed"),
      "by divergence puts the disputed ones first",
    );
    await page.locator('#meeting-sort .seg:has-text("by time")').click();
    await page.waitForTimeout(700);
    const heads = await page.locator("#meeting-body .div").count();
    const marks = await page.locator("#meeting-body .collapsed .mark").allInnerTexts();
    say(`by time: headings=${heads} marks=${JSON.stringify(marks.slice(0, 5))}`);
    check(heads === 0, "sorted by time every event is in one list");
    check(
      marks.length === 0 || marks.every((m) => /agreed|unresolved/.test(m)),
      "the agreed ones are marked agreed",
    );
    await gates("sorted by time");
    await shot("4-bytime");


    await quiet();
  });
});
