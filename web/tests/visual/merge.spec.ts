import { expect, test, type Page } from "@playwright/test";
import { stateFor, boxOf } from "./setup";
import { mockTurn, SEND } from "./turn";

/** The coach asks whether two people are one with both of them side by side on
 * one card (Patrick's pick M1). The card is a chip: one tap puts it in the
 * message box, amber, and nothing joins until the reader sends it (R-0072,
 * R-0073). The reply after says who was joined into whom, what moved over and
 * what was dropped (M2). */

test.use({ storageState: stateFor("moves") });

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(400);
};

const ASKED = 9601;

const asked = async (page: Page) => {
  await mockTurn(page, {
    statement: "I have Ben and Cal both down, and they may be one man. Are they one person? [[merge:2,3]]",
    statement_id: ASKED,
  });
  await settle(page);
  await page.locator("#composer").fill("Ben moved away that spring.");
  await page.locator("#send").click();
  return page.locator(`.bub.coach[data-statement="${ASKED}"] button.chip.merge`);
};

// R-0072, R-0073
test("the card sets both people side by side inside the bubble, without a line of its own for the yes", async ({ page }) => {
  const card = await asked(page);
  await expect(card.locator(".half .nm")).toHaveText(["Ben", "Cal"]);
  // measured again until it holds, so a card caught while the thread is still
  // being redrawn is not the one that is judged
  await expect(async () => {
    const [bubble, box, yes, a, b] = await Promise.all(
      [
        card.locator("xpath=ancestor::div[contains(@class,'bub')]"),
        card,
        card.locator(".yes"),
        card.locator(".half").first(),
        card.locator(".half").last(),
      ].map(boxOf),
    );
    expect(box.x).toBeGreaterThanOrEqual(bubble.x);
    expect(box.x + box.width).toBeLessThanOrEqual(bubble.x + bubble.width + 1);
    // the yes rides on the card's top border, so the card is only as tall as
    // its two sides
    expect(yes.y).toBeLessThan(box.y + 4);
    expect(box.height).toBeLessThanOrEqual(Math.max(a.height, b.height) + 2);
  }).toPass({ timeout: 5000 });
});

// R-0072, R-0073
test("one tap puts the card in the message box as the amber yes, and sending it sends the pair", async ({ page }) => {
  const card = await asked(page);
  await card.click();
  const chip = page.locator("#composer .chip");
  await expect(chip).toHaveText("same person");
  await expect(chip).toHaveAttribute("data-kind", "merge");
  await expect(chip).toHaveClass(/ask/);
  await page.unroute(SEND);
  await page.route(SEND, (route) => route.abort());
  const [request] = await Promise.all([page.waitForRequest(SEND), page.locator("#send").click()]);
  expect((request.postDataJSON() as { statement: string }).statement).toBe("[[merge:2,3]]");
});

// R-0478
test("the reply after says who was joined into whom, what moved over and what was dropped", async ({ page }) => {
  await mockTurn(page, {
    statement: "One Ben now. Say undo if that was wrong.",
    statement_id: 9603,
    did: [
      {
        type: "tool_call",
        name: "merge_people",
        args: { keep: 2, drop: 3, version: 4, take: { birth: "keep" } },
        names: {
          keep: "Ben",
          drop: "Cal",
          moved: ["Cal · moved to Fairbanks · 1981"],
          dropped: ["born 1944 dropped · 1942 kept"],
        },
        refusal: null,
      },
    ],
  });
  await settle(page);
  await page.locator("#composer").fill("They are the same man.");
  await page.locator("#send").click();
  await expect(page.locator('.bub.coach[data-statement="9603"] .did')).toHaveText(
    "Joined Cal into Ben; moved Cal · moved to Fairbanks · 1981; born 1944 dropped · 1942 kept",
  );
});
