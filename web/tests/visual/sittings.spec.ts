import { expect, test, type Page } from "./fixtures";
import { watch } from "./gate";
import { inside, stateFor, boxOf } from "./setup";

/** A family has one thread. A light line with the day stands where each
 * sitting starts, with the start time too when the sitting before it started
 * that day, never the sitting's summary; older sittings read in as the
 * reader scrolls up, and nothing lets anyone open or start a conversation. */

const open = async (page: Page) => {
  const w = watch(page);
  await page.goto("/app/");
  await expect(page.locator("#chat .bub").first()).toBeVisible();
  // the thread holds its newest words in view while fonts and the picture land
  await page.waitForTimeout(1200);
  return w;
};

const sideways = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

/** Every line lies inside the thread's box, across it and within what it
 * scrolls, and says only a day, and a time after it. Read in one pass, so a
 * page read in meanwhile cannot move the lines under the check. */
const DAY = /^(Today|Yesterday|[A-Z][a-z]{2} \d{1,2}(, \d{4})?)(, \d{1,2}:\d{2} [ap]m)?$/;

async function held(page: Page): Promise<void> {
  const outside = await page.locator("#chat").evaluate((chat) => {
    const box = chat.getBoundingClientRect();
    const top = box.top - chat.scrollTop;
    return [...chat.querySelectorAll(".sitting")].flatMap((line) => {
      const r = line.getBoundingClientRect();
      const out =
        r.left < box.left - 1 ||
        r.right > box.right + 1 ||
        r.top < top - 1 ||
        r.bottom > top + chat.scrollHeight + 1;
      return out ? [line.textContent] : [];
    });
  });
  expect(outside).toEqual([]);
  for (const day of await page.locator("#chat .sitting").allInnerTexts())
    expect(day).toMatch(DAY);
}

test.describe("a family with one sitting", () => {
  test.use({ storageState: stateFor("sitting") });

  // R-0055
  test("one line above the first words, saying today", async ({ page }) => {
    const w = await open(page);
    const line = page.locator("#chat .sitting");
    await expect(line).toHaveCount(1);
    await expect(line).toHaveText("Today");
    expect(await page.locator("#chat > *").first().getAttribute("class")).toBe("sitting");
    await line.scrollIntoViewIfNeeded();
    await inside(line, page.locator("#chat"));
    expect(await sideways(page)).toBe(0);
    expect(w.bad).toEqual([]);
  });

  // R-0055
  test("nothing opens or starts another conversation", async ({ page }) => {
    const w = await open(page);
    await expect(page.locator("#sessions-open")).toBeHidden();
    const bar = await boxOf(page.locator("#inbar"));
    await page.mouse.move(bar.x + 20, bar.y + 10);
    await page.mouse.down();
    await page.mouse.move(bar.x + 20, bar.y - 120, { steps: 6 });
    await page.mouse.up();
    await expect(page.locator("#sessions-sheet")).toBeHidden();
    expect(w.bad).toEqual([]);
  });

  // R-0055
  test("the line takes the app's quiet colours in light and dark", async ({ page }) => {
    await open(page);
    const day = page.locator("#chat .sitting");
    const read = () =>
      day.evaluate((node) => {
        const probe = document.body.appendChild(document.createElement("i"));
        probe.style.color = "var(--faint)";
        probe.style.borderColor = "var(--line)";
        const want = [getComputedStyle(probe).color, getComputedStyle(probe).borderTopColor];
        probe.remove();
        return { want, drawn: [getComputedStyle(node).color, getComputedStyle(node, "::before").borderTopColor] };
      });
    const light = await read();
    expect(light.drawn).toEqual(light.want);
    await page.emulateMedia({ colorScheme: "dark" });
    const dark = await read();
    expect(dark.drawn).toEqual(dark.want);
    expect(dark.drawn).not.toEqual(light.drawn);
  });
});

test.describe("twelve sittings over eight months", () => {
  test.use({ storageState: stateFor("sittings") });

  // R-0055
  test("every line sits inside the thread and says only the day, whatever the summary", async ({
    page,
  }) => {
    const w = await open(page);
    const lines = page.locator("#chat .sitting");
    await expect(lines).toHaveCount(9);
    await expect(lines.nth(7)).toHaveText("Yesterday");
    await expect(lines.nth(8)).toHaveText("Today");
    // the sittings carry summaries of sixty characters, none, empty and unicode
    await held(page);
    expect(await sideways(page)).toBe(0);
    expect(w.bad).toEqual([]);
  });

  // R-0055
  test("scrolling up reads older sittings in without moving the words on screen", async ({
    page,
  }) => {
    const w = await open(page);
    const chat = page.locator("#chat");
    await expect(chat.locator(".bub")).toHaveCount(50);
    const was = await chat.evaluate((c) => {
      c.scrollTop = 0;
      const ref = c.querySelector(".bub")!;
      (window as unknown as { ref: Element }).ref = ref;
      return ref.getBoundingClientRect().top;
    });
    await expect(chat.locator(".bub")).toHaveCount(64);
    const now = await page.evaluate(
      () => (window as unknown as { ref: Element }).ref.getBoundingClientRect().top,
    );
    expect(Math.abs(now - was)).toBeLessThanOrEqual(1);
    await expect(chat.locator(".sitting")).toHaveCount(12);
    expect(await chat.evaluate((c) => c.firstElementChild!.className)).toBe("sitting");
    await held(page);
    expect(await sideways(page)).toBe(0);
    expect(w.bad).toEqual([]);
  });
});

test.describe("two sittings on one day", () => {
  test.use({ storageState: stateFor("sameday") });

  // R-0055
  test("the second line that day says when it started, the first only the day", async ({
    page,
  }) => {
    const w = await open(page);
    const lines = page.locator("#chat .sitting");
    await expect(lines).toHaveCount(2);
    const [first, second] = await lines.allInnerTexts();
    expect(first).toMatch(/^[A-Z][a-z]{2} \d{1,2}(, \d{4})?$/);
    expect(second).toBe(`${first}, 9:40 pm`);
    await held(page);
    expect(await sideways(page)).toBe(0);
    expect(w.bad).toEqual([]);
  });
});
