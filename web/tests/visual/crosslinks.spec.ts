import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** One record, reached from either side. A person's editor offers the events
 * about them; an event's editor offers the people in it; and the words on the
 * picture reach the moment's own editor. Every jump keeps the drawer open and
 * changes the tab under it. */

const settle = async (page: Page) => {
  await page.goto("/personal/");
  await expect(page.locator(".ss")).toBeVisible();
  await page.waitForTimeout(500);
};

const openList = async (page: Page) => {
  await page.locator("#menu-open").click();
  await expect(page.locator("#menu-screen")).toBeVisible();
};

const editor = (page: Page) => page.locator("#menu-body .editor");

test.describe("the person editor", () => {
  test.use({ storageState: stateFor("three40") });

  test("says what the record keeps, and where the rest is kept", async ({
    page,
  }) => {
    await settle(page);
    await openList(page);
    await page.locator("#tab-people").click();
    await page.locator("#menu-body .row").first().click();

    await expect(editor(page).locator(".lab").last()).toHaveText("Kind");
    await expect(editor(page).locator(".hint")).toHaveText(
      "Add birth and death events by chatting with the coach.",
    );
    // never sex, never gender: two of the five are kinds of person symbol
    await expect(editor(page)).not.toContainText("Sex");
    await expect(editor(page).locator('.segs[data-name="gender"] .seg')).toHaveCount(5);
  });
});

test.describe("an event and the people in it", () => {
  test.use({ storageState: stateFor("three40") });

  test("the person it is about opens their own editor", async ({ page }) => {
    await settle(page);
    await openList(page);
    await page.locator("#menu-body .row").first().click();
    await expect(editor(page)).toBeVisible();

    // the person already chosen: tapping them goes to them
    await editor(page).locator('.segs[data-name="person"] .seg.on').click();
    await expect(page.locator("#tab-people")).toHaveClass(/on/);
    await expect(page.locator("#menu-screen")).toBeVisible();
    await expect(editor(page).locator('[data-name="name"]')).toHaveValue("Ada");
  });

  test("a person not yet chosen is still chosen by tapping", async ({ page }) => {
    await settle(page);
    await openList(page);
    await page.locator("#menu-body .row").first().click();
    const off = editor(page).locator('.segs[data-name="person"] .seg:not(.on)').nth(1);
    const words = await off.innerText();
    await off.click();
    // still the event's editor, with that person now chosen
    await expect(page.locator("#tab-events")).toHaveClass(/on/);
    await expect(
      editor(page).locator('.segs[data-name="person"] .seg.on'),
    ).toHaveText(words);
  });
});

test.describe("a person the record knows the birth and death of", () => {
  test.use({ storageState: stateFor("longmove") });

  test("offers those two events, and one opens its own editor", async ({
    page,
  }) => {
    await settle(page);
    await openList(page);
    await page.locator("#tab-people").click();
    await page.locator('#menu-body .row:has-text("Ada")').first().click();

    const life = editor(page).locator("[data-event]");
    await expect(life).toHaveCount(2);
    await expect(life.first()).toHaveText("Their birth");
    await expect(life.last()).toHaveText("Their death");

    await life.first().click();
    await expect(page.locator("#tab-events")).toHaveClass(/on/);
    await expect(editor(page).locator('.segs[data-name="kind"] .seg.on')).toHaveText(
      "birth",
    );
  });
});

test.describe("the picture with one cluster open", () => {
  test.use({ storageState: stateFor("three40") });

  const openCluster = async (page: Page) => {
    await page.locator('.ss-hit[data-target="cluster"]').first().click();
    await expect(page.locator('.ss-hit[data-target="zone"]').first()).toBeVisible();
    await page.waitForTimeout(400);
  };

  test("shows the way back to all of them", async ({ page }) => {
    await settle(page);
    // the name of the picture is the way back, and says so while one is open
    await expect(page.locator("#crumb")).toHaveText("Family timeline");
    await openCluster(page);
    await expect(page.locator("#crumb")).toHaveText("← Family timeline");

    await page.locator("#crumb").click();
    await expect(page.locator('.ss-hit[data-target="cluster"]').first()).toBeVisible();
    await expect(page.locator("#crumb")).toHaveText("Family timeline");
  });

  test("the words of the moment picked open its editor", async ({ page }) => {
    await settle(page);
    await openCluster(page);
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    await expect(page.locator(".ss-t.on").first()).toBeVisible();

    const label = page.locator(".ss-t.on").first();
    const box = (await label.boundingBox())!;
    await page.mouse.click(box.x + 30, box.y + box.height / 2);

    await expect(page.locator("#menu-screen")).toBeVisible();
    await expect(page.locator("#tab-events")).toHaveClass(/on/);
    await expect(editor(page)).toBeVisible();
  });
});
