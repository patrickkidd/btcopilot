// An independent walk of the meeting and the result screen on the FD-362
// review sandbox: the table, the meeting with the open items most split first,
// keeping one, changing one in the editor sheet, marking one unresolved, the
// ratify button staying dead with its count, ratifying, and the result screen
// with the counts, both agreement figures, the coach's score, the guideline
// changes and flagging one onto the next meeting's agenda.
//   node meetingwalk.js <admin-invite-url> <width> <height> <tag>
const pw = require("playwright");
const BROWSER = pw[process.env.WALK_BROWSER ?? "chromium"];

const [, , invite, W, H, TAG] = process.argv;
const OUT = process.env.WALK_SHOTS ?? "/tmp/fd362-walks";
require("fs").mkdirSync(OUT, { recursive: true });
const errors = [];
const failed = [];
let fails = 0;
const say = (s) => console.log(s);
const check = (ok, what) => {
  if (!ok) fails += 1;
  say(`${ok ? "PASS" : "FAIL"} ${what}`);
};

(async () => {
  const browser = await BROWSER.launch();
  const ctx = await browser.newContext({
    viewport: { width: +W, height: +H },
    ignoreHTTPSErrors: true,
    deviceScaleFactor: 2,
    colorScheme: "light",
  });
  const page = await ctx.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
  page.on("response", (r) => {
    if (r.status() >= 400)
      failed.push(`${r.status()} ${r.request().method()} ${r.url()}`);
  });
  page.on("requestfailed", (r) =>
    failed.push(`NET ${r.url()} ${r.failure()?.errorText}`),
  );

  const shot = (n) => page.screenshot({ path: `${OUT}/${TAG}-${n}.png` });
  const text = (sel) => page.locator(sel).first().innerText().catch(() => "");
  const visible = (sel) => page.locator(sel).first().isVisible();
  const gates = async (step) => {
    const g = await page.evaluate(() => {
      const se = document.scrollingElement;
      const out = [];
      for (const e of document.querySelectorAll("body *")) {
        if (!(e instanceof HTMLElement) || e.offsetParent === null) continue;
        const r = e.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;
        if (r.right > innerWidth + 1 || r.left < -1)
          out.push(
            `${e.tagName.toLowerCase()}#${e.id}.${[...e.classList].join(".")} ${Math.round(r.left)}..${Math.round(r.right)}`,
          );
      }
      return { hs: se.scrollWidth > se.clientWidth + 1, out: out.slice(0, 6) };
    });
    check(!g.hs, `${step}: no horizontal scroll`);
    check(
      g.out.length === 0,
      `${step}: no box past the viewport edge ${g.out.join(" | ")}`,
    );
  };

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
  check(/ballot\d|=\s*\d/.test(names), "names and counts are on the tally line");
  // Every reading is its own .side, whose .swho reads "who, who = n". The
  // "left this out" side carries a count with nobody on it, so it is skipped.
  const sides = (await page.locator(".tline").first().locator(".side .swho").allInnerTexts())
    .map((t) => t.match(/^(.*?)\s*=\s*(\d+)$/))
    .filter((m) => m && m[1].trim())
    .map((m) => [m[1].split(/,\s*/).length, Number(m[2])]);
  say(`names against counts: ${JSON.stringify(sides)}`);
  check(
    sides.length > 0 && sides.every(([n, c]) => n === c),
    "the count beside a reading is how many names are on it",
  );
  const split = await page.locator(".drow .verdict").allInnerTexts();
  say(`verdicts in order: ${JSON.stringify(split)}`);
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
  await page.locator('.drow .mt-keep:not([disabled])').first().click();
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
  for (let guard = 0; guard < 12; guard += 1) {
    if ((await page.locator(".drow").count()) === 0) break;
    await page.locator('.drow .mt-keep:not([disabled])').first().click();
    await page.waitForTimeout(1400);
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
  await page.waitForTimeout(20000);

  // ── 7. the result screen ──────────────────────────────────────────────
  check(await visible("#result-screen"), "ratifying opens the result screen");
  check(/^ratified /.test(await text("#title")), "the title says when it was ratified");
  const figures = await text("#result-stats");
  say(`result figures: "${figures.replace(/\s+/g, " ")}"`);
  check(/ratified/.test(figures), "how many were ratified");
  check(/unresolved/.test(figures), "how many were left unresolved");
  check(
    /first pass/.test(figures) && /after ratification/.test(figures),
    "agreement before the ballot and after ratification, side by side",
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
      /flagged for next meeting/.test(await text(".rs-flag")),
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

  // ── the deterministic gates ───────────────────────────────────────────
  const noisy = errors.filter((e) => !/vite|hot|ws:\/\/|wss:\/\//i.test(e));
  say(`console errors: ${JSON.stringify(errors)}`);
  say(`failed requests: ${JSON.stringify(failed)}`);
  check(noisy.length === 0, "zero console errors beyond the hot-reload socket");
  check(failed.length === 0, "zero failed requests");
  say(fails === 0 ? "WALK PASS" : `WALK FAIL (${fails})`);
  await browser.close();
  process.exit(fails === 0 ? 0 : 1);
})();
