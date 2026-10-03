import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** How tall the about card stands on screen while it travels: read on every
 * frame as it opens, and as a scroll up the chat takes it away before the
 * picture folds. */

test.use({ storageState: stateFor("hostile"), hasTouch: true });

const open = async (page: Page) => {
  await page.addInitScript(() => localStorage.setItem("fd-home-screen-asked", String(Date.now())));
  await page.goto("/app/");
  await expect(page.locator(".bub").first()).toBeVisible();
  await page.waitForTimeout(1200);
  await page.locator('#view .ss-hit[data-target="cluster"]').first().click();
  await expect(page.locator("#info")).toBeVisible();
  await page.waitForTimeout(400);
};

interface Seen {
  /** How much of the about page shows on screen, on its own or in a moving copy. */
  h: number;
  sliding: boolean;
  folded: boolean;
}

/** Every frame for a while after `act`: how tall the about page shows. */
async function frames(page: Page, act: () => Promise<void>): Promise<Seen[]> {
  await page.evaluate(() => {
    const pic = document.querySelector<HTMLElement>("#chat-screen > .pic")!;
    const seen: Seen[] = [];
    (window as unknown as { SEEN: Seen[] }).SEEN = seen;
    const read = () => {
      const box = pic.getBoundingClientRect();
      const clips = getComputedStyle(pic).overflowY !== "visible";
      let h = 0;
      for (const card of pic.querySelectorAll<HTMLElement>(".card")) {
        if (getComputedStyle(card).visibility === "hidden") continue;
        const r = card.getBoundingClientRect();
        if (r.left >= box.right - 1 || r.width === 0) continue;
        h = Math.max(h, (clips ? Math.min(r.bottom, box.bottom) : r.bottom) - r.top);
      }
      seen.push({
        h: Math.round(h),
        sliding: !!pic.querySelector(".slide-lay .card"),
        folded: pic.parentElement!.classList.contains("folded"),
      });
      if (seen.length < 90) requestAnimationFrame(read);
    };
    requestAnimationFrame(read);
  });
  await act();
  await page.waitForTimeout(1600);
  return page.evaluate(() => (window as unknown as { SEEN: Seen[] }).SEEN);
}

const shown = (seen: Seen[]) => seen.filter((s) => s.h > 0).map((s) => s.h);

// R-0680
test("the about page slides in at its full height, with no jump once it lands", async ({ page }) => {
  await open(page);
  const seen = await frames(page, () => page.locator("#info").click());
  const h = shown(seen);
  expect(seen.some((s) => s.sliding)).toBe(true);
  expect(h.length).toBeGreaterThan(0);
  expect(Math.max(...h) - h[0]).toBeLessThanOrEqual(2);
});

// R-0680
test("scrolling up the chat slides the about page out at its full height before the picture folds", async ({ page }) => {
  await open(page);
  await page.locator("#info").click();
  await page.waitForTimeout(800);
  const full = shown(await frames(page, async () => undefined))[0];
  expect(full).toBeGreaterThan(100);

  const seen = await frames(page, async () => {
    await page.locator("#chat").hover();
    await page.mouse.wheel(0, -400);
  });
  expect(seen.some((s) => s.sliding)).toBe(true);
  expect(shown(seen).filter((h) => h < full - 2)).toEqual([]);
  expect(seen.filter((s) => s.h > 0 && s.folded)).toEqual([]);
  expect(seen[seen.length - 1]).toEqual({ h: 0, sliding: false, folded: true });
});
