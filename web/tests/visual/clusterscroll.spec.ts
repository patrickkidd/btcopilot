import { expect, test, type Page } from "./fixtures";
import { boxOf, shell, stateFor } from "./setup";

/** Clusters come in from the worker while the person is looking: the
 * timeline is drawn again where it stands, never slid away from where the
 * person left it, in every view that shows it. */

test.use({ storageState: stateFor("dense60") });

/** The diagram open and its clusters. */
const opened = (page: Page) =>
  page.evaluate(async () => {
    const id = (window as unknown as { BOOTSTRAP: { diagram: { id: number } } }).BOOTSTRAP.diagram.id;
    const tl = await (await fetch(`/app/timeline?diagram_id=${id}`)).json();
    return { id, clusters: (tl.clusters as { id: string }[]).map((c) => c.id) };
  });

/** A cluster write from the server, as the worker's grouping makes one: a
 * cluster set aside, or brought back; the page has read it once it returns. */
async function write(page: Page, diagram: number, cluster: string, field: string, after: string): Promise<void> {
  const read = page.waitForResponse((r) => r.url().includes("/app/timeline") && r.request().method() === "GET");
  shell(
    [
      "from btcopilot import record",
      "from btcopilot.models.change import Author",
      `record.apply(${diagram}, [{"item_kind": "cluster", "item_id": "${cluster}", "field": "${field}", "after": ${after}}], author=Author.Coach, turn_id="cluster-scroll")`,
    ].join("\n"),
  );
  await read;
  await page.waitForTimeout(800);
}

const setAside = (page: Page, diagram: number, cluster: string, aside: boolean) =>
  write(page, diagram, cluster, "setAside", aside ? "True" : "False");

const slack = (page: Page, view: string) => page.locator(`${view} .ss-scroll`).evaluate((s) => s.scrollWidth - s.clientWidth);

/** The line slid a little way in, to a resting place where it has one. */
const slide = (page: Page, view: string) =>
  page.locator(`${view} .ss-scroll`).evaluate((scroll) => {
    const max = scroll.scrollWidth - scroll.clientWidth;
    const stops = [...scroll.querySelectorAll<HTMLElement>(".ss-snap")]
      .map((stop) => parseFloat(stop.style.left))
      .filter((left) => left > 0 && left < max);
    scroll.scrollLeft = stops.length ? Math.min(...stops) : Math.round(max / 2);
    return scroll.scrollLeft;
  });

const at = (page: Page, view: string) =>
  page.locator(`${view} .ss-scroll`).evaluate((s) => ({ left: s.scrollLeft, end: s.scrollWidth - s.clientWidth }));

/** Every cluster set aside, so the line is its dots alone and rests at the
 * present; then they come back, as clusters arrive once detection finishes:
 * the line is still at the present, its end, however much wider it now is. */
async function staysAtPresent(page: Page, view: string): Promise<void> {
  await expect(page.locator(`${view} .ss-scroll`)).toBeVisible();
  await page.waitForTimeout(500);
  const { id, clusters } = await opened(page);
  for (const one of clusters) await setAside(page, id, one, true);
  try {
    const bare = await at(page, view);
    expect(bare.left).toBeGreaterThanOrEqual(bare.end - 1);
    for (const one of clusters) await setAside(page, id, one, false);
    const back = await at(page, view);
    expect(back.end).toBeGreaterThan(bare.end);
    expect(back.end - back.left).toBeLessThanOrEqual(1);
  } finally {
    // the fixture is the next test's too
    for (const one of clusters) await setAside(page, id, one, false);
  }
}

/** The line slid in, and a cluster's words rewritten under it, as a
 * regroup rewrites them: the line stays where it was slid. */
async function staysSlid(page: Page, view: string): Promise<void> {
  await expect(page.locator(`${view} .ss-scroll`)).toBeVisible();
  await page.waitForTimeout(500);
  expect(await slack(page, view)).toBeGreaterThan(0);
  const before = await slide(page, view);
  expect(before).toBeGreaterThan(0);
  await page.waitForTimeout(500);
  const { id, clusters } = await opened(page);
  await write(page, id, clusters[0], "summary", `"Written again ${Date.now()}"`);
  expect(Math.abs((await at(page, view)).left - before)).toBeLessThanOrEqual(1);
}

/** Where the line's first and last events stand: the ruler's end years are
 * drawn at those two points, and a cluster write moves no event, so the share
 * of the way between them is the same date before and after. */
const ends = (page: Page, view: string) =>
  page.locator(`${view} .ss-line svg`).evaluate((svg) => {
    const at = (anchor: string) => Number(svg.querySelector(`text.ep-yrs[text-anchor="${anchor}"]`)!.getAttribute("x"));
    return { first: at("start"), last: at("end") };
  });

/** The line slid to its middle, and clusters come in and draw it wider: the
 * date that was in the middle of the screen is still there. A cluster is set
 * aside first, one that leaves the line wider than the screen, and comes back. */
async function keepsDate(page: Page, view: string): Promise<void> {
  const scroll = page.locator(`${view} .ss-scroll`);
  await expect(scroll).toBeVisible();
  await page.waitForTimeout(500);
  const { id, clusters } = await opened(page);
  let cluster: string | null = null;
  for (const one of clusters) {
    await setAside(page, id, one, true);
    if ((await slack(page, view)) > 0) {
      cluster = one;
      break;
    }
    await setAside(page, id, one, false);
  }
  expect(cluster, "a cluster whose absence leaves the line wider than the screen").not.toBeNull();
  try {
    const before = await scroll.evaluate((s) => {
      s.scrollLeft = Math.round((s.scrollWidth - s.clientWidth) / 2);
      return { left: s.scrollLeft, half: s.clientWidth / 2, end: s.scrollWidth - s.clientWidth };
    });
    await page.waitForTimeout(500);
    const was = await ends(page, view);
    const share = (before.left + before.half - was.first) / (was.last - was.first);
    await setAside(page, id, cluster!, false);
    const after = await scroll.evaluate((s) => ({ left: s.scrollLeft, end: s.scrollWidth - s.clientWidth }));
    expect(after.end).toBeGreaterThan(before.end);
    const now = await ends(page, view);
    // the same date, as far along the line, is under the middle of the screen
    expect(Math.abs(now.first + share * (now.last - now.first) - after.left - before.half)).toBeLessThanOrEqual(4);
  } finally {
    if ((await opened(page)).clusters.length < clusters.length) await setAside(page, id, cluster!, false);
  }
}

// R-0937
test("the chat's timeline keeps the date in the middle of the screen when clusters come in and widen it", async ({ page }) => {
  await page.goto("/app/");
  await keepsDate(page, "#view");
});

for (const [name, where, view] of [
  ["chat", "/app/", "#view"],
  ["case report", "/app/case-report", "#case-view"],
] as const) {
  // R-0937
  test(`the ${name}'s timeline stays at the present when clusters come in`, async ({ page }) => {
    await page.goto(where);
    await staysAtPresent(page, view);
  });

  // R-0937
  test(`the ${name}'s timeline stays where it was slid when its clusters are written again`, async ({ page }) => {
    await page.goto(where);
    await staysSlid(page, view);
  });
}

/** The first of the line's targets of this kind wholly in sight. */
async function seen(page: Page, target: string) {
  const line = await boxOf(page.locator("#view .ss-scroll"));
  for (const hit of await page.locator(`#view .ss-hit[data-target="${target}"]`).all()) {
    const box = await boxOf(hit);
    if (box.x >= line.x && box.x + box.width <= line.x + line.width) return box;
  }
  throw new Error(`no ${target} wholly in sight`);
}

/** A finger on a point of the line, held as a tap holds, and lifted. */
async function press(page: Page, x: number, y: number): Promise<void> {
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.waitForTimeout(120);
  await page.mouse.up();
  await page.waitForTimeout(800);
}

type Box = { x: number; y: number; width: number; height: number };

const centre = (box: Box) => [box.x + box.width / 2, box.y + box.height / 2] as const;

/** The middle of the part of a target the line shows. */
const shown = (box: Box, line: Box) =>
  [(Math.max(box.x, line.x) + Math.min(box.x + box.width, line.x + line.width)) / 2, box.y + box.height / 2] as const;

const lastPill = (page: Page) => boxOf(page.locator('#view .ss-hit[data-target="cluster"]').last());

// R-0953
test("a tap on the cluster the line shows after the page loads leaves the line where it rests", async ({ page }) => {
  await page.goto("/app/");
  const scroll = page.locator("#view .ss-scroll");
  await expect(scroll).toBeVisible();
  await page.waitForTimeout(500);
  const before = await at(page, "#view");
  expect(before.end).toBeGreaterThan(0);
  await press(page, ...shown(await lastPill(page), await boxOf(scroll)));
  expect((await at(page, "#view")).left).toBe(before.left);
});

test.describe("a tap on an event in sight", () => {
  test.use({ storageState: stateFor("whitlock") });

  // R-0953
  test("leaves the line where it stands, a little short of a resting place", async ({ page }) => {
    await page.goto("/app/");
    const scroll = page.locator("#view .ss-scroll");
    await expect(scroll).toBeVisible();
    await page.waitForTimeout(500);
    // where a swipe or a redraw can leave it, near enough a resting place for
    // the browser to slide it there were snapping back on
    const before = await scroll.evaluate((s) => (s.scrollLeft = s.scrollWidth - s.clientWidth - 14));
    await page.waitForTimeout(500);
    for (let i = 0; i < 2; i++) {
      await press(page, ...centre(await seen(page, "zone")));
      expect((await at(page, "#view")).left).toBe(before);
    }
  });
});

// R-0953
test("a tap on a cluster partly out of sight brings it into view", async ({ page }) => {
  await page.goto("/app/");
  const scroll = page.locator("#view .ss-scroll");
  await expect(scroll).toBeVisible();
  await page.waitForTimeout(500);
  await scroll.evaluate((s) => (s.scrollLeft = 0));
  await page.waitForTimeout(500);
  const line = await boxOf(scroll);
  const pill = await lastPill(page);
  expect(pill.x + pill.width).toBeGreaterThan(line.x + line.width);
  const start = pill.x - line.x;
  await press(page, ...shown(pill, line));
  const after = (await at(page, "#view")).left;
  expect(after).toBeGreaterThan(0);
  expect(after).toBeLessThanOrEqual(start);
});
