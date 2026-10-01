import { expect, test, type Page } from "@playwright/test";
import { openList, stateFor } from "./setup";
import { mockTurn, SEND } from "./turn";

/** A tapped row in the events list opens the event read-only, and its one
 * action carries the event into the message box as a lit chip; the send clears
 * it (Patrick's picks D2 to D4, 2026-10-01). The form is not reached from the
 * list while it is parked. */

const TALK = "Tap to comment or change this event in chat";

const opened = async (page: Page) => {
  await page.goto("/app/");
  await openList(page);
  const row = page.locator("#menu-body .row[data-event]").first();
  await row.click();
  return Number(await row.getAttribute("data-event"));
};

test.describe("the event detail view", () => {
  test.use({ storageState: stateFor("three40") });

  // R-0199, R-0141
  test("a row opens the event's facts, read-only, and never the form", async ({ page }) => {
    const id = await opened(page);
    const view = page.locator("#menu-body .det");
    await expect(view).toBeVisible();
    const event = await page.evaluate(
      async (id) => (await (await fetch("/app/timeline")).json()).events.find((e: { id: number }) => e.id === id),
      id,
    );
    await expect(view.locator(".what")).toHaveText(event.label);
    await expect(view.locator(".k")).toContainText(["When", "Who"]);
    await expect(view.locator(".who").first()).toHaveText(event.person_name);
    await expect(view.locator("input, textarea, select, .segs, .save, .del")).toHaveCount(0);
    await expect(view.locator(".talk")).toHaveText(TALK);
    await expect(page.locator("#menu-body .editor")).toHaveCount(0);
    await expect(view).not.toContainText("!");
  });

  // R-0069, R-0199
  test("its action drops the event into the message box as a lit chip, and the send clears it", async ({ page }) => {
    test.skip(test.info().project.name !== "phone");
    const id = await opened(page);
    await page.locator("#menu-body .det .talk").click();
    const chip = page.locator(`#composer .chip[data-kind="event"][data-target="${id}"]`);
    await expect(chip).toBeVisible();
    await expect(chip).toHaveClass(/\blit\b/);
    await expect(page.locator("#composer")).toBeFocused();
    await expect(page.locator("#menu-screen")).toBeHidden();

    await mockTurn(page, { statement: "Moved it.", statement_id: 9601 });
    await page.keyboard.type("that was 1982");
    const [request] = await Promise.all([page.waitForRequest(SEND), page.locator("#send").click()]);
    expect((request.postDataJSON() as { statement: string }).statement).toContain(`[[event:${id}`);
    await expect(page.locator('.bub.coach[data-statement="9601"]')).toContainText("Moved it.");
    await expect(page.locator("#composer .chip")).toHaveCount(0);
  });
});
