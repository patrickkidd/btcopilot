import { expect, test, type Page } from "@playwright/test";
import { flask, shell, stateFor, username } from "./setup";

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
/** Folded, the card holds no buttons: a tap on it shows them under the words. */
const unfold = (page: Page) => strip(page).locator(".strip-m").click();
const account = (page: Page) => page.locator("#account");
/** The Notices row on the account view, which carries the unread count. */
const noticesRow = (page: Page) =>
  page.locator('.sn-pane[data-page="root"] .sn-row', { hasText: "Notices" });
/** The account view's Notices, opened from its row on the account view. */
const list = async (page: Page) => {
  await account(page).click();
  await noticesRow(page).click();
  return page.locator('.sn-pane.in[data-page="notices"] .sn-row');
};

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

// R-0017
test("a coach message never takes the strip: the notice under it does, and once the notice is put away the strip stays empty", async ({
  page,
}) => {
  await arrive(page);
  await expect(strip(page)).toHaveCount(1);
  await expect(strip(page)).toBeVisible();
  await expect(strip(page).locator(".strip-t")).toHaveText(NEW);

  await unfold(page);
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
test("a notice shows once in a strip above the message box, the cross counts it opened, and it lives on in the account view's Notices", async ({
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
  await unfold(page);
  await strip(page).locator(".cardx").click();
  expect((await put).ok()).toBe(true);
  await expect(strip(page)).toBeHidden();
  await expect(account(page)).not.toHaveClass(/\bunread\b/);

  await arrive(page);
  await expect(strip(page)).toBeHidden();
  const rows = await list(page);
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toContainText(NEW);
  await expect(rows.nth(1)).toContainText(OLD);
  await expect(rows.locator(".sn-unread")).toHaveCount(0);
});

// R-0017
test("a 60-character title and a 100-character body take two lines, each cut with its own ellipsis, beside the mark that the card opens and with no buttons, and nothing leaves the card", async ({
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
      const cut = el.scrollWidth > el.clientWidth || el.scrollHeight > el.clientHeight;
      return { left: r.left, right: r.right, height: r.height, cut };
    };
    return {
      card: box(".strip-c"),
      words: box(".strip-m"),
      title: box(".strip-t"),
      body: box(".strip-s"),
      more: box(".strip-more"),
      ellipses: [".strip-t", ".strip-s"].map((s) => getComputedStyle(document.querySelector(s)!).textOverflow),
      sideways: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });
  expect(at.title.height).toBeLessThanOrEqual(LINE);
  expect(at.body.height).toBeLessThanOrEqual(LINE);
  expect(at.words.height).toBeLessThanOrEqual(TWO_LINES);
  expect([at.title.cut, at.body.cut]).toEqual([true, true]);
  expect(at.ellipses).toEqual(["ellipsis", "ellipsis"]);
  await expect(strip(page).locator(".stepbtn")).toBeHidden();
  await expect(strip(page).locator(".cardx")).toBeHidden();
  for (const part of [at.words, at.more]) {
    expect(part.left).toBeGreaterThanOrEqual(at.card.left);
    expect(part.right).toBeLessThanOrEqual(at.card.right);
  }
  expect(at.card.right).toBeLessThanOrEqual(page.viewportSize()!.width);
  expect(at.sideways).toBeLessThanOrEqual(0);
});

// R-0017
test("a 160-character body folds to two lines, a tap shows all of it and then Open and the cross, without counting it opened, and a tap on the words folds it", async ({
  page,
}) => {
  const body = "Choose how often under Coach messages on your account page, and **turn them off** there. ".repeat(2).slice(0, 160);
  await page.route("**/app/notifications?all=true", async (route) => {
    const res = await route.fetch();
    const rows = (await res.json()) as { body: string | null }[];
    for (const one of rows) one.body = body;
    await route.fulfill({ response: res, json: rows });
  });
  const patched: string[] = [];
  page.on("request", (r) => r.method() === "PATCH" && patched.push(r.url()));
  await arrive(page);
  const words = strip(page).locator(".strip-m");
  const at = () =>
    page.evaluate(() => {
      const card = document.querySelector(".strip-c")!.getBoundingClientRect();
      const s = document.querySelector(".strip-s")!;
      return {
        card: { left: card.left, right: card.right },
        cut: s.scrollHeight > s.clientHeight,
        sideways: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      };
    });

  expect((await words.boundingBox())!.height).toBeLessThanOrEqual(TWO_LINES);
  expect((await at()).cut).toBe(true);
  await expect(strip(page).locator(".stepbtn")).toBeHidden();
  await expect(strip(page).locator(".cardx")).toBeHidden();

  await strip(page).locator(".strip-s").click();
  await expect(strip(page)).toHaveClass(/\bopen\b/);
  expect((await words.boundingBox())!.height).toBeGreaterThan(TWO_LINES);
  const open = await at();
  expect(open.cut).toBe(false);
  await expect(strip(page).locator(".strip-s strong")).toHaveText("turn them off");
  await expect(strip(page).locator(".strip-c > .stepbtn")).toBeVisible();
  await expect(strip(page).locator(".strip-c > .cardx")).toBeVisible();
  await expect(strip(page).locator(".strip-more")).toBeHidden();
  const under = (await words.boundingBox())!;
  for (const button of [".stepbtn", ".cardx"])
    expect((await strip(page).locator(button).boundingBox())!.y).toBeGreaterThanOrEqual(under.y + under.height);
  expect(open.card.left).toBeGreaterThanOrEqual(0);
  expect(open.card.right).toBeLessThanOrEqual(page.viewportSize()!.width);
  expect(open.sideways).toBeLessThanOrEqual(0);

  await strip(page).locator(".strip-t").click();
  await expect(strip(page)).not.toHaveClass(/\bopen\b/);
  expect((await words.boundingBox())!.height).toBeLessThanOrEqual(TWO_LINES);
  expect((await at()).cut).toBe(true);
  await expect(strip(page)).toBeVisible();
  expect(patched).toEqual([]);
});

// R-0017
test("Open Coach settings on a notice pointing at the coach settings lands on the coach settings page and clears the mark on the account button", async ({
  page,
}) => {
  await arrive(page);
  const rows = await list(page);
  await expect(noticesRow(page).locator(".sn-val")).toHaveText("1");
  await expect(rows.nth(0).locator(".sn-unread")).toHaveCount(1);
  await expect(rows.nth(0).locator(".sn-chev")).toHaveCount(1);
  await expect(rows.nth(1).locator(".sn-unread")).toHaveCount(0);
  await page.locator("#settings-back").click();
  await page.locator("#settings-back").click();
  await expect(page.locator(".sn-pane")).toHaveCount(0);

  const put = opened(page);
  await unfold(page);
  await strip(page).getByRole("button", { name: "Open Coach settings" }).click();
  expect((await put).ok()).toBe(true);
  await expect(page.locator('.sn-pane.in[data-page="coach"]')).toBeVisible();
  await expect(page.locator("#title")).toHaveText("Coach");
  await expect(noticesRow(page).locator(".sn-val")).toHaveText("");
  await expect(strip(page)).toBeHidden();
  await expect(account(page)).not.toHaveClass(/\bunread\b/);
});

// R-0017
test("a notice pointing at the account view has no Open, and its row in the Notices has no arrow and a tap only counts it read, in place", async ({
  page,
}) => {
  await page.route("**/app/notifications?all=true", async (route) => {
    const res = await route.fetch();
    const rows = (await res.json()) as { title: string; link: string | null }[];
    for (const one of rows) if (one.title === NEW) one.link = "account";
    await route.fulfill({ response: res, json: rows });
  });
  await arrive(page);
  await unfold(page);
  await expect(strip(page).locator(".cardx")).toBeVisible();
  await expect(strip(page).locator(".stepbtn")).toHaveCount(0);

  const rows = await list(page);
  await expect(rows.locator(".sn-chev")).toHaveCount(0);
  const put = opened(page);
  await rows.nth(0).click();
  expect((await put).ok()).toBe(true);
  await expect(page.locator('.sn-pane.in[data-page="notices"]')).toBeVisible();
  await expect(rows.locator(".sn-unread")).toHaveCount(0);
  await expect(account(page)).not.toHaveClass(/\bunread\b/);
});

// R-0017
test("a coach message written from outside the page appears in the thread when the page comes back to the front", async ({
  page,
}) => {
  const said = "Was that the first time she called on a Sunday?";
  await arrive(page);
  await expect(page.locator("#chat")).not.toContainText(said);
  shell(
    [
      "from btcopilot.extensions import db",
      "from btcopilot.models import Statement, User",
      "from btcopilot.routes import current_session",
      `at = current_session(User.query.filter_by(username="${username("notice")}").one())`,
      `db.session.add(Statement(discussion_id=at.id, speaker_id=at.chat_ai_speaker_id, text="${said}", order=len(at.statements)))`,
      "db.session.commit()",
      "",
    ].join("\n"),
  );
  const read = page.waitForResponse((r) => r.url().endsWith("/app/statements"));
  await page.evaluate(() => document.dispatchEvent(new Event("visibilitychange")));
  expect((await read).ok()).toBe(true);
  await expect(page.locator("#chat .bub").last()).toContainText(said);
  await expect(strip(page).locator(".strip-t")).not.toHaveText(said);
});
