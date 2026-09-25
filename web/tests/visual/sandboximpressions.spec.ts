import { expect, test } from "@playwright/test";
import { need, sandboxOnly } from "./sandbox";

// The push-back button beside an impression keeps its whole 44-point target
// inside the row and on the screen. The family's record comes from the
// sandbox; one impression is added to what the page is handed, so the walk
// needs no seeding and makes no model call. INVITE_TURNS is the link
// btcopilot/tests/frontend/seedturns.py prints.

const IMPRESSION = {
  id: "i90",
  text: "When things get tense at home, someone in the family moves away.",
  kind: "impression",
  open: true,
  asked_at: "2026-09-20",
  asked_in: null,
  evidence: [{ kind: "event", id: 1, label: "Moved out" }],
  pushback: null,
};

test.describe(() => {
  sandboxOnly("turns");
  test.use({ viewport: { width: 390, height: 844 } });

  // R-0006
  test("the push-back button's target stays inside its row and the screen", async ({ page }) => {
    await page.route("**/app/timeline*", async (route) => {
      const real = await route.fetch();
      const timeline = await real.json();
      timeline.asked_questions = [...timeline.asked_questions, IMPRESSION];
      await route.fulfill({ response: real, json: timeline });
    });
    await page.goto(need("turns"), { waitUntil: "load" });
    const open = page.locator("#menu-open");
    if (await open.isVisible()) await open.click();
    await page.locator("#tab-questions").click();
    const more = page.locator(`.irow[data-q="${IMPRESSION.id}"] .rmore`);
    await more.scrollIntoViewIfNeeded();
    const target = (await more.boundingBox())!;
    const row = (await page.locator(`.irow[data-q="${IMPRESSION.id}"] .islide`).boundingBox())!;
    const width = page.viewportSize()!.width;
    expect(target.width).toBeGreaterThanOrEqual(44);
    expect(target.height).toBeGreaterThanOrEqual(44);
    expect(target.x).toBeGreaterThanOrEqual(row.x);
    expect(target.x + target.width).toBeLessThanOrEqual(row.x + row.width);
    expect(target.x + target.width).toBeLessThanOrEqual(width);
  });
});
