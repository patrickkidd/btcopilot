import { expect, test, type Page } from "@playwright/test";
import { PIC_H } from "../../src/spotlight";
import { NO_LIST, pinned, stateFor } from "./setup";

/** The layout contract, asserted rather than eyeballed: the picture region owns
 * its level's height and the chat fills what is left, so a tap on a chip or on
 * the picture never moves a chat bubble [Oracle: R-0460]. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
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
      // R-0350: an untouched session carries no bubble at all, only the block
      // of words inviting the first message, so no bubbles is also at rest.
      const started = !!shape || !!document.querySelector("#chat .cta");
      return started && w.__same >= 6;
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

  // R-0168, R-0001
  test("a chip in a coach bubble aims the picture and moves nothing", async ({
    page,
  }) => {
    await settle(page);
    // The chip in the newest ordinary bubble. It must be one already on screen,
    // or Playwright scrolls the thread to reach it and that scroll is measured
    // as the page moving; and it must not be a play-by-play, whose chips are
    // ruled to step the board, which is the one deliberate level change.
    const chip = page
      .locator(".bub.coach:not([data-play])")
      .last()
      .locator(".chip")
      .first();
    await expect(chip).toBeVisible();
    // Bring it into view first: the thread's own scroll to reach a chip is not
    // the page moving, and measuring before that scroll would count it as one.
    await chip.scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);

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

  // R-0210
  test("tapping the wire selects a moment and moves nothing", async ({ page }) => {
    await settle(page);
    const before = await frame(page);
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    await expect(page.locator("#view .ss-t.on").first()).toBeVisible();
    const after = await frame(page);

    expect(after.picture).toEqual(before.picture);
    expect(after.caption).toEqual(before.caption);
    expect(after.bubbles).toEqual(before.bubbles);
  });

  // R-0212
  test("the row keeps its height and its three chips whatever is picked", async ({
    page,
  }) => {
    await settle(page);
    // this record opens on the cluster the coach's last message named, so the
    // picture is put down first to see the row with nothing picked
    await page.locator("#crumb").click();
    await page.waitForTimeout(400);
    const empty = await frame(page);
    await expect(page.locator("#chat-screen .caption .cta")).toHaveText("tap a cluster");

    await page.locator('.ss-hit[data-target="cluster"]').first().click();
    await page.waitForTimeout(400);
    // a cluster open: ask about it, or have it explained
    await expect(page.locator("#cap-chip")).not.toHaveClass(/dim/);
    await expect(page.locator("#cap-play")).not.toHaveClass(/dim/);
    await expect(page.locator("#cap-trace")).toHaveClass(/dim/);
    const open = await frame(page);

    await page.locator('.ss-hit[data-target="zone"]').first().click();
    // a moment picked: ask about it, or go to where it was said
    await expect(page.locator("#cap-play")).toHaveClass(/dim/);
    await expect(page.locator("#cap-trace")).not.toHaveClass(/dim/);
    const picked = await frame(page);

    // and the row is the same height throughout
    expect(open.caption).toEqual(empty.caption);
    expect(picked.caption).toEqual(empty.caption);
  });

  // R-0212
  test("the caption stays one strip however many controls it holds", async ({
    page,
  }) => {
    await settle(page);
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    await expect(page.locator("#cap-chip")).toBeVisible();
    // The three chips are 26 tall in the middle of the 44 band, on one line,
    // and each is as wide as its own word (picked plate F).
    const strip = await page.locator("#chat-screen .caption").evaluate((node) => ({
      height: Math.round(node.getBoundingClientRect().height),
      children: node.childElementCount,
      rows: new Set(
        [...node.children].map((c) => {
          const at = c.getBoundingClientRect();
          return Math.round(at.top + at.height / 2);
        }),
      ).size,
      heights: [...node.children].map((c) =>
        Math.round(c.getBoundingClientRect().height),
      ),
      fits: node.scrollWidth <= node.clientWidth,
    }));
    // ask, explain and in chat, and the list button where one is drawn
    const chips = [26, 26, 26];
    expect(strip.heights).toEqual((await pinned(page)) ? chips : [...chips, 44]);
    expect(strip.height).toBe(44);
    expect(strip.rows).toBe(1);
    // and with one word each they fit across a phone, which the record's own
    // words in the asking chip never did
    expect(strip.fits).toBe(true);
  });
});

/** The caption row on every record the app can be handed: it stays one line at
 * its reserved height, and nothing it holds sits outside it. With one word on
 * each of the three chips the row fits across a phone (picked plate F), where
 * the record's own words in the asking chip never did. */
for (const key of ["one", "three40", "dense60", "hostile", "moves", "play", "longmove", "longname"] as const) {
  test.describe(`the caption row on the ${key} record`, () => {
    test.use({ storageState: stateFor(key) });

    // R-0212
    test("holds every control inside itself, on one line", async ({ page }) => {
      await settle(page);
      // a record whose moments are inside a cluster needs it opened first
      const clusters = page.locator('.ss-hit[data-target="cluster"]');
      if (await clusters.first().isVisible().catch(() => false)) {
        await clusters.first().click();
        await page.waitForTimeout(400);
      }
      const zones = page.locator('.ss-hit[data-target="zone"]');
      await zones.first().click();
      await expect(page.locator("#chat-screen .caption .tok").first()).toBeVisible();

      const row = await page.locator("#chat-screen .caption").evaluate((node) => {
        const box = node.getBoundingClientRect();
        return {
          height: Math.round(box.height),
          // one line: the controls are different heights, so what tells a
          // wrap from a row is where their middles sit
          rows: new Set(
            [...node.children].map((c) => {
              const at = c.getBoundingClientRect();
              return Math.round(at.top + at.height / 2);
            }),
          ).size,
          // where a control sits in the strip's own content, which is what it
          // may not leave: above its top, or past everything it holds
          escaped: [...node.children]
            .filter((c) => {
              const at = c.getBoundingClientRect();
              const left = at.left - box.left + node.scrollLeft;
              return left < -1 || left + at.width > node.scrollWidth + 1;
            })
            .map((c) => (c as HTMLElement).id),
          // the chips are 26 in the middle of the band; the button that opens
          // the list is the row's own 44 control at its end
          tall: [...node.children].filter((c) =>
            c.classList.contains("tok")
              ? Math.round(c.getBoundingClientRect().height) !== 26
              : Math.round(c.getBoundingClientRect().height) !== 44,
          ).length,
        };
      });
      expect(row.escaped).toEqual([]);
      expect(row.tall).toBe(0);
      expect(row.rows).toBe(1);
      expect(row.height).toBe(44);
    });
  });
}


test.describe("a scrollbar appearing never shifts the page", () => {
  // The undated shelf used to be the tap this watched. It is no longer drawn
  // or tappable (R-0359) — the empty record offers nothing on the picture to
  // touch at all — so the tap that brings the row of controls in is a moment
  // picked on a record that has some.
  test.use({ storageState: stateFor("three40") });

  // R-0460
  test("picking a moment moves nothing sideways", async ({ page }) => {
    await settle(page);
    const before = await frame(page);
    await page.locator('#view .ss-hit[data-target="cluster"]').first().click();
    await page.locator('#view .ss-hit[data-target="zone"]').first().click();
    await expect(page.locator("#cap-chip")).toBeVisible();
    await page.waitForTimeout(300);
    const after = await frame(page);
    expect(after.chat).toEqual(before.chat);
    expect(after.picture).toEqual(before.picture);
    expect(after.bubbles).toEqual(before.bubbles);
  });
});

test.describe("the board is the only thing that resizes the picture", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0212
  test("the way onto the board says explain, and moves nothing until it is tapped", async ({
    page,
  }) => {
    await settle(page);
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    await expect(page.locator("#cap-play")).toHaveText("explain");

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

test.describe("a long family name", () => {
  test.use({ storageState: stateFor("longname") });

  // R-0181
  test("is cut with an ellipsis rather than spilling over the picture", async ({
    page,
  }) => {
    await settle(page);
    const title = page.locator("#title");
    // the record's own name, not a stock phrase
    await expect(title).toHaveText("The Fitzgerald-Winterbottom Family Files");

    const fit = await title.evaluate((node) => {
      const row = node.parentElement!.getBoundingClientRect();
      const at = node.getBoundingClientRect();
      return {
        // a wide window has room for the whole name; a phone has not
        clipped: node.scrollWidth > node.clientWidth,
        ellipsised: getComputedStyle(node).textOverflow === "ellipsis",
        spillsRight: Math.round(at.right - row.right),
        rows: Math.round(at.height),
      };
    });
    expect(fit.ellipsised).toBe(true);
    expect(fit.spillsRight).toBeLessThanOrEqual(0);
    // one line: a wrapped title is what pushed the picture down
    expect(fit.rows).toBeLessThanOrEqual(24);

    // and the control beside it keeps its ruled size
    const avatar = (await page.locator("#account").boundingBox())!;
    expect(Math.round(avatar.width)).toBe(44);
    expect(Math.round(avatar.height)).toBe(44);
    // the list button is at the end of the row of chips, at its ruled size
    if (!(await pinned(page))) {
      const list = (await page.locator("#menu-open").boundingBox())!;
      expect([Math.round(list.width), Math.round(list.height)]).toEqual([44, 44]);
    }

    // the picture starts where it always starts
    expect(await pictureHeight(page)).toBe(BAND);
  });
});

test.describe("the moves board fills the room it takes", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0210, R-0132
  test("no empty band under the drawing or the controls", async ({ page }) => {
    await settle(page);
    await page.locator("#cap-play").click();
    await expect(page.locator("#view .ss.board")).toBeVisible();
    await page.waitForTimeout(600);

    const fit = await page.evaluate(() => {
      const view = document.querySelector("#view")!;
      const parts = [...view.children].map((n) => n.getBoundingClientRect().height);
      const last = view.lastElementChild!;
      return {
        region: Math.round(view.getBoundingClientRect().height),
        content: Math.round(parts.reduce((a, b) => a + b, 0)),
        lastClass: last.className,
        lastBottom: Math.round(last.getBoundingClientRect().bottom),
        regionBottom: Math.round(view.getBoundingClientRect().bottom),
      };
    });
    // the region is exactly what it holds, and the controls are the last thing
    expect(fit.region).toBe(fit.content);
    expect(fit.lastClass).toContain("pctl");
    expect(fit.regionBottom - fit.lastBottom).toBeLessThanOrEqual(1);

    // and the ruled control height survives
    for (const box of await page.locator("#chat-screen .pctl .btn").all())
      expect(Math.round((await box.boundingBox())!.height)).toBeGreaterThanOrEqual(44);
  });
});

test.describe("a moment traces back to the words that coded it", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0220, R-0192
  test("the said chip takes the thread to where it was said", async ({
    page,
  }) => {
    await settle(page);
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    const chip = page.locator("#cap-trace");
    await expect(chip).toHaveText("in chat");
    await expect(chip).not.toHaveClass(/dim/);

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

/** The band the line is drawn in: 72 of the picture's 144 (picked phone mockup
 * 2026-09-08, band grown by six on 2026-09-08 so the year under the picked
 * moment clears the row of controls, and by six more on 2026-09-24 so the
 * picked dot stands clear of its words), the other 72 being the name row and
 * the row of controls under it. */
const BAND = PIC_H;

const pictureHeight = (page: Page) =>
  page.locator("#view").evaluate((node) => Math.round(node.getBoundingClientRect().height));

/** What each row of the picture region measures, which is what the 144 is made
 * of. Exact, because the whole point of the number is that nothing under it
 * moves. */
const rowHeights = (page: Page) =>
  page.evaluate(() =>
    [".pin-label", "#view", ".caption"].map((sel) =>
      Math.round(document.querySelector(sel)!.getBoundingClientRect().height),
    ),
  );

test.describe("each level is one fixed height", () => {
  for (const key of ["empty", "one", "three40", "dense60"] as const) {
    test.describe(() => {
      test.use({ storageState: stateFor(key) });
      // R-0210
      test(`the band the line is drawn in is ${BAND} high at rest on the ${key} record`, async ({
        page,
      }) => {
        await settle(page);
        expect(await pictureHeight(page)).toBe(BAND);
        // the name row, the band, and the row of controls: 28, 72 and 44
        expect(await rowHeights(page)).toEqual([28, BAND, 44]);
      });
    });
  }

  // A tap on the picture opens a cluster, or picks a moment that is in none,
  // and that is the one thing most likely to move the chat, so it is checked on
  // every shape of record.
  for (const key of ["one", "three40", "dense60"] as const) {
    test.describe(() => {
      test.use({ storageState: stateFor(key) });
      // R-0210, R-0132
      test(`opening a cluster moves nothing on the ${key} record`, async ({
        page,
      }) => {
        await settle(page);
        const before = await frame(page);
        expect(await pictureHeight(page)).toBe(BAND);

        // a record with no cluster of its own has its moments as loose dots
        const box = page.locator('.ss-hit[data-target="cluster"]');
        if (await box.first().isVisible().catch(() => false)) await box.first().click();
        else await page.locator('.ss-hit[data-target="zone"]').first().click();
        await expect(page.locator('.ss-hit[data-target="zone"]').first()).toBeVisible();
        await page.waitForTimeout(400);

        const open = await frame(page);
        expect(await pictureHeight(page)).toBe(BAND);
        expect(open.picture).toEqual(before.picture);
        expect(open.caption).toEqual(before.caption);
        expect(open.chat).toEqual(before.chat);
        expect(open.bubbles).toEqual(before.bubbles);

        // and tapping about inside the open cluster changes nothing either
        await page.locator('.ss-hit[data-target="zone"]').first().click();
        const after = await frame(page);
        expect(after.picture).toEqual(open.picture);
        expect(after.bubbles).toEqual(open.bubbles);
      });
    });
  }
});

/** Which of the row's buttons can be pressed right now. */
const live = (page: Page) =>
  page
    .locator("#caption button.tok:not(.dim)")
    .evaluateAll((buttons) => buttons.map((b) => b.id));

test.describe("the row under the picture from one view to the next", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0450
  test("the picture stays put while the row's buttons change", async ({ page }) => {
    await settle(page);
    await page.locator("#up").click();
    await expect(page.locator('#view .ss-hit[data-target="cluster"]').first()).toBeVisible();
    await page.waitForTimeout(400);
    const rest = { at: await frame(page), live: await live(page) };

    await page.locator('#view .ss-hit[data-target="cluster"]').first().click();
    await page.waitForTimeout(400);
    const open = { at: await frame(page), live: await live(page) };

    await page.locator('#view .ss-hit[data-target="zone"]').first().click();
    await page.waitForTimeout(300);
    const picked = { at: await frame(page), live: await live(page) };

    // what can be pressed follows what is on the picture
    expect(rest.live).toEqual([]);
    expect(open.live).toEqual(["cap-chip", "cap-play"]);
    expect(picked.live).toEqual(["cap-chip", "cap-trace"]);
    // and nothing above or around the row moves for it
    for (const now of [open.at, picked.at]) {
      expect(now.picture).toEqual(rest.at.picture);
      expect(now.caption).toEqual(rest.at.caption);
      expect(now.bubbles).toEqual(rest.at.bubbles);
    }
    expect(rest.at.caption?.[3]).toBe(44);
  });

  // R-0450
  test("the row keeps its height with the board open", async ({ page }) => {
    await settle(page);
    const before = await frame(page);
    await page.locator("#cap-play").click();
    await expect(page.locator("#view .ss.board")).toBeVisible();
    await page.waitForTimeout(600);
    const after = await frame(page);
    expect(after.caption?.[3]).toBe(before.caption?.[3]);
  });
});

test.describe("the button that opens the lists", () => {
  test.use({ storageState: stateFor("three40") });

  const place = (page: Page) =>
    page.evaluate(() => {
      const row = document.querySelector("#caption")!;
      const box = row.getBoundingClientRect();
      const button = document.querySelector("#menu-open")!.getBoundingClientRect();
      return {
        inRow: button.top >= box.top - 1 && button.bottom <= box.bottom + 1,
        fromRight: Math.round(box.right - button.right),
        last: row.lastElementChild?.id,
        order: [...row.children].map((c) => c.id).filter(Boolean),
      };
    });

  // R-0221
  test("sits in the row under the picture, at its right end", async ({ page }) => {
    await settle(page);
    test.skip(await pinned(page), NO_LIST);
    const at = await place(page);
    expect(at.inRow).toBe(true);
    expect(at.last).toBe("menu-open");
    expect(at.fromRight).toBeGreaterThanOrEqual(0);
    expect(at.fromRight).toBeLessThanOrEqual(16);
  });

  // R-0221
  test("stays at the right end after ask, explain and in chat", async ({ page }) => {
    await settle(page);
    test.skip(await pinned(page), NO_LIST);
    await page.locator('#view .ss-hit[data-target="cluster"]').first().click();
    await page.locator('#view .ss-hit[data-target="zone"]').first().click();
    await expect(page.locator("#cap-chip")).toBeVisible();
    const at = await place(page);
    expect(at.order).toEqual(["cap-chip", "cap-play", "cap-trace", "menu-open"]);
    expect(at.inRow).toBe(true);
    expect(at.fromRight).toBeGreaterThanOrEqual(0);
    expect(at.fromRight).toBeLessThanOrEqual(16);
  });
});
