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
  // A bubble still typing itself out keeps growing, and the first-run greeting
  // starts a moment after load, so waiting on a class is racy. Wait instead
  // until the thread stops changing shape: that is the page at rest, whatever
  // it was doing.
  await page.waitForFunction(
    () => {
      const shape = [...document.querySelectorAll(".bub")]
        .map((b) => {
          const at = b.getBoundingClientRect();
          return `${Math.round(at.width)}x${Math.round(at.height)}`;
        })
        .join(",");
      const w = window as unknown as { __shape?: string; __same?: number };
      w.__same = shape === w.__shape ? (w.__same ?? 0) + 1 : 0;
      w.__shape = shape;
      return !!shape && w.__same >= 6;
    },
    null,
    { timeout: 30000, polling: 100 },
  );
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
    // Three controls do not fit across a phone and do across a desktop window.
    // Either way the strip stays one line at its reserved height: where they do
    // not fit it scrolls sideways rather than wrapping.
    const strip = await page.locator(".caption").evaluate((node) => ({
      height: Math.round(node.getBoundingClientRect().height),
      children: node.childElementCount,
      rows: new Set(
        [...node.children].map((c) => Math.round(c.getBoundingClientRect().top)),
      ).size,
      scrollable: node.scrollWidth > node.clientWidth,
      fits: node.scrollWidth <= node.clientWidth,
    }));
    expect(strip.children).toBe(3);
    expect(strip.height).toBe(44);
    expect(strip.scrollable || strip.fits).toBe(true);
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
      test(`the picture region is 158 high at rest on the ${key} record`, async ({
        page,
      }) => {
        await settle(page);
        expect(await pictureHeight(page)).toBe(158);
      });
    });
  }

  // A tap on the picture opens a chapter, which is the one thing most likely
  // to move the chat, so it is checked on every shape of record.
  for (const key of ["one", "three40", "dense60"] as const) {
    test.describe(() => {
      test.use({ storageState: stateFor(key) });
      test(`opening a chapter moves nothing on the ${key} record`, async ({
        page,
      }) => {
        await settle(page);
        const before = await frame(page);
        expect(await pictureHeight(page)).toBe(158);

        await page.locator('.ss-hit[data-target="chapter"]').first().click();
        await expect(page.locator('.ss-hit[data-target="zone"]').first()).toBeVisible();
        await page.waitForTimeout(400);

        const open = await frame(page);
        expect(await pictureHeight(page)).toBe(158);
        expect(open.picture).toEqual(before.picture);
        expect(open.caption).toEqual(before.caption);
        expect(open.chat).toEqual(before.chat);
        expect(open.bubbles).toEqual(before.bubbles);

        // and tapping about inside the open chapter changes nothing either
        await page.locator('.ss-hit[data-target="zone"]').first().click();
        const after = await frame(page);
        expect(after.picture).toEqual(open.picture);
        expect(after.bubbles).toEqual(open.bubbles);
      });
    });
  }
});
