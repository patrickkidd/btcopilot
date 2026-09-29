import { expect, test, type Page } from "@playwright/test";
import { flask, stateFor } from "./setup";

/** Notices against the fixture that holds one unread notice, one opened four
 * days ago, and an unread coach message newer than both. Each test puts the
 * fixture back first, since each one opens the notice. */
test.use({ storageState: stateFor("notice") });

const NEW = "Coach messages can now come weekly";
const OLD = "Welcome to the app";
/** Two lines of the strip's 15px words at 1.3, give or take a pixel. */
const TWO_LINES = 2 * 15 * 1.3 + 1;

const strip = (page: Page) => page.locator(".strip");
const account = (page: Page) => page.locator("#account");

/** The app, once it has read the reader's notifications. */
async function arrive(page: Page): Promise<void> {
  const read = page.waitForResponse((r) => r.url().endsWith("/app/notifications?all=true"));
  await page.goto("/app/");
  expect((await read).ok()).toBe(true);
}

const opened = (page: Page) =>
  page.waitForResponse(
    (r) => r.request().method() === "PATCH" && /\/app\/notifications\/\d+$/.test(r.url()),
  );

test.beforeEach(() => {
  flask("app", "fixtures", "notice");
});

// R-0611, R-0606
test("a coach message never takes the strip: the notice under it does, and once the notice is put away the strip stays empty", async ({
  page,
}) => {
  await arrive(page);
  await expect(strip(page)).toHaveCount(1);
  await expect(strip(page)).toBeVisible();
  await expect(strip(page).locator(".strip-t")).toHaveText(NEW);

  await strip(page).locator(".cardx").click();
  await expect(strip(page)).toBeHidden();
  const read = page.waitForResponse((r) => r.url().endsWith("/app/notifications?all=true"));
  await page.reload();
  const unread = ((await (await read).json()) as { kind: string; opened_at: string | null }[])
    .filter((one) => one.opened_at === null)
    .map((one) => one.kind);
  expect(unread).toEqual(["coach"]);
  await expect(strip(page)).toBeHidden();
});

// R-0611
test("a notice shows once in a strip above the message box, the cross counts it opened, and it lives on in the account's list", async ({
  page,
}) => {
  await arrive(page);
  const box = (await strip(page).boundingBox())!;
  const bar = (await page.locator("#inbar").boundingBox())!;
  expect(box.y + box.height).toBeLessThanOrEqual(bar.y);
  expect((await strip(page).locator(".strip-m").boundingBox())!.height).toBeLessThanOrEqual(
    TWO_LINES,
  );
  await expect(page.locator("#chat")).not.toContainText(NEW);
  await expect(account(page)).toHaveClass(/\bunread\b/);

  const put = opened(page);
  await strip(page).locator(".cardx").click();
  expect((await put).ok()).toBe(true);
  await expect(strip(page)).toBeHidden();
  await expect(account(page)).not.toHaveClass(/\bunread\b/);

  await arrive(page);
  await expect(strip(page)).toBeHidden();
  await account(page).click();
  const rows = page.locator('.sn-pane[data-page="root"] .sn-grp').filter({ hasText: OLD }).locator(".sn-row");
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toContainText(NEW);
  await expect(rows.nth(1)).toContainText(OLD);
  await expect(rows.locator(".sn-unread")).toHaveCount(0);
});

// R-0611
test("the strip's way in opens the screen the notice points to and clears the mark on the account button", async ({
  page,
}) => {
  await arrive(page);
  await account(page).click();
  const rows = page.locator('.sn-pane[data-page="root"] .sn-grp').filter({ hasText: OLD }).locator(".sn-row");
  await expect(rows.nth(0).locator(".sn-unread")).toHaveCount(1);
  await expect(rows.nth(1).locator(".sn-unread")).toHaveCount(0);
  await page.locator("#settings-back").click();
  await expect(page.locator(".sn-pane")).toHaveCount(0);

  const put = opened(page);
  await strip(page).locator(".stepbtn").click();
  expect((await put).ok()).toBe(true);
  await expect(page.locator('.sn-pane.in[data-page="root"]')).toBeVisible();
  await expect(rows.locator(".sn-unread")).toHaveCount(0);
  await expect(strip(page)).toBeHidden();
  await expect(account(page)).not.toHaveClass(/\bunread\b/);
});
