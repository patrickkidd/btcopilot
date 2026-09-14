import { expect, test, type Page, type TestInfo } from "@playwright/test";

/** The review walks: whole journeys through the coding, ballot and meeting
 * screens, driven against a running review sandbox rather than the fixture
 * records the goldens use.
 *
 * They need a sandbox that already holds the review fixture state (the scripts
 * in `~/worktrees/fd362-sandbox` put it there) and one sign-in link per fixture
 * person, named in the environment:
 *
 *   SANDBOX_URL     the sandbox, e.g. https://turin:8891
 *   INVITE_TABLE    a link for the admin who runs the table and the meeting
 *   INVITE_CODER    a link for a coder on the ballot
 *   INVITE_EDITOR   a link for the person whose family is edited
 *   INVITE_PRO      a link for the professional licence
 *
 * Without those links the specs skip, so a plain golden run is unaffected.
 * Nothing here compares a picture: each check is a sentence about behaviour,
 * and a failure names the step. */

export const link = (who: string): string | undefined =>
  process.env[`INVITE_${who.toUpperCase()}`];

/** Skip the file unless the sandbox named every link it drives. */
export function sandboxOnly(...who: string[]): void {
  const missing = who.filter((one) => !link(one));
  test.skip(
    !process.env.SANDBOX_URL || missing.length > 0,
    `needs a review sandbox and sign-in links: ${missing.map((one) => `INVITE_${one.toUpperCase()}`).join(", ")}`,
  );
}

export function need(who: string): string {
  const found = link(who);
  if (!found) throw new Error(`INVITE_${who.toUpperCase()} is not set`);
  return found;
}

/** The gates every walk runs, and the little words each step is written in.
 * A check is soft, so one broken step does not hide the rest of the journey. */
export function walker(page: Page, info: TestInfo) {
  const errors: string[] = [];
  const failed: string[] = [];
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

  // Written straight out rather than attached: an attachment is a promise, and
  // a walk that fires twenty of them without waiting leaves the test holding
  // work it can never finish.
  const say = (s: string) => console.log(s);
  const check = (ok: boolean, what: string) =>
    expect.soft(ok, what).toBeTruthy();
  // Saved beside the run's other output rather than attached: an attachment is
  // more machinery than a picture of a step needs, and the runner keeps the
  // whole folder.
  const shot = (n: string) =>
    page.screenshot({ path: info.outputPath(`${n}.png`) });
  const text = (sel: string) =>
    page
      .locator(sel)
      .first()
      .innerText()
      .catch(() => "");
  const visible = (sel: string) =>
    page
      .locator(sel)
      .first()
      .isVisible()
      .catch(() => false);
  const gates = async (step: string) => {
    // A page that never answers is a failure of this step, not a run that eats
    // its whole budget in silence.
    await page.waitForLoadState("domcontentloaded").catch(() => {});
    const asked = page.evaluate(() => {
      const se = document.scrollingElement!;
      const out: string[] = [];
      for (const e of document.querySelectorAll("body *")) {
        if (!(e instanceof HTMLElement) || e.offsetParent === null) continue;
        // A row held open by a swipe is slid left on purpose to show the
        // actions behind it, so its own words sit off the edge while it is
        // open. Everything else must stay inside.
        if (e.closest(".row.swiped")) continue;
        const r = e.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;
        if (r.right > innerWidth + 1 || r.left < -1)
          out.push(
            `${e.tagName.toLowerCase()}.${[...e.classList].join(".")} ${Math.round(r.left)}..${Math.round(r.right)}`,
          );
      }
      return { hs: se.scrollWidth > se.clientWidth + 1, out: out.slice(0, 6) };
    });
    const g = await Promise.race([
      asked,
      new Promise<null>((done) => setTimeout(() => done(null), 20_000)),
    ]);
    if (!g) {
      check(false, `${step}: the page did not answer within twenty seconds`);
      return;
    }
    check(!g.hs, `${step}: no horizontal scroll`);
    check(
      g.out.length === 0,
      `${step}: nothing past the edge ${g.out.join(" | ")}`,
    );
  };
  const dom = () => page.evaluate(() => document.body.innerHTML.length);
  const changed = async (what: string, act: () => Promise<unknown>) => {
    const before = await dom();
    await act();
    await page.waitForTimeout(500);
    check((await dom()) !== before, `${what}: the page changed`);
  };
  /** The two gates that hold for the whole journey rather than one step. */
  const quiet = async () => {
    const real = errors.filter((e) => !/\[vite\]|hot|ws:\/\/|wss:\/\//i.test(e));
    check(
      real.length === 0,
      `zero console errors beyond the hot-reload socket ${real.slice(0, 3).join(" | ")}`,
    );
    check(
      failed.length === 0,
      `zero failed requests ${failed.slice(0, 3).join(" | ")}`,
    );
  };

  return { errors, failed, say, check, shot, text, visible, gates, changed, dom, quiet };
}
