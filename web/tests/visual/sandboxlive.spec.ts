import { expect, test, type Page } from "@playwright/test";
import { badLines, deadTaps, settle, stored, tap, thread, trackRequests, watch, watchDom } from "./gate";
import { need, sandboxOnly } from "./sandbox";

// Real coach turns on the sandbox: try again finishes the failed turn with a
// genuine reply, and a new message gets one, each reading the same after two
// reloads. INVITE_TURNS is the link seedturns.py prints; SANDBOX_LIVE=1 says
// the walk may make model calls.
//
// This walk passes no key itself — it uses whatever model the sandbox server
// was started with: local Ollama by default, which costs nothing, or with
// SANDBOX_MODEL=anthropic the ANTHROPIC_TESTING_KEY, never production's key;
// this walk does not check which.

const FAILURE_TEXT = /did not finish that turn/i;

/** Wait on the server, not the page, until the session's last statement is a
 * finished reply. */
async function finished(page: Page, sessionId: number, minCount: number, timeoutMs: number) {
  const start = Date.now();
  let stmts: any[] | null = null;
  while (Date.now() - start < timeoutMs) {
    stmts = await stored(page, sessionId);
    const last = stmts?.at(-1);
    if (stmts && stmts.length >= minCount && last && last.unfinished !== true)
      return { stmts, last, timedOut: false };
    await page.waitForTimeout(2000);
  }
  stmts = (await stored(page, sessionId)) ?? stmts ?? [];
  return { stmts, last: stmts.at(-1), timedOut: true };
}

async function reloaded(page: Page) {
  await settle(page);
  await page.reload({ waitUntil: "load" });
  await page.waitForTimeout(1200);
  return thread(page);
}

test.describe(() => {
  sandboxOnly("turns");
  test.skip(!process.env.SANDBOX_LIVE, "makes real model calls; set SANDBOX_LIVE=1");
  test.describe.configure({ timeout: 240_000 });

  // R-0477
  test("try again finishes the failed turn with a real reply", async ({ page }, info) => {
    await watchDom(page);
    trackRequests(page);
    const w = watch(page);
    await page.goto(need("turns"), { waitUntil: "load" });
    await page.waitForSelector("#chat button.retry");
    await page.waitForTimeout(800);
    const before = await thread(page);
    const users = before.bubs.filter((b) => b.role === "user").length;

    const resumed = page.waitForResponse((r) => /\/app\/turns\/.+\/resume$/.test(r.url()), {
      timeout: 60_000,
    });
    await tap(page, page.locator("#chat button.retry"));
    const r = await resumed;
    const done = await finished(page, before.session, before.statements.length + 1, 150_000);
    expect.soft(done.timedOut, "the resumed turn finished within 150s").toBeFalsy();
    expect.soft(done.stmts.length, "resume adds exactly the coach reply").toBe(
      before.statements.length + 1,
    );

    const after = await reloaded(page);
    const reply = after.bubs.filter((b) => b.role === "coach").at(-1);
    const lines = after.bubs.flatMap((b) => b.lines);
    const calls = (done.stmts.at(-1)?.tools ?? []).map((t: any) => JSON.stringify([t.name, t.args]));
    console.log(
      `${info.project.name} resume: statements ${before.statements.length}->${done.stmts.length}; retry ${after.retry}; ` +
        `repeated calls ${calls.length - new Set(calls).size}; errors ${JSON.stringify(w.bad)}`,
    );
    await page.screenshot({ path: info.outputPath("resume.png") });
    expect.soft(r.request().method()).toBe("POST");
    expect.soft(after.bubs.filter((b) => b.role === "user").length, "resume says nothing new").toBe(users);
    expect.soft(after.retry, "try again is gone once the turn finished").toBe(0);
    expect.soft(reply?.text ?? "").not.toMatch(FAILURE_TEXT);
    expect.soft((reply?.text ?? "").length, "the reply has words beyond its lines").toBeGreaterThan(
      (reply?.lines ?? []).join("").length + 10,
    );
    expect.soft(new Set(reply?.lines ?? []).size, "no line twice in the resumed reply").toBe(
      (reply?.lines ?? []).length,
    );
    const again = await reloaded(page);
    expect.soft(again.bubs.flatMap((b) => b.lines), "lines stable across reloads").toEqual(lines);
    expect.soft(w.bad).toEqual([]);
    expect.soft(deadTaps, "every tap changes the page").toEqual([]);
  });

  // R-0478
  test("a new message gets a real reply whose lines survive a reload", async ({ page }, info) => {
    await watchDom(page);
    trackRequests(page);
    const w = watch(page);
    await page.goto(need("turns"), { waitUntil: "load" });
    await page.waitForSelector("#chat");
    await page.waitForTimeout(800);
    const before = await thread(page);

    await tap(page, page.locator("#composer"));
    await page.keyboard.type("My dad's name was Walter, he was born in 1931.");
    await tap(page, page.locator("#send"));
    const done = await finished(page, before.session, before.statements.length + 2, 90_000);
    const after = await reloaded(page);
    const reply = after.bubs.filter((b) => b.role === "coach").at(-1);
    console.log(
      `${info.project.name} new turn: statements ${before.statements.length}->${done.stmts.length}; ` +
        `lines ${JSON.stringify(reply?.lines)}; errors ${JSON.stringify(w.bad)}`,
    );
    await page.screenshot({ path: info.outputPath("newturn.png") });
    expect.soft(done.timedOut, "the turn finished within 90s").toBeFalsy();
    expect.soft(done.last?.failure, "no failure recorded").toBeFalsy();
    expect.soft(after.retry).toBe(0);
    expect.soft(reply?.text ?? "").not.toMatch(FAILURE_TEXT);
    const again = await reloaded(page);
    const last = again.bubs.filter((b) => b.role === "coach").at(-1);
    expect.soft(last?.lines, "lines stable across reloads").toEqual(reply?.lines);
    expect.soft(badLines(again.bubs.flatMap((b) => b.lines))).toEqual([]);
    expect.soft(w.bad).toEqual([]);
    expect.soft(deadTaps, "every tap changes the page").toEqual([]);
  });
});
