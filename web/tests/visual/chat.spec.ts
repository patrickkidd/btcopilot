import { expect, test } from "@playwright/test";
import { stateFor } from "./setup";

/** Chips have to stay inside their bubble whatever the record calls things, and
 * the play-by-play has to light each chip as its move is drawn. A reply ends in
 * offered chips [Oracle: R-0074], and a chip is the primitive a reference is
 * drawn as in both speakers' messages [Oracle: R-0072]. */

test.describe("chips in a bubble", () => {
  test.use({ storageState: stateFor("hostile") });

  // R-0169, R-0072
  test("twelve long chips wrap inside the bubble", async ({ page }) => {
    await page.goto("/app/");
    await expect(page.locator(".bub").first()).toBeVisible();
    await page.waitForTimeout(400);
    const bubble = page.locator(".bub").filter({ hasText: "Twelve of them" });
    await bubble.scrollIntoViewIfNeeded();
    await expect(bubble).toHaveScreenshot("twelve-chips.png");
  });

  // R-0169
  test("no chip anywhere reaches past the edge of its bubble", async ({ page }) => {
    await page.goto("/app/");
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

  // R-0169
  test("every chip shows its whole label, at one size", async ({ page }) => {
    await page.goto("/app/");
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

  // no ruling
  test("a coach bubble says who is speaking", async ({ page }) => {
    await page.goto("/app/");
    await expect(page.locator(".bub.coach .who").first()).toHaveText("Coach");
  });
});

test.describe("the question that closes a reply", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0358, R-0291
  test("it stands apart in amber", async ({ page }) => {
    await page.goto("/app/");
    await expect(page.locator(".bub").first()).toBeVisible();
    await page.waitForTimeout(400);
    const bubble = page.locator(".bub.coach").last();
    await expect(bubble.locator("> .ask")).toHaveText(
      "What do you remember about the winter it started?",
    );
    // offered answers are no longer written (Patrick, 2026-09-21); an old
    // transcript's run of them is still laid out under the question
    await expect(bubble.locator("> .offer .chip.ask")).toHaveCount(3);
    // the question is lifted out of the narration, not repeated in it
    expect(await bubble.locator("> .ask").evaluate((n) => getComputedStyle(n).fontWeight)).toBe("500");
  });
});

test.describe("the message box", () => {
  test.use({ storageState: stateFor("moves") });

  /** Type two lines with Return between them; the bubbles there were before,
   * and what was POSTed meanwhile. */
  const twoLines = async (page: import("@playwright/test").Page) => {
    await page.goto("/app/");
    await expect(page.locator(".bub").first()).toBeVisible();
    const bubbles = await page.locator(".bub").count();
    const posts: string[] = [];
    page.on("request", (r) => r.method() === "POST" && posts.push(r.url()));
    await page.locator("#composer").click();
    await page.keyboard.type("first");
    await page.keyboard.press("Enter");
    await page.keyboard.type("second");
    await page.waitForTimeout(400);
    return { bubbles, posts };
  };

  // R-0368
  test("Return sends nothing; only the send button sends", async ({ page }) => {
    const { bubbles, posts } = await twoLines(page);
    expect(posts.filter((u) => !/telemetry|collect|events/.test(u))).toEqual([]);
    await expect(page.locator(".bub")).toHaveCount(bubbles);
  });

  // R-0368
  test("Return starts a new line in the message", async ({ page }) => {
    // Known defect: a newline inserted at the very end of the box does not
    // render as a line in Chromium, so the next letters join the line above.
    test.fail();
    await twoLines(page);
    expect(await page.locator("#composer").evaluate((n) => n.textContent)).toBe(
      "first\nsecond",
    );
  });
});
