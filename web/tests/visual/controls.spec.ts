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
  await page.goto("/personal/");
  await expect(page.locator(".ss")).toBeVisible();
  await page.waitForTimeout(400);
};

/** What the control row is: each control's words, in order, and whether it can
 * be taken. */
const controls = (page: Page) =>
  page.locator(".pctl").evaluate((row) =>
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
  await expect(page.locator(".ss.board")).toBeVisible();
  await page.waitForTimeout(800);
};

test.describe("the board opened from a dot on the wire", () => {
  test.use({ storageState: stateFor("moves") });

  test("shows back, explain and forward", async ({ page }) => {
    await fromTheWire(page);
    expect(await controls(page)).toEqual([
      { words: "◀", dead: true },
      { words: "▶ explain", dead: false },
      { words: "▶", dead: false },
    ]);
  });
});

test.describe("the board opened from the coach's words", () => {
  test.use({ storageState: stateFor("play") });

  test("shows the same three controls", async ({ page }) => {
    await settle(page);
    // the third chip of the walk, which opens the board on the third move
    await page.locator(".bub .chip.data").nth(2).click();
    await expect(page.locator(".ss.board")).toBeVisible();
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

  test("keep their height when a long moment wraps", async ({ page }) => {
    await fromTheWire(page);
    const next = page.locator('.pctl [data-target="next"]');
    const heights = new Set<number>();
    const tops = new Set<number>();
    for (let i = 0; i < 17; i += 1) {
      const cap = await page.locator(".bcap").boundingBox();
      const row = await page.locator(".pctl").boundingBox();
      heights.add(Math.round(cap?.height ?? 0));
      tops.add(Math.round(row?.y ?? 0));
      if (await next.isEnabled()) await next.click();
      await page.waitForTimeout(120);
    }
    // one height for the words and one place for the controls, all the way
    expect([...heights]).toHaveLength(1);
    expect([...tops]).toHaveLength(1);
  });

  test("say a person and their own words, and never a count", async ({ page }) => {
    await fromTheWire(page);
    const words = await page.locator(".bcap").innerText();
    expect(words).toMatch(/^Ada · /);
    expect(words).not.toMatch(/\d+\/\d+/);
  });
});
