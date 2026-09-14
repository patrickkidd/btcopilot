// A coder's own sentence about a marriage and about a parent: the scribe adds
// the people and the bond, and writes what it did under the coder's words.
//   node codingscribe.cjs <coder-invite> <width> <height> <tag>
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

  const code = async (turn, sentence) => {
    await page.locator("#coding-chat .bub.line").nth(turn).click();
    await page.waitForTimeout(400);
    await page.locator("#coding-composer").click();
    await page.keyboard.type(sentence);
    say(
      `typed into the box: "${await page.locator("#coding-composer").innerText()}"` +
        ` send enabled=${await page.locator("#coding-send").isEnabled()}`,
    );
    await page.locator("#coding-send").click();
    await page.waitForTimeout(25000);
    const lines = await page.locator("#coding-chat .did").allInnerTexts();
    return lines;
  };

  await page.goto(invite, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  if (await visible("#task-screen")) {
    say(`the one card says: ${(await text("#task-body")).replace(/\s+/g, " ")}`);
    await page.locator("#task-screen .addbtn").first().click();
    await page.waitForTimeout(2500);
  } else {
    await page.locator("#sessions-open").click();
    await page.waitForTimeout(800);
    const card = page.locator(".fs-task").first();
    say(`the card says: ${(await card.innerText()).replace(/\s+/g, " ")}`);
    await card.click();
    await page.waitForTimeout(2000);
  }
  check(await visible("#coding-screen"), "the coding thread opens");
  await shot("1-thread");
  if (!(await visible("#coding-screen"))) {
    say("cannot drive the scribe: no coding task on this fixture");
    await browser.close();
    process.exit(1);
  }

  const married = await code(6, "Marcus and Delphine married in 1970.");
  say(`after the marriage sentence: ${JSON.stringify(married.slice(-3))}`);
  check(
    married.some((l) => /Marcus & Delphine/.test(l) && /married/.test(l)),
    "a sentence about a marriage is written as a bond line",
  );

  const born = await code(7, "Corinne is the daughter of Marcus and Delphine.");
  say(`after the parent sentence: ${JSON.stringify(born.slice(-3))}`);
  check(
    born.some((l) => /Corinne/.test(l) && /Marcus & Delphine/.test(l)),
    "a sentence about a parent is written as a birth line",
  );
  check(
    (await page.locator("#coding-chat .bub.said").count()) >= 2,
    "the coder's own words stay in the thread under the line",
  );
  await shot("2-written");

  const real = errors.filter((e) => !/\[vite\]|hot-reload|hmr/i.test(e));
  say(`console errors: ${JSON.stringify(real)}`);
  say(`failed requests: ${JSON.stringify(failed)}`);
  check(real.length === 0, "zero console errors beyond the hot-reload socket");
  check(failed.length === 0, "zero failed requests");

  await browser.close();
  say(fails ? `WALK FAIL (${fails})` : "WALK PASS");
  process.exit(fails ? 1 : 0);
})();
