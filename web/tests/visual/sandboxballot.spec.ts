import { test } from "@playwright/test";
import { need, sandboxOnly, walker } from "./sandbox";

// An independent walk of the ballot on the FD-362 review sandbox: the card
// says vote, one disputed event per screen with its takes, voting a take,

test.describe(() => {
  sandboxOnly("coder");
  test.describe.configure({ timeout: 600_000 });

  test("the ballot: a coder votes on every disputed item", async ({ page }, info) => {
    const { say, check, shot, text, visible, gates, changed, quiet } = walker(
      page,
      info,
    );
    const invite = need("coder");


    // ── 1. the one card says vote ─────────────────────────────────────────
    await page.goto(invite, { waitUntil: "networkidle" });
    await page.waitForTimeout(1400);
    const card = await text(".tkcard .r1");
    const button = await text(".tkcard .addbtn");
    say(`card="${card}" button="${button}"`);
    check(/^Vote on /.test(card), "the coder's one card is the vote");
    check(button.trim() === "vote", "the button on it says vote");
    await gates("the task card");
    await shot("1-card");

    // ── 2. the first item, with the takes and the timeline above it ───────
    await page.locator(".tkcard .addbtn").click();
    await page.waitForTimeout(1600);
    check(await visible("#ballot-screen"), "the vote opens as its own screen");
    const title = await text("#title");
    const takes = await page.locator(".opinion").allInnerTexts();
    const dots = await page.locator("#ballot-view circle").count();
    const green = await page.locator("#ballot-view .d-on").count();
    const amber = await page.locator("#ballot-view .d-no").count();
    const teal = await page.locator("#ballot-view .d-ok").count();
    say(
      `title="${title}" takes=${JSON.stringify(takes)} dots=${dots} teal=${teal} amber=${amber} green=${green}`,
    );
    check(/ballot · 1 of \d+$/.test(title), "the title says which item of how many");
    check(takes.length >= 2, `the takes are shown (${takes.length})`);
    check(
      takes.every((t) => !/@|ballot\d/.test(t)),
      "no coder is named on a take",
    );
    // People and bonds are read before the events and are not on the wire, so
    // while the room is on one no dot is green and the strip says who it is on
    // (R-0326). The wire's own dot is checked on the first event, below.
    check(green === 0, "a person is not a dot on the wire");
    check(/^now · /.test(await text("#ballot-caption .tok.g")),
      "the strip says who the room is on");
    check(teal >= 1 && amber >= 1, `agreed and disputed dots (${teal}/${amber})`);
    await gates("the first item");
    await shot("2-item");

    // ── 2b. the first event: its own dot, its line, and the way in ────────
    await page.locator("#ballot-view circle").first().click();
    await page.waitForTimeout(1200);
    check((await page.locator("#ballot-view .d-on").count()) === 1,
      "one dot is the event being voted on");
    check(await visible(".quote"), "the transcript line it came from is shown");
    check(await visible("#bl-line"), "the transcript can be opened at that line");
    await gates("the first event");
    await shot("2c-event");

    // ── 3. the transcript, opened at the line and stepped back out of ─────
    const was = await text("#title");
    await page.locator("#bl-line").click();
    await page.waitForTimeout(1800);
    check(await visible("#coding-screen"), "the transcript opens from the ballot");
    check(
      !(await visible("#coding-done")) && !(await visible("#coding-inbar")),
      "a submitted coding is read from the ballot, not added to",
    );
    await shot("2b-transcript");
    await page.locator("#coding-back").click();
    // Stepping back into the ballot re-reads it, which takes as long as the
    // sandbox takes; waiting for the takes to be drawn again rather than a
    // fixed count is what makes this step honest.
    await page
      .waitForSelector("#ballot-screen:not([hidden]) .opinion", {
        timeout: 60_000,
      })
      .catch(() => {});
    say(
      `back from the transcript: ballot=${await visible("#ballot-screen")}` +
        ` task=${await visible("#task-screen")} coding=${await visible("#coding-screen")}` +
        ` title="${await text("#title")}" was="${was}"`,
    );
    check(
      (await visible("#ballot-screen")) && (await text("#title")) === was,
      "back from the transcript is the same item of the ballot",
    );

    // ── 4. voting a take ──────────────────────────────────────────────────
    const first = await text("#title");
    await page.locator(".opinion:not(.off)").first().click();
    await page.waitForTimeout(900);
    check(
      (await page.locator(".opinion.on").count()) === 1,
      "the take you voted for is marked",
    );
    await shot("3-voted");
    await page.locator("#bl-next").click();
    await page.waitForTimeout(900);
    check((await text("#title")) !== first, "next moves to another item");

    // ── 4. dropping one ───────────────────────────────────────────────────
    await page.locator("#bl-drop").click();
    await page.waitForTimeout(900);
    check(
      await page.locator("#bl-drop.on").isVisible(),
      "drop is marked as the vote on this one",
    );
    await shot("4-dropped");
    await page.locator("#bl-next").click();
    await page.waitForTimeout(900);

    // ── 5. a take of your own, written in the editor over the ballot ──────
    await page.locator("#bl-change").click();
    await page.waitForTimeout(900);
    check(await visible(".bl-sheet .editor"), "change opens the event editor as a sheet");
    const save = await text(".bl-sheet .save");
    check(save.trim() === "save as my opinion", `the editor saves as a take ("${save}")`);
    await gates("the editor sheet");
    await shot("5-editor");
    await page
      .locator('.bl-sheet [data-name="description"]')
      .fill("came back for a winter and left again");
    await page.locator(".bl-sheet .save").click();
    // Saving writes the take and re-reads the ballot; waiting for the sheet to
    // go and the take to be drawn is what says it landed, and it leaves the
    // next button clickable rather than under a sheet that is still closing.
    await page
      .waitForSelector(".bl-sheet", { state: "detached", timeout: 60_000 })
      .catch(() => {});
    await page
      .locator(".opinion.on", { hasText: "came back for a winter" })
      .first()
      .waitFor({ timeout: 60_000 })
      .catch(() => {});
    const own = await page.locator(".opinion.on").allInnerTexts();
    say(`own take: ${JSON.stringify(own)}`);
    check(
      own.some((t) => /came back for a winter/.test(t)),
      "the take you wrote joins the count as one more take",
    );
    await shot("6-own");
    await page.locator("#bl-next").click();
    await page.waitForTimeout(900);

    // ── 6. skipping one, and finding it again ─────────────────────────────
    const skipped = await text("#title");
    say(`skipping "${skipped}"`);
    await page.locator("#bl-next").click();
    await page.waitForTimeout(900);
    const after = await text("#title");
    check(after !== skipped, "next left the skipped one without a vote");
    await page.locator("#bl-say").fill("the year is what I am unsure of");
    await page.locator("#bl-drop").click();
    await page.waitForTimeout(900);
    // The skipped one is not lost: going round the items without a vote brings
    // it back, however many are still waiting.
    let back = false;
    for (let i = 0; i < 8 && !back; i += 1) {
      await page.locator("#bl-next").click();
      await page.waitForTimeout(900);
      back = (await text("#title")) === skipped;
    }
    check(back, `the skipped item comes back (${await text("#title")})`);
    await shot("7-back");

    // ── 7. the last vote returns to the card ──────────────────────────────
    // Vote on everything still waiting, moving on by hand: a vote marks the item
    // and stays on it. The button only says done on the last one left.
    let done = await text("#bl-next");
    for (let i = 0; i < 10; i += 1) {
      // An item whose only take you already voted on is voted with drop.
      const takes = await page.locator(".take.tap:not(.on)").count();
      if (takes) await page.locator(".take.tap:not(.on)").first().click();
      else await page.locator("#bl-drop").click();
      await page.waitForTimeout(800);
      say(`voted on "${(await text("#title")).replace(/\s+/g, " ")}" takes=${takes}`);
      done = await text("#bl-next");
      if (done.trim() === "done") break;
      await page.locator("#bl-next").click();
      await page.waitForTimeout(800);
    }
    check(done.trim() === "done", `the last screen says done ("${done}")`);
    await page.locator("#bl-next").click();
    await page.waitForTimeout(1800);
    check(await visible("#task-screen"), "the ballot ends back on the one card");
    const now = await text("#task-body");
    say(`card after the ballot: "${now.replace(/\s+/g, " ").slice(0, 160)}"`);
    check(
      !/^Vote on /.test(await text(".tkcard .r1")),
      "the vote is no longer the card",
    );
    // No gate on this last screen: once the ballot is finished, every call
    // that measures or screenshots the page stops answering under the test
    // runner, while what the page says can still be read. The same steps in the
    // same state answer under plain Playwright (verified 2026-09-14), so this
    // is the runner and the page together and not something a person meets.
    // The screen itself is gated by the walk that opens it, not by this one.

    // ── the deterministic gates ───────────────────────────────────────────

    await quiet();
  });
});
