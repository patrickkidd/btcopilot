import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { badLines, thread, watch } from "./gate";

// Threads drawn from stored turns: every tool call the coach made is one line
// under its reply, live and after a reload; a failed last turn offers try
// again, and try again resumes that turn without saying anything new.
//
// THREAD_LINKS names a JSON file of { name: { link } }, one sign-in link per
// thread, as btcopilot/tests/frontend/seedthreads.py prints it; "std" is the
// link seedturns.py prints. Without it these skip.

const LINKS: Record<string, { link: string }> = process.env.THREAD_LINKS
  ? JSON.parse(readFileSync(process.env.THREAD_LINKS, "utf8"))
  : {};
const DATE = /\b\d{4}-\d{2}-\d{2}\b/;

test.describe(() => {
  test.skip(!process.env.SANDBOX_URL || !process.env.THREAD_LINKS, "needs SANDBOX_URL and THREAD_LINKS");

  for (const key of Object.keys(LINKS)) {
    // R-0478, R-0186
    test(`${key}: every call is one line under its reply`, async ({ page }, info) => {
      const w = watch(page);
      await page.goto(LINKS[key].link, { waitUntil: "load" });
      await page.waitForSelector("#chat");
      await page.waitForTimeout(1500);
      const s = await thread(page);
      const coach = s.statements.filter((x) => x.role === "coach");
      // a turn that failed before its reply still shows its calls, in a bubble
      // of its own
      const extra = s.statements.filter((x) => x.unfinished && x.tools.length).length;
      const lastUnfinished = s.statements.at(-1)?.unfinished === true;
      const all = s.bubs.flatMap((b) => b.lines);
      const calls = s.statements.reduce((n, x) => n + x.tools.length, 0);
      console.log(
        `${info.project.name} [${key}] bubbles=${s.bubs.length} statements=${s.statements.length} calls=${calls} lines=${all.length} retry=${s.retry} hscroll=${s.hscroll} outside=${s.outside.length}\n` +
          `  bad lines=${JSON.stringify(badLines(all))} dated=${JSON.stringify(all.filter((l) => DATE.test(l)).slice(0, 3))}\n` +
          `  errors=${JSON.stringify(w.bad)}`,
      );
      expect.soft(badLines(all)).toEqual([]);
      expect.soft(all.filter((l) => DATE.test(l))).toEqual([]);
      expect.soft(w.bad).toEqual([]);
      expect.soft(s.hscroll).toBeLessThanOrEqual(0);
      expect.soft(s.outside).toEqual([]);
      expect.soft(s.bubs.length).toBe(s.statements.length + extra);
      expect.soft(s.retry).toBe(lastUnfinished ? 1 : 0);
      expect.soft(all.length, "every stored call is drawn, refused ones too").toBe(calls);
      for (const st of coach) {
        const b = s.bubs.find((x) => x.statement === String(st.id));
        expect.soft(b?.lines.length, `coach ${st.id} lines`).toBe(st.tools.length);
      }
      if (info.project.name === "sandbox-phone")
        await page.screenshot({ path: info.outputPath(`${key}.png`) });
    });
  }

  // R-0477
  test("try again resumes the failed turn and says nothing new", async ({ page }, info) => {
    // Without a model the resumed turn fails again, which is what lets the
    // same failed turn be tried twice; sandboxlive tries it with one.
    test.skip(!LINKS.std || !process.env.SANDBOX_NO_MODEL, "needs the std thread and SANDBOX_NO_MODEL=1");
    const w = watch(page);
    await page.goto(LINKS.std.link, { waitUntil: "load" });
    await page.waitForSelector("#chat button.retry");
    await page.waitForTimeout(800);
    const before = await thread(page);
    const linesBefore = before.bubs.flatMap((b) => b.lines);
    for (let round = 1; round <= 2; round++) {
      const resumed = page.waitForResponse((r) => /\/resume$/.test(r.url()));
      await page.locator("#chat button.retry").click();
      const r = await resumed;
      const changedNow = (await thread(page)).html !== before.html;
      await page.waitForSelector("#chat button.retry", { timeout: 30_000 });
      await page.waitForTimeout(800);
      const after = await thread(page);
      const fresh = await page.evaluate(
        async (id) => (await fetch(`/app/sessions/${id}`)).json(),
        before.session,
      );
      const stmts = fresh.statements ?? fresh.session?.statements;
      const linesAfter = after.bubs.flatMap((b) => b.lines);
      console.log(
        `${info.project.name} round ${round}: resume ${r.request().method()} -> ${r.status()}; page changed on click=${changedNow}; posts=${JSON.stringify(w.posts)}\n` +
          `  statements ${before.statements.length}->${stmts?.length}; bubbles ${before.bubs.length}->${after.bubs.length}; retry=${after.retry}`,
      );
      expect.soft(r.request().method()).toBe("POST");
      expect.soft(w.posts.filter((p) => /\/chat$|\/statements$/.test(p))).toEqual([]);
      expect.soft(stmts?.length).toBe(before.statements.length);
      expect.soft(linesAfter).toEqual(linesBefore);
      expect.soft(changedNow).toBe(true);
    }
    await page.reload({ waitUntil: "load" });
    await page.waitForTimeout(1500);
    const reloaded = await thread(page);
    expect.soft(reloaded.bubs.flatMap((b) => b.lines)).toEqual(linesBefore);
    expect.soft(w.bad).toEqual([]);
  });
});
