// A walk of the chat app's own screens: the picture at rest, a cluster, the
// row of chips under it, the lists drawer and its two editors, the sessions
// sheet, the account page and the about page.
//   node appwalk.cjs <invite-url> <width> <height> <tag>
const pw = require("playwright");
const BROWSER = pw[process.env.WALK_BROWSER ?? "chromium"];

const [, , invite, W, H, TAG] = process.argv;
const OUT = process.env.WALK_SHOTS ?? "/tmp/fd362-walks";
require("fs").mkdirSync(OUT, { recursive: true });
let fails = 0;
const errors = [];
const failed = [];
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
  const visible = (sel) =>
    page.locator(sel).first().isVisible().catch(() => false);
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
            `${e.tagName.toLowerCase()}.${[...e.classList].join(".")} ${Math.round(r.left)}..${Math.round(r.right)}`,
          );
      }
      return { hs: se.scrollWidth > se.clientWidth + 1, out: out.slice(0, 6) };
    });
    check(!g.hs, `${step}: no horizontal scroll`);
    check(g.out.length === 0, `${step}: nothing past the edge ${g.out.join(" | ")}`);
  };
  const dom = () => page.evaluate(() => document.body.innerHTML.length);
  const changed = async (what, act) => {
    const before = await dom();
    await act();
    await page.waitForTimeout(500);
    check((await dom()) !== before, `${what}: the page changed`);
  };

  // ── 1. the picture at rest ────────────────────────────────────────────
  await page.goto(invite, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  check(await visible("#chat-screen"), "signing in lands on the chat");
  check(await visible("#view"), "one picture sits above the chat");
  const band = (await text("#caption")).trim();
  say(`band="${band}"`);
  check(/tap a cluster/.test(band), "the band reads tap a cluster when nothing is picked");
  check(await visible("#menu-open"), "the list button sits at the end of that row");
  const h1 = await page.locator("#view").boundingBox();
  await gates("the picture at rest");
  await shot("1-rest");

  // ── 2. picking a mark, when the record has anything on its line ───────
  const marks = page.locator(".ss-hit");
  const n = await marks.count();
  say(`marks on the line: ${n}`);
  if (n > 0) {
    await changed("tapping a mark", () => marks.first().click());
    const row = (await text("#caption")).replace(/\s+/g, " ");
    say(`row after a tap: "${row}"`);
    check(/ask/.test(row), "the row offers ask");
    check(/explain/.test(row), "the row offers explain");
    check(/in chat/.test(row), "the row offers in chat");
    const h2 = await page.locator("#view").boundingBox();
    check(Math.abs(h1.height - h2.height) < 2, "the picture keeps its height");
    await gates("a mark picked");
    await shot("2-picked");
  } else {
    const empty = (await text("#view")).replace(/\s+/g, " ");
    say(`nothing on the line: "${empty}"`);
    check(
      /Nothing on your line yet/.test(empty),
      "an empty record says nothing is on your line yet",
    );
    say("NOT VERIFIED picking a mark: no fixture record carries events");
  }

  // ── 3. the lists drawer ───────────────────────────────────────────────
  await changed("opening the lists", () => page.locator("#menu-open").click());
  check(await visible("#menu-body"), "the list button opens the drawer");
  check(await visible("#tab-events"), "the drawer has an events tab");
  check(await visible("#tab-people"), "the drawer has a people tab");
  check(await visible("#menu-search"), "the lists can be searched");
  check(await visible("#menu-add"), "there is a button to add an event");
  const rows = await page.locator("#menu-body .row").count();
  say(`event rows: ${rows}`);
  await gates("the events list");
  await shot("3-events");

  // ── 4. the people list and the person editor ──────────────────────────
  await changed("the people tab", () => page.locator("#tab-people").click());
  const people = await page.locator("#menu-body .row").allInnerTexts();
  say(`people: ${people.slice(0, 6).map((s) => s.replace(/\s+/g, " ")).join(" | ")}`);
  check(people.length > 0, "the people list has rows");
  check(
    people.every((t) => t.trim().split("\n").length === 1),
    "a person's row is one line, with no chip and no second line",
  );
  await gates("the people list");
  await changed("opening a person", () =>
    page.locator("#menu-body .row").first().click(),
  );
  const ed = (await text("#menu-body")).replace(/\s+/g, " ");
  say(`person editor: ${ed.slice(0, 300)}`);
  check(/kind/i.test(ed), "the person's kind field is labelled Kind");
  check(/born to/i.test(ed), "the editor asks who the person was born to");
  check(/bond/i.test(ed), "the editor lists the bonds this person has");
  await gates("the person editor");
  await shot("4-person");

  // ── 5. the sessions sheet ─────────────────────────────────────────────
  if (await visible("#menu-close")) await page.locator("#menu-close").click();
  await page.waitForTimeout(500);
  await changed("opening the sessions sheet", () =>
    page.locator("#sessions-open").click(),
  );
  check(await visible(".fs-sheet"), "a button beside the input opens the sessions sheet");
  const sheet = (await text(".fs-sheet")).replace(/\s+/g, " ");
  say(`sheet: ${sheet.slice(0, 240)}`);
  check(await visible(".fs-search"), "sessions are searchable");
  check(await visible(".fs-new"), "a button at the foot starts a new session");
  await gates("the sessions sheet");
  await shot("5-sessions");
  await page.locator(".fs-scrim.in").click({ position: { x: 10, y: 10 } });
  await page.waitForTimeout(800);

  // ── 6. the account page ───────────────────────────────────────────────
  await changed("opening the account page", () => page.locator("#account").click());
  const acc = (await text(".sn-stack")).replace(/\s+/g, " ");
  say(`account: ${acc.slice(0, 300)}`);
  check(/sign out/i.test(acc), "sign out sits at the bottom");
  check(/speak|out loud/i.test(acc), "there is a row for the coach speaking its replies");
  check(/light|dark|appearance/i.test(acc), "there is a row for light, dark or the phone");
  await gates("the account page");
  await shot("6-account");
  await page.goBack().catch(() => {});
  await page.waitForTimeout(600);

  // ── 7. every icon button is the same size ─────────────────────────────
  const odd = await page.evaluate(() => {
    const out = [];
    for (const e of document.querySelectorAll("button.ico, .ico")) {
      if (!(e instanceof HTMLElement) || e.offsetParent === null) continue;
      const r = e.getBoundingClientRect();
      if (Math.abs(r.width - 44) > 1.5 || Math.abs(r.height - 44) > 1.5)
        out.push(`${e.id || e.className} ${Math.round(r.width)}x${Math.round(r.height)}`);
    }
    return out;
  });
  say(`icon buttons off 44pt: ${odd.join(", ") || "none"}`);
  check(odd.length === 0, "every icon button is a forty-four point target");

  // ── the gates ─────────────────────────────────────────────────────────
  const real = errors.filter((e) => !/\[vite\]|hot-reload|hmr/i.test(e));
  say(`console errors: ${JSON.stringify(real)}`);
  say(`failed requests: ${JSON.stringify(failed)}`);
  check(real.length === 0, "zero console errors beyond the hot-reload socket");
  check(failed.length === 0, "zero failed requests");

  await browser.close();
  say(fails ? `WALK FAIL (${fails})` : "WALK PASS");
  process.exit(fails ? 1 : 0);
})();
