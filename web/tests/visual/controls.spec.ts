import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** The board's controls, and the words under it.
 *
 * The board must not look like a different thing depending on how it was
 * opened: one row, back, explain, forward, whichever way in was taken. And the
 * words under it are a person and what happened to them, in a block that keeps
 * its height however long they are, so the board never shifts down the screen
 * while a reader steps through it. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(400);
};

/** What the control row is: each control's words, in order, and whether it can
 * be taken. */
const controls = (page: Page) =>
  page.locator("#chat-screen .pctl").evaluate((row) =>
    [...row.children].map((c) => ({
      words: (c as HTMLElement).innerText.trim(),
      dead: (c as HTMLButtonElement).disabled,
    })),
  );

const fromTheWire = async (page: Page) => {
  await settle(page);
  // a record whose moments sit inside a cluster needs it opened to reach them
  const clusters = page.locator('.ss-hit[data-target="cluster"]');
  if (await clusters.first().isVisible().catch(() => false)) {
    await clusters.first().click();
    await page.waitForTimeout(400);
  }
  await page.locator("#cap-play").click();
  await expect(page.locator("#view .ss.board")).toBeVisible();
  await page.waitForTimeout(800);
};

test.describe("the board opened from a dot on the wire", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0180
  test("shows back, explain and forward", async ({ page }) => {
    await fromTheWire(page);
    expect(await controls(page)).toEqual([
      { words: "◀", dead: true },
      { words: "▶ explain", dead: false },
      { words: "▶", dead: false },
    ]);
  });
});

test.describe("explain", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0166
  test("is the word on the button, and nothing offers to watch", async ({ page }) => {
    await fromTheWire(page);
    await expect(page.locator('#chat-screen .pctl [data-target="explain"]')).toHaveText(/explain/);
    await expect(page.locator("#chat-screen .pic")).not.toContainText(/watch/i);
  });

  // R-0166
  test("asks the coach to talk the cluster through", async ({ page }) => {
    const asked: unknown[] = [];
    await page.route(/\/app\/play$/, async (route) => {
      asked.push(route.request().postDataJSON());
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          statement: "Ada moved toward Ben first.",
          statement_id: 9301,
          kind: "play",
          cluster_id: (route.request().postDataJSON() as { cluster_id: string }).cluster_id,
        }),
      });
    });
    await fromTheWire(page);
    await page.locator('#chat-screen .pctl [data-target="explain"]').click();
    await expect(page.locator(".bub.coach").last()).toContainText("Ada moved toward Ben first.");
    expect(asked).toHaveLength(1);
    expect(asked[0]).toHaveProperty("cluster_id");
  });
});

test.describe("the board opened from the coach's words", () => {
  test.use({ storageState: stateFor("play") });

  // R-0180
  test("shows the same three controls", async ({ page }) => {
    await settle(page);
    // the third chip of the walk, which opens the board on the third move
    await page.locator(".bub .chip.data").nth(2).click();
    await expect(page.locator("#view .ss.board")).toBeVisible();
    await page.waitForTimeout(800);
    expect(await controls(page)).toEqual([
      { words: "◀", dead: false },
      { words: "▶ explain", dead: false },
      { words: "▶", dead: false },
    ]);
  });
});

test.describe("the words under the board", () => {
  test.use({ storageState: stateFor("longmove") });

  // R-0178
  test("keep their height when a long moment wraps", async ({ page }) => {
    await fromTheWire(page);
    const next = page.locator('.pctl [data-target="next"]');
    const heights = new Set<number>();
    const tops = new Set<number>();
    for (let i = 0; i < 17; i += 1) {
      const cap = await page.locator("#chat-screen .bcap").boundingBox();
      const row = await page.locator("#chat-screen .pctl").boundingBox();
      heights.add(Math.round(cap?.height ?? 0));
      tops.add(Math.round(row?.y ?? 0));
      if (await next.isEnabled()) await next.click();
      await page.waitForTimeout(120);
    }
    // one height for the words and one place for the controls, all the way
    expect([...heights]).toHaveLength(1);
    expect([...tops]).toHaveLength(1);
  });

  // R-0178, R-0162
  test("say a person and their own words, and never a count", async ({ page }) => {
    await fromTheWire(page);
    const words = await page.locator("#chat-screen .bcap").innerText();
    expect(words).toMatch(/^Ada · /);
    expect(words).not.toMatch(/\d+\/\d+/);
  });
});
