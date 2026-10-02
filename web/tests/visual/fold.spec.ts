import { expect, test, type Page } from "@playwright/test";
import { stateFor, boxOf } from "./setup";

/** The picture folds to a 40-tall strip under the title row while a phone's
 * keyboard is up or the chat is scrolled up, and opens back to the full picture
 * when the keyboard goes down, the chat is back on its newest bubble, or the
 * strip is tapped (Patrick, 2026-10-01, frame A1). The full picture is exactly
 * what it was before the strip was added. */

test.use({ storageState: stateFor("hostile"), hasTouch: true });

const PIC = "#chat-screen > .pic";
const MARKS = "#view svg .dot, #view svg .pill";

/** The full picture on release 3.2026.10.1.2, before the strip: its height, how
 * many dots and pills it draws, and where three of its dots sit. */
const BEFORE = {
  phone: { height: 144, marks: 4, dots: [[226.2, 126.5], [297.8, 126.5], [369.5, 126.5]] },
  desktop: { height: 144, marks: 4, dots: [[535.9, 126.5], [637.2, 126.5], [738.5, 126.5]] },
};

const open = async (page: Page) => {
  // a phone that already answered the add-to-home-screen card
  await page.addInitScript(() => localStorage.setItem("fd-home-screen-asked", String(Date.now())));
  await page.goto("/app/");
  await expect(page.locator(".bub").first()).toBeVisible();
  await page.waitForTimeout(1200);
};

const height = async (page: Page) => (await boxOf(page.locator(PIC))).height;

/** Every dot and pill's middle lies inside the picture's box. */
const shown = (page: Page) =>
  page.evaluate(
    ([pic, marks]) => {
      const box = document.querySelector(pic)!.getBoundingClientRect();
      return [...document.querySelectorAll(marks)].filter((mark) => {
        const b = mark.getBoundingClientRect();
        const y = b.y + b.height / 2;
        return y > box.top && y < box.bottom;
      }).length;
    },
    [PIC, MARKS],
  );

const settle = (page: Page) => page.waitForTimeout(450);

// R-0610, R-0570
test("with the keyboard down and the chat on its newest bubble the picture is unchanged", async ({ page }) => {
  await open(page);
  const before = BEFORE[test.info().project.name as keyof typeof BEFORE];
  expect(await height(page)).toBe(before.height);
  const dots = await page.evaluate(
    (marks) =>
      [...document.querySelectorAll(marks)]
        .filter((mark) => mark.tagName === "circle")
        .map((mark) => {
          const b = mark.getBoundingClientRect();
          return [Math.round(b.x * 10) / 10, Math.round(b.y * 10) / 10];
        }),
    MARKS,
  );
  expect(await page.locator(MARKS).count()).toBe(before.marks);
  expect(dots.slice(0, 3)).toEqual(before.dots);
});

// R-0610, R-0570
test("the keyboard folds the picture to the strip and the newest bubble stays above the box", async ({ page }) => {
  await open(page);
  const marks = await page.locator(MARKS).count();
  const size = page.viewportSize()!;
  await page.locator("#composer").click();
  // a phone keyboard takes the lower half of the visible area
  await page.setViewportSize({ width: size.width, height: 460 });
  await settle(page);
  const strip = await height(page);
  expect(strip).toBeGreaterThanOrEqual(38);
  expect(strip).toBeLessThanOrEqual(42);
  expect(await shown(page)).toBe(marks);
  await expect(page.locator("#speakrow")).toBeHidden();
  const [last, chat, bar] = await Promise.all([
    boxOf(page.locator(".bub").last()),
    boxOf(page.locator("#chat")),
    boxOf(page.locator("#inbar")),
  ]);
  expect(last.y + last.height).toBeLessThanOrEqual(bar.y + 1);
  expect(last.y + last.height).toBeGreaterThan(chat.y);
  await page.locator("#composer").evaluate((box) => box.blur());
  await page.setViewportSize(size);
  await settle(page);
  expect(await height(page)).toBe(144);
  await expect(page.locator("#speakrow")).toBeVisible();
});

// R-0610, R-0570
test("scrolling up folds the picture, and back down to the newest bubble opens it", async ({ page }) => {
  await open(page);
  const chat = page.locator("#chat");
  await chat.hover();
  await page.mouse.wheel(0, -400);
  await settle(page);
  expect(await height(page)).toBeLessThanOrEqual(42);
  await expect(page.locator("#speakrow")).toBeVisible();
  await page.mouse.wheel(0, 4000);
  await settle(page);
  expect(await height(page)).toBe(144);
});

// R-0610
test("a tap on the strip opens the full picture", async ({ page }) => {
  await open(page);
  await page.locator("#chat").hover();
  await page.mouse.wheel(0, -400);
  await settle(page);
  expect(await height(page)).toBeLessThanOrEqual(42);
  await page.locator(PIC).click();
  await settle(page);
  expect(await height(page)).toBe(144);
});

const ZONE = (part: number) => `#view .ss-hit[data-target="zone"][aria-label$="part ${part}"]`;
const CLUSTER = `#view .ss-hit[data-target="cluster"]`;
const CHIP = (part: number) => `#chat .bub .chip:text-is("moment number ${part}")`;

/** Scrolled up the chat, so the picture is the strip. */
const folded = async (page: Page) => {
  await page.locator("#chat").hover();
  await page.mouse.wheel(0, -400);
  await settle(page);
  expect(await height(page)).toBeLessThanOrEqual(42);
};

/** A tap on the wire under one target, where it shows on the strip. */
const tapOnStrip = async (page: Page, target: string) => {
  const hit = await boxOf(page.locator(target).first());
  const wire = await boxOf(page.locator("#view line.wire").first(), true);
  await page.mouse.click(hit.x + hit.width / 2, wire.y + wire.height / 2);
  await page.waitForTimeout(700);
};

/** What is picked, and how the path above the picture writes its last step. */
const picked = (page: Page) =>
  page.evaluate(() => {
    const here = document.querySelector("#path .here")!;
    const step = document.querySelector("#path .step");
    return {
      dot: document.querySelectorAll("#view circle.dot.on").length,
      open: document.querySelectorAll("#view rect.pill.on").length,
      lit: here.classList.contains("on"),
      same: step !== null && getComputedStyle(here).color === getComputedStyle(step).color,
    };
  });

// R-0168, R-0540, R-0543
test("a tap on an event on the strip opens the picture with that event picked, its name in the path", async ({ page }) => {
  await open(page);
  await tapOnStrip(page, ZONE(4));
  const direct = await picked(page);
  expect(direct).toEqual({ dot: 1, open: 0, lit: true, same: true });

  await open(page);
  await folded(page);
  await tapOnStrip(page, ZONE(4));
  expect(await height(page)).toBe(144);
  expect(await picked(page)).toEqual(direct);
});

// R-0168, R-0540, R-0543
test("a tap on a cluster on the strip opens the picture with that cluster open", async ({ page }) => {
  await open(page);
  await folded(page);
  await tapOnStrip(page, CLUSTER);
  expect(await height(page)).toBe(144);
  expect(await picked(page)).toEqual({ dot: 0, open: 1, lit: false, same: false });
});

// R-0168, R-0540
test("a tap on an event chip with the picture folded opens it with that event picked", async ({ page }) => {
  await open(page);
  await tapOnStrip(page, ZONE(4));
  const direct = await picked(page);

  await open(page);
  await folded(page);
  const chip = page.locator(CHIP(4)).first();
  await chip.evaluate((el) => el.scrollIntoView({ block: "center" }));
  await settle(page);
  expect(await height(page)).toBeLessThanOrEqual(42);
  await chip.click();
  await page.waitForTimeout(700);
  expect(await height(page)).toBe(144);
  expect(await picked(page)).toEqual(direct);
});

// R-0540
test("with nothing picked the path stays in the quiet grey", async ({ page }) => {
  await open(page);
  expect(await picked(page)).toEqual({ dot: 0, open: 0, lit: false, same: false });
});
