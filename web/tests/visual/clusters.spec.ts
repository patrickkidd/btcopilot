import { expect, test, type Page } from "@playwright/test";
import { stateFor, tellWithoutModel } from "./setup";

/** Opening a cluster and coming back out of it: the boxes at rest, the path
 * that goes back up, the page behind the small i, the board, and the card
 * each of those slides in on. Words, structure and geometry only. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(500);
};

const boxes = (page: Page) => page.locator('#view .ss-hit[data-target="cluster"]');
/** One step of the path over the line: 0 is the whole timeline, 1 the cluster. */
const step = (page: Page, i: number) => page.locator(`#path [data-step="${i}"]`);
const path = (page: Page) => page.locator("#path");
const name = (page: Page) => page.locator("#view .ss-name");
const zones = (page: Page) => page.locator('#view .ss-hit[data-target="zone"]');

const openCluster = async (page: Page, index = 0) => {
  await boxes(page).nth(index).click();
  await expect(step(page, 0)).toBeVisible();
  await page.waitForTimeout(400);
};

/** The moves record opens on the cluster its last coach message named, so the
 * whole line is one level up from where it starts. */
const toRest = async (page: Page) => {
  await step(page, 0).click();
  await expect(boxes(page).first()).toBeVisible();
  await page.waitForTimeout(400);
};

const pickMoment = async (page: Page) => {
  await zones(page).first().click();
  await expect(page.locator("#view .ss-t.on").first()).toBeVisible();
};

const wireY = (page: Page) =>
  page.locator("#view line.wire").first().evaluate((n) => Number(n.getAttribute("y1")));

test.describe("the three levels on the moves record", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0128, R-0570
  test("the whole line, one cluster, then its play-by-play, each in turn", async ({ page }) => {
    await tellWithoutModel(page);
    await settle(page);
    await toRest(page);
    await expect(path(page)).toHaveText("Timeline");
    await openCluster(page);
    await expect(name(page)).toHaveText("The walk (17)");
    await page.locator("#cap-play").click();
    await expect(page.locator("#pbp")).toBeVisible();
    await expect(page.locator("#view .ss.board")).toHaveCount(0);
  });

  // R-0213, R-0538, R-0583
  test("an open cluster's title ends with how many events it holds", async ({ page }) => {
    await tellWithoutModel(page);
    await settle(page);
    await toRest(page);
    const { clusters } = await (await page.request.get("/app/timeline")).json();
    const walk = clusters.find((c: { title: string; label: string }) => (c.title || c.label) === "The walk");
    await openCluster(page);
    await expect(name(page)).toHaveText(`The walk (${walk.count})`);
  });

  // R-0376
  test("a crowded box at rest carries no number of events", async ({ page }) => {
    await settle(page);
    await toRest(page);
    const words = await page.locator("#view svg text").allTextContents();
    expect(words).not.toContain("17");
  });
});

test.describe("the boxes at rest", () => {
  test.describe(() => {
    test.use({ storageState: stateFor("dense60") });
    // R-0112
    test("one box for each cluster the record holds", async ({ page }) => {
      await settle(page);
      await expect(page.locator("#view rect.pill")).toHaveCount(2);
      await expect(boxes(page)).toHaveCount(2);
    });
  });

  test.describe(() => {
    test.use({ storageState: stateFor("three40") });

    // R-0112, R-0543
    test("a pill reaches only as far as the events it holds, with none drawn inside", async ({
      page,
    }) => {
      await settle(page);
      const reach = await page.locator("#view svg").first().evaluate((svg) => {
        const pill = svg.querySelector("rect.pill") as SVGRectElement;
        const wire = svg.querySelector("line.wire") as SVGLineElement;
        const [x1, x2] = ["x1", "x2"].map((a) => Number(wire.getAttribute(a)));
        const t = (iso: string) => new Date(iso).getTime();
        // the record runs from its first event to its one loose one
        const at = (iso: string) =>
          x1 + ((t(iso) - t("1981-05-01")) / (t("2021-11-02") - t("1981-05-01"))) * (x2 - x1);
        const left = Number(pill.getAttribute("x"));
        const right = left + Number(pill.getAttribute("width"));
        const inside = [...svg.querySelectorAll("circle.dot")]
          .map((dot) => Number(dot.getAttribute("cx")))
          .filter((x) => x >= left && x <= right);
        return {
          dots: inside.length,
          before: at("1981-05-01") - left,
          after: right - at("2003-09-10"),
        };
      });
      expect(reach.dots).toBe(0);
      expect(reach.before).toBeLessThanOrEqual(12);
      expect(reach.after).toBeLessThanOrEqual(12);
    });

    // R-0129
    test("the row under the picture says a tap opens a cluster", async ({ page }) => {
      await settle(page);
      await expect(page.locator("#caption .cta")).toHaveText("tap a cluster");
    });

    // R-0129
    test("a tap near either end of a box opens it", async ({ page }) => {
      await settle(page);
      const box = (await page.locator("#view rect.pill").boundingBox())!;
      for (const x of [box.x + 4, box.x + box.width - 4]) {
        await page.mouse.click(x, box.y + box.height / 2);
        await expect(name(page)).toHaveText("Leaving and losing (3)");
        await step(page, 0).click();
        await expect(path(page)).toHaveText("Timeline");
        await page.waitForTimeout(400);
      }
    });
  });
});

test.describe("one cluster open on the sparse record", () => {
  test.use({ storageState: stateFor("three40") });

  // R-0540
  test("the path closes it and shows the whole line", async ({ page }) => {
    await settle(page);
    await openCluster(page);
    await step(page, 0).click();
    await expect(boxes(page).first()).toBeVisible();
    await expect(path(page)).toHaveText("Timeline");
    await expect(page.locator("#path button")).toHaveCount(0);
  });

  // R-0362, R-0540
  test("the path closes it even with a moment picked inside", async ({ page }) => {
    await settle(page);
    await openCluster(page);
    await pickMoment(page);
    await step(page, 0).click();
    await expect(page.locator("#view .ss-t.on")).toHaveCount(0);
    await expect(boxes(page).first()).toBeVisible();
    await expect(path(page)).toHaveText("Timeline");
  });

  // R-0202, R-0540, R-0543
  test("the way back stays up, and the open pill's own events take no tap", async ({
    page,
  }) => {
    await settle(page);
    await openCluster(page);
    // the one target on the line is the loose event's; none sits on the pill
    await expect(zones(page)).toHaveCount(1);
    const pill = (await page.locator("#view rect.pill").boundingBox())!;
    const zone = (await zones(page).first().boundingBox())!;
    expect(zone.x).toBeGreaterThanOrEqual(pill.x + pill.width - 1);
    await expect(step(page, 0)).toBeVisible();
    await expect(path(page)).toHaveText("Timeline \u203a 1981\u20132003");
  });


  // R-0213, R-0540
  test("the i says the cluster's reason under its name", async ({ page }) => {
    await settle(page);
    await openCluster(page);
    await page.locator("#info").click();
    await expect(path(page)).toHaveText("Timeline \u203a 1981\u20132003 \u203a about");
    await expect(page.locator("#view")).toContainText(
      "Ada lost her grandmother, and then moved away from everyone she knew.",
    );
  });

  // R-0213
  test("the i writes out no list of the cluster's moments", async ({ page }) => {
    test.skip(true, "unbuilt ruling, needs a design: what the picture spot draws behind a cluster's i, with no list and no count");
    await settle(page);
    await openCluster(page);
    await page.locator("#info").click();
    await expect(page.locator("#view")).toContainText("Ada lost her grandmother");
    await expect(page.locator("#view li")).toHaveCount(0);
  });

  // R-0376
  test("the page behind the i gives no count of events", async ({ page }) => {
    test.skip(true, "unbuilt ruling, needs a design: what the picture spot draws behind a cluster's i, with no list and no count");
    await settle(page);
    await openCluster(page);
    await page.locator("#info").click();
    await expect(page.locator("#view")).toContainText("Ada lost her grandmother");
    await expect(page.locator("#view")).not.toContainText(/\d+ events?/);
  });

  // R-0378
  test("the picture spot stays a drawing behind the i", async ({ page }) => {
    test.skip(true, "unbuilt ruling, needs a design: what the picture spot draws behind a cluster's i, with no list and no count");
    await settle(page);
    await openCluster(page);
    await page.locator("#info").click();
    await expect(page.locator("#view")).toContainText("Ada lost her grandmother");
    await expect(page.locator("#view svg")).not.toHaveCount(0);
  });

  // R-0540, R-0538
  test("a picked loose moment is written the way one inside a cluster is", async ({
    page,
  }) => {
    await settle(page);
    const resting = await wireY(page);

    // at rest the one moment no cluster claims is the only dot with a target
    await zones(page).first().click();
    await expect(page.locator("#view .ss-t.on").first()).toHaveText("Nov 2021");
    expect(await page.locator("#view .ss-t.on").count()).toBeLessThanOrEqual(2);
    await expect(page.locator("#view circle.dot.on")).toHaveCount(1);
    // the line stays where it runs at every level, and the box stays whole,
    // dimmed, under the words (R-0540)
    expect(await wireY(page)).toBe(resting);
    await expect(page.locator("#view rect.pill.dim")).toHaveCount(1);
  });
});

test.describe("every cluster on the dense record", () => {
  test.use({ storageState: stateFor("dense60") });

  // R-0202, R-0540
  test("shows the way back when tapped open", async ({ page }) => {
    await settle(page);
    for (const index of [0, 1]) {
      await expect(page.locator("#path button")).toHaveCount(0);
      await openCluster(page, index);
      await expect(step(page, 0)).toBeVisible();
      await step(page, 0).click();
      await expect(boxes(page).first()).toBeVisible();
      await page.waitForTimeout(400);
    }
  });
});

test.describe("a chip in the coach's words that names a cluster", () => {
  test.use({ storageState: stateFor("hostile") });

  // R-0373
  test("opens that cluster on the picture", async ({ page }) => {
    await settle(page);
    await expect(path(page)).toHaveText("Timeline");
    await page.locator(".bub.coach .chip.data").first().click();
    await expect(name(page)).toHaveText(
      "the cluster when everybody stopped speaking about the house and the money (3)",
    );
    await expect(step(page, 0)).toBeVisible();
  });
});

/** The layers of a slide are on the page for its length: going in, the level
 * leaving and the level arriving; going back, the level leaving alone. Each
 * must stand on ground of its own. */
const cards = (page: Page, layers: number) =>
  page.waitForFunction(
    (n) => {
      const lays = [...document.querySelectorAll(".pic .slide-lay")];
      if (lays.length < n) return null;
      return lays.map((lay) => getComputedStyle(lay).backgroundColor);
    },
    layers,
    { polling: "raf", timeout: 5000 },
  ).then((handle) => handle.jsonValue() as Promise<string[]>);

const solid = (colour: string) =>
  colour !== "transparent" && !/rgba\(.*,\s*0\)$/.test(colour);

test.describe("a level sliding in", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0230, R-0542
  test("the about page slides in on ground of its own", async ({ page }) => {
    await settle(page);
    const seen = cards(page, 2);
    await page.locator("#info").click();
    const colours = await seen;
    expect(colours.every(solid)).toBe(true);
  });

  // R-0230, R-0570, R-0132
  test("the play-by-play slides in on ground of its own", async ({ page }) => {
    await tellWithoutModel(page);
    await settle(page);
    await page.locator("#cap-play").click();
    await expect(page.locator("#pbp")).toBeVisible();
    expect(solid(await page.locator("#pbp").evaluate((d) => getComputedStyle(d).backgroundColor))).toBe(true);
  });

  // R-0230, R-0542
  test("going back up slides the level away on ground of its own", async ({ page }) => {
    await settle(page);
    await page.locator("#info").click();
    await page.waitForTimeout(600);
    const seen = cards(page, 1);
    await step(page, 1).click();
    const colours = await seen;
    expect(colours.every(solid)).toBe(true);
  });
});
