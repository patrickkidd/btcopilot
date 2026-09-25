import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** Opening a cluster and coming back out of it: the boxes at rest, the arrow
 * that goes up one level, the page behind the small i, the board, and the
 * card each of those slides in on. Words, structure and geometry only. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(500);
};

const boxes = (page: Page) => page.locator('#view .ss-hit[data-target="cluster"]');
const zones = (page: Page) => page.locator('#view .ss-hit[data-target="zone"]');

const openCluster = async (page: Page, index = 0) => {
  await boxes(page).nth(index).click();
  await expect(zones(page).first()).toBeVisible();
  await page.waitForTimeout(400);
};

/** The moves record opens on the cluster its last coach message named, so the
 * whole line is one level up from where it starts. */
const toRest = async (page: Page) => {
  await page.locator("#up").click();
  await expect(boxes(page).first()).toBeVisible();
  await page.waitForTimeout(400);
};

const pickMoment = async (page: Page) => {
  await zones(page).first().click();
  await expect(page.locator("#view .ss-t.on").first()).toBeVisible();
};

const tapWords = async (page: Page) => {
  const box = (await page.locator("#view .ss-t.on").first().boundingBox())!;
  await page.mouse.click(box.x + Math.min(30, box.width / 2), box.y + box.height / 2);
};

const wireY = (page: Page) =>
  page.locator("#view line.wire").first().evaluate((n) => Number(n.getAttribute("y1")));

test.describe("the three levels on the moves record", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0128
  test("the whole line, one cluster, then its board, each in turn", async ({ page }) => {
    await settle(page);
    await toRest(page);
    await expect(page.locator("#crumb")).toHaveText("Family timeline");
    await openCluster(page);
    await expect(page.locator("#crumb")).toHaveText("The walk");
    await page.locator("#cap-play").click();
    await expect(page.locator("#view .ss.board")).toBeVisible();
    await expect(page.locator("#view .pctl button")).toHaveCount(3);
  });

  // R-0131
  test("the arrow on the board goes back to the cluster it came from", async ({ page }) => {
    await settle(page);
    await page.locator("#cap-play").click();
    await expect(page.locator("#view .ss.board")).toBeVisible();
    await page.locator("#up").click();
    await expect(page.locator("#view .ss.board")).toHaveCount(0);
    await expect(zones(page).first()).toBeVisible();
    await expect(page.locator("#crumb")).toHaveText("The walk");
  });

  // R-0071
  test("explain puts the whole cluster on the board at once", async ({ page }) => {
    await settle(page);
    await page.locator("#cap-play").click();
    await expect(page.locator("#view .ss.board")).toBeVisible();
    // the first move is between two people, and everyone the cluster
    // involves is already on stage for it
    for (const name of ["Ada", "Ben", "Cal"])
      await expect(page.locator("#view .ss.board svg")).toContainText(name);
    await expect(page.locator('#view [data-target="prev"]')).toBeDisabled();
    await expect(page.locator('#view [data-target="next"]')).toBeEnabled();
  });

  // R-0376
  test("a crowded box at rest carries no number of events", async ({ page }) => {
    test.fail(true, "a cluster of more than eight moments is drawn as a ring with its count");
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
      await expect(page.locator("#view rect.ep-edge")).toHaveCount(2);
      await expect(boxes(page)).toHaveCount(2);
    });
  });

  test.describe(() => {
    test.use({ storageState: stateFor("three40") });

    // R-0112
    test("a box reaches only as far as the moments it holds", async ({ page }) => {
      await settle(page);
      const reach = await page.locator("#view svg").first().evaluate((svg) => {
        const box = svg.querySelector("rect.ep-edge") as SVGRectElement;
        const left = Number(box.getAttribute("x"));
        const right = left + Number(box.getAttribute("width"));
        const inside = [...svg.querySelectorAll("circle.dot")]
          .map((dot) => Number(dot.getAttribute("cx")))
          .filter((x) => x >= left && x <= right);
        return {
          count: inside.length,
          before: Math.min(...inside) - left,
          after: right - Math.max(...inside),
        };
      });
      expect(reach.count).toBe(3);
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
      const box = (await page.locator("#view rect.ep-edge").boundingBox())!;
      for (const x of [box.x + 4, box.x + box.width - 4]) {
        await page.mouse.click(x, box.y + box.height / 2);
        await expect(page.locator("#crumb")).toHaveText("Leaving and losing");
        await page.locator("#up").click();
        await expect(page.locator("#crumb")).toHaveText("Family timeline");
        await page.waitForTimeout(400);
      }
    });
  });
});

test.describe("one cluster open on the sparse record", () => {
  test.use({ storageState: stateFor("three40") });

  // R-0131
  test("the arrow closes it and shows the whole line", async ({ page }) => {
    await settle(page);
    await openCluster(page);
    await page.locator("#up").click();
    await expect(boxes(page).first()).toBeVisible();
    await expect(page.locator("#crumb")).toHaveText("Family timeline");
    await expect(page.locator("#up")).toBeHidden();
  });

  // R-0362
  test("the arrow closes it even with a moment picked inside", async ({ page }) => {
    await settle(page);
    await openCluster(page);
    await pickMoment(page);
    await page.locator("#up").click();
    await expect(page.locator("#view .ss-t.on")).toHaveCount(0);
    await expect(boxes(page).first()).toBeVisible();
    await expect(page.locator("#crumb")).toHaveText("Family timeline");
  });

  // R-0202
  test("the arrow stays up while a moment inside it is picked", async ({ page }) => {
    await settle(page);
    await openCluster(page);
    await pickMoment(page);
    await expect(page.locator("#up")).toBeVisible();
  });

  // R-0207
  test("the editor the words open is the picked moment's own", async ({ page }) => {
    await settle(page);
    await openCluster(page);
    await pickMoment(page);
    await expect(page.locator("#view .ss-t.on").first()).toHaveText("Ada · Grandmother died");
    await tapWords(page);
    await expect(page.locator("#menu-screen")).toBeVisible();
    await expect(
      page.locator('#menu-body .editor .f[data-name="description"]'),
    ).toHaveValue("Grandmother died");
  });

  // R-0207
  test("from that editor the back arrow returns to the same open cluster", async ({
    page,
  }) => {
    await settle(page);
    await openCluster(page);
    await pickMoment(page);
    await tapWords(page);
    await expect(page.locator("#menu-body .editor")).toBeVisible();
    await page.locator("#menu-close").click();
    await expect(page.locator("#menu-screen")).toBeHidden();
    await expect(page.locator("#crumb")).toHaveText("Leaving and losing");
    await expect(zones(page).first()).toBeVisible();
  });

  // R-0207
  test("the jump lands on the list of events, not people", async ({ page }) => {
    await settle(page);
    await openCluster(page);
    await pickMoment(page);
    await tapWords(page);
    await expect(page.locator("#tab-events")).toHaveClass(/on/);
    await expect(page.locator("#tab-people")).not.toHaveClass(/on/);
    await expect(page.locator("#menu-body .editor")).toBeVisible();
  });

  // R-0213
  test("the i says the cluster's reason under its name", async ({ page }) => {
    await settle(page);
    await openCluster(page);
    await page.locator("#info").click();
    await expect(page.locator("#crumb")).toHaveText("Leaving and losing");
    await expect(page.locator("#view")).toContainText(
      "Ada lost her grandmother, and then moved away from everyone she knew.",
    );
  });

  // R-0213
  test("the i writes out no list of the cluster's moments", async ({ page }) => {
    test.fail(true, "the page behind the i lists every moment with its year");
    await settle(page);
    await openCluster(page);
    await page.locator("#info").click();
    await expect(page.locator("#view")).toContainText("Ada lost her grandmother");
    await expect(page.locator("#view li")).toHaveCount(0);
  });

  // R-0376
  test("the page behind the i gives no count of events", async ({ page }) => {
    test.fail(true, "the page behind the i says how many events the cluster holds");
    await settle(page);
    await openCluster(page);
    await page.locator("#info").click();
    await expect(page.locator("#view")).toContainText("Ada lost her grandmother");
    await expect(page.locator("#view")).not.toContainText(/\d+ events?/);
  });

  // R-0378
  test("the picture spot stays a drawing behind the i", async ({ page }) => {
    test.fail(true, "the page behind the i is words alone in the picture spot");
    await settle(page);
    await openCluster(page);
    await page.locator("#info").click();
    await expect(page.locator("#view")).toContainText("Ada lost her grandmother");
    await expect(page.locator("#view svg")).not.toHaveCount(0);
  });

  // R-0235
  test("a picked loose moment is written the way one inside a cluster is", async ({
    page,
  }) => {
    await settle(page);
    const resting = await wireY(page);
    await openCluster(page);
    const opened = await wireY(page);
    await page.locator("#up").click();
    await expect(boxes(page).first()).toBeVisible();
    await page.waitForTimeout(400);

    // at rest the one moment no cluster claims is the only dot with a target
    await zones(page).first().click();
    await expect(page.locator("#view .ss-t.on").first()).toHaveText("Ben · Ben stopped calling");
    expect(await page.locator("#view .ss-t.on").count()).toBeLessThanOrEqual(2);
    await expect(page.locator("#view .ss-yr.on")).toHaveText("2021");
    await expect(page.locator("#view circle.dot.on")).toHaveCount(1);
    expect(opened).not.toBe(resting);
    expect(await wireY(page)).toBe(opened);
    // the box stays, faded to nothing going up, under the words
    await expect(page.locator("#view rect.ep")).toHaveAttribute("style", /epfade/);
  });
});

test.describe("every cluster on the dense record", () => {
  test.use({ storageState: stateFor("dense60") });

  // R-0202
  test("shows the back arrow when tapped open", async ({ page }) => {
    await settle(page);
    for (const index of [0, 1]) {
      await expect(page.locator("#up")).toBeHidden();
      await openCluster(page, index);
      await expect(page.locator("#up")).toBeVisible();
      await page.locator("#up").click();
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
    await expect(page.locator("#crumb")).toHaveText("Family timeline");
    await page.locator(".bub.coach .chip.data").first().click();
    await expect(page.locator("#crumb")).toHaveText(
      "the cluster when everybody stopped speaking about the house and the money",
    );
    await expect(page.locator("#up")).toBeVisible();
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

  // R-0230
  test("a cluster slides in on ground of its own", async ({ page }) => {
    await settle(page);
    await toRest(page);
    const seen = cards(page, 2);
    await boxes(page).first().click();
    const colours = await seen;
    expect(colours.every(solid)).toBe(true);
  });

  // R-0230
  test("the board slides in on ground of its own", async ({ page }) => {
    await settle(page);
    const seen = cards(page, 2);
    await page.locator("#cap-play").click();
    const colours = await seen;
    expect(colours.every(solid)).toBe(true);
  });

  // R-0230
  test("going back up slides the level away on ground of its own", async ({ page }) => {
    await settle(page);
    const seen = cards(page, 1);
    await page.locator("#up").click();
    const colours = await seen;
    expect(colours.every(solid)).toBe(true);
  });
});
