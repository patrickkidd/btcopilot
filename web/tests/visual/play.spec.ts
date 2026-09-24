import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** Step chips in a play-by-play (owner review round 1). The `play` record holds
 * one moment per move, all in one stored cluster, and its session holds a
 * play-by-play about that cluster whose chips are its moves in order.
 *
 * The walk is coach-authored and each move is a chip [Oracle: R-0074], and a
 * button reaches a whole digestible concept rather than cycling one datum at a
 * time [Oracle: R-0071].
 *
 * What is under test is routing, not drawing: a chip in a walk opens the board
 * if it is closed, goes to the move it names, and never puts the picture back
 * on the timeline. No coach turn is involved, so it is deterministic. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(400);
};

/** The chips of the walk, in the order the coach wrote them. */
const walk = (page: Page) => page.locator(".bub .chip.data");

const board = (page: Page) => page.locator("#view .ss.board");

/** The words under the board. The board that is leaving and the board that is
 * arriving are both on the page for the length of the zoom, so wait for the
 * one caption before reading it. A move names the pair it is aimed at, which
 * is who the moment is about. */
const expectCaption = async (page: Page, words: string) => {
  const caption = page.locator("#chat-screen .bcap");
  await expect(caption).toHaveCount(1);
  await expect(caption).toHaveText(words);
};

test.describe("a chip in a play-by-play", () => {
  test.use({ storageState: stateFor("play") });

  // R-0170
  test("the third chip opens the board on the third move", async ({ page }) => {
    await settle(page);
    await expect(board(page)).toHaveCount(0);
    await walk(page).nth(2).click();
    await expect(board(page)).toBeVisible();
    await expectCaption(page, "Ada \u2192 Ben · distance");
  });

  // R-0170
  test("a further chip steps the board and never leaves it", async ({ page }) => {
    await settle(page);
    await walk(page).nth(2).click();
    await expectCaption(page, "Ada \u2192 Ben · distance");
    await walk(page).nth(6).click();
    await expect(board(page)).toBeVisible();
    // a move aimed at nobody names only the person it is about
    await expectCaption(page, "Ada · defined self");
  });

  // R-0178
  test("the picture keeps its height while the walk is stepped", async ({
    page,
  }) => {
    await settle(page);
    await walk(page).nth(2).click();
    await expect(board(page)).toBeVisible();
    await page.waitForTimeout(800);
    const before = await page.locator("#chat-screen .pic").boundingBox();
    await walk(page).nth(6).click();
    await page.waitForTimeout(500);
    const after = await page.locator("#chat-screen .pic").boundingBox();
    expect(after?.height).toBe(before?.height);
  });
});

/** The coach talking a cluster through: two moves, each named in its own
 * sentence, answered at once so the pacing is the page's own. */
const walkThrough = async (page: Page) => {
  await page.route(/\/app\/play$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        statement:
          "In 1990 Ada [[event:20|moved toward Ben]], and it was the start of a long " +
          "stretch of trying. A year later she [[event:21|pulled away from him]] again.",
        statement_id: 9401,
        kind: "play",
        cluster_id: (route.request().postDataJSON() as { cluster_id: string }).cluster_id,
      }),
    }),
  );
  await settle(page);
  const cluster = page.locator('.ss-hit[data-target="cluster"]');
  if (await cluster.first().isVisible().catch(() => false)) await cluster.first().click();
  await page.locator("#cap-play").click();
  await expect(board(page)).toBeVisible();
  await page.waitForTimeout(800);
};

test.describe("a play-through", () => {
  test.use({ storageState: stateFor("play") });

  // R-0171
  test("holds a move until its sentence is typed, and about two seconds more", async ({
    page,
  }) => {
    await walkThrough(page);
    await page.evaluate(() => {
      const log: { at: number; what: string; text: string }[] = [];
      (window as unknown as { paced: typeof log }).paced = log;
      new MutationObserver(() => {
        const words = [...document.querySelectorAll(".bub.coach .words")].at(-1);
        const caption = document.querySelector("#chat-screen .bcap");
        log.push({ at: performance.now(), what: "words", text: words?.textContent ?? "" });
        log.push({ at: performance.now(), what: "caption", text: caption?.textContent ?? "" });
      }).observe(document.body, { subtree: true, childList: true, characterData: true });
    });
    await page.locator('#chat-screen .pctl [data-target="explain"]').click();
    await expect(page.locator("#chat-screen .bcap")).toContainText("away", { timeout: 30_000 });
    const log = await page.evaluate(
      () => (window as unknown as { paced: { at: number; what: string; text: string }[] }).paced,
    );
    const stepped = log.find((e) => e.what === "caption" && e.text.includes("away"))!.at;
    // the last words written before the board moved on: the sentence about
    // the first move and the start of the next one, up to its chip
    const typed = log
      .filter((e) => e.what === "words" && e.at < stepped - 100)
      .reduce((last, e, i, all) => (i && e.text !== all[i - 1].text ? e : last)).at;
    expect(stepped - typed).toBeGreaterThanOrEqual(1500);
    expect(stepped - typed).toBeLessThanOrEqual(2600);
  });

  // R-0171
  test("keeps each move's own eight-second loop while it is held", async ({ page }) => {
    await walkThrough(page);
    await page.locator('#chat-screen .pctl [data-target="explain"]').click();
    await expect(page.locator(".bub.coach .chip").first()).toBeVisible({ timeout: 30_000 });
    const loop = await page.locator("#view .ss.board .tarrow").evaluate((arrow) => ({
      css: arrow.getAnimations().map((a) => Number(a.effect!.getTiming().duration)),
      svg: [...arrow.querySelectorAll("animate")].map((a) => a.getAttribute("dur")),
    }));
    expect(loop.css).toEqual([8000]);
    expect(new Set(loop.svg)).toEqual(new Set(["8s"]));
  });
});
