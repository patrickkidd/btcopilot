import { expect, test, type Page } from "@playwright/test";
import { watch } from "./gate";
import { flask, stateFor, username, boxOf } from "./setup";

/** Every jump goes one way, from wherever it starts. A teal chip under an
 * impression's "Based on:" goes where the same chip in the thread goes: an
 * event is picked on the picture, which opens if it was folded, and a message
 * is brought into view; nothing goes into the message box, which is what an
 * amber chip does. The day an impression was raised goes to the message that
 * raised it, and a session tapped in the sessions drawer goes to the line where
 * it starts. The thread glides there and rings what it landed on, and jumps
 * without the glide for a reader who asks for less motion (Patrick,
 * 2026-10-01). Twelve sittings, so the words are far up the thread. */

test.use({ storageState: stateFor("sittings") });

const PIC = "#chat-screen > .pic";
const ID = "i90";
const ROW = `.irow[data-q="${ID}"]`;

type Said = { id: number; session_id: number; text: string };

/** The page with one impression added to what it is handed, resting on the
 * record's event and on one message, and raised in another; both messages are
 * far up the thread. */
async function open(page: Page): Promise<{ event: string; rests: Said; raised: Said }> {
  await page.addInitScript(() => localStorage.setItem("fd-home-screen-asked", String(Date.now())));
  const said: Said[] = await (await page.request.get("/app/statements")).json();
  const [rests, raised] = [said[3], said[6]];
  let event = "";
  await page.route("**/app/timeline*", async (route) => {
    const real = await route.fetch();
    const timeline = await real.json();
    const one = timeline.events[0];
    event = one.label;
    timeline.asked_questions = [
      ...timeline.asked_questions,
      {
        id: ID,
        text: "When things get tense at home, someone in the family moves away.",
        kind: "impression",
        open: true,
        asked_at: "2026-09-20",
        asked_in: { discussion_id: raised.session_id, statement_id: raised.id },
        evidence: [
          { kind: "event", id: one.id, label: one.label },
          { kind: "statement", id: rests.id, label: "What she said first", discussion_id: rests.session_id },
        ],
        pushback: null,
      },
    ];
    await route.fulfill({ response: real, json: timeline });
  });
  await page.goto("/app/");
  await expect(page.locator("#chat .bub").first()).toBeVisible();
  await page.waitForTimeout(1200);
  return { event, rests, raised };
}

const toQuestions = async (page: Page) => {
  const list = page.locator("#menu-open");
  if (await list.isVisible()) await list.click();
  await page.locator("#tab-questions").click();
  await expect(page.locator(ROW)).toBeVisible();
};

/** Where the thread stands at the moment a jump rings what it lands on, and
 * every place it passes through on the way. */
const watchJump = (page: Page) =>
  page.locator("#chat").evaluate((chat) => {
    const w = window as unknown as { tops: number[]; atMark: number | null };
    w.tops = [];
    w.atMark = null;
    chat.addEventListener("scroll", () => w.tops.push(chat.scrollTop), { passive: true });
    new MutationObserver((changes) => {
      for (const change of changes)
        if ((change.target as Element).classList.contains("traced") && w.atMark === null)
          w.atMark = chat.scrollTop;
    }).observe(chat, { subtree: true, attributes: true, attributeFilter: ["class"] });
  });

/** Where the jump ended, once it has settled: how far the item's middle (or
 * its top) is from the thread's middle (or its top), and whether it is ringed. */
const landed = async (page: Page, item: string, top = false) => {
  await page.waitForFunction(
    () => (window as unknown as { atMark: number | null }).atMark !== null,
  );
  const ringed = await page.locator(item).evaluate((el) => el.classList.contains("traced"));
  await page.waitForTimeout(1500);
  return page.locator("#chat").evaluate(
    (chat, [sel, top]) => {
      const w = window as unknown as { tops: number[]; atMark: number };
      const box = chat.getBoundingClientRect();
      const at = document.querySelector(sel as string)!.getBoundingClientRect();
      const off = top ? at.top - box.top : at.top + at.height / 2 - (box.top + box.height / 2);
      return {
        off: Math.abs(Math.round(off)),
        glided: chat.scrollTop !== w.atMark,
        steps: new Set(w.tops).size,
      };
    },
    [item, top] as const,
  ).then((r) => ({ ...r, ringed }));
};

const height = async (page: Page) => (await boxOf(page.locator(PIC))).height;

// R-0168, R-0540, R-0587
test("an event chip under Based on picks the event on the picture, opening it when folded, and puts nothing in the message box", async ({ page }) => {
  const w = watch(page);
  const { event } = await open(page);
  await toQuestions(page);
  // the thread scrolled up under the list, so the picture is the strip
  await page.locator("#chat").evaluate((chat) => (chat.scrollTop -= 400));
  await page.waitForTimeout(450);
  expect(await height(page)).toBeLessThanOrEqual(42);
  await page.locator(`${ROW} [data-ev="0"]`).click();
  await page.waitForTimeout(700);
  await expect(page.locator("#chat")).toBeVisible();
  expect(await height(page)).toBeGreaterThan(42);
  // the path writes the event as the picture does, its person's name first and
  // the title running on as one sentence (R-0681)
  await expect(page.locator("#path .here.on")).toContainText(event.split(" ").slice(0, 3).join(" "), { ignoreCase: true });
  await expect(page.locator("#composer .chip")).toHaveCount(0);
  expect(w.bad).toEqual([]);
});

// R-0055, R-0587
test("a message chip under Based on glides the thread to that message and rings it", async ({ page }) => {
  const { rests } = await open(page);
  await toQuestions(page);
  await watchJump(page);
  await page.locator(`${ROW} [data-ev="1"]`).click();
  const end = await landed(page, `#chat .bub[data-statement="${rests.id}"]`);
  expect(end).toEqual({ off: end.off, glided: true, steps: end.steps, ringed: true });
  expect(end.off).toBeLessThanOrEqual(2);
  expect(end.steps).toBeGreaterThan(4);
  await expect(page.locator("#composer .chip")).toHaveCount(0);
});

// R-0055
test("the day an impression was raised glides the thread to the message that raised it", async ({ page }) => {
  const { raised } = await open(page);
  await toQuestions(page);
  await watchJump(page);
  await page.locator(`${ROW} button.qwhen`).click();
  const end = await landed(page, `#chat .bub[data-statement="${raised.id}"]`);
  expect(end).toEqual({ off: end.off, glided: true, steps: end.steps, ringed: true });
  expect(end.off).toBeLessThanOrEqual(2);
  expect(end.steps).toBeGreaterThan(4);
});

// R-0055
test("with less motion asked for, the same jump lands at once", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const { raised } = await open(page);
  await toQuestions(page);
  await watchJump(page);
  await page.locator(`${ROW} button.qwhen`).click();
  const end = await landed(page, `#chat .bub[data-statement="${raised.id}"]`);
  expect(end.glided).toBe(false);
  expect(end.off).toBeLessThanOrEqual(2);
  expect(end.ringed).toBe(true);
});

/** Only Patrick sees the family's sessions listed in the drawer. */
test.describe("a session tapped in the sessions drawer", () => {
  const roles = (...names: string[]) =>
    flask("admin", "run", "--", "users", "roles", username("sittings"), ...names, "--yes");
  test.beforeAll(() => roles("admin", "subscriber"));
  test.afterAll(() => roles("subscriber"));

  // R-0055
  test("closes the drawer and glides the thread to the line where that session starts", async ({ page }) => {
    const w = watch(page);
    await open(page);
    await page.locator("#sessions-open").click();
    const row = page.locator("#sessions-sheet .fs-body .row").last();
    await expect(row).toBeVisible();
    await page.waitForTimeout(400);
    const id = await row.getAttribute("data-id");
    await watchJump(page);
    await row.locator(".rsub").click();
    await expect(page.locator("#sessions-sheet")).toBeHidden();
    const end = await landed(page, `#chat .sitting[data-sitting="${id}"]`, true);
    expect(end).toEqual({ off: end.off, glided: true, steps: end.steps, ringed: true });
    expect(end.off).toBeLessThanOrEqual(2);
    expect(w.bad).toEqual([]);
  });
});
