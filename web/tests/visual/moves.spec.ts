import { expect, test } from "@playwright/test";
import { CASES, drawings, freeze } from "./drawings";
import { inside, lists, openList, stateFor } from "./setup";

/** The move language, one drawing per move: each draws its people, named, inside
 * its cell. Pixels are not compared here (R-0416).
 *
 * They are taken off a page that renders the real `moves.ts` against the real
 * `theme.css`, not off the app. A chip no longer opens the moves board, because
 * a level change from a chip tap would move the chat bubbles below it, and the
 * board's own entry runs a live coach turn, which no golden can depend on. The
 * drawings are the thing under test, so the page under test is the drawings.
 *
 * Every clock is frozen at the same instant before each shot: the SVG timeline
 * with `setCurrentTime`, and the CSS animations through the Web Animations API.
 * A move runs an 8, 10 or 12 second loop, so the instant decides what is on
 * screen and it has to be the same one every run. */

/** Two thirds through the 8s story loop: past every move's first beat, before
 * the ones that end early have gone. */
const AT_MS = 5200;

test.describe("the move language", () => {
  const url = drawings();

  for (const spec of CASES) {
    // R-0137
    test(`the ${spec.name} drawing`, async ({ page: browser }) => {
      // the drawings do not change with the window, so one size is the story
      test.skip(test.info().project.name !== "phone");
      await browser.goto(url);
      await freeze(browser, AT_MS);
      const cell = browser.locator(`#m-${spec.name}`);
      await expect(cell.locator(".node")).toHaveCount(spec.three ? 3 : 2);
      expect((await cell.locator(".nm").allTextContents()).sort()).toEqual(
        spec.three ? ["Ann", "Bo", "Cy"] : ["Ann", "Bo"],
      );
      await inside(cell.locator("svg"), cell);
    });
  }

  // R-0288
  test("the board a coach's triangle opens", async ({ page: browser }) => {
    test.skip(test.info().project.name !== "phone");
    await browser.goto(url);
    const cell = browser.locator("#m-triangle-board");
    await expect(cell.locator("svg")).toBeVisible();
    await inside(cell.locator("svg"), cell);
  });
});

test.describe("what a chip does", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0168
  test("what the coach named stays lit on the picture", async ({ page }) => {
    await page.goto("/app/");
    await expect(page.locator("#view .ss")).toBeVisible();
    await page.waitForTimeout(500);
    // the record rests on one open cluster, which writes no words on the
    // drawing (owner, 2026-09-09): what the coach named is lit on its dots
    await expect(page.locator("#view .dot.lit").first()).toBeVisible();
  });
});

test.describe("the timeline behind the menu", () => {
  test.use({ storageState: stateFor("three40") });

  // R-0141
  test("the list of everything", async ({ page }) => {
    await page.goto("/app/");
    await openList(page);
    await expect(page.locator("#menu-body .row").first()).toBeVisible();
    await expect(page.locator("#menu-body .row").first()).not.toBeEmpty();
    await inside(page.locator("#menu-body .row").first(), lists(page), true);
  });

  // R-0174
  test("the editor's fields, text centred in the box", async ({ page }) => {
    await page.goto("/app/");
    await openList(page);
    await page.locator("#menu-body .row").first().click();
    await expect(page.locator(".editor .segs").first()).toBeVisible();
    await inside(page.locator(".editor").first(), lists(page), true);
  });
});

/** The editor shows a second person, a child and the shift block only for the
 * kinds `EventForm.qml` shows them for. These assert behaviour, not pixels. */
test.describe("the editor's fields by kind", () => {
  test.use({ storageState: stateFor("editable") });

  const openEditor = async (page: import("@playwright/test").Page) => {
    await page.goto("/app/");
    await openList(page);
    await page.locator("#menu-body .row").first().click();
    await expect(page.locator(".editor .segs").first()).toBeVisible();
  };
  const pick = (page: import("@playwright/test").Page, group: string, value: string) =>
    page.locator(`.segs[data-name="${group}"] .seg[data-value="${value}"]`).click();
  const block = (page: import("@playwright/test").Page, name: string) =>
    page.locator(`.editor [data-block="${name}"]`);

  for (const [kind, spouse, child] of [
    ["shift", false, false],
    ["death", false, false],
    ["married", true, false],
    ["bonded", true, false],
    ["separated", true, false],
    ["divorced", true, false],
    // a noted event is only its own words: nobody else is named on it (R-0363)
    ["noted", false, false],
    ["birth", true, true],
    ["adopted", true, true],
  ] as [string, boolean, boolean][]) {
    // R-0144
    test(`${kind} shows ${spouse ? "a" : "no"} second person and ${child ? "a" : "no"} child`, async ({
      page,
    }) => {
      await openEditor(page);
      await pick(page, "kind", kind);
      await expect(block(page, "pair")).toBeVisible({ visible: spouse });
      await expect(block(page, "child")).toBeVisible({ visible: child });
      await expect(block(page, "shift")).toBeVisible({ visible: kind === "shift" });
    });
  }

  // R-0144
  test("the second person is named for the kind", async ({ page }) => {
    await openEditor(page);
    await pick(page, "kind", "married");
    await expect(page.locator('.editor [data-label="spouse"]')).toHaveText("Partner 2");
    await pick(page, "kind", "birth");
    await expect(page.locator('.editor [data-label="person"]')).toHaveText("Parent 1");
    await expect(page.locator('.editor [data-label="spouse"]')).toHaveText("Parent 2");
    // a noted event names nobody but the person it is about
    await pick(page, "kind", "noted");
    await expect(block(page, "pair")).toBeHidden();
  });

  // R-0144, R-0049
  test("targets appear with a relationship, triangles only inside and outside", async ({
    page,
  }) => {
    await openEditor(page);
    await pick(page, "kind", "shift");
    // these tests write to the record they open, so the one that saves leaves a
    // relationship behind for the next run: start from none whatever is there
    await pick(page, "relationship", "");
    await expect(block(page, "targets")).toBeHidden();
    await pick(page, "relationship", "conflict");
    await expect(block(page, "targets")).toBeVisible();
    await expect(page.locator('.editor [data-label="targets"]')).toHaveText("Other(s)");
    await expect(block(page, "triangles")).toBeHidden();
    await pick(page, "relationship", "inside");
    await expect(block(page, "triangles")).toBeVisible();
    await expect(page.locator('.editor [data-label="triangles"]')).toHaveText("Outside(s)");
    await expect(page.locator('.editor [data-label="person"]')).toHaveText("Person");
    await pick(page, "relationship", "overfunctioning");
    await expect(page.locator('.editor [data-label="person"]')).toHaveText("Overfunctioner");
  });

  // R-0142
  test("a relationship saves with two targets", async ({ page }) => {
    await openEditor(page);
    await pick(page, "kind", "shift");
    await pick(page, "relationship", "conflict");
    const targets = page.locator('.segs[data-name="relationshipTargets"] .seg');
    // whatever a previous run left on comes off first, so two is two
    for (const chip of await page
      .locator('.segs[data-name="relationshipTargets"] .seg.on')
      .all())
      await chip.click();
    await targets.nth(0).click();
    await targets.nth(1).click();
    const saved = page.waitForResponse(
      (r) => /\/app\/events/.test(r.url()) && r.request().method() === "PATCH",
    );
    await page.locator(".editor .save").click();
    const body = (await saved).request().postDataJSON();
    expect(body.relationship).toBe("conflict");
    expect(body.relationshipTargets).toHaveLength(2);
    // The row is redrawn from the record, so the codes prove the write stuck.
    await expect(page.locator("#menu-body .r2").first()).toContainText("R conflict");
  });

  /** A kind that does not use the shift fields does not save them either: the
   * editor keeps what was picked so switching back restores it, but the write
   * carries only the fields the chosen kind uses. */
  // R-0144
  test("a kind with no shift fields saves none of them", async ({ page }) => {
    await openEditor(page);
    await pick(page, "kind", "shift");
    await pick(page, "relationship", "conflict");
    await page.locator('.segs[data-name="relationshipTargets"] .seg').nth(0).click();
    await pick(page, "anxiety", "up");
    await pick(page, "kind", "married");
    const saved = page.waitForResponse(
      (r) => /\/app\/events/.test(r.url()) && r.request().method() === "PATCH",
    );
    await page.locator(".editor .save").click();
    const body = (await saved).request().postDataJSON();
    expect(body.kind).toBe("married");
    expect(body.relationship).toBeNull();
    expect(body.relationshipTargets).toEqual([]);
    expect(body.anxiety).toBeNull();
  });
});
