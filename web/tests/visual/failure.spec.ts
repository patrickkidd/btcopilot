import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";
import { mockTurn, SEND } from "./turn";

/** What the reader sees when a send does not go through. The failure was an
 * empty coach bubble that looked like it was still coming; it must be a
 * warning that says what happened and offers to send it again, and it must
 * still be there when the reader looks back. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(400);
};

const say = async (page: Page, words: string) => {
  await page.locator("#composer").fill(words);
  await page.locator("#send").click();
};

const warning = (page: Page) => page.locator(".sys.warn");

test.describe("a send that does not go through", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0182
  test("says the server refused it, and sends again on the retry", async ({
    page,
  }) => {
    await settle(page);
    let refuse = true;
    await mockTurn(page, {
      statement: "I put that down.",
      statement_id: 9001,
      refuse: () => (refuse ? 400 : null),
    });

    await say(page, "My dad moved out.");
    await expect(warning(page)).toHaveText(/would not take that/);
    // the words the reader typed are still in the thread, and nothing is typing
    await expect(page.locator(".bub.user").last()).toHaveText("My dad moved out.");
    await expect(page.locator(".bub.typing")).toHaveCount(0);

    // it holds still: no fade, no timer taking it away
    await page.waitForTimeout(1500);
    await expect(warning(page)).toBeVisible();

    refuse = false;
    await warning(page).locator("button").click();
    await expect(page.locator(".bub.coach").last()).toHaveText(/I put that down\./);
    await expect(warning(page)).toHaveCount(0);
  });

  // R-0182
  test("says nothing came back when the server never answers", async ({ page }) => {
    await settle(page);
    await page.route(SEND, (route) => route.abort("failed"));

    await say(page, "My dad moved out.");
    await expect(warning(page)).toHaveText(/No answer from the server/);
    await expect(page.locator(".bub.typing")).toHaveCount(0);
  });

  // R-0182
  test("goes when a later message lands, not only on the retry", async ({
    page,
  }) => {
    await settle(page);
    let refuse = true;
    await mockTurn(page, {
      statement: "I put that down.",
      statement_id: 9002,
      refuse: () => (refuse ? 500 : null),
    });

    await say(page, "My dad moved out.");
    await expect(warning(page)).toHaveText(/server broke/);

    // a second failure says the same thing in the same place, never a pile
    await say(page, "And my mum got ill.");
    await expect(warning(page)).toHaveCount(1);

    // the reader says something else and it lands: the old warning is no
    // longer true, and goes without being tapped
    refuse = false;
    await say(page, "She is better now.");
    await expect(page.locator(".bub.coach").last()).toHaveText(/I put that down\./);
    await expect(warning(page)).toHaveCount(0);
  });
});

test.describe("an explain that does not go through", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0182
  test("warns under the board and leaves the board up", async ({ page }) => {
    await settle(page);
    await page.route("**/app/play", (route) =>
      route.fulfill({ status: 500, body: "no" }),
    );
    await page.locator("#cap-play").click();
    await expect(page.locator("#view .ss.board")).toBeVisible();

    // the board leaving and the board arriving overlap for the zoom
    const explain = page.locator('#chat-screen .pctl [data-target="explain"]');
    await expect(explain).toHaveCount(1);
    await explain.click();
    await expect(warning(page)).toHaveText(/server broke/);
    await expect(page.locator("#view .ss.board")).toBeVisible();
    // and the control is live again, so it can be asked a second time
    await expect(explain).toBeEnabled();
  });
});
