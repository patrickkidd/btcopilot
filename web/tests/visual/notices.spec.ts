import { expect, test, type Page } from "@playwright/test";
import { flask, stateFor } from "./setup";

/** Notices against the fixture that holds one unread notice, one opened four
 * days ago, and an unread coach message newer than both. Each test puts the
 * fixture back first, since each one opens the notice. */
test.use({ storageState: stateFor("notice") });

const NEW = "Coach messages can now come weekly";
const OLD = "Welcome to the app";
/** One line of the strip's 15px words at 1.3, give or take a pixel. */
const LINE = 15 * 1.3 + 1;
const TWO_LINES = 2 * LINE;

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

// R-0017, R-0606
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

// R-0017
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

// R-0017
test("a 60-character title and a 100-character body take two lines, each cut with its own ellipsis, and nothing leaves the card", async ({
  page,
}) => {
  await page.route("**/app/notifications?all=true", async (route) => {
    const res = await route.fetch();
    const rows = (await res.json()) as { title: string; body: string | null }[];
    for (const one of rows) {
      one.title = "Coach messages now come weekly ".repeat(2).slice(0, 60);
      one.body = "Choose how often under Coach messages on your account page. ".repeat(2).slice(0, 100);
    }
    await route.fulfill({ response: res, json: rows });
  });
  await arrive(page);
  const at = await page.evaluate(() => {
    const box = (s: string) => {
      const el = document.querySelector(s)!;
      const r = el.getBoundingClientRect();
      return { left: r.left, right: r.right, height: r.height, cut: el.scrollWidth > el.clientWidth };
    };
    return {
      card: box(".strip-c"),
      words: box(".strip-m"),
      title: box(".strip-t"),
      body: box(".strip-s"),
      open: box(".strip-c > .stepbtn"),
      cross: box(".strip-c > .cardx"),
      ellipses: [".strip-t", ".strip-s"].map((s) => getComputedStyle(document.querySelector(s)!).textOverflow),
      sideways: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });
  expect(at.title.height).toBeLessThanOrEqual(LINE);
  expect(at.body.height).toBeLessThanOrEqual(LINE);
  expect(at.words.height).toBeLessThanOrEqual(TWO_LINES);
  expect([at.title.cut, at.body.cut]).toEqual([true, true]);
  expect(at.ellipses).toEqual(["ellipsis", "ellipsis"]);
  for (const part of [at.words, at.open, at.cross]) {
    expect(part.left).toBeGreaterThanOrEqual(at.card.left);
    expect(part.right).toBeLessThanOrEqual(at.card.right);
  }
  expect(at.card.right).toBeLessThanOrEqual(page.viewportSize()!.width);
  expect(at.sideways).toBeLessThanOrEqual(0);
});

// R-0017
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
