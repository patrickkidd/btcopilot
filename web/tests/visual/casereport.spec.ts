import { expect, test, type Page } from "@playwright/test";
import { stateFor, type Key } from "./setup";

/** The case report on the three case report fixtures at a phone's and a
 * desktop's size, in both schemes: the cards and the strip one to one, every
 * chip one line inside its card, nothing scrolling sideways, no console error;
 * and its taps: a strip item glides to its card, a chip lights the timeline,
 * a book raises its passages. Geometry and words only, no golden pictures. */

const FIXTURES: Key[] = ["case-report", "case-report-thin", "case-report-dense"];
const SIZES = [
  { width: 393, height: 852 },
  { width: 1280, height: 800 },
];
const SCHEMES = ["light", "dark"] as const;

/** The report opened at its address, every console error kept. */
async function open(page: Page): Promise<string[]> {
  const errors: string[] = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto("/app/case-report");
  await expect(page.locator("#case-body .level").first()).toBeVisible();
  await page.waitForTimeout(400);
  return errors;
}

for (const key of FIXTURES)
  for (const size of SIZES)
    for (const scheme of SCHEMES)
      test.describe(`${key} at ${size.width} in ${scheme}`, () => {
        test.use({ storageState: stateFor(key), viewport: size, colorScheme: scheme });

        // R-0702, R-0689, R-0690
        test("draws every card with its strip item, each chip one line inside its card, nothing sideways", async ({ page }) => {
          const errors = await open(page);
          const seen = await page.evaluate(() => {
            const out = (inner: DOMRect, outer: DOMRect) =>
              inner.left < outer.left - 0.5 || inner.right > outer.right + 0.5 || inner.top < outer.top - 0.5 || inner.bottom > outer.bottom + 0.5;
            const chips = [...document.querySelectorAll<HTMLElement>("#case-body .chips .chip")];
            return {
              strip: [...document.querySelectorAll<HTMLElement>("#case-rail [data-jump]")].map((b) => b.dataset.jump),
              cards: [...document.querySelectorAll<HTMLElement>("#case-body .level, #case-dash .level")].map((l) => l.dataset.card),
              wrapped: chips.filter((c) => c.getClientRects().length !== 1 || c.offsetHeight > 40).length,
              // a stored title shows whole: no chip cut short with an ellipsis
              cut: chips
                .filter((c) => {
                  const words = document.createRange();
                  words.selectNodeContents(c);
                  const pad = parseFloat(getComputedStyle(c).paddingLeft) + parseFloat(getComputedStyle(c).paddingRight);
                  return words.getBoundingClientRect().width > c.clientWidth - pad + 1;
                })
                .map((c) => c.textContent),
              outside: chips.filter((c) => out(c.getBoundingClientRect(), c.closest(".level")!.getBoundingClientRect())).length,
              sideways: document.documentElement.scrollWidth > window.innerWidth,
              stripRows: new Set([...document.querySelectorAll<HTMLElement>("#case-rail [data-jump]")].map((b) => b.offsetTop)).size,
              text: document.querySelector("#case-screen")!.textContent ?? "",
              folds: document.querySelectorAll("#case-body details").length,
              sides: document.querySelectorAll("#case-body details.side").length,
            };
          });
          expect([...seen.cards].sort()).toEqual([...seen.strip].sort());
          expect(seen.strip).toHaveLength(10);
          expect(seen.stripRows).toBe(1);
          expect(seen.wrapped).toBe(0);
          expect(seen.cut).toEqual([]);
          expect(seen.outside).toBe(0);
          expect(seen.sideways).toBe(false);
          expect(seen.text).not.toMatch(/NaN|undefined|not in the record|From the record/);
          // only each side of the family folds (R-0689)
          expect(seen.folds).toBe(seen.sides);
          expect(errors).toEqual([]);
        });
      });

test.describe("the case report's taps", () => {
  test.use({ storageState: stateFor("case-report"), viewport: SIZES[0] });

  // R-0702
  test("a strip item glides the cards to its card and lights its item", async ({ page }) => {
    await open(page);
    const body = page.locator("#case-body");
    const tops: number[] = [];
    await page.locator('#case-rail [data-jump="effort"]').click();
    for (let i = 0; i < 12; i++) {
      tops.push(await body.evaluate((b) => b.scrollTop));
      await page.waitForTimeout(40);
    }
    await page.waitForTimeout(600);
    const end = await body.evaluate((b) => b.scrollTop);
    // sampled on the way: at least one stop strictly between the start and the end
    expect(tops.some((t) => t > 0 && t < end)).toBe(true);
    const card = await page.locator('#case-body .level[data-card="effort"]').boundingBox();
    const bodyBox = await body.boundingBox();
    expect(card!.y).toBeLessThan(bodyBox!.y + bodyBox!.height);
    await expect(page.locator('#case-rail [data-jump="effort"]')).toHaveClass(/on/);
  });

  // R-0702
  test("the strip is one button high and scrolls sideways", async ({ page }) => {
    await open(page);
    const strip = await page.locator("#case-rail").evaluate((rail) => {
      const button = rail.querySelector<HTMLElement>("[data-jump]")!;
      const pad = parseFloat(getComputedStyle(rail).paddingTop) + parseFloat(getComputedStyle(rail).paddingBottom);
      const tops = new Set([...rail.querySelectorAll<HTMLElement>("[data-jump]")].map((b) => b.offsetTop));
      return { inner: rail.clientHeight - pad, button: button.offsetHeight, rows: tops.size, wider: rail.scrollWidth > rail.clientWidth };
    });
    expect(strip.rows).toBe(1);
    expect(strip.inner).toBe(strip.button);
    expect(strip.wider).toBe(true);
  });

  // R-0696
  test("the timeline folds to the chat's strip while the cards are read, and opens at their top and on a chip", async ({ page }) => {
    await open(page);
    const pic = page.locator("#case-screen > .pic");
    const full = (await pic.boundingBox())!.height;
    await page.locator("#case-body").evaluate((b) => (b.scrollTop = 600));
    await expect.poll(async () => (await pic.boundingBox())!.height).toBeLessThan(full);
    await expect(page.locator("#case-screen")).toHaveClass(/folded/);
    // still on screen, pinned at the top
    expect((await pic.boundingBox())!.y).toBeLessThan(120);
    await page.locator('#case-body .chip[data-kind="event"]:visible').first().click();
    await expect(page.locator("#case-screen")).not.toHaveClass(/folded/);
    await page.locator("#case-body").evaluate((b) => (b.scrollTop = 600));
    await expect(page.locator("#case-screen")).toHaveClass(/folded/);
    await page.locator("#case-body").evaluate((b) => (b.scrollTop = 0));
    await expect(page.locator("#case-screen")).not.toHaveClass(/folded/);
  });

  // R-0700
  test("putting the cluster away closes its play-by-play", async ({ page }) => {
    await open(page);
    await page.locator('#case-view .ss-hit[data-target="cluster"]').first().click();
    await page.locator("#case-caption #cap-play").click();
    await expect(page.locator("#case-pbp")).toHaveClass(/in/);
    await page.locator('#case-path [data-step="0"]').click();
    await expect(page.locator("#case-pbp")).not.toHaveClass(/in/);
  });

  // R-0698
  test("a guess is the chat's coach bubble with no guess heading over it", async ({ page }) => {
    await open(page);
    const main = page.locator('#case-body .level[data-card="main"]');
    await expect(main.locator(".bub.coach .who")).toHaveText("Coach");
    await expect(page.locator("#case-body")).not.toContainText(/A guess, yours to reject|Rests on|The record covers|open questions|Left off this page/i);
  });

  // R-0702
  test("the family card is one button, the same as the strip's family item", async ({ page }) => {
    await open(page);
    const card = page.locator('#case-body .level[data-card="family"]');
    await expect(card.locator("> *")).toHaveCount(1);
    await expect(card.locator("button.famcard")).toHaveText((await page.locator('#case-rail [data-jump="family"]').textContent())!);
    await card.locator("button.famcard").click();
    await expect(page.locator("#case-famout")).toHaveClass(/in/);
  });

  // R-0700, R-0696
  test("a person's chip lights that person's events on the timeline", async ({ page }) => {
    await open(page);
    const before = await page.locator("#case-view").innerHTML();
    await page.locator('#case-body .chip[data-kind="person"]').first().click();
    await expect.poll(() => page.locator("#case-view").innerHTML()).not.toBe(before);
    await expect(page.locator("#case-view .ss-t.on").first()).toBeVisible();
  });

  // R-0700
  test("a cluster opened on the timeline offers explain, and explain opens the play-by-play", async ({ page }) => {
    await open(page);
    await page.locator('#case-view .ss-hit[data-target="cluster"]').first().click();
    await expect(page.locator("#case-caption #cap-play")).toBeEnabled();
    await page.locator("#case-caption #cap-play").click();
    await expect(page.locator("#case-pbp")).toHaveClass(/in/);
    // a strip tap puts the play-by-play away so the scroll is seen (R-0702)
    await page.locator('#case-rail [data-jump="sides"]').click();
    await expect(page.locator("#case-pbp")).not.toHaveClass(/in/);
  });

  // R-0700
  test("a cluster's chip on a card opens it on the timeline with explain offered, and explain opens the play-by-play", async ({ page }) => {
    await open(page);
    await page.locator('#case-body .chip[data-kind="cluster"]').first().click();
    await expect(page.locator("#case-path [data-step]").first()).toBeVisible();
    await page.locator("#case-caption #cap-play").click();
    await expect(page.locator("#case-pbp")).toHaveClass(/in/);
  });

  // R-0715
  test("the header names who presents, by name and never by email", async ({ page }) => {
    await open(page);
    await expect(page.locator("#case-title")).toHaveText("Nora · Case report");
    await expect(page.locator("#case-by")).toHaveText("presented by Nora Halloran");
  });

  // R-0691, R-0692
  test("a card's book raises its passages and puts them away", async ({ page }) => {
    await open(page);
    await page.locator('#case-body .level[data-card="main"] .book').click();
    const sheet = page.locator(".fs-sheet.bk");
    await expect(sheet).toHaveClass(/in/);
    await expect(sheet.locator("blockquote").first()).toBeVisible();
    await sheet.locator(".cardx").click();
    await expect(sheet).not.toHaveClass(/in/);
  });

  // R-0697
  test("on the phone the family button slides the family out over the report", async ({ page }) => {
    await open(page);
    await page.locator("#case-family").click();
    await expect(page.locator("#case-famout")).toHaveClass(/in/);
    await expect(page.locator("#case-famout .fam svg").first()).toBeVisible();
    await page.locator("#case-famout-close").click();
    await expect(page.locator("#case-famout")).not.toHaveClass(/in/);
  });
});
