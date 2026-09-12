import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** The settings stack: the avatar in the title row, and the pages it pushes.
 * Every value has one home, and the chat view's speak-replies row is the one
 * named shortcut onto the same value. */

const settle = async (page: Page) => {
  await page.goto("/personal/");
  await expect(page.locator(".ss")).toBeVisible();
  await page.waitForTimeout(600);
};

const openSettings = async (page: Page) => {
  await page.locator("#account").click();
  await expect(page.locator('.sn-pane[data-page="root"]')).toBeVisible();
  await page.waitForTimeout(300);
};

test.describe("the settings stack", () => {
  test.use({ storageState: stateFor("moves") });

  test("the avatar sits in the title row at the ruled size", async ({ page }) => {
    await settle(page);
    const avatar = page.locator("#account");
    const inTitle = await avatar.evaluate((node) => !!node.closest(".titlerow"));
    expect(inTitle).toBe(true);
    const box = (await avatar.boundingBox())!;
    expect(Math.round(box.width)).toBe(44);
    expect(Math.round(box.height)).toBe(44);
  });

  test("it opens on Account with the ruled rows in the ruled order", async ({
    page,
  }) => {
    await settle(page);
    await openSettings(page);
    await expect(page.locator("#title")).toHaveText("Account");
    const labels = await page.locator(".sn-pane.in .sn-lbl").allTextContents();
    expect(labels).toEqual([
      "Coach",
      "Appearance",
      "Your diagrams",
      "Plan and licenses",
    ]);
    await expect(page.locator(".sn-out")).toHaveText("Sign out");
    await expect(page.locator(".sn-foot")).toHaveText("Family Diagram · beta");
  });

  test("a row pushes its own page and the chevron pops it", async ({ page }) => {
    await settle(page);
    await openSettings(page);
    await page.locator(".sn-row.push").first().click();
    await expect(page.locator("#title")).toHaveText("Coach");
    await expect(page.locator('.sn-pane[data-page="coach"]')).toBeVisible();
    await page.locator("#settings-back").click();
    await page.waitForTimeout(300);
    await expect(page.locator("#title")).toHaveText("Account");
  });

  test("the back chevron on the root page closes the stack", async ({ page }) => {
    await settle(page);
    await openSettings(page);
    await page.locator("#settings-back").click();
    await page.waitForTimeout(300);
    await expect(page.locator(".sn-stack")).toBeHidden();
    // the title row names the family the app is on, not a stock phrase
    await expect(page.locator("#title")).toHaveText("FD-362 visual fixture");
  });

  test("speak replies is a switch of the ruled size, not a checkbox", async ({
    page,
  }) => {
    await settle(page);
    await openSettings(page);
    await page.locator(".sn-row.push").first().click();
    await page.waitForTimeout(300);
    const box = (await page.locator(".sw").boundingBox())!;
    expect(Math.round(box.width)).toBe(51);
    expect(Math.round(box.height)).toBe(31);
    expect(await page.locator(".sn-pane.in input[type=checkbox]").count()).toBe(0);
  });

  test("the chat row and the coach page write the same speak value", async ({
    page,
  }) => {
    await settle(page);
    const row = page.locator("#speak");
    const before = await row.isChecked();
    await row.setChecked(!before);
    await page.waitForTimeout(500);

    await openSettings(page);
    await page.locator(".sn-row.push").first().click();
    await page.waitForTimeout(300);
    await expect(page.locator(".sw")).toHaveAttribute(
      "aria-checked",
      String(!before),
    );

    await page.locator(".sw").click();
    await page.waitForTimeout(500);
    await page.locator("#settings-back").click();
    await page.locator("#settings-back").click();
    await page.waitForTimeout(400);
    expect(await row.isChecked()).toBe(before);
  });

  test("the profile page carries the three ruled fields", async ({ page }) => {
    await settle(page);
    await openSettings(page);
    await page.locator(".sn-cell").click();
    await page.waitForTimeout(300);
    await expect(page.locator("#title")).toHaveText("Profile");
    const labels = await page
      .locator('.sn-pane[data-page="profile"] .sn-lbl')
      .allTextContents();
    expect(labels).toEqual([
      "first name",
      "last name",
      "birthdate",
      "email",
      "sign in",
    ]);
  });

  test("nothing in the stack falls under the 44px floor", async ({ page }) => {
    await settle(page);
    await openSettings(page);
    const small = await page.evaluate(() =>
      [
        ...document.querySelectorAll(
          ".sn-pane.in .sn-row, .sn-pane.in .sn-cell, .sn-pane.in button, .sn-pane.in input",
        ),
      ]
        .map((node) => ({
          what: node.className || node.tagName,
          height: Math.round(node.getBoundingClientRect().height),
        }))
        .filter((row) => row.height > 0 && row.height < 44),
    );
    expect(small).toEqual([]);
  });
});
