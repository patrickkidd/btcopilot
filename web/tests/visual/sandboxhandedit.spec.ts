import { expect, test, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { deadTaps, tap, watch, watchDom } from "./gate";
import { need, sandboxOnly } from "./sandbox";

// Hand edits on the lists drawer: each one writes one change row by the user,
// with the version it made, and what the page refuses it says in plain words
// without sending anything. INVITE_TURNS is the link seedturns.py prints;
// SANDBOX_PG names the sandbox's Postgres container, read only.

const sql = (q: string) =>
  execFileSync("docker", [
    "exec",
    "-e",
    "PGOPTIONS=-c default_transaction_read_only=on",
    process.env.SANDBOX_PG as string,
    "psql",
    "-U",
    "familydiagram",
    "-d",
    "familydiagram",
    "-tAc",
    `select coalesce(json_agg(t), '[]') from (${q}) t`,
  ])
    .toString()
    .trim();
const rows = (q: string) => JSON.parse(sql(q)) as any[];

/** The family the page is on, as the page was handed it. */
const diagramId = (page: Page): Promise<number> =>
  page.evaluate(() => (window as any).BOOTSTRAP.diagram.id);
const changes = (d: number) =>
  rows(`select id, author, version, deltas from diagram_changes where diagram_id=${d} order by id`);
const version = (d: number) => rows(`select version from diagrams where id=${d}`)[0].version;

async function openList(page: Page) {
  await page.waitForTimeout(1000);
  const open = page.locator("#menu-open");
  if (await open.isVisible().catch(() => false)) await tap(page, open);
  await page.locator("#menu-body .row[data-event]").first().waitFor();
}

test.describe(() => {
  sandboxOnly("turns");
  test.skip(!process.env.SANDBOX_PG, "needs SANDBOX_PG, the sandbox's database container");
  test.describe.configure({ timeout: 180_000 });

  // R-0084
  test("hand edits to events each write one change row by the user", async ({ page }, info) => {
    await watchDom(page);
    const { bad } = watch(page);
    const log = (s: string) => console.log(`[${info.project.name}] ${s}`);
    await page.goto(need("turns"), { waitUntil: "load" });
    const d = await diagramId(page);
    await openList(page);

    // words changed on an event
    const before = changes(d);
    const v0 = version(d);
    const row = page.locator("#menu-body .row[data-event]").first();
    const eid = await row.getAttribute("data-event");
    await tap(page, row);
    const words = `Hand edit ${info.project.name} ${Date.now() % 100000}`;
    await page.locator("#menu-body .editor [data-name=description]").fill(words);
    const patch = page.waitForResponse(
      (r) => r.request().method() === "PATCH" && /\/app\/events\//.test(r.url()),
    );
    await tap(page, page.locator("#menu-body .editor .save"));
    await patch;
    await page.waitForTimeout(800);
    const new1 = changes(d).slice(before.length);
    log(`edit event ${eid}: new rows ${new1.length}; version ${v0}->${version(d)}`);
    expect(new1.length).toBe(1);
    expect(new1[0].author).toBe("user");
    expect(new1[0].version).toBe(v0 + 1);
    await page.reload({ waitUntil: "load" });
    await openList(page);
    expect(await page.locator(`#menu-body .row[data-event="${eid}"]`).innerText()).toContain(words);

    // a noted event added, then deleted
    const b2 = changes(d).length;
    await tap(page, page.locator("#menu-add"));
    const ed = page.locator("#menu-body .editor").first();
    await tap(page, ed.locator('.segs[data-name=kind] .seg[data-value="noted"]'));
    await ed.locator("[data-name=description]").fill(`Added by hand ${info.project.name}`);
    const post = page.waitForResponse(
      (r) => r.request().method() === "POST" && /\/app\/events(\?|$)/.test(r.url()),
    );
    await tap(page, ed.locator(".save"));
    const newId = (await (await post).json()).id;
    await page.waitForTimeout(800);
    expect(changes(d).length - b2).toBe(1);
    const b3 = changes(d).length;
    await tap(page, page.locator(`#menu-body .row[data-event="${newId}"]`));
    const del = page.waitForResponse(
      (r) => r.request().method() === "DELETE" && /\/app\/events\//.test(r.url()),
    );
    await tap(page, page.locator("#menu-body .editor .del"));
    await del;
    await page.waitForTimeout(800);
    expect(changes(d).length - b3).toBe(1);
    expect(await page.locator(`#menu-body .row[data-event="${newId}"]`).count()).toBe(0);
    const clean = [...bad];

    // a noted event with no words is stopped on the page
    const b5 = changes(d).length;
    await tap(page, page.locator("#menu-add"));
    const e5 = page.locator("#menu-body .editor").first();
    await tap(page, e5.locator('.segs[data-name=kind] .seg[data-value="noted"]'));
    await tap(page, e5.locator(".save"));
    await page.waitForTimeout(600);
    expect((await e5.locator(".refused").allInnerTexts()).join(" ")).toMatch(/noted event needs/);

    // a shift that moved nothing is stopped on the page and nothing is sent
    await page.reload({ waitUntil: "load" });
    await openList(page);
    const n = bad.length;
    const posts: string[] = [];
    page.on("request", (r) => {
      if (r.method() === "POST" && /\/app\/events(\?|$)/.test(r.url())) posts.push(r.url());
    });
    await tap(page, page.locator("#menu-add"));
    const e6 = page.locator("#menu-body .editor").first();
    await tap(page, e6.locator('.segs[data-name=kind] .seg[data-value="shift"]'));
    await e6.locator("[data-name=description]").fill("Shift that moved nothing");
    await tap(page, e6.locator(".save"));
    await page.waitForTimeout(3000);
    log(`stopped on the page: new rows ${changes(d).length - b5}`);
    await page.screenshot({ path: info.outputPath("refused.png") });
    expect(posts.length).toBe(0);
    expect((await e6.locator(".refused").allInnerTexts()).join(" ")).toMatch(/shift needs/);
    expect(await page.locator("#menu-body .editor").count()).toBe(1);
    expect(bad.slice(n)).toEqual([]);

    // a refusal the server still sends is said in plain words, and goes the
    // moment a field changes
    const m = bad.length;
    await tap(page, e6.locator('.segs[data-name=kind] .seg[data-value="noted"]'));
    expect(await e6.locator(".refused").count()).toBe(0);
    await e6.locator("[data-name=dateTime]").fill("2020-05-01");
    await e6.locator("[data-name=endDateTime]").fill("2019-01-01");
    const post7 = page.waitForResponse(
      (r) => r.request().method() === "POST" && /\/app\/events(\?|$)/.test(r.url()),
    );
    await tap(page, e6.locator(".save"));
    const p7 = await post7;
    await page.waitForTimeout(3000);
    expect(p7.status()).toBe(400);
    expect(await e6.locator(".refused").allInnerTexts()).toEqual([
      "The end date is before the start date.",
    ]);
    await e6.locator("[data-name=endDateTime]").fill("2021-01-01");
    expect(await e6.locator(".refused").count()).toBe(0);
    expect(await page.locator("#menu-body .editor").count()).toBe(1);
    expect(bad.slice(m).filter((b) => !b.startsWith("http 400"))).toEqual([]);
    expect(clean).toEqual([]);
    expect.soft(deadTaps, "every tap changes the page").toEqual([]);
  });
});
