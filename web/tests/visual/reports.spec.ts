import { expect, test, type Page, type Request } from "@playwright/test";
import { stateFor } from "./setup";
import { mockTurn, SEND, STREAM } from "./turn";

/** A bug report and feedback: a sheet up from the bottom over the thread,
 * which it never changes. A coach turn that breaks raises the bug sheet; the
 * coach offering the person's words about the app raises the feedback sheet.
 * Sent, the sheet says so, and goes on OK or after ten seconds. */

const SENT_MS = 10_000;
const REPORTS = "**/app/observations";

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
    if (r.method() === "POST" && r.url().endsWith("/app/observations")) sent.push(r);
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
  test.afterEach(({ page }) => answer(page, { bug_reports: "ask" }));

  // R-0056, R-0182
  test("raises the bug sheet over the thread, which Send turns into the card saying it was sent", async ({ page }) => {
    await settle(page);
    const sent = posted(page);
    await breaks(page, "The coach could not answer");
    await say(page, "My dad moved out.");

    await expect(heading(page)).toHaveText("Something went wrong");
    // the thread keeps its own warning, and nothing behind the sheet answers
    await expect(page.locator(".sys.warn")).toBeVisible();
    expect(await page.locator("#chat").evaluate((chat) => chat.closest("[inert]") !== null)).toBe(true);
    const rows = sheet(page).locator(".rp-row");
    await expect(rows.locator(".rp-l")).toHaveText(["Your last message", "The error", "The app version"]);
    const version = await page.evaluate(() => window.BOOTSTRAP.version);
    await expect(rows.locator(".rp-v")).toHaveText(["My dad moved out.", "The coach could not answer", version]);
    await expect(sheet(page).getByRole("button", { name: "Don't send" })).toBeDisabled();
    await expect(sheet(page).getByText("Disabled during the beta")).toBeVisible();
    const before = await thread(page);

    await sheet(page).getByRole("button", { name: "Send the report" }).click();
    await expect(heading(page)).toHaveText("Your report was sent");
    await expect(sheet(page).getByRole("button", { name: "OK" })).toBeVisible();
    expect(sent).toHaveLength(1);
    expect(sent[0].postDataJSON()).toEqual({
      kind: "bug",
      turn_id: "broke1",
      text: "My dad moved out.",
      error: "The coach could not answer",
      version,
    });
    expect((await sent[0].response())!.status()).toBe(201);

    await page.clock.fastForward(SENT_MS);
    await expect(sheet(page)).toBeHidden();
    expect(await thread(page)).toBe(before);
    // the same error is never raised twice
    await say(page, "My dad moved out.");
    await expect(page.locator(".sys.warn")).toBeVisible();
    await expect(sheet(page)).toBeHidden();
  });

  // R-0056
  test("sends with no sheet once the person chose Always send, and only says it was sent", async ({ page }) => {
    await settle(page);
    const sent = posted(page);
    await breaks(page, "The coach could not answer");
    await say(page, "My dad moved out.");
    await sheet(page).getByRole("button", { name: "Always send" }).click();
    await expect(heading(page)).toHaveText("Your report was sent");
    await sheet(page).getByRole("button", { name: "OK" }).click();
    await expect(sheet(page)).toBeHidden();

    await breaks(page, "The model timed out");
    await say(page, "And my mum got ill.");
    await expect(heading(page)).toHaveText("Your report was sent");
    await expect(sheet(page).getByRole("button", { name: "Send the report" })).toHaveCount(0);
    expect(sent.map((r) => r.postDataJSON().error)).toEqual([
      "The coach could not answer",
      "The model timed out",
    ]);
    await page.clock.fastForward(SENT_MS);
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
    expect(sent[0].postDataJSON()).toEqual({ kind: "feedback", turn_id: "t1", text: WORDS });
    expect((await sent[0].response())!.status()).toBe(201);
    await sheet(page).getByRole("button", { name: "OK" }).click();
    await expect(sheet(page)).toBeHidden();
    expect(await thread(page)).toBe(before);
  });
});
