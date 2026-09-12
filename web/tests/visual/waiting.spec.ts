import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** From the moment a message is sent until the coach's first words arrive,
 * the coach's side of the thread shows that something is coming. It is never
 * an empty bubble, and it is gone the moment there are words to read — or the
 * moment the warning takes its place. */

const settle = async (page: Page) => {
  await page.goto("/personal/");
  await expect(page.locator(".ss")).toBeVisible();
  await page.waitForTimeout(500);
};

const SEND = /\/personal\/(chat|sessions\/\d+\/statements)$/;

const waiting = (page: Page) => page.locator(".bub.coach.typing");

const reply = {
  statement: "I put that down.",
  statement_id: 9101,
  discussion_id: 1,
  kind: "turn",
  events: [],
};

test.describe("waiting for the coach", () => {
  test.use({ storageState: stateFor("moves") });

  test("shows it is coming until the words arrive", async ({ page }) => {
    await settle(page);
    let answer: () => void = () => {};
    const held = new Promise<void>((go) => (answer = go));
    await page.route(SEND, async (route) => {
      await held;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(reply),
      });
    });

    await page.locator("#composer").fill("My dad moved out.");
    await page.locator("#send").click();

    // it is there while the answer is held, and it is not an empty bubble
    await expect(waiting(page)).toBeVisible();
    expect(await waiting(page).innerText()).not.toBe("");
    await expect(waiting(page)).toHaveCount(1);
    // three dots at text height, moving
    const dots = await waiting(page).evaluate((bubble) => {
      const mark = getComputedStyle(bubble, "::after");
      return {
        width: mark.width,
        height: mark.height,
        beside: (mark.boxShadow.match(/rgb/g) ?? []).length,
        animation: mark.animationName,
        seconds: mark.animationDuration,
      };
    });
    expect(dots).toEqual({
      width: "6px",
      height: "6px",
      // two more dots beside the first, cast as its shadows
      beside: 2,
      animation: "think",
      seconds: "1.2s",
    });

    answer();
    await expect(page.locator(".bub.coach").last()).toHaveText(/I put that down\./);
    await expect(page.locator(".bub.typing")).toHaveCount(0);
  });

  test("gives way to the warning when nothing comes back", async ({ page }) => {
    await settle(page);
    await page.route(SEND, (route) => route.abort("failed"));

    await page.locator("#composer").fill("My dad moved out.");
    await page.locator("#send").click();

    await expect(page.locator(".sys.warn")).toBeVisible();
    await expect(page.locator(".bub.typing")).toHaveCount(0);
  });
});
