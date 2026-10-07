import { expect, test, type Page } from "./fixtures";
import { stateFor, boxOf } from "./setup";

/** The words of the event already picked lead back to where it was said. */

test.use({ storageState: stateFor("three40") });

/** Pick an event on the line, then tap its own words. */
const tapItsWords = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(400);
  // the one event on this record that belongs to no cluster
  await page.locator('.ss-hit[data-target="zone"]').last().click();
  const words = page.locator("#view .ss-t.on").first();
  await expect(words).toBeVisible();
  const label = (await page.locator("#path .here").textContent()) ?? "";
  const box = await boxOf(words);
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  return label;
};

// R-0192
test("tapping the picked event's words takes the chat to where it was said", async ({
  page,
}) => {
  await tapItsWords(page);
  await expect(page.locator(".bub.traced")).toHaveCount(1);
  await expect(page.locator(".bub.traced")).toBeInViewport();
});

// R-0192
test("the chat lands on the very words that recorded that event", async ({ page }) => {
  const label = await tapItsWords(page);
  const timeline = await (await page.request.get("/app/timeline")).json();
  // the path runs the title on after the person's name, so it is matched without case (R-0681)
  const event = timeline.events.find((e: { label: string }) => label.toLowerCase().includes(e.label.toLowerCase()));
  const where = timeline.coded_in[String(event.id)];
  await expect(page.locator(".bub.traced")).toHaveAttribute(
    "data-statement",
    String(where.statement_id),
  );
});
