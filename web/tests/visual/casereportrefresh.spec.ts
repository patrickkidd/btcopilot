import { expect, test, type Page, type Route } from "./fixtures";
import { stateFor } from "./setup";

/** A case report out of date (Patrick's approved mockup, 2026-10-07): the
 * sheet that asks on opening, the grey line at the top of the cards, and the
 * coach's five cards dimmed while it rewrites them. The server's answers are
 * stubbed to doc/API.md's shapes, since a rewrite on the sandbox's local model
 * takes minutes. */

const SENTENCE = "Delphine's 1995 diagnosis was added after the coach wrote this report.";
const WRITTEN = ["main", "guesses", "own_part", "choice", "work_on"];

/** The report's record, out of date until `current` says otherwise. */
async function answer(page: Page, current: () => boolean): Promise<void> {
  await page.route("**/case-report-passages*", (route) => route.fulfill({ json: {} }));
  await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, async (route: Route) => {
    const tl = await (await route.fetch()).json();
    tl.report_out_of_date = current() ? null : { change_id: 41, at: "2026-10-07T09:00:00", sentence: SENTENCE };
    await route.fulfill({ json: tl });
  });
}

/** A rewrite the server starts, answered with each state in turn when asked. */
async function rewrite(page: Page, states: (number | string)[], onDone = () => {}): Promise<void> {
  await page.route(/\/app\/case-report-rewrites\?diagram_id=\d+$/, (route) => route.fulfill({ status: 202, json: { id: "r1", state: "running" } }));
  await page.route("**/case-report-rewrites/r1", (route) => {
    const next = states.length > 1 ? states.shift()! : states[0];
    if (typeof next === "number") return route.fulfill({ status: next, body: "" });
    if (next === "done") onDone();
    return route.fulfill({ json: { id: "r1", state: next } });
  });
}

const open = async (page: Page) => {
  await page.goto("/app/case-report");
  await expect(page.locator("#case-body .level").first()).toBeVisible();
};

const sheet = (page: Page) => page.locator(".fs-sheet.rc");
const line = (page: Page) => page.locator("#case-body button.aged");
const dimmed = (page: Page) => page.locator("#case-body .level.dim");
const FAILED = "The coach could not rewrite the report. Try again.";

test.describe("a case report out of date", () => {
  test.use({ storageState: stateFor("case-report") });

  // R-0826, R-0827
  test("asks on opening, keeps asking until answered, and after Show the last report shows only the grey line until something newer changes", async ({ page }) => {
    await answer(page, () => false);
    await open(page);
    await expect(sheet(page)).toBeVisible();
    await expect(sheet(page).locator(".cf-t")).toHaveText("This report is out of date");
    await expect(sheet(page)).toContainText(SENTENCE);
    await expect(sheet(page)).toContainText("The coach can rewrite its five cards now. Or you can read the report as it was last written.");
    await expect(sheet(page).locator("button")).toHaveText(["Refresh the report", "Show the last report"]);
    // the scrim does not put it away
    await page.mouse.click(10, 10);
    await expect(sheet(page)).toBeVisible();

    await sheet(page).getByText("Show the last report").click();
    await expect(sheet(page)).toBeHidden();
    await expect(line(page)).toHaveText(SENTENCE);
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
    await expect(line(page)).toHaveText(SENTENCE);
    await page.waitForTimeout(400);
    await expect(sheet(page)).toBeHidden();

    // the line asks again
    await line(page).click();
    await expect(sheet(page)).toBeVisible();
  });

  // R-0826
  test("on a wide window the sheet is a card as wide as the bug report's, never a band across the window", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await answer(page, () => false);
    await open(page);
    await expect(sheet(page)).toBeVisible();
    const size = await sheet(page).evaluate((n) => {
      const report = document.createElement("div");
      report.className = "fs-sheet cf-sheet rp";
      n.after(report);
      const rule = getComputedStyle(report).maxWidth;
      report.remove();
      return { rule, own: getComputedStyle(n).maxWidth, width: n.getBoundingClientRect().width };
    });
    expect(size.own).toBe(size.rule);
    expect(size.width).toBe(parseFloat(size.rule));
  });

  // R-0825
  test("Refresh the report dims the coach's five cards until the rewrite is done, then reads the report again with the line gone", async ({ page }) => {
    let done = false;
    await answer(page, () => done);
    await rewrite(page, ["running", "done"], () => (done = true));
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

  for (const [how, states] of [
    ["fails", ["running", "failed"]],
    ["is no longer known to the server", ["running", 404]],
  ] as const)
    // R-0825, R-0826
    test(`a rewrite that ${how} says so and puts the cards back as they were, without asking again at once`, async ({ page }) => {
      await answer(page, () => false);
      await rewrite(page, [...states]);
      await open(page);
      await sheet(page).getByText("Refresh the report").click();
      await expect(page.locator(".toast")).toHaveText(FAILED, { timeout: 10_000 });
      await expect(dimmed(page)).toHaveCount(0);
      await expect(line(page)).toHaveText(SENTENCE);
      await expect(sheet(page)).toBeHidden();
    });

  // R-0825
  test("a rewrite the server will not start now says so and leaves the report as it was", async ({ page }) => {
    await answer(page, () => false);
    await page.route(/\/app\/case-report-rewrites\?diagram_id=\d+$/, (route) =>
      route.fulfill({ status: 409, body: "the case report is already being written again" }),
    );
    await open(page);
    await sheet(page).getByText("Refresh the report").click();
    await expect(page.locator(".toast")).toHaveText("The report is already being rewritten, or this family has no session yet");
    await expect(dimmed(page)).toHaveCount(0);
    await expect(line(page)).toHaveText(SENTENCE);
  });
});
