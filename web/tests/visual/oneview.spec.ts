import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";
import { mockTurn } from "./turn";

/** The strip reads as one view: one drawing at every level, a path row that
 * says where the reader is and is the way back, and what the coach touches
 * coloured on that same drawing while it replies. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(500);
};

const boxes = (page: Page) => page.locator('#view .ss-hit[data-target="cluster"]');
const zones = (page: Page) => page.locator('#view .ss-hit[data-target="zone"]');
const path = (page: Page) => page.locator("#path");
const step = (page: Page, i: number) => page.locator(`#path [data-step="${i}"]`);

const wireY = (page: Page) =>
  page.locator("#view line.wire").first().evaluate((n) => Number(n.getAttribute("y1")));

const openCluster = async (page: Page, index = 0) => {
  await boxes(page).nth(index).click();
  await expect(zones(page).first()).toBeVisible();
  await page.waitForTimeout(400);
};

const dot = (page: Page, id: number) => page.locator(`#view circle.dot[data-event="${id}"]`);

test.describe("one drawing at every level", () => {
  test.use({ storageState: stateFor("three40") });

  // R-0538, R-0377
  test("the line never changes height, whatever is open or picked", async ({ page }) => {
    await settle(page);
    const resting = await wireY(page);
    await openCluster(page);
    expect(await wireY(page)).toBe(resting);
    await zones(page).first().click();
    await expect(page.locator("#view .ss-t.on").first()).toBeVisible();
    expect(await wireY(page)).toBe(resting);
    await step(page, 0).click();
    await expect(boxes(page).first()).toBeVisible();
    await page.waitForTimeout(400);
    // the one moment no cluster claims, picked at rest
    await zones(page).first().click();
    await expect(page.locator("#view .ss-t.on").first()).toHaveText("Nov 2021");
    expect(await wireY(page)).toBe(resting);
    await expect(page.locator('#view [style*="epfade"]')).toHaveCount(0);
  });

  // R-0538
  test("an open cluster keeps the box it is drawn in and every other dot", async ({ page }) => {
    await settle(page);
    const dots = await page.locator("#view circle.dot").count();
    await openCluster(page);
    await expect(page.locator("#view rect.ep-edge")).toHaveCount(1);
    await expect(page.locator("#view .ep-g.open")).toHaveCount(1);
    await expect(page.locator("#view circle.dot")).toHaveCount(dots);
    // the loose moment stays, dimmed, rather than going
    await expect(dot(page, 13)).toHaveAttribute("opacity", /0\.\d+/);
    await expect(dot(page, 10)).not.toHaveAttribute("opacity", /.+/);
  });
});

test.describe("a tap on a box", () => {
  test.use({ storageState: stateFor("three40") });

  // R-0537
  test("opens its cluster wherever it lands in the box, even on one of its dots", async ({
    page,
  }) => {
    await settle(page);
    for (const id of [10, 11, 12]) {
      const at = (await dot(page, id).boundingBox())!;
      await page.mouse.click(at.x + at.width / 2, at.y + at.height / 2);
      await expect(page.locator("#view .ss-name")).toHaveText("Leaving and losing");
      await step(page, 0).click();
      await expect(path(page)).toHaveText("Timeline");
      await page.waitForTimeout(400);
    }
  });
});

test.describe("an open cluster among others", () => {
  test.use({ storageState: stateFor("dense60") });

  // R-0538
  test("every other box stays, dimmed, with the open one set apart", async ({ page }) => {
    await settle(page);
    await openCluster(page, 0);
    await expect(page.locator("#view rect.ep-edge")).toHaveCount(2);
    await expect(page.locator("#view .ep-g.open")).toHaveCount(1);
    await expect(page.locator("#view .ep-g.dim")).toHaveCount(1);
    // the other box still opens its own cluster
    await expect(boxes(page)).toHaveCount(1);
  });
});

test.describe("the path row", () => {
  test.use({ storageState: stateFor("three40") });

  // R-0540, R-0538
  test("says where the reader is, and each earlier step goes back to it", async ({ page }) => {
    await settle(page);
    await expect(path(page)).toHaveText("Timeline");
    await expect(page.locator("#path button")).toHaveCount(0);
    await openCluster(page);
    await expect(path(page)).toHaveText("Timeline › 1981–2003");
    await expect(page.locator("#view .ss-name")).toHaveText("Leaving and losing");
    await zones(page).first().click();
    await expect(path(page)).toHaveText("Timeline › 1981–2003 › Ada Grandmother died");
    // a moment picked takes the words over the line; the chip row never
    // carries the name
    await expect(page.locator("#view .ss-name")).toHaveCount(0);
    // what the path says is not said again over the line: only the date
    await expect(page.locator("#view .ss-t.on")).toHaveText(["1981"]);
    await expect(page.locator("#view .ss-yr")).toHaveCount(0);
    await expect(page.locator("#caption .name")).toHaveCount(0);

    await step(page, 1).click();
    await expect(page.locator("#view .ss-t.on")).toHaveCount(0);
    await expect(zones(page).first()).toBeVisible();
    await expect(path(page)).toHaveText("Timeline › 1981–2003");

    await step(page, 0).click();
    await expect(boxes(page).first()).toBeVisible();
    await expect(path(page)).toHaveText("Timeline");
    await expect(page.locator("#caption .cta")).toHaveText("tap a cluster");
  });

  // R-0540
  test("stands in for the back arrow and the cross, which are gone", async ({ page }) => {
    await settle(page);
    await openCluster(page);
    await zones(page).first().click();
    await expect(page.locator("#up, #clear")).toHaveCount(0);
    await step(page, 0).click();
    await page.waitForTimeout(400);
    // a loose moment picked at rest: the whole line is the way to put it down
    await zones(page).first().click();
    await expect(path(page)).toHaveText("Timeline › Ben stopped calling");
    await step(page, 0).click();
    await expect(page.locator("#view .ss-t.on")).toHaveCount(0);
    await expect(path(page)).toHaveText("Timeline");
  });

  // R-0540
  test("the page behind the i is a mode of the cluster", async ({ page }) => {
    await settle(page);
    await openCluster(page);
    await page.locator("#info").click();
    await expect(path(page)).toHaveText("Timeline › 1981–2003 › about");
    await step(page, 1).click();
    await expect(zones(page).first()).toBeVisible();
  });
});

test.describe("the path row on the board", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0540
  test("names the play-by-play as a mode of its cluster, and goes back to it", async ({
    page,
  }) => {
    await settle(page);
    await page.locator("#cap-play").click();
    await expect(page.locator("#view .ss.board")).toBeVisible();
    await expect(path(page)).toHaveText(/^Timeline › [\d–]+ › explain$/);
    await step(page, 1).click();
    await expect(page.locator("#view .ss.board")).toHaveCount(0);
    await expect(zones(page).first()).toBeVisible();
  });
});

test.describe("the path row at a phone's width", () => {
  test.use({ storageState: stateFor("three40") });

  // R-0540
  test("keeps a short last step whole, the earlier steps giving way first", async ({
    page,
  }) => {
    await settle(page);
    await openCluster(page);
    await zones(page).first().click();
    await expect(page.locator("#path .here")).toHaveText("Ada Grandmother died");
    const cut = await page
      .locator("#path .here")
      .evaluate((here) => here.scrollWidth - here.clientWidth);
    expect(cut).toBeLessThanOrEqual(0);
  });
});

test.describe("the modes of a cluster", () => {
  const still = async (page: Page, open: () => Promise<void>) => {
    const where = async () => ({
      view: Math.round((await page.locator("#view").boundingBox())!.height),
      bubble: Math.round((await page.locator(".bub").first().boundingBox())!.y),
      header: Math.round((await page.locator(".pin-label").first().boundingBox())!.y),
    });
    const before = await where();
    await open();
    await page.waitForTimeout(700);
    await expect(page.locator("#view .card")).toBeVisible();
    const bg = await page.locator("#view .card").evaluate((c) => getComputedStyle(c).backgroundColor);
    expect(bg).not.toMatch(/rgba\(.*,\s*0\)$|transparent/);
    expect(await where()).toEqual(before);
  };

  test.describe(() => {
    test.use({ storageState: stateFor("three40") });
    // R-0460, R-0230
    test("the about page opens as a card over the chat, and nothing moves", async ({ page }) => {
      await settle(page);
      await openCluster(page);
      await still(page, () => page.locator("#info").click());
    });
  });

  test.describe(() => {
    test.use({ storageState: stateFor("moves") });
    // R-0460, R-0230
    test("the board opens as a card over the chat, and nothing moves", async ({ page }) => {
      await settle(page);
      await still(page, () => page.locator("#cap-play").click());
    });
  });
});

test.describe("the open cluster's name on a crowded line", () => {
  test.use({ storageState: stateFor("dense60") });

  // R-0538
  test("stays inside the picture, whichever cluster is open", async ({ page }) => {
    await settle(page);
    for (const index of [1, 0]) {
      await boxes(page).nth(index).click();
      await expect(page.locator("#view .ss-name")).toBeVisible();
      await page.waitForTimeout(600);
      const [name, pic] = await Promise.all([
        page.locator("#view .ss-name").boundingBox(),
        page.locator("#chat-screen .pic").boundingBox(),
      ]);
      expect(name!.x).toBeGreaterThanOrEqual(pic!.x);
      expect(name!.x + name!.width).toBeLessThanOrEqual(pic!.x + pic!.width);
      await step(page, 0).click();
      await page.waitForTimeout(600);
    }
  });
});

test.describe("the path row with long words", () => {
  test.use({ storageState: stateFor("hostile") });

  // R-0540
  test("stays one line, the last step cut short rather than wrapped", async ({ page }) => {
    await settle(page);
    await openCluster(page);
    await zones(page).first().click();
    await expect(page.locator("#path .here")).toBeVisible();
    const fit = await page.evaluate(() => {
      const row = document.querySelector("#path") as HTMLElement;
      const here = document.querySelector("#path .here") as HTMLElement;
      return {
        lines: Math.round(here.getBoundingClientRect().height / parseFloat(getComputedStyle(here).lineHeight)),
        spill: row.scrollWidth - row.clientWidth,
        right: row.getBoundingClientRect().right,
        page: document.documentElement.clientWidth,
      };
    });
    expect(fit.lines).toBe(1);
    expect(fit.spill).toBeLessThanOrEqual(0);
    expect(fit.right).toBeLessThanOrEqual(fit.page);
  });
});

test.describe("what the coach touches while it replies", () => {
  test.use({ storageState: stateFor("three40") });

  // R-0539
  test("colours each event as the call lands and keeps it until the next message", async ({
    page,
  }) => {
    await settle(page);
    const delta = (id: string, field: string | null, before: unknown, after: unknown) => ({
      item_kind: "event",
      item_id: id,
      field,
      before,
      after,
    });
    await mockTurn(page, {
      statement: "I looked back over those years.",
      statement_id: 9401,
      pause: 2500,
      did: [
        {
          type: "tool_call",
          name: "read_events",
          args: { cluster: "cT" },
          names: {},
          refusal: null,
          read: [10, 11, 12],
        },
        {
          type: "tool_call",
          name: "edit_event",
          args: { id: 13, version: 1, description: "Ben stopped calling" },
          names: { it: "Ben stopped calling" },
          refusal: null,
        },
        { type: "record_patch", deltas: [delta("13", "description", "a", "b")], turn_id: "t1" },
        {
          type: "tool_call",
          name: "remove",
          args: { item_kind: "event", item_id: 11, version: 1 },
          names: { it: "The winter she stopped calling home" },
          refusal: null,
        },
        { type: "record_patch", deltas: [delta("11", null, { id: 11 }, null)], turn_id: "t1" },
      ],
    });
    await page.locator("#composer").fill("Look back over it.");
    await page.locator("#send").click();

    // while the coach is still working: a read over the whole cluster greys
    // its box, not every dot; a change is yellow and a removal red
    await expect(page.locator("#view .ep-g.read")).toHaveCount(1);
    await expect(dot(page, 13)).toHaveClass(/\bchange\b/);
    await expect(dot(page, 11)).toHaveClass(/\bremove\b/);
    await expect(dot(page, 10)).not.toHaveClass(/\bread\b/);

    await expect(page.locator(".bub.coach").last()).toContainText("I looked back", {
      timeout: 10000,
    });
    await expect(dot(page, 13)).toHaveClass(/\bchange\b/);
    await expect(page.locator("#view .ep-g.read")).toHaveCount(1);

    await mockTurn(page, { statement: "Noted.", statement_id: 9403 });
    await page.locator("#composer").fill("Thanks.");
    await page.locator("#send").click();
    await expect(dot(page, 13)).not.toHaveClass(/\bchange\b/);
    await expect(page.locator("#view .ep-g.read")).toHaveCount(0);
  });
});
