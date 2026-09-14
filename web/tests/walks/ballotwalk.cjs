// An independent walk of the ballot on the FD-362 review sandbox: the card
// says vote, one disputed event per screen with its takes, voting a take,
// dropping one, writing a take of your own in the editor sheet, skipping one
// and finding it again, and the card afterwards.
//   node ballotwalk.js <coder-invite-url> <width> <height> <tag>
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
  await page.waitForTimeout(1600);
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
  await page.waitForTimeout(1200);
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
  await gates("the card after the ballot");
  await shot("8-after");

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
