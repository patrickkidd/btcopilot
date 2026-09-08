import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** The layout contract, asserted rather than eyeballed: the picture region owns
 * its level's height and the chat fills what is left, so a tap on a chip or on
 * the picture never moves a chat bubble. The owner's words: the visual and the
 * header cannot change size when you click on chips, and chat bubbles must
 * never change position on screen just from a click on a chip. */

const settle = async (page: Page) => {
  await page.goto("/companion/");
  await expect(page.locator(".ss")).toBeVisible();
  await page.waitForTimeout(600);
};

/** Where every bubble sits, and how tall the two fixed regions above them are. */
const frame = (page: Page) =>
  page.evaluate(() => {
    const box = (selector: string) => {
      const at = document.querySelector(selector)?.getBoundingClientRect();
      return at ? [at.x, at.y, at.width, at.height] : null;
    };
    return {
      title: box(".titlerow"),
      picture: box(".pic"),
      caption: box(".caption"),
      chat: box(".chat"),
      bubbles: [...document.querySelectorAll(".bub")].map((bubble) => {
        const at = bubble.getBoundingClientRect();
        return [at.x, at.y, at.width, at.height];
      }),
    };
  });

test.describe("nothing moves when a chip is tapped", () => {
  test.use({ storageState: stateFor("moves") });

  test("a chip in a coach bubble aims the picture and moves nothing", async ({
    page,
  }) => {
    await settle(page);
    const chip = page.locator(".bub.coach .chip").first();
    await expect(chip).toBeVisible();

    const before = await frame(page);
    await chip.click();
    await page.waitForTimeout(500);
    const after = await frame(page);

    expect(after.title).toEqual(before.title);
    expect(after.picture).toEqual(before.picture);
    expect(after.caption).toEqual(before.caption);
    expect(after.chat).toEqual(before.chat);
    expect(after.bubbles).toEqual(before.bubbles);
  });

  test("tapping the wire selects a moment and moves nothing", async ({ page }) => {
    await settle(page);
    const before = await frame(page);
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    await expect(page.locator(".ss-t.on").first()).toBeVisible();
    const after = await frame(page);

    expect(after.picture).toEqual(before.picture);
    expect(after.caption).toEqual(before.caption);
    expect(after.bubbles).toEqual(before.bubbles);
  });

  test("the caption keeps its height whether or not anything is selected", async ({
    page,
  }) => {
    await settle(page);
    const empty = await frame(page);
    expect(await page.locator(".caption").innerHTML()).toBe("");

    await page.locator('.ss-hit[data-target="zone"]').first().click();
    await expect(page.locator(".caption .chip").first()).toBeVisible();
    const filled = await frame(page);

    expect(filled.caption).toEqual(empty.caption);
  });

  test("the caption stays one strip however many controls it holds", async ({
    page,
  }) => {
    await settle(page);
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    await expect(page.locator(".caption .trace")).toBeVisible();
    // three controls at 390px do not fit side by side, so the strip scrolls
    // sideways rather than wrapping onto a second line
    const strip = await page.locator(".caption").evaluate((node) => ({
      height: Math.round(node.getBoundingClientRect().height),
      children: node.childElementCount,
      overflows: node.scrollWidth > node.clientWidth,
    }));
    expect(strip.children).toBe(3);
    expect(strip.height).toBe(44);
    expect(strip.overflows).toBe(true);
  });
});

test.describe("the board is the only thing that resizes the picture", () => {
  test.use({ storageState: stateFor("moves") });

  test("the entry button says how many moves, and moves nothing until it is tapped", async ({
    page,
  }) => {
    await settle(page);
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    const enter = page.locator("#cap-play");
    await expect(enter).toContainText(/watch the \d+ moves?/);

    // the button appearing must not have moved anything
    const before = await frame(page);
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    const after = await frame(page);
    expect(after.picture).toEqual(before.picture);
    expect(after.caption).toEqual(before.caption);
    expect(after.bubbles).toEqual(before.bubbles);
  });
});

test.describe("a moment traces back to the words that coded it", () => {
  test.use({ storageState: stateFor("moves") });

  test("the chip names the session and the tap outlines the bubble", async ({
    page,
  }) => {
    await settle(page);
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    const chip = page.locator(".caption .trace");
    await expect(chip).toContainText("coded in:");

    const before = await frame(page);
    await chip.click();
    await expect(page.locator(".bub.traced")).toHaveCount(1);
    const after = await frame(page);

    // tracing scrolls the thread, it does not resize anything above it
    expect(after.picture).toEqual(before.picture);
    expect(after.caption).toEqual(before.caption);
    expect(after.chat).toEqual(before.chat);
  });
});

const pictureHeight = (page: Page) =>
  page.locator("#view").evaluate((node) => Math.round(node.getBoundingClientRect().height));

test.describe("each level is one fixed height", () => {
  for (const key of ["empty", "one", "three40", "dense60"] as const) {
    test.describe(() => {
      test.use({ storageState: stateFor(key) });
      test(`the resting level is 78 high on the ${key} record`, async ({
        page,
      }) => {
        await settle(page);
        expect(await pictureHeight(page)).toBe(78);
      });
    });
  }

  test.describe(() => {
    test.use({ storageState: stateFor("three40") });
    test("opening a chapter takes it to 158 and holds it there", async ({
      page,
    }) => {
      await settle(page);
      expect(await pictureHeight(page)).toBe(78);

      await page.locator('.ss-hit[data-target="chapter"]').first().click();
      await expect(page.locator('.ss-hit[data-target="zone"]').first()).toBeVisible();
      await page.waitForTimeout(400);
      expect(await pictureHeight(page)).toBe(158);

      // once open, tapping about inside the chapter never changes it again
      const before = await frame(page);
      await page.locator('.ss-hit[data-target="zone"]').first().click();
      expect(await pictureHeight(page)).toBe(158);
      const after = await frame(page);
      expect(after.picture).toEqual(before.picture);
      expect(after.bubbles).toEqual(before.bubbles);
    });
  });
});
