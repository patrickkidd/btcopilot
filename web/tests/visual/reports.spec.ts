import { expect, test, type Page, type Request } from "./fixtures";
import { stateFor } from "./setup";
import { mockTurn } from "./turn";

/** A bug report and feedback: a sheet up from the bottom over the thread,
 * which it never changes, raised only when the coach offers the person's
 * words about the app. Sent, the sheet says so, and goes on OK or after ten
 * seconds. An error in the code raises no sheet: it is Grafana's. */

const SENT_MS = 10_000;
/** How long the sheet takes to go down, after which it is hidden. */
const LOWER_MS = 280;

/** The card saying the report was sent goes, and then the sheet is down; run
 * through rather than jumped, so the lowering the card's going schedules
 * fires too. */
const sentOut = (page: Page) => page.clock.runFor(SENT_MS + LOWER_MS);

const settle = async (page: Page) => {
  await page.clock.install();
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(400);
};

const say = async (page: Page, words: string) => {
  await page.locator("#composer").fill(words);
  await page.locator("#send").click();
};

const sheet = (page: Page) => page.locator(".fs-sheet.rp");
const heading = (page: Page) => sheet(page).locator(".cf-t");
const thread = (page: Page) => page.locator("#chat").innerHTML();
/** The widest the sheet grows on a wide screen. */
const WIDEST = 480;

/** As wide as the page on a phone, and on a wide screen no wider than
 * WIDEST and centred at the bottom. */
const fits = async (page: Page) => {
  const at = await sheet(page).evaluate((s) => {
    const r = s.getBoundingClientRect();
    const host = s.parentElement!.getBoundingClientRect();
    return { width: r.width, host: host.width, left: r.left - host.left, right: host.right - r.right };
  });
  expect(at.width).toBeCloseTo(Math.min(WIDEST, at.host), 0);
  expect(at.left).toBeCloseTo(at.right, 0);
};

/** Every report the page sends. */
const posted = (page: Page) => {
  const sent: Request[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().endsWith("/app/reports")) sent.push(r);
  });
  return sent;
};

const answer = (page: Page, prefs: Record<string, string>) =>
  page.evaluate(async (body) => {
    const csrf = document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')!.content;
    await fetch("/app/preferences", {
      method: "PATCH",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify(body),
    });
  }, prefs);

test.describe("what the person says about the app", () => {
  test.use({ storageState: stateFor("moves") });

  const WORDS = "I wish the picture had bigger names on it.";
  const offered = (page: Page, id: number, words = WORDS) =>
    mockTurn(page, {
      statement: "I will pass that on. What happened after he left?",
      statement_id: id,
      did: [
        { type: "tool_call", name: "report", args: { kind: "feedback", words }, names: {}, refusal: null },
        { type: "report", report: { kind: "feedback", words } },
      ],
    });

  // R-0056
  test("raises the feedback sheet, and Not feedback puts it away and sends where it was, never the words", async ({
    page,
  }) => {
    await settle(page);
    const sent = posted(page);
    await offered(page, 9201);
    await say(page, WORDS);

    await expect(heading(page)).toHaveText("Send this as feedback?");
    await fits(page);
    // the sheet takes the focus, not one of its buttons, and nothing behind it answers
    await expect(sheet(page)).toBeFocused();
    expect(await page.locator("#chat").evaluate((chat) => chat.closest("[inert]") !== null)).toBe(true);
    await expect(sheet(page).locator(".rp-v")).toHaveText(WORDS);
    await expect(sheet(page).getByRole("button")).toHaveText(["Send the report", "Not feedback"]);
    await expect(page.locator('.bub.coach[data-statement="9201"]')).toContainText("What happened after he left?");
    const before = await thread(page);

    await sheet(page).getByRole("button", { name: "Not feedback" }).click();
    await expect(sheet(page)).toBeHidden();
    await expect.poll(() => sent.length).toBe(1);
    expect(sent[0].postDataJSON()).toEqual({
      kind: "feedback",
      status: "declined",
      release: await page.evaluate(() => window.BOOTSTRAP.version),
      address: new URL(page.url()).pathname,
      turn_id: "t1",
      statement_id: 9201,
    });
    expect((await sent[0].response())!.status()).toBe(201);
    expect(await thread(page)).toBe(before);
  });

  // R-0056
  test("comes up once the reply is done, and never twice a sitting for the same words", async ({ page }) => {
    await settle(page);
    await mockTurn(page, {
      statement: "I will pass that on. What happened after he left?",
      statement_id: 9203,
      did: [
        { type: "tool_call", name: "report", args: { kind: "feedback", words: WORDS }, names: {}, refusal: null },
        { type: "report", report: { kind: "feedback", words: WORDS } },
      ],
      pause: 1500,
    });
    await say(page, WORDS);
    await page.waitForTimeout(700);
    await expect(sheet(page)).toBeHidden();
    await expect(heading(page)).toHaveText("Send this as feedback?", { timeout: 10_000 });
    await expect(page.locator('.bub.coach[data-statement="9203"]')).toContainText("What happened after he left?");
    await sheet(page).getByRole("button", { name: "Not feedback" }).click();
    await expect(sheet(page)).toBeHidden();

    await page.unrouteAll({ behavior: "wait" });
    await offered(page, 9204, `  ${WORDS.toUpperCase()} `);
    await say(page, "Really, the names are too small.");
    await expect(page.locator('.bub.coach[data-statement="9204"]')).toBeVisible();
    await page.waitForTimeout(400);
    await expect(sheet(page)).toBeHidden();

    const DOTS = "And the dots are too small.";
    await page.unrouteAll({ behavior: "wait" });
    await offered(page, 9205, DOTS);
    await say(page, DOTS);
    await expect(heading(page)).toHaveText("Send this as feedback?");
    await expect(sheet(page).locator(".rp-v")).toHaveText(DOTS);
  });

  // R-0056
  test("sends one report on Send and says so", async ({ page }) => {
    await settle(page);
    const sent = posted(page);
    await offered(page, 9202);
    await say(page, WORDS);
    await expect(heading(page)).toHaveText("Send this as feedback?");
    await expect(page.locator('.bub.coach[data-statement="9202"]')).toContainText("What happened after he left?");
    const before = await thread(page);

    await sheet(page).getByRole("button", { name: "Send the report" }).click();
    await expect(heading(page)).toHaveText("Your report was sent");
    await fits(page);
    expect(sent).toHaveLength(1);
    expect(sent[0].postDataJSON()).toEqual({
      kind: "feedback",
      status: "sent",
      release: await page.evaluate(() => window.BOOTSTRAP.version),
      address: new URL(page.url()).pathname,
      turn_id: "t1",
      statement_id: 9202,
      words: WORDS,
    });
    expect((await sent[0].response())!.status()).toBe(201);
    // the card goes on OK, or by itself after ten seconds
    await expect(sheet(page).getByRole("button", { name: "OK" })).toBeVisible();
    await sentOut(page);
    await expect(sheet(page)).toBeHidden();
    expect(await thread(page)).toBe(before);
  });
});

test.describe("a bug the coach offers", () => {
  test.use({ storageState: stateFor("moves") });
  test.afterEach(({ page }) => answer(page, { bug_reports: "ask" }));

  const offered = (page: Page, id: number, words: string) =>
    mockTurn(page, {
      statement: "I will pass that on. What happened after he left?",
      statement_id: id,
      did: [
        { type: "tool_call", name: "report", args: { kind: "bug", words }, names: {}, refusal: null },
        { type: "report", report: { kind: "bug", words } },
      ],
    });

  // R-0056
  test("asks with the words and cannot be turned down in the beta, and after Always send goes with no sheet and no card", async ({
    page,
  }) => {
    await settle(page);
    const sent = posted(page);
    const FIRST = "The picture did not update after I told you about my sister.";
    await offered(page, 9401, FIRST);
    await say(page, FIRST);

    await expect(heading(page)).toHaveText("Send this as a bug report?");
    await expect(sheet(page).locator(".rp-v")).toHaveText(FIRST);
    await expect(sheet(page).getByRole("button")).toHaveText(["Send the report", "Always send", "Don't send"]);
    const not = sheet(page).getByRole("button", { name: "Don't send" });
    await expect(not).toBeDisabled();
    await expect(not).toHaveAccessibleDescription("Disabled during the beta");
    await expect(sheet(page).locator(".rp-why")).toBeVisible();
    // tapped anyway, it does nothing: the sheet stays and nothing is written
    await not.click({ force: true });
    await page.waitForTimeout(400);
    await expect(heading(page)).toHaveText("Send this as a bug report?");
    expect(sent).toHaveLength(0);

    await sheet(page).getByRole("button", { name: "Always send" }).click();
    await expect(sheet(page)).toBeHidden();

    const SECOND = "You keep asking me the same question.";
    await page.unrouteAll({ behavior: "wait" });
    await offered(page, 9402, SECOND);
    await say(page, SECOND);
    await expect(page.locator('.bub.coach[data-statement="9402"]')).toBeVisible();
    await expect.poll(() => sent.map((r) => r.postDataJSON().words)).toEqual([FIRST, SECOND]);
    expect(sent[0].postDataJSON()).toEqual({
      kind: "bug",
      status: "sent",
      release: await page.evaluate(() => window.BOOTSTRAP.version),
      address: new URL(page.url()).pathname,
      turn_id: "t1",
      statement_id: 9401,
      words: FIRST,
    });
    expect((await sent[0].response())!.status()).toBe(201);
    await page.waitForTimeout(400);
    await expect(sheet(page)).toBeHidden();
  });
});

test.describe("a reply the page could not draw", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0056, R-0182
  test("stops following the turn and warns in the thread, with no sheet", async ({ page }) => {
    await settle(page);
    const sent = posted(page);
    await mockTurn(page, {
      statement: "Here is what happened after he left.",
      statement_id: 9301,
      did: [{ type: "view", view: null }],
    });
    await say(page, "My dad moved out.");

    await expect(page.locator(".sys.warn")).toContainText("This reply could not be shown");
    // nothing after the step that broke is drawn
    await expect(page.locator('.bub.coach[data-statement="9301"]')).toHaveCount(0);
    await page.waitForTimeout(400);
    await expect(sheet(page)).toBeHidden();
    expect(sent).toHaveLength(0);
  });
});
