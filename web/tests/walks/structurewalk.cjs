// A walk of the three screens people and family structure reach: the person
// editor, the ballot with a person on it, and the meeting with the same person.
//   node structurewalk.js <editor-invite> <coder-invite> <admin-invite> <width> <height> <tag>
const pw = require("playwright");
const BROWSER = pw[process.env.WALK_BROWSER ?? "chromium"];

const [, , editorInvite, coderInvite, adminInvite, W, H, TAG] = process.argv;
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
            `${e.tagName.toLowerCase()}.${[...e.classList].join(".")} ${Math.round(r.left)}..${Math.round(r.right)}`,
          );
      }
      return { hs: se.scrollWidth > se.clientWidth + 1, out: out.slice(0, 6) };
    });
    check(!g.hs, `${step}: no horizontal scroll`);
    check(g.out.length === 0, `${step}: nothing past the edge ${g.out.join(" | ")}`);
  };

  // ── 1. the person editor: born to, and add parents ────────────────────
  await page.goto(editorInvite, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.locator(".caption .listglyph").first().click();
  await page.waitForTimeout(900);
  await page.locator("#tab-people").click();
  await page.waitForTimeout(700);
  // A person of this walk's own, so the run starts from somebody with nobody.
  const who = `Corinne${Date.now() % 1000}`;
  await page.locator("#menu-add").click();
  await page.waitForTimeout(700);
  await page.locator('.editor [data-name="name"]').fill(who);
  await page.locator(".editor .save").click();
  await page.waitForTimeout(1400);
  await page.locator("#menu-body .row").filter({ hasText: who }).first().click();
  await page.waitForTimeout(900);
  const labels = await page.locator(".editor .lab").allInnerTexts();
  say(`editor fields: ${JSON.stringify(labels)}`);
  const said = labels.map((one) => one.trim().toLowerCase());
  check(said.includes("born to"), "the person editor asks who they were born to");
  check(said.includes("bonds"), "the person editor lists the bonds they are in");
  check(
    await visible('.editor .segs[data-name="parents"] .seg'),
    "the couples on the record are offered as choices",
  );
  await gates("the person editor");
  await shot("1-person-editor");

  const before = await page.locator("#menu-body .row").count();
  await page
    .locator('.editor .segs[data-name="parents"] .seg')
    .filter({ hasText: "add parents" })
    .first()
    .click();
  await page.waitForTimeout(1600);
  const after = await page.locator("#menu-body .row").count();
  say(`people before=${before} after=${after}`);
  check(after === before + 2, "add parents puts a father and a mother on the record");
  const names = await page.locator("#menu-body .row .r1").allInnerTexts();
  check(
    names.some((one) => one.trim() === `${who}'s father`),
    `a parent nobody named is named after the child (${names.join(", ")})`,
  );
  await shot("2-parents-added");

  // ── 1b. a bond of their own, made in the bond's own editor ────────────
  const partner = `Theo${Date.now() % 1000}`;
  await page.locator("#menu-add").click();
  await page.waitForTimeout(700);
  await page.locator('.editor [data-name="name"]').fill(partner);
  await page.locator(".editor .save").click();
  await page.waitForTimeout(1400);
  await page.locator("#menu-body .row").filter({ hasText: who }).first().click();
  await page.waitForTimeout(900);
  await page.locator(".editor .bondrow").last().click();
  await page.waitForTimeout(600);
  check(await visible(".editor.bond"), "a bond row opens the bond's own editor");
  await page
    .locator('.editor.bond .segs[data-name="partner"] .seg')
    .filter({ hasText: partner })
    .first()
    .click();
  await page.waitForTimeout(300);
  await page
    .locator('.editor.bond .segs[data-name="married"] .seg')
    .first()
    .click();
  await gates("the bond editor");
  await shot("2b-bond-editor");
  await page.locator(".editor.bond .save").click();
  await page.waitForTimeout(1500);
  await page.locator("#menu-body .row").filter({ hasText: who }).first().click();
  await page.waitForTimeout(900);
  const bonds = await page.locator(".editor .bondrow").allInnerTexts();
  say(`bond rows: ${JSON.stringify(bonds)}`);
  check(
    bonds.some((one) => one.includes(partner) && /married/.test(one)),
    "the bond is a row saying who and whether they married",
  );
  await shot("2c-bond-row");

  // ── 2. the ballot with a person on it ─────────────────────────────────
  await page.goto(coderInvite, { waitUntil: "networkidle" });
  await page.waitForTimeout(1600);
  await page.locator(".tkcard .addbtn").first().click();
  await page.waitForTimeout(1800);
  check(await visible("#ballot-screen"), "the vote opens as its own screen");
  let found = false;
  for (let i = 0; i < 14 && !found; i += 1) {
    found = /a person|a couple/.test(await text("#ballot-body .progress"));
    if (!found) {
      await page.locator("#bl-next").click();
      await page.waitForTimeout(700);
    }
  }
  check(found, "a person or a couple is one of the items on the ballot");
  const versions = await page.locator("#ballot-body .opinion").count();
  const drawn = await page.locator("#ballot-body .opinion svg.fragment").count();
  say(
    `item="${await text("#ballot-body h3")}" versions=${versions} drawn=${drawn}`,
  );
  check(versions >= 2, `the versions are shown (${versions})`);
  check(drawn === versions, `each version is drawn as a family (${drawn})`);
  await gates("the ballot with a person on it");
  await shot("3-ballot-person");

  await page.locator("#bl-change").click();
  await page.waitForTimeout(900);
  check(
    await visible(".bl-sheet .editor"),
    "change opens the person's own editor as a sheet",
  );
  await gates("the person editor over the ballot");
  await shot("4-ballot-editor");
  await page.locator(".bl-sheet .acts .del").click();
  await page.waitForTimeout(800);

  // ── 3. the meeting with the same person ───────────────────────────────
  await page.goto(adminInvite, { waitUntil: "networkidle" });
  await page.waitForTimeout(1800);
  await page.locator("#sessions-open").click();
  await page.waitForTimeout(900);
  await page.locator(".fs-agenda").click();
  await page.waitForTimeout(1600);
  await page.locator(".tb-meet").first().click();
  await page.waitForTimeout(2200);
  check(await visible("#meeting-screen"), "the meeting opens");
  const key = await text("#meeting-stats .mkey");
  const rowNames = await page.locator("#meeting-body .pick, #meeting-body .collapsed span").allInnerTexts();
  const shapes = await page.locator("#meeting-body svg.fragment").count();
  say(`legend="${key.replace(/\n/g, " ")}" shapes=${shapes}`);
  check(/people/.test(key) && /bonds?/.test(key), "the legend counts the family");
  check(
    (await page.locator("#meeting-view circle").count()) > 0,
    "the wire still draws the events",
  );
  check(
    rowNames.some((one) => /Corinne/.test(one)),
    `the person is a row in the list (${rowNames.slice(0, 4).join(" | ")})`,
  );
  check(shapes > 0, `a version of the person is drawn in the room (${shapes})`);
  await gates("the meeting with a person on it");
  await shot("5-meeting-person");

  check(errors.length === 0, `no console errors ${errors.slice(0, 3).join(" | ")}`);
  check(failed.length === 0, `no failed requests ${failed.slice(0, 3).join(" | ")}`);
  say(fails ? `FAILED ${fails}` : "ALL PASS");
  await browser.close();
  process.exit(fails ? 1 : 0);
})();
