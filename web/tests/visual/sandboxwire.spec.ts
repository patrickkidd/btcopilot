import { expect, test, type Page } from "@playwright/test";
import { need, sandboxOnly } from "./sandbox";

// The meeting's agreement wire on its own: a tap on any dot, the journey the
// list takes to that dot's card, the band held at the top while the list
// scrolls under it, and the colours the dots are drawn in. Nothing here
// chooses, votes or ratifies, so the walk leaves the fixture as it found it.

/** Open the meeting on the cut that is on the table, the way the table walk
 * reaches it. */
async function meeting(page: Page): Promise<void> {
  await page.goto(need("table"), { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  if (await page.locator("#task-screen").isVisible())
    await page.locator("#task-screen .addbtn").first().click();
  else {
    await page.locator("#sessions-open").click();
    await page.waitForTimeout(700);
    await page.locator(".fs-task.fs-agenda").first().click();
  }
  await page.waitForTimeout(1200);
  if (!(await page.locator("#meeting-screen").isVisible())) {
    await page.locator(".tb-meet").first().click();
    await page.waitForTimeout(1500);
  }
  await expect(page.locator("#meeting-screen")).toBeVisible();
  await expect(page.locator("#meeting-view [data-item]").first()).toBeAttached();
}

const dots = (page: Page) => page.locator("#meeting-view [data-item]");

/** The ids of the dots, in the order they sit on the wire. */
const dotIds = (page: Page) =>
  dots(page).evaluateAll((all) => all.map((d) => Number((d as HTMLElement).dataset.item)));

test.describe(() => {
  sandboxOnly("table");
  test.describe.configure({ timeout: 300_000 });

  // R-0320
  test("every dot on the meeting's wire answers a tap", async ({ page }) => {
    await meeting(page);
    const ids = await dotIds(page);
    expect(ids.length).toBeGreaterThan(1);
    const silent: number[] = [];
    for (const id of ids) {
      const toasts = await page.locator(".toast").count();
      await page.locator(`#meeting-view [data-item="${id}"]`).click({ force: true });
      await page.waitForTimeout(500);
      // the room is now on it, or the app says why it cannot be
      const on = await page.locator(`#meeting-view .d-on[data-item="${id}"]`).count();
      const told = (await page.locator(".toast").count()) > toasts;
      if (!on && !told) silent.push(id);
    }
    expect(silent).toEqual([]);
  });

  // R-0338
  test("a tapped dot takes the list to its card on a visible journey", async ({ page }) => {
    await meeting(page);
    const ids = await dotIds(page);
    // the dot furthest along whose card is in the list
    const listed = await page
      .locator("#meeting-body [data-item]")
      .evaluateAll((all) => all.map((n) => Number((n as HTMLElement).dataset.item)));
    const id = [...ids].reverse().find((one) => listed.includes(one));
    expect(id).toBeDefined();
    const steps = await page.evaluate(async (item) => {
      const scroller = document.querySelector("#meeting-screen .mscroll") as HTMLElement;
      scroller.scrollTop = 0;
      await new Promise((r) => requestAnimationFrame(r));
      const dot = document.querySelector(`#meeting-view [data-item="${item}"]`)!;
      const seen: number[] = [];
      dot.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      const until = performance.now() + 800;
      while (performance.now() < until) {
        seen.push(Math.round(scroller.scrollTop));
        await new Promise((r) => requestAnimationFrame(r));
      }
      return seen;
    }, id!);
    const last = steps[steps.length - 1];
    expect(last).toBeGreaterThan(0);
    // it passed through the places in between rather than jumping there
    expect(new Set(steps.filter((s) => s > 0 && s < last)).size).toBeGreaterThanOrEqual(3);
    // and the card came to rest just under the band held at the top
    const gap = await page.evaluate((item) => {
      const card = document.querySelector(`#meeting-body [data-item="${item}"]`)!;
      const band = document.querySelector("#meeting-screen .mstick")!;
      return card.getBoundingClientRect().top - band.getBoundingClientRect().bottom;
    }, id!);
    expect(gap).toBeGreaterThanOrEqual(0);
    expect(gap).toBeLessThanOrEqual(24);
  });

  // R-0340
  test("the wire, its legend and the sort stay at the top while the title scrolls away", async ({
    page,
  }) => {
    await meeting(page);
    const at = await page.evaluate(async () => {
      const scroller = document.querySelector("#meeting-screen .mscroll") as HTMLElement;
      scroller.scrollTop = Math.min(600, scroller.scrollHeight - scroller.clientHeight);
      await new Promise((r) => setTimeout(r, 300));
      const top = scroller.getBoundingClientRect().top;
      const band = document.querySelector("#meeting-screen .mstick")!;
      const first = document.querySelector("#meeting-body > *")!;
      return {
        scrolled: scroller.scrollTop,
        band: band.getBoundingClientRect().top - top,
        head: document.getElementById("meeting-stats")!.getBoundingClientRect().bottom - top,
        beneath: first.getBoundingClientRect().top < band.getBoundingClientRect().bottom,
        held: ["meeting-view", "meeting-key", "meeting-sort"].every((id) =>
          band.contains(document.getElementById(id)),
        ),
      };
    });
    expect(at.scrolled).toBeGreaterThan(100);
    expect(Math.abs(at.band)).toBeLessThanOrEqual(1);
    expect(at.head).toBeLessThanOrEqual(1);
    expect(at.beneath).toBe(true);
    expect(at.held).toBe(true);
  });

  // R-0278
  test("the meeting's wire draws agreed dots teal and disputed ones amber", async ({ page }) => {
    await meeting(page);
    const look = await page.evaluate(() => {
      const probe = (value: string) => {
        const span = document.createElement("span");
        span.style.color = value;
        document.body.append(span);
        const out = getComputedStyle(span).color;
        span.remove();
        return out;
      };
      const fills = (cls: string) =>
        [...document.querySelectorAll(`#meeting-view .${cls}`)].map((d) => getComputedStyle(d).fill);
      return {
        teal: probe("var(--data)"),
        amber: probe("var(--ask)"),
        agreed: fills("d-ok"),
        disputed: fills("d-no"),
      };
    });
    expect(look.agreed.length).toBeGreaterThan(0);
    expect(look.disputed.length).toBeGreaterThan(0);
    expect(new Set(look.agreed)).toEqual(new Set([look.teal]));
    expect(new Set(look.disputed)).toEqual(new Set([look.amber]));
  });
});
