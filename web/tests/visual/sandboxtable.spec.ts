import { test } from "@playwright/test";
import { need, sandboxOnly, walker } from "./sandbox";

// Independent walk of Patrick's own screens on the FD-362 review sandbox:
// putting a conversation on the table, placing the cut, and the table itself.

test.describe(() => {
  sandboxOnly("table");
  test.describe.configure({ timeout: 600_000 });

  test("the table: a conversation goes on the agenda and the vote opens", async ({ page }, info) => {
    const { say, check, shot, text, visible, gates, changed, quiet } = walker(
      page,
      info,
    );
    const invite = need("table");


    /** Swipe one session row left far enough to reveal its actions. */
    const swipe = async (rowSel) => {
      const box = await page.locator(rowSel).first().boundingBox();
      const y = box.y + box.height / 2;
      await page.mouse.move(box.x + box.width - 30, y);
      await page.mouse.down();
      for (const dx of [20, 50, 90, 130]) {
        await page.mouse.move(box.x + box.width - 30 - dx, y);
        await page.waitForTimeout(40);
      }
      await page.mouse.up();
      await page.waitForTimeout(300);
    };

    /** Open the sessions sheet and swipe the conversation the walk cuts. */
    const openActions = async () => {
      // The sessions button lives beside the message box, so the sheet is
      // reached from the chat, not from a full-screen review screen.
      if (!(await visible("#sessions-open"))) {
        await page.locator("#coding-back").click();
        await page.waitForTimeout(600);
      }
      await page.locator("#sessions-open").click();
      await page.waitForTimeout(700);
      say(`sheet: ${(await text(".fs-sheet .fs-body")).replace(/\s+/g, " ").slice(0, 300)}`);
      const row = '.fs-sheet .fs-body .row:has-text("The mine years")';
      await swipe(row);
      return row;
    };

    // ── 1. the sessions sheet offers Patrick one more action ───────────────
    await page.goto(invite, { waitUntil: "networkidle" });
    await page.waitForTimeout(900);
    say(`url after invite: ${page.url()}`);
    const row = await openActions();
    const acts = (await text(".fs-acts")).replace(/\s+/g, " ");
    say(`swipe actions: "${acts}"`);
    check(await visible(".fs-act.tbl"), "an admin's swipe offers Put on the agenda");
    check(/Put on the agenda/.test(acts) && /Rename/.test(acts) && /Delete/.test(acts),
      "the agenda action stands beside rename and delete");
    await gates("sessions sheet");
    await shot("1-swipe");

    // ── 2. placing the cut ────────────────────────────────────────────────
    await page.locator(".fs-act.tbl").click();
    await page.waitForTimeout(1200);
    check(await visible("#cut-screen"), "the conversation opened to place the cut");
    check(!(await visible("#chat-screen")), "the chat is not on screen");
    const bubbles = await page.locator("#cut-chat .bub.line").count();
    const nowLbl = await text("#cut-chat .cutline.now .lb");
    const hint = await text(".ct-hint");
    const go = await text(".ct-go");
    say(`bubbles=${bubbles} cut="${nowLbl}" hint="${hint}" button="${go}"`);
    check(bubbles === 12, `every turn of the conversation is shown (${bubbles})`);
    check(/^cut here · turn 11 /.test(nowLbl), "the cut starts at the last turn");
    check(hint.trim() === "tap any line to move the cut", "the screen says a tap moves the cut");
    check(/^put on the agenda at turn 11$/.test(go.trim()), "the button names the turn it will cut at");
    check((await page.locator("#cut-chat .bub.line.after").count()) === 0,
      "nothing is dimmed while the cut is at the last turn");
    await gates("cut at the last turn");
    await shot("2-cut");

    // ── 3. moving the cut back dims what comes after it ───────────────────
    const ninth = page.locator("#cut-chat .bub.line").nth(8);
    await ninth.click();
    await page.waitForTimeout(400);
    const dimmed = await page.locator("#cut-chat .bub.line.after").count();
    const moved = await text("#cut-chat .cutline.now .lb");
    const go2 = await text(".ct-go");
    say(`moved="${moved}" dimmed=${dimmed} button="${go2}"`);
    check(/^cut here · turn 8 /.test(moved), "tapping a line moved the cut to it");
    check(dimmed === 3, `turns after the cut are dimmed (${dimmed} of 12)`);
    check(/^put on the agenda at turn 8$/.test(go2.trim()), "the button follows the cut");
    await gates("cut moved");
    await shot("3-moved");

    // ── 4. the table ──────────────────────────────────────────────────────
    await page.locator(".ct-go").click();
    await page.waitForTimeout(1500);
    check(await visible("#agenda-screen"), "putting it on the table opens the table");
    const title = await text("#title");
    const cuts = await page.locator(".tb-cut").count();
    const rows = await page.locator(".srow").allInnerTexts();
    const note = await text(".plnote");
    say(`title="${title}" cuts=${cuts} coders=${JSON.stringify(rows)} note="${note}"`);
    check(/^Next meeting · \w{3}, \w{3} \d+$/.test(title.trim()),
      `the title names the meeting by its day ("${title.trim()}")`);
    check(cuts >= 2, `what is on the table is listed (${cuts})`);
    check((await text(".tb-cut")).includes("up to turn"), "each one says how far it is cut");
    check(rows.length >= 4, `one line per coder (${rows.length})`);
    check(rows.some((r) => /not started/.test(r)) && rows.some((r) => /coding|done|voted/.test(r)),
      "the lines say not started, coding, done or voted");
    check(/^closed out: \d+ of \d+/.test(note.trim()), `the count of who is closed out reads "${note.trim()}"`);
    check(await visible(".tb-nudge"), "one control nudges the ones who are not done");
    check(await visible(".tb-vote"), "one button opens the vote");
    check(await visible(".tb-date"), "the meeting date row carries the phone's own date picker");
    await gates("the table");
    await shot("4-table");

    // ── 5. taking a conversation off the table, before anyone started ─────
    const offable = await page.locator(".tb-cut:has(.pl-btn)").count();
    const started = await page.locator(".tb-cut:not(:has(.pl-btn))").count();
    say(`cuts with a cross=${offable} without=${started}`);
    check(offable >= 1 && started >= 1,
      "only a cut nobody has started carries the cross that takes it off");
    await page.locator(".tb-cut .pl-btn").first().click();
    await page.waitForTimeout(1200);
    const left = await page.locator(".tb-cut").count();
    check(left === cuts - 1, `one tap took it off the table (${cuts} → ${left})`);
    await shot("5-off");

    // put it back, so the rest of the walk has it
    await openActions();
    await page.locator(".fs-act.tbl").click();
    await page.waitForTimeout(1000);
    await page.locator(".ct-go").click();
    await page.waitForTimeout(1500);
    check((await page.locator(".tb-cut").count()) === cuts, "it goes back on the table the same way");

    // ── 6. the meeting date ───────────────────────────────────────────────
    await page.locator(".tb-date").fill("2026-09-25");
    await page.waitForTimeout(1400);
    const moved2 = await text("#title");
    say(`title after the date moved: "${moved2}"`);
    check(/Sep 25/.test(moved2), "changing the date changes the meeting the table is for");
    await page.locator(".tb-date").fill("2026-09-18");
    await page.waitForTimeout(1400);
    check(/Sep 18/.test(await text("#title")), "and back again");

    // ── 7. the nudge ──────────────────────────────────────────────────────
    // Never tapped here: the sandbox sends real mail, and the fixture coders'
    // addresses are not real. The control and its words are checked instead.
    const behind = await text(".tb-nudge");
    say(`nudge button="${behind}"`);
    check(/^nudge the \d+ who (is|are) not done$/.test(behind.trim()), "the nudge says how many are waited on");
    await shot("6-nudge-not-tapped");

    // ── 8. nothing opens the vote but this button ─────────────────────────
    await page.locator(".tb-vote").click();
    await page.waitForTimeout(2500);
    const notes = await page.locator(".plnote").allInnerTexts();
    say(`notes after opening the vote: ${JSON.stringify(notes)}`);
    check((await page.locator(".tb-vote").count()) === 0, "the button that opened the vote is gone");
    check(notes.some((n) => /^The vote is open\.$/.test(n.trim())),
      "a plain line says the vote is open");
    await gates("vote open");
    await shot("7-vote-open");


    // ── the deterministic gates ───────────────────────────────────────────

    await quiet();
  });
});
