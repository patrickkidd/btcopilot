import { expect, test, type Page } from "@playwright/test";
import { stateFor, tellWithoutModel } from "./setup";

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

const openCluster = async (page: Page) => {
  await settle(page);
  // a record whose moments sit inside a cluster needs it opened to reach them
  const clusters = page.locator('.ss-hit[data-target="cluster"]');
  if (await clusters.first().isVisible().catch(() => false)) {
    await clusters.first().click();
    await page.waitForTimeout(400);
  }
};


test.describe("explain", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0166
  test("is the word on the button, and nothing offers to watch", async ({ page }) => {
    await openCluster(page);
    await expect(page.locator("#cap-play")).toHaveText(/explain/);
    await expect(page.locator("#chat-screen .pic")).not.toContainText(/watch/i);
  });

  // R-0166
  test("asks the coach to talk the cluster through", async ({ page }) => {
    const asked: unknown[] = [];
    page.on("request", (r) => r.url().endsWith("/app/play") && asked.push(r.postDataJSON()));
    await tellWithoutModel(page);
    await openCluster(page);
    await page.locator("#cap-play").click();
    await expect(page.locator("#pbp")).toBeVisible();
    await expect(page.locator(".bub.coach").last()).toContainText("One thing followed another.");
    expect(asked).toHaveLength(1);
    expect(asked[0]).toHaveProperty("cluster_id");
  });
});

