import { test } from "./fixtures";
import { need, sandboxOnly, walker } from "./sandbox";
import { placeCut, toTheirDiagram, username } from "./setup";

// Independent walk of Patrick's own screens on the FD-362 review sandbox:
// putting a conversation on the table, placing the cut, and the table itself.

test.describe(() => {
  sandboxOnly("table");
  test.describe.configure({ timeout: 600_000 });

  // R-0346, R-0268, R-0629, R-0631
  test("the table: a conversation goes on the agenda and the vote opens", async ({ page }, info) => {
    const { say, check, shot, text, visible, gates, changed, quiet } = walker(
      page,
      info,
    );
    const invite = need("table");


    /** The sessions sheet lists only the case the app is on (R-0347), so the
     * walk switches to the case that holds the conversation first: the account
     * mark at the top right, the Cases row, then the case. */
    const switchCase = async (name) => {
      await page.locator("#account").click();
      await page.waitForTimeout(700);
      await page
        .locator(".sn-row.push")
        .filter({ hasText: /^(Cases|Diagrams)/ })
        .first()
        .click();
      await page.waitForTimeout(700);
      const row = page.locator(`.sn-row.push[data-name="${name.toLowerCase()}"]`);
      say(`cases on the account page: ${JSON.stringify(await page.locator(".sn-row.push .sn-t").allInnerTexts())}`);
      if ((await row.count()) && !(await row.first().getAttribute("class")).includes("cur"))
        await row.first().click();
      await page.waitForTimeout(2500);
      // Picking a case closes the whole account stack on its own; the back
      // chevron is only needed when the walk was already on the right case.
      // The sessions button stays drawn under the account stack, so the stack
      // itself is what says the walk is not back on the chat yet.
      for (let i = 0; i < 8 && ((await visible("#settings-back")) || (await visible("#coding-back"))); i += 1) {
        if (await visible("#settings-back")) await page.locator("#settings-back").click();
        else if (await visible("#coding-back")) await page.locator("#coding-back").click();
        await page.waitForTimeout(900);
      }
      say(
        `on screen after the switch: ${JSON.stringify(
          await page.evaluate(() =>
            [...document.querySelectorAll("[id$='-screen']")]
              .filter((e) => (e as HTMLElement).offsetParent !== null)
              .map((e) => e.id),
          ),
        )}`,
      );
      check(
        await visible("#sessions-open"),
        `switching to ${name} lands back on the chat, beside its sessions button`,
      );
    };

    /** From the meeting page, its button to the Diagrams page and the
     * family's diagram, opened with selecting a cut on. */
    const openActions = async () => {
      if (!(await visible("#agenda-screen"))) {
        await page.locator("#account").click();
        await page.waitForTimeout(700);
        await page.locator(".sn-pane.in .sn-row", { hasText: "Next meeting" }).click();
        await page.waitForTimeout(1200);
      }
      await toTheirDiagram(page, username("sittings"));
    };

    // ── 1. the meeting page's button opens someone's chat to select in ────
    await page.goto(invite, { waitUntil: "networkidle" });
    await page.waitForTimeout(900);
    say(`url after invite: ${page.url()}`);
    await switchCase("Marcus's side");
    await openActions();
    check(await visible("#cut-strip"), "the chat opened with selecting a cut on");
    await gates("selecting a cut");
    await shot("1-select");

    // ── 2. the first tap rings one line ───────────────────────────────────
    const lines = page.locator("#chat .bub[data-statement]");
    const count = await lines.count();
    await lines.nth(count - 4).click();
    await page.waitForTimeout(400);
    check((await text("#cut-say")).endsWith("now tap the last line"), "the amber line asks for the last line");
    check((await page.locator("#chat .bub.lit").count()) === 1, "one line ringed");
    await shot("2-first");

    // ── 3. the second tap rings the range and fades what comes after ──────
    await lines.nth(count - 2).click();
    await page.waitForTimeout(400);
    const lit = await page.locator("#chat .bub.lit").count();
    const dimmed = await page.locator("#chat .bub.after").count();
    say(`lit=${lit} dimmed=${dimmed} say="${await text("#cut-say")}"`);
    check(lit === 3, `the lines between are ringed (${lit})`);
    check(dimmed === 1, `the line after the cut fades (${dimmed})`);
    check(/ sittings?$/.test(await text("#cut-say")), "the amber line says what the cut spans");
    await gates("cut selected");
    await shot("3-selected");

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
    check(/ · \d+ sittings?$/.test(await text(".tb-cut .sn-s")), "each one says the days and sittings it spans");
    check(rows.length >= 4, `one line per coder (${rows.length})`);
    check(rows.every((r) => /not started|coding|done|voted/.test(r)),
      `every line says not started, coding, done or voted (${JSON.stringify(rows.slice(0, 3))})`);
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
    await page.locator(".ag.cf-sheet button", { hasText: "Take it off" }).click();
    await page.waitForTimeout(1200);
    const left = await page.locator(".tb-cut").count();
    check(left === cuts - 1, `one tap took it off the table (${cuts} → ${left})`);
    await shot("5-off");

    // put it back, so the rest of the walk has it
    await openActions();
    await placeCut(page);
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
