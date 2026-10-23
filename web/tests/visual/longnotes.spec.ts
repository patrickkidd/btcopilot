import { expect, test, type Page } from "./fixtures";
import { stateFor } from "./setup";
import { mockTurn, SEND } from "./turn";

/** Notes too long for one part are priced before they go: the person sees
 * the words, the parts, the dollars and the minutes, and starts or cancels.
 * While the coach enters them the bubble says which part is running. */

const notes = (words: number) =>
  Array.from({ length: words }, (_, i) => (i % 80 === 79 ? "said.\n\n" : "she")).join(" ");

/** The line the page should show, from the numbers the server gave it. */
const expected = (page: Page, words: number) =>
  page.evaluate((words) => {
    const at = (window as unknown as { BOOTSTRAP: { notes: { part_words: number; usd_per_1000_words: number; seconds_per_part: number } } }).BOOTSTRAP.notes;
    const parts = Math.ceil(words / at.part_words);
    const dollars = (Math.round((words / 1000) * at.usd_per_1000_words * 20) / 20).toFixed(2);
    const minutes = Math.ceil((parts * at.seconds_per_part) / 60);
    return `About ${words.toLocaleString("en-US")} words in ${parts} parts. Roughly $${dollars} and ${minutes} minutes.`;
  }, words);

const open = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(300);
};

for (const scheme of ["light", "dark"] as const) {
  test.describe(`long notes, ${scheme}`, () => {
    test.use({ storageState: stateFor("moves"), colorScheme: scheme });
    test.beforeEach(async ({ page }, info) => {
      if (info.project.name === "phone") await page.setViewportSize({ width: 393, height: 852 });
    });

    // R-0897
    test("a 4,000-word paste is priced first; Cancel keeps it, Start sends it", async ({ page }) => {
      const errors: string[] = [];
      page.on("console", (m) => void (m.type() === "error" && errors.push(m.text())));
      page.on("pageerror", (e) => void errors.push(e.message));
      let sends = 0;
      page.on("request", (r) => void (r.method() === "POST" && SEND.test(r.url()) && (sends += 1)));
      await mockTurn(page, {
        statement: "I put those notes down.",
        statement_id: 9401,
        did: [{ type: "part", part: 2, parts: 3 }],
        pause: 800,
      });
      await open(page);

      const text = notes(4000);
      await page.locator("#composer").fill(text);
      await page.locator("#send").click();
      const sheet = page.locator(".fs-sheet.ln.in");
      await expect(sheet.locator(".cf-t")).toHaveText("Long notes");
      await expect(sheet.locator(".cf-p")).toHaveText(await expected(page, 4000));
      const box = (await sheet.boundingBox())!;
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.x + box.width).toBeLessThanOrEqual(page.viewportSize()!.width + 1);

      await sheet.getByRole("button", { name: "Cancel" }).click();
      await expect(sheet).toHaveCount(0);
      expect(sends).toBe(0);
      // nothing went, and the notes are still in the box
      expect(await page.locator("#composer").innerText()).toContain("she she");

      await page.locator("#send").click();
      await sheet.getByRole("button", { name: "Start" }).click();
      await expect(sheet).toHaveCount(0);
      // the part under way shows in the bubble until the reply lands
      await expect(page.locator(".bub.coach .did.part")).toHaveText("Part 2 of 3");
      await expect(page.locator(".bub.coach").last()).toContainText("I put those notes down.");
      await expect(page.locator(".bub.coach .did.part")).toHaveCount(0);
      expect(sends).toBe(1);
      expect(errors).toEqual([]);
    });

    // R-0897
    test("a 300-word message goes without asking", async ({ page }) => {
      const errors: string[] = [];
      page.on("console", (m) => void (m.type() === "error" && errors.push(m.text())));
      page.on("pageerror", (e) => void errors.push(e.message));
      await mockTurn(page, { statement: "Noted.", statement_id: 9411 });
      await open(page);
      await page.locator("#composer").fill(notes(300));
      await page.locator("#send").click();
      await expect(page.locator(".bub.coach").last()).toContainText("Noted.");
      await expect(page.locator(".fs-sheet.ln.in")).toHaveCount(0);
      expect(errors).toEqual([]);
    });
  });
}
