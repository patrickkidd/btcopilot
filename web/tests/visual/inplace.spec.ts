import { expect, test, type Page } from "./fixtures";
import { stateFor } from "./setup";

/** A list drawn from the record changes in place when the record is read
 * again: the rows already on screen are the same elements afterwards, and the
 * list stays scrolled where it was. */

test.use({ storageState: stateFor("case-report-dense") });

/** The drawer's list on its tab: beside the chat on a computer, its own
 * screen on a phone. */
async function list(page: Page, tab: string): Promise<void> {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  if (await page.locator("#menu-open").isVisible()) await page.locator("#menu-open").click();
  await page.locator(tab).click();
  await expect(page.locator("#menu-body").locator(".row, .qrow").first()).toBeVisible();
}

/** Every row marked, the list scrolled halfway; what was marked and where. */
const mark = (page: Page, rows: string) =>
  page.evaluate((rows) => {
    const body = document.querySelector<HTMLElement>("#menu-body")!;
    body.style.scrollBehavior = "auto";
    body.scrollTop = Math.round((body.scrollHeight - body.clientHeight) / 2);
    const marked = [...body.querySelectorAll<HTMLElement>(rows)];
    for (const row of marked) (row as unknown as { kept: boolean }).kept = true;
    (window as unknown as { marked: HTMLElement[] }).marked = marked;
    return { rows: marked.length, top: body.scrollTop };
  }, rows);

/** The marked rows still on the page with their mark, and the list's offset. */
const after = (page: Page) =>
  page.evaluate(() => {
    const marked = (window as unknown as { marked: HTMLElement[] }).marked;
    return {
      kept: marked.filter((row) => row.isConnected && (row as unknown as { kept: boolean }).kept).length,
      top: document.querySelector<HTMLElement>("#menu-body")!.scrollTop,
    };
  });

/** A write to the record from outside this view, which the page reads back. */
const write = (page: Page, path: string, body: object) =>
  page.evaluate(
    async ([path, body]) => {
      const csrf = document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')!.content;
      const diagram = (window as unknown as { BOOTSTRAP: { diagram: { id: number } } }).BOOTSTRAP.diagram.id;
      const answer = await fetch(`/app/${path}?diagram_id=${diagram}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify(body),
      });
      return answer.status;
    },
    [path, body] as const,
  );

/** Every marked row still there, and the offset where it was, to the pixel a
 * device scale of two rounds by. */
async function stays(page: Page, before: { rows: number; top: number }): Promise<void> {
  const now = await after(page);
  expect(now.kept).toBe(before.rows);
  expect(Math.abs(now.top - before.top)).toBeLessThanOrEqual(1);
}

const reread = (page: Page) => page.waitForResponse((r) => r.url().includes("/app/timeline") && r.request().method() === "GET");

/** A day after every event the fixture holds, a new one each run, since the
 * record refuses the same event twice and the fixtures are installed once per
 * run of every browser. */
const late = () => {
  const pick = (n: number) => 1 + Math.floor(Math.random() * n);
  return `${2089 + pick(10)}-${String(pick(12)).padStart(2, "0")}-${String(pick(28)).padStart(2, "0")}`;
};

const lateEvent = async (page: Page) => {
  const person = await page.evaluate(async () => {
    const id = (window as unknown as { BOOTSTRAP: { diagram: { id: number } } }).BOOTSTRAP.diagram.id;
    return (await (await fetch(`/app/timeline?diagram_id=${id}`)).json()).people[0].id as number;
  });
  return { kind: "noted", title: "Moved abroad", description: "Moved abroad for good", dateTime: late(), person };
};

// R-0937
test("the events list keeps its rows and where it was scrolled when an event is added", async ({ page }) => {
  await list(page, "#tab-events");
  const before = await mark(page, ".row[data-event]");
  const body = await lateEvent(page);
  const read = reread(page);
  expect(await write(page, "events", body)).toBe(201);
  await read;
  await expect(page.locator("#menu-body .row[data-event]")).toHaveCount(before.rows + 1);
  await stays(page, before);
});

// R-0937
test("the people list keeps its rows and where it was scrolled when a person is added", async ({ page }) => {
  await list(page, "#tab-people");
  const before = await mark(page, ".row[data-person]");
  const read = reread(page);
  expect(await write(page, "people", { name: `Zuzana ${late()}`, last_name: "Zywiec" })).toBe(201);
  await read;
  await expect(page.locator("#menu-body .row[data-person]")).toHaveCount(before.rows + 1);
  await stays(page, before);
});

// R-0937
test("the questions list keeps its rows and where it was scrolled when the record is read again", async ({ page }) => {
  await list(page, "#tab-questions");
  const before = await mark(page, ".qrow, .irow");
  expect(before.rows).toBeGreaterThan(0);
  const body = await lateEvent(page);
  const read = reread(page);
  expect(await write(page, "events", body)).toBe(201);
  await read;
  await page.waitForTimeout(300);
  await stays(page, before);
});
