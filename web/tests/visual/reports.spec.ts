import { expect, test, type Page, type Request } from "@playwright/test";
import { stateFor } from "./setup";
import { mockTurn, SEND, STREAM } from "./turn";

/** A bug report and feedback: a sheet up from the bottom over the thread,
 * which it never changes. A coach turn that breaks raises the bug sheet; the
 * coach offering the person's words about the app raises the feedback sheet.
 * Sent, the sheet says so, and goes on OK or after ten seconds. */

const SENT_MS = 10_000;
/** How long the sheet takes to go down, after which it is hidden. */
const LOWER_MS = 280;
const REPORTS = "**/app/reports";

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

/** Every report the page sends. */
const posted = (page: Page) => {
  const sent: Request[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().endsWith("/app/reports")) sent.push(r);
  });
  return sent;
};

/** A turn that starts and then ends in an error on its own stream. */
const breaks = async (page: Page, message: string) => {
  await page.unrouteAll({ behavior: "wait" });
  await page.route(SEND, (route) =>
    route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ turn_id: "broke1", discussion_id: 1, statement_id: 9100 }),
    }),
  );
  await page.route(STREAM, (route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      body: `id: 1\ndata: ${JSON.stringify({ type: "failed", message })}\n\n`,
    }),
  );
};

/** An error thrown from the app's own bundle, as its stack names it; off a
 * microtask, since the installed clock catches what a timer throws. */
const throws = (page: Page, message: string) =>
  page.evaluate((message) => {
    queueMicrotask(() => {
      const error = new TypeError(message);
      error.stack = `TypeError: ${message}\n    at draw (${location.origin}/app/static/web/assets/index.js:1:52301)`;
      throw error;
    });
  }, message);

const answer = (page: Page, prefs: Record<string, string>) =>
  page.evaluate(async (body) => {
    const csrf = document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')!.content;
    await fetch("/app/preferences", {
      method: "PATCH",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify(body),
    });
  }, prefs);

test.describe("a coach turn that breaks", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0056, R-0182
  test("raises the bug sheet over the thread, which Send turns into the card saying it was sent, posting nothing more", async ({ page }) => {
    await settle(page);
    const sent = posted(page);
    await breaks(page, "The coach could not answer");
    await say(page, "My dad moved out.");

    await expect(heading(page)).toHaveText("Something went wrong");
    // the thread keeps its own warning, and nothing behind the sheet answers
    await expect(page.locator(".sys.warn")).toBeVisible();
    expect(await page.locator("#chat").evaluate((chat) => chat.closest("[inert]") !== null)).toBe(true);
    const rows = sheet(page).locator(".rp-row");
    await expect(rows.locator(".rp-l")).toHaveText(["The error", "The reply that failed", "The app version"]);
    const version = await page.evaluate(() => window.BOOTSTRAP.version);
    await expect(rows.locator(".rp-v")).toHaveText(["The coach could not answer", "broke1", version]);
    await expect(sheet(page).getByRole("button", { name: "Don't send" })).toBeDisabled();
    await expect(sheet(page).getByText("Disabled during the beta")).toBeVisible();
    const before = await thread(page);

    await sheet(page).getByRole("button", { name: "Send the report" }).click();
    await expect(heading(page)).toHaveText("Your report was sent");
    await expect(sheet(page).getByRole("button", { name: "OK" })).toBeVisible();
    // the server kept the failure under the turn when it happened
    expect(sent).toHaveLength(0);

    await sentOut(page);
    await expect(sheet(page)).toBeHidden();
    expect(await thread(page)).toBe(before);
    // the same error is never raised twice
    await say(page, "My dad moved out.");
    await expect(page.locator(".sys.warn")).toBeVisible();
    await expect(sheet(page)).toBeHidden();
  });
});

test.describe("Always send", () => {
  test.use({ storageState: stateFor("moves") });
  test.afterEach(({ page }) => answer(page, { bug_reports: "ask" }));

  // R-0056
  test("sends with no sheet once the person chose it, and only says it was sent", async ({ page }) => {
    await settle(page);
    const sent = posted(page);
    await throws(page, "x is undefined");
    await sheet(page).getByRole("button", { name: "Always send" }).click();
    await expect(heading(page)).toHaveText("Your report was sent");
    await sheet(page).getByRole("button", { name: "OK" }).click();
    await expect(sheet(page)).toBeHidden();

    await throws(page, "y is undefined");
    await expect(heading(page)).toHaveText("Your report was sent");
    await expect(sheet(page).getByRole("button", { name: "Send the report" })).toHaveCount(0);
    await expect
      .poll(() => sent.map((r) => r.postDataJSON().error))
      .toEqual(["TypeError: x is undefined", "TypeError: y is undefined"]);
    await sentOut(page);
    await expect(sheet(page)).toBeHidden();
  });
});

test.describe("what the person says about the app", () => {
  test.use({ storageState: stateFor("moves") });

  const WORDS = "I wish the picture had bigger names on it.";
  const offered = (page: Page, id: number) =>
    mockTurn(page, {
      statement: "I will pass that on. What happened after he left?",
      statement_id: id,
      did: [
        { type: "tool_call", name: "report", args: { kind: "feedback", words: WORDS }, names: {}, refusal: null },
        { type: "report", report: { kind: "feedback", words: WORDS } },
      ],
    });

  // R-0056
  test("raises the feedback sheet, and Not feedback puts it away and sends nothing", async ({ page }) => {
    await settle(page);
    const sent = posted(page);
    await offered(page, 9201);
    await say(page, WORDS);

    await expect(heading(page)).toHaveText("Send this as feedback?");
    await expect(sheet(page).locator(".rp-v")).toHaveText(WORDS);
    await expect(page.locator('.bub.coach[data-statement="9201"]')).toContainText("What happened after he left?");
    const before = await thread(page);

    await sheet(page).getByRole("button", { name: "Not feedback" }).click();
    await expect(sheet(page)).toBeHidden();
    expect(sent).toHaveLength(0);
    expect(await thread(page)).toBe(before);
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
    expect(sent).toHaveLength(1);
    expect(sent[0].postDataJSON()).toEqual({
      kind: "feedback",
      status: "sent",
      release: await page.evaluate(() => window.BOOTSTRAP.version),
      address: new URL(page.url()).pathname,
      turn_id: "t1",
      words: WORDS,
    });
    expect((await sent[0].response())!.status()).toBe(201);
    await sheet(page).getByRole("button", { name: "OK" }).click();
    await expect(sheet(page)).toBeHidden();
    expect(await thread(page)).toBe(before);
  });
});

test.describe("the server breaking", () => {
  test.use({ storageState: stateFor("moves") });

  /** How often the page reads the thread again while it is in front. */
  const CATCH_UP_MS = 60_000;
  const ID = { "X-Request-Id": "5d1c0ffee" };

  // R-0056
  test("raises the bug sheet once for an endpoint the server itself broke on, never for a proxy or a refusal", async ({
    page,
  }) => {
    await settle(page);
    const sent = posted(page);
    const SERVER_BROKE = { status: 500, headers: ID, body: "the server's own words" };
    let answer = {};
    let asked = 0;
    await page.route("**/app/statements*", (route) => {
      asked += 1;
      return route.fulfill(answer);
    });
    /** The thread read again with this answer: the minute is gone through
     * again until the page asks, since the clock can pass a timer by. */
    const minute = async (given: object) => {
      answer = given;
      const before = asked;
      await expect
        .poll(async () => {
          if (asked === before) await page.clock.fastForward(CATCH_UP_MS);
          return asked;
        })
        .toBeGreaterThan(before);
      await page.waitForTimeout(400);
    };

    await minute({ status: 502, body: "bad gateway" });
    await expect(sheet(page)).toBeHidden();
    await minute({ status: 404, headers: ID, body: "gone" });
    await expect(sheet(page)).toBeHidden();
    await minute(SERVER_BROKE);
    await expect(heading(page)).toHaveText("Something went wrong");
    const version = await page.evaluate(() => window.BOOTSTRAP.version);
    const rows = sheet(page).locator(".rp-row");
    await expect(rows.locator(".rp-l")).toHaveText([
      "The request",
      "The server's answer",
      "The request's id",
      "The app version",
    ]);
    await expect(rows.locator(".rp-v")).toHaveText(["GET /app/statements", "500", "5d1c0ffee", version]);
    await sheet(page).getByRole("button", { name: "Send the report" }).click();
    await expect(heading(page)).toHaveText("Your report was sent");
    expect(sent).toHaveLength(1);
    expect(sent[0].postDataJSON()).toEqual({
      kind: "bug",
      status: "sent",
      source: "page",
      release: version,
      address: new URL(page.url()).pathname,
      error: "500 GET /app/statements",
      request_id: "5d1c0ffee",
    });
    expect((await sent[0].response())!.status()).toBe(201);
    await sheet(page).getByRole("button", { name: "OK" }).click();
    await expect(sheet(page)).toBeHidden();

    await minute(SERVER_BROKE);
    await expect(sheet(page)).toBeHidden();
    expect(sent).toHaveLength(1);
  });
});

test.describe("the page breaking", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0056
  test("names the screen and the newest message, never the person's words", async ({ page }) => {
    await settle(page);
    const sent = posted(page);
    await throws(page, "x is undefined");

    await expect(heading(page)).toHaveText("Something went wrong");
    const { version, newest } = await page.evaluate(() => ({
      version: window.BOOTSTRAP.version,
      newest: window.BOOTSTRAP.statements.at(-1)!.id,
    }));
    const here = new URL(page.url());
    const frame = `${here.origin}/app/static/web/assets/index.js:1:52301`;
    const rows = sheet(page).locator(".rp-row");
    await expect(rows.locator(".rp-l")).toHaveText([
      "The error",
      "Where it broke",
      "The screen",
      "The newest message",
      "The app version",
    ]);
    await expect(rows.locator(".rp-v")).toHaveText([
      "TypeError: x is undefined",
      frame,
      here.pathname,
      `Number ${newest}, not its words`,
      version,
    ]);
    await sheet(page).getByRole("button", { name: "Send the report" }).click();
    await expect(heading(page)).toHaveText("Your report was sent");
    expect(sent[0].postDataJSON()).toEqual({
      kind: "bug",
      status: "sent",
      source: "page",
      release: version,
      address: here.pathname,
      statement_id: newest,
      error: "TypeError: x is undefined",
      frames: [frame],
    });
    expect((await sent[0].response())!.status()).toBe(201);
    await sheet(page).getByRole("button", { name: "OK" }).click();

    // the same error again raises nothing
    await throws(page, "x is undefined");
    await page.waitForTimeout(400);
    await expect(sheet(page)).toBeHidden();
  });
});
