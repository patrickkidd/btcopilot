import { expect, test, type Page } from "@playwright/test";
import { inside, stateFor, steady } from "./setup";

/** The moves board: the level a cluster opens into, and the chrome around the
 * drawings. The drawings themselves are checked in moves.spec.ts; these
 * watch the things only the app can produce — the entry button, the people
 * the record puts on the ellipse, the pair bonds beneath them, the earlier
 * moves held behind the current one, the caption, and the step controls at
 * their ends.
 *
 * Driven the way a reader drives it: select a moment, take the entry button,
 * then step. No live coach turn is involved, so it is deterministic.
 *
 * The `moves` record is one moment per move the picture can draw, all in a
 * single cluster, so the board it opens has every move on it in order. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(400);
};

/** Select a moment so the caption row offers its cluster. */
const pickCluster = async (page: Page) => {
  // explain belongs to the cluster, not to a moment inside it, so nothing is
  // picked before it is taken (owner review round 3)
  const box = page.locator('.ss-hit[data-target="cluster"]');
  if (await box.first().isVisible().catch(() => false)) {
    await box.first().click();
    await page.waitForTimeout(400);
  }
  await expect(page.locator("#cap-play")).toBeEnabled();
};

const enter = async (page: Page) => {
  await pickCluster(page);
  await page.locator("#cap-play").click();
  // the way in opens the board itself now, with no coach turn behind it
  await expect(page.locator("#view .ss.board")).toBeVisible({ timeout: 30_000 });
  // past the .6s zoom, so the board is settled rather than mid-flight
  await page.waitForTimeout(800);
};

/** Hold every clock at one instant, or an 8, 10 or 12 second loop decides what
 * the shot catches. */
const freeze = (page: Page, ms = 2400) =>
  page.evaluate((at) => {
    for (const svg of document.querySelectorAll("svg")) {
      svg.pauseAnimations();
      svg.setCurrentTime(at / 1000);
    }
    for (const animation of document.getAnimations()) {
      animation.pause();
      animation.currentTime = at;
    }
  }, ms);

const picture = (page: Page) => page.locator("#chat-screen .pic");

test.describe("the moves board", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0180, R-0212
  test("a cluster offers to walk its moves", async ({ page }) => {
    await settle(page);
    await pickCluster(page);
    await expect(page.locator("#cap-play")).toHaveText("explain");
    await inside(page.locator("#view .ss"), picture(page));
  });

  // R-0178
  test("the board opens on the first move", async ({ page }) => {
    await settle(page);
    await enter(page);
    // the words under the board name the move, and never count them
    await expect(page.locator("#chat-screen .bcap")).toHaveText("Ada \u2192 Ben · toward");
    await freeze(page);
    await expect(picture(page)).toHaveScreenshot("board-first-move.png", steady(page));
  });

  // R-0181
  test("earlier moves stay behind the one being drawn", async ({ page }) => {
    await settle(page);
    await enter(page);
    for (let i = 0; i < 4; i += 1)
      await page.locator('.pctl [data-target="next"]').click();
    await expect(page.locator("#chat-screen .bcap")).toHaveText("Ada \u2192 Ben · conflict");
    await inside(page.locator("#view .ss.board"), picture(page));
  });

  // R-0180
  test("the last move has nowhere further to go", async ({ page }) => {
    await settle(page);
    await enter(page);
    const next = page.locator('.pctl [data-target="next"]');
    while (await next.isEnabled()) await next.click();
    await expect(page.locator('.pctl [data-target="prev"]')).toBeEnabled();
    await expect(next).toBeDisabled();
    await inside(page.locator("#view .ss.board"), picture(page));
  });

  // the one way up is the arrow beside the view's name; the board carries no
  // corner arrow of its own (owner ruling 2026-09-08)
  // R-0223
  test("back goes up one level, to the cluster the board was showing", async ({
    page,
  }) => {
    await settle(page);
    const before = await picture(page).boundingBox();
    await enter(page);
    await expect(page.locator('[data-target="back"]')).toHaveCount(0);
    await page.locator("#up").click();
    await expect(page.locator("#view .ss.board")).toHaveCount(0);
    // past the .25s height transition, or the box is read mid-flight
    await page.waitForTimeout(500);
    const after = await picture(page).boundingBox();
    // the resting picture is one fixed height whatever it has been showing
    expect(after?.height).toBe(before?.height);
  });

  // R-0113
  test("the move is a drawing, with no legend and no table", async ({ page }) => {
    await settle(page);
    await enter(page);
    await expect(picture(page).locator("table")).toHaveCount(0);
    await expect(picture(page)).not.toContainText(/legend|key:/i);
    // the first move is toward, drawn as an arrow between the two
    await expect(page.locator("#view .ss.board .cast .tarrow")).toHaveCount(1);
  });

  // R-0130
  test("the board arrives by zooming in from the level above", async ({ page }) => {
    await settle(page);
    await pickCluster(page);
    await page.locator("#cap-play").click();
    const zoom = await page.locator("#view .ss.board svg").evaluate((svg) =>
      svg.getAnimations().map((a) =>
        (a.effect as KeyframeEffect)
          .getKeyframes()
          .map((frame) => new DOMMatrix(String(frame.transform ?? "none")).a),
      ),
    );
    expect(zoom).toHaveLength(1);
    expect(zoom[0][0]).toBeGreaterThan(1);
    expect(zoom[0].at(-1)).toBe(1);
  });

  // R-0130
  test("the zoom is long enough to be seen and short enough not to wait on", async ({
    page,
  }) => {
    await settle(page);
    await pickCluster(page);
    await page.locator("#cap-play").click();
    const [ms] = await page.locator("#view .ss.board svg").evaluate((svg) =>
      svg.getAnimations().map((a) => Number(a.effect!.getTiming().duration)),
    );
    expect(ms).toBeGreaterThanOrEqual(300);
    expect(ms).toBeLessThanOrEqual(1000);
  });

  // R-0136
  test("the one who moves is marked, and the arrow points at who they move toward", async ({
    page,
  }) => {
    await settle(page);
    await enter(page);
    await expect(page.locator("#view .ss.board .nm.on")).toHaveText(["Ada"]);
    const centre = async (sel: string) => {
      const box = (await page.locator(sel).first().boundingBox())!;
      return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
    };
    const head = await centre("#view .ss.board .tarrow .tipfill");
    const ada = await centre('#view .ss.board .node[data-person="1"] .disc');
    const ben = await centre('#view .ss.board .node[data-person="2"] .disc');
    const far = (p: { x: number; y: number }) => Math.hypot(p.x - head.x, p.y - head.y);
    expect(far(ben)).toBeLessThan(far(ada));
  });

  // R-0173
  test("the drawing is only as tall as what it holds", async ({ page }) => {
    await settle(page);
    await enter(page);
    const [box, drawn] = await page.locator("#view .ss.board").evaluate((board) => [
      board.getBoundingClientRect().height,
      board.querySelector("svg")!.getBoundingClientRect().height,
    ]);
    expect(Math.round(box)).toBe(Math.round(drawn));
    const viewBox = await page
      .locator("#view .ss.board svg")
      .evaluate((svg) => (svg as SVGSVGElement).viewBox.baseVal.height);
    expect(Math.round(box)).toBe(Math.round(viewBox));
  });

  // R-0177
  test("the move being played is its dot in the action green", async ({ page }) => {
    await settle(page);
    await enter(page);
    const fill = (sel: string) =>
      page.locator(sel).first().evaluate((el) => getComputedStyle(el).fill);
    expect(await fill("#view .ss.board .ax-now")).toBe(await fill("#view .ss.board .tarrow .tipfill"));
    expect(await fill("#view .ss.board .ax-now")).not.toBe(await fill("#view .ss.board .ax-dot"));
  });

  // R-0292
  test("nothing on screen calls the view the moves board", async ({ page }) => {
    await settle(page);
    await enter(page);
    const words = await page.evaluate(() =>
      [
        document.body.innerText,
        ...[...document.querySelectorAll("[aria-label], [title]")].map(
          (el) => `${el.getAttribute("aria-label") ?? ""} ${el.getAttribute("title") ?? ""}`,
        ),
      ].join(" "),
    );
    expect(words).not.toMatch(/moves board/i);
  });
});
