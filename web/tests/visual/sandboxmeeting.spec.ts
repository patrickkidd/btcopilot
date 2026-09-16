import { test } from "@playwright/test";
import { need, sandboxOnly, walker } from "./sandbox";

// An independent walk of the meeting and the result screen on the FD-362
// review sandbox: the table, the meeting with the open items most split first,

test.describe(() => {
  sandboxOnly("table");
  test.describe.configure({ timeout: 600_000 });

  test("the meeting and the result: every item decided, then ratified", async ({ page }, info) => {
    const { say, check, shot, text, visible, gates, changed, quiet } = walker(
      page,
      info,
    );
    const invite = need("table");


    // ── 1. the table, with the vote open ──────────────────────────────────
    await page.goto(invite, { waitUntil: "networkidle" });
    await page.waitForTimeout(1400);
    await page.locator("#sessions-open").click();
    await page.waitForTimeout(900);
    await page.locator(".fs-agenda").click();
    await page.waitForTimeout(1600);
    check(await visible("#agenda-screen"), "the table opens");
    check(await visible(".tb-meet"), "the meeting can be run on the open cut");
    await gates("the table");
    await shot("1-table");

    // ── 2. the meeting: the open items, most split first ──────────────────
    await page.locator(".tb-meet").first().click();
    await page.waitForTimeout(1800);
    check(await visible("#meeting-screen"), "the meeting opens as its own screen");
    check(/ratify$/.test(await text("#title")), "the title says ratify");
    const rows = await page.locator(".drow").count();
    const collapsed = await page.locator(".collapsed").count();
    const dots = await page.locator("#meeting-view circle").count();
    say(`open=${rows} settled=${collapsed} dots=${dots}`);
    check(rows >= 2, `every disputed item is a row (${rows})`);
    check(collapsed >= 1, `the agreed ones are collapsed below (${collapsed})`);
    check(dots >= 2, `the agreement timeline is above the list (${dots})`);
    const names = await page.locator(".tline").first().innerText();
    say(`the first tally line: "${names.replace(/\s+/g, " ")}"`);
    check(/ballot\d|[A-Z]\./.test(names), "names are on the tally line");
    // Every reading is its own .side, whose .swho reads "who, who" — initials
    // only (R-0342). The "left this out" side carries a count with nobody on it.
    const sides = (await page.locator(".tline").first().locator(".side .swho").allInnerTexts())
      .filter((t) => !/^=\s*\d+$/.test(t.trim()));
    say(`names on each reading: ${JSON.stringify(sides)}`);
    check(
      sides.length > 0 && sides.every((t) => !/=/.test(t)),
      "a reading carries initials and no count",
    );
    say(
      `items in order: ${JSON.stringify(
        (await page.locator(".drow .pick").allInnerTexts()).slice(0, 4),
      )}`,
    );
    const stats = await text("#meeting-stats");
    say(`figures: "${stats.replace(/\s+/g, " ")}"`);
    // R-0321: one title line, then three labelled figures and nothing twice.
    check(
      /\d+ events?/.test(stats) &&
        /\d+ disputed/.test(stats) &&
        /agreed before the vote/.test(stats),
      "how many events, how many disputed, and what agreement was before the vote",
    );
    check(
      /still need/.test(await text(".mt-ratify")),
      `ratify says how many still need a choice ("${await text(".mt-ratify")}")`,
    );
    check(
      await page.locator(".mt-ratify").first().isDisabled(),
      "ratify is dead while items are open",
    );
    await gates("the meeting");
    await shot("2-meeting");

    // ── 3. keep one ───────────────────────────────────────────────────────
    const before = await page.locator(".drow").count();
    // A version is kept by tapping the version itself; there is no separate
    // keep button beside it any more.
    await page.locator(".drow .side.tap:not(.on)").first().click();
    await page.waitForTimeout(1600);
    const afterKeep = await page.locator(".drow").count();
    check(afterKeep === before - 1, `keeping settles one item (${before} → ${afterKeep})`);
    await shot("3-kept");

    // ── 4. change one through the event editor ────────────────────────────
    // A person or a bond opens its own editor instead (R-0326), and those rows
    // carry a drawing of the version; the event rows are the ones without one.
    const eventRow = page.locator(".drow:not(:has(.frag))").first();
    await eventRow.locator('.mt-choice[data-choice="change"]').click();
    await page.waitForTimeout(1000);
    check(await visible(".bl-sheet .editor"), "change opens the event editor as a sheet");
    const save = await text(".bl-sheet .save");
    // R-0309: the meeting's word is a decision, never a settle.
    check(save.trim() === "decide on this", `the editor decides ("${save}")`);
    await gates("the editor sheet");
    await shot("4-editor");
    await page
      .locator('.bl-sheet [data-name="description"]')
      .fill("the room's own wording for this one");
    await page.locator(".bl-sheet .save").click();
    await page.waitForTimeout(2000);
    const afterChange = await page.locator(".drow").count();
    const said = await text(".toast");
    if (said) say(`the meeting said: "${said.replace(/\s+/g, " ")}"`);
    check(
      afterChange === afterKeep - 1,
      `changing settles one item (${afterKeep} → ${afterChange})`,
    );
    await shot("5-changed");

    // ── 5. mark one unresolved ────────────────────────────────────────────
    await page
      .locator('.drow .mt-choice[data-choice="unresolved"]')
      .first()
      .click();
    await page.waitForTimeout(1600);
    const left = await page.locator(".drow").count();
    check(left === afterChange - 1, `unresolved takes one off (${left} left)`);
    check(
      left === 0 || (await page.locator(".mt-ratify").first().isDisabled()),
      "ratify stays dead while any item is still open",
    );
    say(`ratify now says "${await text(".mt-ratify")}"`);
    await shot("6-unresolved");

    // ── 6. every remaining item given a choice, then ratify ───────────────
    // An item nobody wrote a second reading of has nothing to keep, so it is
    // closed the only way the room can close it: marked unresolved. Each row
    // is waited out rather than counted out, so a slow answer is not read as a
    // row that refused its choice.
    for (let guard = 0; guard < 20; guard += 1) {
      const row = page.locator(".drow").first();
      if ((await row.count()) === 0) break;
      const item = await row.getAttribute("data-item");
      const keep = row.locator(".side.tap:not(.on)").first();
      if (await keep.count()) await keep.click();
      else await row.locator('.mt-choice[data-choice="unresolved"]').click();
      await page
        .waitForSelector(`.drow[data-item="${item}"]`, {
          state: "detached",
          timeout: 30_000,
        })
        .catch(() => {});
    }
    check(
      (await page.locator(".drow").count()) === 0,
      "every open item took a choice",
    );
    check(
      !(await page.locator(".mt-ratify").first().isDisabled()),
      "ratify comes alive when the last item has a choice",
    );
    check(
      (await text(".mt-ratify")).trim() === "ratify",
      "and stops saying how many need one",
    );
    await gates("the meeting with nothing open");
    await shot("7-ready");
    await page.locator(".mt-ratify").click();
    // Ratifying writes the guidelines, which takes as long as the model takes.
    // Waiting for the screen it opens rather than a fixed count means a fast
    // run is not held and a slow one is not called a failure.
    await page.waitForSelector("#result-screen:not([hidden])", {
      timeout: 180_000,
    });
    await page.waitForTimeout(1200);

    // ── 7. the result screen ──────────────────────────────────────────────
    check(await visible("#result-screen"), "ratifying opens the result screen");
    check(/^ratified /.test(await text("#title")), "the title says when it was ratified");
    const figures = await text("#result-stats");
    say(`result figures: "${figures.replace(/\s+/g, " ")}"`);
    check(/ratified/.test(figures), "how many were ratified");
    check(/unresolved/.test(figures), "how many were left unresolved");
    check(
      /agreed before the vote/.test(figures) && /% after\b/.test(figures),
      "agreement before the vote and after it, side by side",
    );
    check(
      await visible(".rcard"),
      "the guideline changes the meeting wrote are on the screen",
    );
    const provenance = await page.locator(".rcard .prov").allInnerTexts();
    say(`provenance: ${JSON.stringify(provenance.slice(0, 3))}`);
    await gates("the result");
    await shot("8-result");

    // ── 8. flagging a rule puts it on the next meeting's agenda ───────────
    const flags = await page.locator(".rs-flag").count();
    say(`rules on the screen: ${flags}`);
    if (flags) {
      await page.locator(".rs-flag").first().click();
      await page.waitForTimeout(1800);
      check(
        /flagged for the next meeting/.test(await text(".rs-flag")),
        "the rule reads as flagged afterwards",
      );
      await shot("9-flagged");
      await page.locator("#coding-back").click();
      await page.waitForTimeout(1600);
      await page.locator("#coding-back").click();
      await page.waitForTimeout(1600);
      await page.locator("#sessions-open").click();
      await page.waitForTimeout(900);
      await page.locator(".fs-agenda").click();
      await page.waitForTimeout(1800);
      const agenda = await text(".agbox");
      say(`agenda: "${agenda.replace(/\s+/g, " ").slice(0, 200)}"`);
      check(/flagged/.test(agenda), "the flagged rule is on the next agenda");
      await gates("the agenda after flagging");
      await shot("10-agenda");
    } else {
      say("SKIP the flag walk: the coach drafted no rule for this cut");
    }

    // ── the way back to the result once the cut is ratified (R-0275) ──────

    // The sessions button lives beside the message box, so the walk steps back
    // out of whatever full-screen it ended on before it can open the sheet.
    for (let i = 0; i < 4 && !(await visible("#sessions-open")); i += 1) {
      if (await visible("#coding-back")) await page.locator("#coding-back").click();
      await page.waitForTimeout(1000);
    }
    await page.locator("#sessions-open").click();
    await page.waitForTimeout(900);
    check(
      await visible(".fs-task:not(.fs-agenda)"),
      "a coder's sheet offers the task card with nothing left to code",
    );
    await page.locator(".fs-agenda").click();
    await page.waitForTimeout(1600);
    check(
      await visible(".tb-result"),
      "the ratified conversation offers the result on the agenda",
    );
    const ratified = await page.locator(".sn-row .sn-s").last().innerText();
    say(`the ratified row: "${ratified.replace(/\s+/g, " ")}"`);
    check(
      /up to .+ · ratified /.test(ratified),
      "a ratified row says where the cut stops and when it was ratified",
    );
    await page.locator(".tb-result").first().click();
    await page.waitForTimeout(1800);
    check(await visible("#result-screen"), "that opens the result screen");

    // ── the deterministic gates ───────────────────────────────────────────

    await quiet();
  });
});
