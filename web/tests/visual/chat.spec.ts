import { expect, test } from "@playwright/test";
import { stateFor } from "./setup";

/** Chips have to stay inside their bubble whatever the record calls things, and
 * the play-by-play has to light each chip as its move is drawn. */

test.describe("chips in a bubble", () => {
  test.use({ storageState: stateFor("hostile") });

  test("twelve long chips wrap inside the bubble", async ({ page }) => {
    await page.goto("/companion/");
    await expect(page.locator(".bub").first()).toBeVisible();
    await page.waitForTimeout(400);
    const bubble = page.locator(".bub").filter({ hasText: "Twelve of them" });
    await bubble.scrollIntoViewIfNeeded();
    await expect(bubble).toHaveScreenshot("twelve-chips.png");
  });

  test("no chip anywhere reaches past the edge of its bubble", async ({ page }) => {
    await page.goto("/companion/");
    await expect(page.locator(".bub").first()).toBeVisible();
    await page.waitForTimeout(400);
    const escaped = await page.evaluate(() =>
      [...document.querySelectorAll(".bub")].flatMap((bubble) => {
        const box = bubble.getBoundingClientRect();
        return [...bubble.querySelectorAll(".chip")]
          .filter((chip) => {
            const at = chip.getBoundingClientRect();
            return at.right > box.right + 1 || at.left < box.left - 1;
          })
          .map((chip) => chip.textContent ?? "");
      }),
    );
    expect(escaped).toEqual([]);
  });

  test("a label too long to fit shows the rest when it is tapped", async ({ page }) => {
    await page.goto("/companion/");
    await expect(page.locator(".bub").first()).toBeVisible();
    const clipped = page.locator(".bub .chip.clip").first();
    const before = (await clipped.textContent()) ?? "";
    await clipped.scrollIntoViewIfNeeded();
    await clipped.click();
    const opened = page.locator(".bub .chip").filter({ hasText: before.slice(0, 12) });
    await expect(opened.first()).not.toHaveClass(/clip/);
    // looking at the rest of the words costs nothing
    await expect(page.locator("#composer")).toHaveText("");
  });
});

test.describe("the coach's words", () => {
  test.use({ storageState: stateFor("hostile") });

  test("a coach bubble says who is speaking", async ({ page }) => {
    await page.goto("/companion/");
    await expect(page.locator(".bub.coach .who").first()).toHaveText("Coach");
  });
});
