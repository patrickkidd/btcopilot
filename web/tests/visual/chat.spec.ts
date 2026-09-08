import { expect, test } from "@playwright/test";
import { stateFor } from "./setup";

/** Chips have to stay inside their bubble whatever the record calls things, and
 * the play-by-play has to light each chip as its move is drawn. */

test.describe("chips in a bubble", () => {
  test.use({ storageState: stateFor("hostile") });

  test("twelve long chips wrap inside the bubble", async ({ page }) => {
    await page.goto("/personal/");
    await expect(page.locator(".bub").first()).toBeVisible();
    await page.waitForTimeout(400);
    const bubble = page.locator(".bub").filter({ hasText: "Twelve of them" });
    await bubble.scrollIntoViewIfNeeded();
    await expect(bubble).toHaveScreenshot("twelve-chips.png");
  });

  test("no chip anywhere reaches past the edge of its bubble", async ({ page }) => {
    await page.goto("/personal/");
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

  test("every chip shows its whole label, at one size", async ({ page }) => {
    await page.goto("/personal/");
    await expect(page.locator(".bub").first()).toBeVisible();
    await page.waitForTimeout(400);
    // The owner ruled out the two-tap expand: labels are capped at the source,
    // so a chip is never cut and never has a second state to discover.
    const cut = await page.evaluate(() =>
      [...document.querySelectorAll(".bub .chip")]
        .filter((c) => {
          const words = c.textContent ?? "";
          // a chip wraps onto more lines rather than being cut, so what marks
          // a cut is the ellipsis and the label not matching what it names
          return /…/.test(words) || words.replace(/^\[|\]$/g, "") !== (c.getAttribute("data-full") ?? words);
        })
        .map((c) => c.textContent),
    );
    expect(cut).toEqual([]);
    expect(await page.locator(".bub .chip.clip").count()).toBe(0);
  });
});

test.describe("the coach's words", () => {
  test.use({ storageState: stateFor("hostile") });

  test("a coach bubble says who is speaking", async ({ page }) => {
    await page.goto("/personal/");
    await expect(page.locator(".bub.coach .who").first()).toHaveText("Coach");
  });
});
