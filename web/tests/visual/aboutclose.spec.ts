import { expect, test, type Page } from "./fixtures";
import { stateFor } from "./setup";

/** A cluster's page closes by its close button alone, and the button stands
 * where it rests from the first frame of the page's slide down. */

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
  /** Milliseconds since the tap. */
  at: number;
  /** Whether it was the moving copy that was read. */
  sliding: boolean;
  /** The close button's box and its cross's box, against the card's own corner. */
  button: string;
  cross: string;
}

/** Where the close button and its cross stand on the card shown, every frame
 * for a while after `act`: the moving copy while there is one, else the page. */
async function frames(page: Page, act: () => Promise<void>): Promise<Seen[]> {
  await page.evaluate(() => {
    const pic = document.querySelector<HTMLElement>("#chat-screen > .pic")!;
    const seen: Seen[] = [];
    (window as unknown as { SEEN: Seen[] }).SEEN = seen;
    const start = performance.now();
    const box = (r: DOMRect, c: DOMRect) =>
      [r.left - c.left, r.top - c.top, r.width, r.height].map((n) => Math.round(n)).join(",");
    const read = () => {
      const moving = pic.querySelector<HTMLElement>(".slide-lay .card");
      const card =
        moving ??
        [...pic.querySelectorAll<HTMLElement>(".view .card")].find((c) => getComputedStyle(c).visibility !== "hidden");
      const x = card?.querySelector<HTMLElement>(".cardx");
      if (card && x) {
        const c = card.getBoundingClientRect();
        const glyph = document.createRange();
        glyph.selectNodeContents(x);
        seen.push({
          at: Math.round(performance.now() - start),
          sliding: moving !== null,
          button: box(x.getBoundingClientRect(), c),
          cross: box(glyph.getBoundingClientRect(), c),
        });
      }
      if (performance.now() - start < 1500) requestAnimationFrame(read);
    };
    requestAnimationFrame(read);
  });
  await act();
  await page.waitForTimeout(1700);
  return page.evaluate(() => (window as unknown as { SEEN: Seen[] }).SEEN);
}

// R-0680
test("the close button stands where it rests from the first frame of the cluster page's slide, and only it closes the page", async ({ page }) => {
  await open(page);
  const seen = await frames(page, () => page.locator("#info").click());
  const at = (ms: number) => seen.find((s) => s.at >= ms) ?? seen[seen.length - 1];
  const rest = seen[seen.length - 1];
  expect(seen.filter((s) => s.sliding).length).toBeGreaterThan(3);
  expect(rest.sliding).toBe(false);
  for (const one of [seen[0], at(50), at(150), rest]) {
    expect({ button: one.button, cross: one.cross }).toEqual({ button: rest.button, cross: rest.cross });
  }
  for (const body of [".ss.about .ab-span", ".ss.about .ab-list li .ab-yr"]) {
    await page.locator(`#view ${body}`).first().click();
    await page.waitForTimeout(300);
    await expect(page.locator("#view .ss.about")).toBeVisible();
  }
  await page.locator("#view .card > .cardx").click();
  await expect(page.locator("#view .ss.about")).toHaveCount(0);
});
