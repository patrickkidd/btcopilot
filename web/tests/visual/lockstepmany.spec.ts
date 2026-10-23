import { expect, test, type Page } from "./fixtures";
import { stateFor } from "./setup";
import { SEND, STREAM } from "./turn";

/** Thirty events the coach adds one call at a time, the stream sending each
 * call with its patch and the next a moment later, the way the server sends
 * them as each call is run. Each line of the coach's work appears with its
 * event already in the list and on the timeline. */

const EDITS = 30;
const FIRST = 9000;

const event = (k: number) => ({
  id: FIRST + k,
  label: `Moved away ${k}`,
  sentence: `Moved away ${k}.`,
  person_name: "",
  person: null,
  dateTime: `${1950 + k}-06-01`,
  endDateTime: null,
  dateCertainty: "certain",
  datePrecision: "day",
  kind: "noted",
  title: `Moved away ${k}`,
  description: `Moved away ${k}`,
  notes: null,
  location: null,
  symptom: null,
  anxiety: null,
  functioning: null,
  relationship: null,
  relationshipTargets: [],
  relationshipTriangles: [],
  spouse: null,
  child: null,
});

const edit = (k: number) => [
  {
    type: "tool_call",
    name: "edit_event",
    args: { kind: "noted", description: `Moved away ${k}`, dateTime: `${1950 + k}-06-01` },
    names: { it: `Moved away ${k}` },
    refusal: null,
  },
  {
    type: "record_patch",
    turn_id: "t1",
    deltas: [
      { item_kind: "event", item_id: String(FIRST + k), field: null, before: null, after: { id: FIRST + k } },
    ],
  },
];

const ENDING = [
  { type: "text", text: "I put those down." },
  {
    type: "done",
    statement: "I put those down.",
    statement_id: 9301,
    discussion_id: 1,
    kind: "turn",
    views: null,
    events: [],
    turn_id: "t1",
  },
];

/** Serves the turn a call at a time, each connection one call and its patch,
 * the browser coming back for the next after a few milliseconds; the record
 * read back holds every event whose patch has gone out. */
async function streamEdits(page: Page): Promise<void> {
  let landed = 0;
  await page.route(SEND, (route) =>
    route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        turn_id: "t1",
        discussion_id: 1,
        statement_id: 9300,
        attachment_name: null,
        attachment_text: null,
      }),
    }),
  );
  await page.route(/\/timeline(\?|$)/, async (route) => {
    const real = await route.fetch();
    const record = await real.json();
    record.events.push(...Array.from({ length: landed }, (_, i) => event(i + 1)));
    await route.fulfill({ response: real, json: record });
  });
  await page.route(STREAM, async (route) => {
    const last = Number(route.request().headers()["last-event-id"] ?? 0);
    const k = last / 2 + 1;
    const events = k <= EDITS ? edit(k) : ENDING;
    if (k <= EDITS) landed = k;
    await route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream", "cache-control": "no-cache" },
      body:
        "retry: 40\n\n" +
        events.map((one, at) => `id: ${last + at + 1}\ndata: ${JSON.stringify(one)}\n\n`).join(""),
    });
  });
}

interface Watched {
  seen: { line: number; listed: string[]; drawn: string[] }[];
  redraws: number[];
  frameAt: number;
}

/** Watches the page from inside: what the events list and the timeline held
 * when each line of the coach's work appeared, and in which frame each redraw
 * of the list landed. */
const watchFrames = () => {
  const w = window as unknown as Watched;
  w.seen = [];
  w.redraws = [];
  w.frameAt = 0;
  const ask = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (done) =>
    ask((at) => {
      w.frameAt = at;
      done(at);
    });
  const ids = (selector: string) =>
    [...document.querySelectorAll<HTMLElement | SVGElement>(selector)].map((one) => one.dataset.event!);
  document.addEventListener("DOMContentLoaded", () => {
    let lines = 0;
    new MutationObserver((changes) => {
      if (changes.some((change) => change.target instanceof Element && change.target.id === "menu-body"))
        w.redraws.push(w.frameAt);
      const now = document.querySelectorAll(".bub.coach .did").length;
      for (; lines < now; lines++)
        w.seen.push({
          line: lines + 1,
          listed: ids("#menu-body .row[data-event]"),
          drawn: ids("#view [data-event]"),
        });
    }).observe(document.body, { childList: true, subtree: true });
  });
};

test.describe("thirty edits, each drawn as its line lands", () => {
  test.use({ storageState: stateFor("moves") });
  // a phone the size of Patrick's in Chromium too
  test.beforeEach(async ({ page }, info) => {
    if (info.project.name === "phone") await page.setViewportSize({ width: 393, height: 852 });
  });

  // R-0898
  test("the list and the timeline hold each event as its line appears, one redraw a frame", async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("console", (m) => void (m.type() === "error" && errors.push(m.text())));
    page.on("pageerror", (e) => void errors.push(e.message));
    await page.addInitScript(watchFrames);
    await streamEdits(page);
    await page.goto("/app/");
    await expect(page.locator("#view .ss")).toBeVisible();
    await page.waitForTimeout(500);
    await page.evaluate(() => void ((window as unknown as Watched).redraws = []));

    await page.locator("#composer").fill("She moved thirty times.");
    await page.locator("#send").click();
    await expect(page.locator(".bub.coach .did")).toHaveCount(EDITS, { timeout: 20_000 });
    await expect(page.locator(".bub.coach").last()).toContainText("I put those down.");

    const { seen, redraws } = await page.evaluate(() => {
      const w = window as unknown as Watched;
      return { seen: w.seen, redraws: w.redraws };
    });
    for (const k of [1, 2, 10, 17, 29, 30]) {
      const at = seen.find((one) => one.line === k)!;
      expect(at.listed, `the list as line ${k} appeared`).toContain(String(FIRST + k));
      expect(at.drawn, `the timeline as line ${k} appeared`).toContain(String(FIRST + k));
    }
    // the list is redrawn as the edits land, not once at the end
    expect(redraws.length).toBeGreaterThanOrEqual(EDITS / 3);
    expect(new Set(redraws).size, "two redraws of the list in one frame").toBe(redraws.length);
    expect(errors).toEqual([]);
  });
});
