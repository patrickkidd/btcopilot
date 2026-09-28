import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";
import { mockTurn, SEND } from "./turn";

/** From the moment a message is sent until the coach's first words arrive,
 * the coach's side of the thread shows that something is coming. It is never
 * an empty bubble, and it is gone the moment there are words to read — or the
 * moment the warning takes its place. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(500);
};

const waiting = (page: Page) => page.locator(".bub.coach.typing");

test.describe("waiting for the coach", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0184
  test("shows it is coming until the words arrive", async ({ page }) => {
    await settle(page);
    let answer: () => void = () => {};
    const held = new Promise<void>((go) => (answer = go));
    // the turn is taken at once; nothing it does arrives until the test says so
    await mockTurn(page, {
      statement: "I put that down.",
      statement_id: 9101,
      hold: held,
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

  // R-0184
  test("keeps showing it while the coach works and has said nothing yet", async ({ page }) => {
    await settle(page);
    await mockTurn(page, {
      statement: "I put that down.",
      statement_id: 9102,
      did: [
        {
          type: "tool_call",
          name: "edit_event",
          args: { description: "moved out", dateTime: "1992-04-01", dateCertainty: "certain" },
          names: { it: "moved out" },
        },
      ],
      pause: 1500,
    });
    await page.locator("#composer").fill("My dad moved out.");
    await page.locator("#send").click();
    // the work has arrived and no words have: something is still coming
    await expect(page.locator(".bub.coach .did").last()).toBeVisible();
    await expect(page.locator(".bub.coach").last()).not.toContainText("I put that down.");
    await expect(waiting(page)).toHaveCount(1);
    await expect(waiting(page)).toBeVisible();
    await expect(page.locator(".bub.coach").last()).toContainText("I put that down.");
    await expect(page.locator(".bub.typing")).toHaveCount(0);
  });

  // R-0182
  test("gives way to the warning when nothing comes back", async ({ page }) => {
    await settle(page);
    await page.route(SEND, (route) => route.abort("failed"));

    await page.locator("#composer").fill("My dad moved out.");
    await page.locator("#send").click();

    await expect(page.locator(".sys.warn")).toBeVisible();
    await expect(page.locator(".bub.typing")).toHaveCount(0);
  });
});
