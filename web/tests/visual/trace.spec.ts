import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

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
  const label = (await page.locator("#view .ss-t.on").allTextContents()).join(" ");
  const box = (await words.boundingBox())!;
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  return label;
};

// defect: at rest the picked event's words carry no tap target, so the tap
// lands on empty ground and puts the picture down
// R-0192
test.fail("tapping the picked event's words takes the chat to where it was said", async ({
  page,
}) => {
  await tapItsWords(page);
  await expect(page.locator(".bub.traced")).toHaveCount(1);
  await expect(page.locator(".bub.traced")).toBeInViewport();
});

// defect: the same missing tap target
// R-0192
test.fail("the chat lands on the very words that recorded that event", async ({ page }) => {
  const label = await tapItsWords(page);
  const timeline = await (await page.request.get("/app/timeline")).json();
  const event = timeline.events.find((e: { label: string }) => label.includes(e.label));
  const where = timeline.coded_in[String(event.id)];
  await expect(page.locator(".bub.traced")).toHaveAttribute(
    "data-statement",
    String(where.statement_id),
  );
});
