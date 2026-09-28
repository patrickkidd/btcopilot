import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";
import { mockTurn } from "./turn";

/** The play-by-play drawer (R-0542, R-0562, R-0563). The `play` record holds
 * one moment per move in one stored cluster, and its session holds a play-by-
 * play about that cluster told in four snapshots. Explaining again is answered
 * with that stored case, so no coach turn is involved and it is deterministic.
 *
 * What the old chip walk tested is gone with it: chips stepping the board
 * (R-0170's first half) and the typed pacing of a play-through (R-0171) are
 * replaced by a drawer tapped through by hand. What R-0170 kept, the play
 * message stored with its kind and cluster, is what reopens the drawer here. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(400);
};

const drawer = (page: Page) => page.locator("#pbp");
const count = (page: Page) => drawer(page).locator(".count");

/** The stored play message, the one the session already holds. */
const stored = (page: Page) => page.locator(".bub.coach[data-play]").last();

test.describe("the play-by-play drawer", () => {
  test.use({ storageState: stateFor("play") });

  // R-0170, R-0563
  test("the stored play message opens its case again on the first snapshot", async ({ page }) => {
    await settle(page);
    await expect(drawer(page)).toBeHidden();
    await stored(page).click();
    await expect(drawer(page)).toBeVisible();
    await expect(count(page)).toHaveText("1 of 4");
    await expect(drawer(page).locator(".point")).toContainText("Ada moved toward Ben");
    await expect(drawer(page).locator(".path .here")).toHaveText("explain");
  });

  // R-0542, R-0540, R-0223
  test("reopened from its message, the path's years step opens that cluster", async ({ page }) => {
    await settle(page);
    await expect(page.locator("#path .here")).toHaveText("Timeline");
    await stored(page).click();
    const years = await drawer(page).locator('.path [data-step="1"]').innerText();
    await drawer(page).locator('.path [data-step="1"]').click();
    await expect(drawer(page)).toBeHidden();
    await expect(page.locator("#path .here")).toHaveText(years);
  });

  // R-0113, R-0161
  test("is a drawing, with no legend, no table and no name for a symbol", async ({ page }) => {
    await settle(page);
    await stored(page).click();
    await expect(drawer(page).locator(".draw svg")).toBeVisible();
    await expect(drawer(page).locator("table")).toHaveCount(0);
    // the words are the people's own; the drawing names no symbol
    await expect(drawer(page).locator(".draw")).not.toContainText(/legend|toward|distance|cutoff|conflict|symptom|functioning|anxiety/i);
  });

  // R-0562, R-0071
  test("steps only when tapped, and Back and the dots step it too", async ({ page }) => {
    await settle(page);
    await stored(page).click();
    await page.waitForTimeout(3000);
    await expect(count(page)).toHaveText("1 of 4");
    await drawer(page).locator('[data-act="next"]').click();
    await expect(count(page)).toHaveText("2 of 4");
    await drawer(page).locator('[data-act="dot"]').nth(3).click();
    await expect(count(page)).toHaveText("4 of 4");
    await expect(drawer(page).locator(".ask")).toHaveText("Where was Cal in the year Ada stopped speaking to Ben?");
    await drawer(page).locator('[data-act="back"]').click();
    await expect(count(page)).toHaveText("3 of 4");
    await expect(drawer(page).locator(".guess")).toHaveText(/^My guess: /);
  });

  // R-0546, R-0561
  test("the picture keeps its height from the first snapshot to the last", async ({ page }) => {
    await settle(page);
    await stored(page).click();
    const height = () => drawer(page).locator(".draw").evaluate((d) => d.getBoundingClientRect().height);
    const first = await height();
    for (let i = 1; i < 4; i++) {
      await drawer(page).locator('[data-act="next"]').click();
      expect(await height()).toBe(first);
    }
  });

  // R-0542, R-0563, R-0071
  test("the cluster's explain opens the told case straight away, never the board", async ({ page }) => {
    await settle(page);
    const statements = await page.evaluate(async () => {
      const sessions = await (await fetch("/app/sessions")).json();
      return (await (await fetch(`/app/sessions/${sessions[0].id}`)).json()).statements;
    });
    const play = statements.find((s: { case: unknown }) => s.case);
    await page.route(/\/app\/play$/, (route) =>
      route.fulfill({
        json: { statement: play.text, statement_id: play.id, kind: "play", cluster_id: play.cluster_id, case: play.case },
      }),
    );
    const cluster = page.locator('.ss-hit[data-target="cluster"]');
    if (await cluster.first().isVisible().catch(() => false)) await cluster.first().click();
    await page.locator("#cap-play").click();
    await expect(drawer(page)).toBeVisible();
    await expect(page.locator("#view .ss.board")).toHaveCount(0);
    await expect(drawer(page).locator(".path")).toHaveText(/^Timeline › .+ › explain$/);
    await expect(count(page)).toHaveText("1 of 4");
    await drawer(page).locator('.path [data-step="1"]').click();
    await expect(drawer(page)).toBeHidden();
    await expect(page.locator("#path .here")).not.toHaveText("Timeline");
  });
});

test.describe("the drawer on a small phone", () => {
  test.use({ storageState: stateFor("whitlock"), viewport: { width: 375, height: 667 } });

  // R-0547, R-0558, R-0561
  test("stops shrinking at 13px labels, 36px shapes and a 20px margin, and scrolls instead", async ({ page }) => {
    await settle(page);
    await stored(page).click();
    await drawer(page).locator('[data-act="dot"]').last().click();
    const seen = await drawer(page).evaluate((p) => {
      const svg = p.querySelector<SVGSVGElement>(".draw svg")!;
      const top = p.querySelector(".draw")!.getBoundingClientRect().top;
      const drawn = [...svg.querySelectorAll(".p")].map((g) => g.getBoundingClientRect());
      const lv = p.querySelector(".lv")!;
      return {
        label: 13 * svg.getScreenCTM()!.a,
        shape: Math.min(...[...svg.querySelectorAll(".shape")].map((s) => s.getBoundingClientRect().width)),
        margin: Math.min(...drawn.map((r) => r.top)) - top,
        scrolls: lv.scrollHeight > lv.clientHeight,
      };
    });
    expect(seen.label).toBeGreaterThanOrEqual(13);
    expect(seen.shape).toBeGreaterThanOrEqual(36);
    expect(seen.margin).toBeGreaterThanOrEqual(20);
    expect(seen.scrolls).toBe(true);
  });
});

test.describe("a new snapshot's marks", () => {
  test.use({ storageState: stateFor("whitlock") });

  // R-0557
  test("are at full strength within 300ms of the tap", async ({ page }) => {
    await settle(page);
    await stored(page).click();
    await page.waitForTimeout(600);
    await drawer(page).locator('[data-act="next"]').click();
    await page.waitForTimeout(300);
    const faint = await drawer(page).evaluate((p) =>
      [...p.querySelectorAll(".draw .now, .draw .pop")]
        .map((m) => Number(getComputedStyle(m).opacity))
        .filter((o) => o < 0.99),
    );
    expect(faint).toEqual([]);
  });
});

test.describe("a chip in a walk told the old way", () => {
  test.use({ storageState: stateFor("play") });

  // R-0501, R-0570, R-0543
  test("opens its moment's cluster on the timeline, in place, and opens nothing", async ({
    page,
  }) => {
    await settle(page);
    const old = page.locator(".bub.coach[data-play]").first();
    await old.locator(".chip.data").first().click();
    // every event of this record is in the one cluster, and an event inside a
    // cluster has no mark of its own, so the chip opens the cluster
    await expect(page.locator("#path .here")).toHaveText(/^\d{4}/);
    await expect(page.locator("#view rect.pill.on")).toHaveCount(1);
    await expect(drawer(page)).toBeHidden();
  });
});

test.describe("what the coach aims at with people and moves", () => {
  test.use({ storageState: stateFor("moves") });

  const aim = async (page: Page, view: Record<string, unknown>) => {
    await mockTurn(page, { statement: "Look at these.", statement_id: 9501, did: [{ type: "view", view }] });
    await settle(page);
    await page.locator("#composer").fill("Show me.");
    await page.locator("#send").click();
    await expect(drawer(page)).toBeVisible();
  };

  // R-0570, R-0075
  test("a sequence opens the play-by-play told by nobody: the events' own words, no point and no question", async ({ page }) => {
    await aim(page, { kind: "sequence", events: [20, 22, 23] });
    await expect(count(page)).toHaveText("1 of 3");
    await expect(drawer(page).locator(".point")).toHaveCount(0);
    await drawer(page).locator('[data-act="dot"]').last().click();
    await expect(drawer(page).locator(".ask")).toHaveCount(0);
    await expect(page.locator(".bub.coach").last()).toContainText("Look at these.");
  });

  // R-0570, R-0076
  test("a triangle opens the play-by-play of the events between its people", async ({ page }) => {
    await aim(page, { kind: "triangle", persons: [1, 2, 3] });
    await expect(count(page)).toContainText(" of ");
    await expect(page.locator("#view .ss.board")).toHaveCount(0);
  });
});
