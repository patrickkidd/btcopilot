import { expect, test, type Page, type Route } from "./fixtures";
import { stateFor } from "./setup";

/** A case report out of date (Patrick's approved mockup, 2026-10-07): the
 * sheet that asks on opening, the grey line at the top of the cards, and the
 * coach's five cards dimmed while it rewrites them. The server's answers are
 * stubbed to doc/API.md's shapes, since a rewrite on the sandbox's local model
 * takes minutes. */

const TEXT = "Delphine's 1995 diagnosis was added after the coach wrote this report.";
const WRITTEN = ["main", "guesses", "own_part", "choice", "work_on"];
const OUT = { change_id: 41, at: "2026-10-07T09:00:00", text: TEXT };

/** The report's record: out of date, and rewriting the turn named, until `current` says otherwise. */
async function answer(page: Page, current: () => boolean, rewriting: () => string | null = () => null): Promise<void> {
  await page.route("**/case-report-passages*", (route) => route.fulfill({ json: {} }));
  await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, async (route: Route) => {
    const tl = await (await route.fetch()).json();
    tl.case_report = { out_of_date: current() ? null : OUT, rewriting: rewriting() };
    await route.fulfill({ json: tl });
  });
}

/** A rewrite's stream as the server sends it: one closing event. */
const stream = (event: object, delay = 0) => async (route: Route) => {
  await new Promise((done) => setTimeout(done, delay));
  await route.fulfill({ status: 200, headers: { "Content-Type": "text/event-stream" }, body: `id: 1\ndata: ${JSON.stringify(event)}\n\n` });
};

const open = async (page: Page) => {
  await page.goto("/app/case-report");
  await expect(page.locator("#case-body .level").first()).toBeVisible();
};

const sheet = (page: Page) => page.locator(".fs-sheet.rc");
const line = (page: Page) => page.locator("#case-body button.aged");
const dimmed = (page: Page) => page.locator("#case-body .level.dim");

test.describe("a case report out of date", () => {
  test.use({ storageState: stateFor("case-report") });

  // R-0826, R-0827
  test("asks on opening, keeps asking until answered, and after Show the last report shows only the grey line until something newer changes", async ({ page }) => {
    await answer(page, () => false);
    await open(page);
    await expect(sheet(page)).toBeVisible();
    await expect(sheet(page).locator(".cf-t")).toHaveText("This report is out of date");
    await expect(sheet(page)).toContainText(TEXT);
    await expect(sheet(page)).toContainText("The coach can rewrite its five cards now. Or you can read the report as it was last written.");
    await expect(sheet(page).locator("button")).toHaveText(["Refresh the report", "Show the last report"]);
    // the scrim does not put it away
    await page.mouse.click(10, 10);
    await expect(sheet(page)).toBeVisible();

    await sheet(page).getByText("Show the last report").click();
    await expect(sheet(page)).toBeHidden();
    await expect(line(page)).toHaveText(TEXT);
    const first = await page.locator("#case-body .case > *").first().evaluate((n) => n.matches("button.aged"));
    expect(first).toBe(true);
    // grey, the report's quiet colour, never the amber of a question
    const colour = await line(page).evaluate((n) => {
      const probe = document.createElement("span");
      probe.style.color = "var(--faint)";
      n.after(probe);
      const faint = getComputedStyle(probe).color;
      probe.remove();
      return { line: getComputedStyle(n).color, faint };
    });
    expect(colour.line).toBe(colour.faint);

    // opened again with nothing newer: the line, no sheet
    await open(page);
    await expect(line(page)).toHaveText(TEXT);
    await page.waitForTimeout(400);
    await expect(sheet(page)).toBeHidden();

    // the line asks again
    await line(page).click();
    await expect(sheet(page)).toBeVisible();
  });

  // R-0825
  test("Refresh the report dims the coach's five cards until the rewrite is done, then reads the report again with the line gone", async ({ page }) => {
    let done = false;
    await answer(page, () => done);
    await page.route(/\/app\/case-report\?diagram_id=\d+$/, (route) =>
      route.request().method() === "POST" ? route.fulfill({ status: 202, json: { turn_id: "rw1" } }) : route.fallback(),
    );
    await page.route("**/turns/rw1/events", async (route) => {
      await new Promise((ready) => setTimeout(ready, 1500));
      done = true;
      await stream({ type: "done", turn_id: "rw1", cards: WRITTEN, version: 9 })(route);
    });
    await open(page);
    await sheet(page).getByText("Refresh the report").click();
    await expect(sheet(page)).toBeHidden();
    for (const card of WRITTEN) await expect(page.locator(`#case-body .level[data-card="${card}"]`)).toHaveClass(/\bdim\b/);
    await expect(page.locator('#case-body .level[data-card="brought"]')).not.toHaveClass(/\bdim\b/);
    await expect(line(page)).toHaveText("The coach is rewriting its five cards from the diagram as it stands now.");
    await expect(line(page)).toHaveCount(0, { timeout: 15_000 });
    await expect(dimmed(page)).toHaveCount(0);
    await expect(sheet(page)).toBeHidden();
  });

  // R-0825
  test("a rewrite running when the report is opened is shown dimmed and followed to its end", async ({ page }) => {
    let done = false;
    await answer(page, () => done, () => (done ? null : "rw3"));
    await page.route("**/turns/rw3/events", async (route) => {
      await new Promise((ready) => setTimeout(ready, 1500));
      done = true;
      await stream({ type: "done", turn_id: "rw3", cards: WRITTEN, version: 9 })(route);
    });
    await open(page);
    await expect(sheet(page)).toBeHidden();
    await expect(dimmed(page)).toHaveCount(WRITTEN.length);
    await expect(line(page)).toHaveCount(0, { timeout: 15_000 });
    await expect(dimmed(page)).toHaveCount(0);
  });

  // R-0825, R-0826
  test("a rewrite that fails or is refused says so and puts the cards back as they were, without asking again at once", async ({ page }) => {
    await answer(page, () => false);
    await page.route(/\/app\/case-report\?diagram_id=\d+$/, (route) =>
      route.request().method() === "POST" ? route.fulfill({ status: 202, json: { turn_id: "rw2" } }) : route.fallback(),
    );
    await page.route("**/turns/rw2/events", stream({ type: "refused", message: "Every model declined." }, 500));
    await open(page);
    await sheet(page).getByText("Refresh the report").click();
    await expect(page.locator(".toast")).toHaveText("The coach could not rewrite the report. Try again.", { timeout: 10_000 });
    await expect(dimmed(page)).toHaveCount(0);
    await expect(line(page)).toHaveText(TEXT);
    await expect(sheet(page)).toBeHidden();
  });

  // R-0825
  test("a rewrite the server will not start now says so and leaves the report as it was", async ({ page }) => {
    await answer(page, () => false);
    await page.route(/\/app\/case-report\?diagram_id=\d+$/, (route) =>
      route.request().method() === "POST" ? route.fulfill({ status: 409, body: "the case report is already being written again" }) : route.fallback(),
    );
    await open(page);
    await sheet(page).getByText("Refresh the report").click();
    await expect(page.locator(".toast")).toHaveText("The report is already being rewritten, or this family has no session yet");
    await expect(dimmed(page)).toHaveCount(0);
    await expect(line(page)).toHaveText(TEXT);
  });
});
