import { expect, test, type Page } from "./fixtures";
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
  /** How far down the moving copy of the about card stands, while there is one. */
  top: number | null;
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
        top: (() => {
          const copy = pic.querySelector(".slide-lay .card");
          return copy ? Math.round(copy.getBoundingClientRect().top) : null;
        })(),
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

/** Where the moving copy stood, frame by frame, once each place. */
const travel = (seen: Seen[]) => [...new Set(seen.flatMap((s) => (s.top === null ? [] : [s.top])))];

// R-0680, R-0768
test("the about page comes down from the top at its full height, with no jump once it lands", async ({ page }) => {
  await open(page);
  const seen = await frames(page, () => page.locator("#info").click());
  const h = shown(seen);
  expect(seen.some((s) => s.sliding)).toBe(true);
  // it comes down from above, over several frames, to where it rests
  const went = travel(seen);
  expect(went.length).toBeGreaterThan(3);
  expect(went[0]).toBeLessThan(went[went.length - 1]);
  expect(h.length).toBeGreaterThan(0);
  expect(Math.max(...h) - h[0]).toBeLessThanOrEqual(2);
});

// R-0680, R-0768
test("Escape puts the about page away, as its cross does", async ({ page }) => {
  await open(page);
  await page.locator("#info").click();
  await page.waitForTimeout(800);
  await expect(page.locator("#chat-screen > .pic .view .card").first()).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator("#chat-screen > .pic .view .card")).toHaveCount(0);
});

// R-0680, R-0768
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
  // it goes back up, over several frames
  const went = travel(seen);
  expect(went.length).toBeGreaterThan(3);
  expect(went[went.length - 1]).toBeLessThan(went[0]);
  expect(shown(seen).filter((h) => h < full - 2)).toEqual([]);
  expect(seen.filter((s) => s.h > 0 && s.folded)).toEqual([]);
  expect(seen[seen.length - 1]).toEqual({ h: 0, sliding: false, top: null, folded: true });
});

interface Reach {
  /** where the moving copy of the about card ends, as its box has it (cut at the window's foot) */
  foot: number;
  /** the lowest point, read down from the region's top, at which the copy is what the page shows there */
  painted: number;
  /** where the picture region's own box ends */
  region: number;
  /** where the lowest-ending ancestor that clips its children ends; the window's foot when none does */
  clipEnd: number;
}

/** Every frame for a while after `act`: how far down the moving copy of the
 * about card is painted, against how far down its box reaches, and whether any
 * ancestor that clips at all ends above that. The copy takes no taps, so that
 * is lifted for the reading, as the bubble test below does. */
async function reaches(page: Page, act: () => Promise<void>): Promise<Reach[]> {
  await page.evaluate(() => {
    const pic = document.querySelector<HTMLElement>("#chat-screen > .pic")!;
    const seen: Reach[] = [];
    (window as unknown as { REACH: Reach[] }).REACH = seen;
    const clips = (el: Element) => {
      const s = getComputedStyle(el);
      return s.overflowX !== "visible" || s.overflowY !== "visible" || s.clipPath !== "none";
    };
    let n = 0;
    const read = () => {
      const lay = pic.querySelector<HTMLElement>(".slide-lay:has(.card)");
      const card = lay?.querySelector<HTMLElement>(".card");
      if (lay && card) {
        const box = pic.getBoundingClientRect();
        const r = card.getBoundingClientRect();
        const foot = Math.min(r.bottom, innerHeight);
        const x = r.left + 8;
        lay.inert = false;
        lay.style.pointerEvents = "auto";
        let painted = box.top;
        for (let y = foot - 1; y > box.top; y -= 2) {
          if (lay.contains(document.elementFromPoint(x, y))) {
            painted = y + 1;
            break;
          }
        }
        lay.inert = true;
        lay.style.pointerEvents = "";
        let clipEnd = innerHeight;
        for (let el = card.parentElement; el && el !== document.body; el = el.parentElement)
          if (clips(el)) clipEnd = Math.min(clipEnd, el.getBoundingClientRect().bottom);
        seen.push({ foot: Math.round(foot), painted: Math.round(painted), region: Math.round(box.bottom), clipEnd: Math.round(clipEnd) });
      }
      if (++n < 90) requestAnimationFrame(read);
    };
    requestAnimationFrame(read);
  });
  await act();
  await page.waitForTimeout(1600);
  return page.evaluate(() => (window as unknown as { REACH: Reach[] }).REACH);
}

/** The frames on which the copy hangs below the region: on each, its whole
 * box down to its foot is painted, and no ancestor's clip ends above its foot.
 * Safari cut the copy at the region's bottom for the length of the slide and
 * let the rest out on the last frame (Patrick, 2026-10-08). */
function wholeWhileHanging(seen: Reach[]): void {
  const hanging = seen.filter((s) => s.foot > s.region + 2);
  expect(hanging.length).toBeGreaterThan(3);
  for (const s of hanging) {
    expect(s.clipEnd, `an ancestor's clip ends at ${s.clipEnd}, above the card's foot at ${s.foot}`).toBeGreaterThanOrEqual(s.foot - 1);
    expect(s.painted, `painted down to ${s.painted}, the card's foot is at ${s.foot}`).toBeGreaterThanOrEqual(s.foot - 2);
  }
}

// R-0768, R-0680
test("the about page is painted whole below the picture on every frame of its way down", async ({ page }) => {
  await open(page);
  wholeWhileHanging(await reaches(page, () => page.locator("#info").click()));
});

// R-0768, R-0680
test("the about page is painted whole below the picture on every frame of its way back up", async ({ page }) => {
  await open(page);
  await page.locator("#info").click();
  await page.waitForTimeout(800);
  await expect(page.locator("#chat-screen > .pic .view .card .cardx")).toBeVisible();
  wholeWhileHanging(await reaches(page, () => page.locator("#chat-screen > .pic .view .card .cardx").click()));
});

// R-0234, R-0691, R-0768
// Patrick, 2026-10-08: the book sits in the lower right corner the way the x sits in the upper right.
test("the book stands in the about page's bottom-right corner as its cross stands in the top-right, the same size and the same distance in", async ({ page }) => {
  await open(page);
  await page.locator("#info").click();
  await page.waitForTimeout(800);
  const card = page.locator("#chat-screen > .pic .view .card");
  const [c, x, b] = await Promise.all([card.boundingBox(), card.locator(".cardx").boundingBox(), card.locator(".book[data-book]").boundingBox()]);
  expect(c && x && b).toBeTruthy();
  const right = (r: { x: number; width: number }) => r.x + r.width;
  const bottom = (r: { y: number; height: number }) => r.y + r.height;
  const within1 = (a: number, b: number, what: string) => expect(Math.abs(a - b), `${what}: ${a} against ${b}`).toBeLessThanOrEqual(1);
  within1(Math.abs(right(c!) - right(b!)), Math.abs(right(c!) - right(x!)), "the book's inset from the right against the cross's");
  within1(Math.abs(bottom(c!) - bottom(b!)), Math.abs(x!.y - c!.y), "the book's inset from the bottom against the cross's from the top");
  within1(b!.width, x!.width, "width");
  within1(b!.height, x!.height, "height");
});

test.describe("a record whose coach has spoken under the picture", () => {
  test.use({ storageState: stateFor("everymark") });

  // R-0768
  test("no chat bubble shows through the about page while it comes down", async ({ page }) => {
    await open(page);
    await page.evaluate(() => {
      const pic = document.querySelector<HTMLElement>("#chat-screen > .pic")!;
      const seen = { covered: 0, through: [] as string[] };
      (window as unknown as { SEEN: typeof seen }).SEEN = seen;
      let n = 0;
      const read = () => {
        const lay = pic.querySelector<HTMLElement>(".slide-lay:has(.card)");
        if (lay) {
          const c = lay.querySelector(".card")!.getBoundingClientRect();
          // the moving copy takes no taps; that is lifted for the reading, to find what is drawn on top
          lay.inert = false;
          lay.style.pointerEvents = "auto";
          for (const bub of document.querySelectorAll<HTMLElement>("#chat .bub")) {
            const b = bub.getBoundingClientRect();
            const [x, y] = [b.left + b.width / 2, b.top + b.height / 2];
            if (x < c.left || x > c.right || y < c.top || y > c.bottom || y > innerHeight) continue;
            seen.covered++;
            if (!pic.contains(document.elementFromPoint(x, y))) seen.through.push(bub.textContent!.slice(0, 30));
          }
          lay.inert = true;
          lay.style.pointerEvents = "";
        }
        if (++n < 90) requestAnimationFrame(read);
      };
      requestAnimationFrame(read);
    });
    await page.locator("#info").click();
    await page.waitForTimeout(1600);
    const seen = await page.evaluate(() => (window as unknown as { SEEN: { covered: number; through: string[] } }).SEEN);
    expect(seen.covered).toBeGreaterThan(0);
    expect(seen.through).toEqual([]);
  });
});
