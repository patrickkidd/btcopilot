import { expect, test, type Page, type Route } from "@playwright/test";
import { stateFor } from "./setup";
import { mockTurn } from "./turn";

/** Shadow replies (R-0636): while they are on, a coach reply waits for the
 * other models' and all of them are voted on unnamed before the reader types
 * again. Then the coach's own is headed Coach and the others fold behind a
 * mark beside the notes, headed only "Shadow reply". */

const REAL = "Your dad called about your mom's care. That puts you between the two of them for a moment. What happened in the call, as best you remember it?";
const REPLIES = [
  { key: "a", text: "So your dad brought her care to you directly. What did he ask of you on the call?" },
  { key: "b", text: REAL },
  { key: "c", text: "It sounds like your mom's care is weighing on the whole family right now. How did you feel when he called, and what do your siblings think should happen?" },
];
const PICKS = [
  { id: 71, left_key: "a", right_key: "b" },
  { id: 72, left_key: "c", right_key: "b" },
];

const MINUTE = 60_000;
const at = (ms: number) => new Date(Date.now() + ms).toISOString();

/** The switch on, turning itself off at `expires`. */
async function serve(page: Page, expires = at(5 * MINUTE)): Promise<Record<string, unknown>[]> {
  const cast: Record<string, unknown>[] = [];
  await page.route(/\/app\/preferences$/, async (route: Route) => {
    const answer = await route.fetch();
    const prefs = await answer.json();
    await route.fulfill({
      json: { ...prefs, shadow_models: ["sonnet", "gemini-pro"], shadow_expires_at: expires },
    });
  });
  await mockTurn(page, { statement: REAL, statement_id: 9601 });
  // the first ask finds one shadow finished, the next both
  let asked = 0;
  await page.route(/\/review\/picks\?turn=t1$/, (route) => {
    asked += 1;
    const picks = asked === 1 ? PICKS.slice(0, 1) : PICKS;
    const keys = new Set(picks.flatMap((p) => [p.left_key, p.right_key]));
    return route.fulfill({
      json: { replies: REPLIES.filter((r) => keys.has(r.key)), real_key: "b", picks },
    });
  });
  await page.route(/\/review\/picks\/\d+$/, async (route) => {
    const id = Number(route.request().url().split("/").pop());
    cast.push({ id, ...route.request().postDataJSON() });
    await route.fulfill({ json: { id, choice: "right", note: null, left: "x", right: "y" } });
  });
  return cast;
}

test.use({ storageState: stateFor("moves") });

const VOTED = [
  { ...PICKS[0], choice: "right", left_acceptable: true, right_acceptable: true, note: "Third asks two things at once" },
  { ...PICKS[1], choice: "right", left_acceptable: false, right_acceptable: true, note: "Third asks two things at once" },
];

/** The thread as a reload finds it after a vote: the coach reply before the
 * newest message was made with two shadow replies, voted on. Answers how
 * often its replies were asked for. */
async function voted(page: Page): Promise<() => number> {
  let asked = 0;
  await page.route(/\/review\/picks\?turn=t9$/, (route) => {
    asked += 1;
    return route.fulfill({ json: { replies: REPLIES, real_key: "b", picks: VOTED } });
  });
  await page.addInitScript(() => {
    let boot: { statements: { id: number; role: string; turn_id: string | null; feedback: number }[] };
    Object.defineProperty(window, "BOOTSTRAP", {
      get: () => boot,
      set: (value) => {
        const past = value.statements.slice(0, -1).filter((s: { role: string }) => s.role === "coach").at(-1);
        Object.assign(past, { turn_id: "t9", feedback: 2 });
        boot = value;
      },
    });
  });
  return () => asked;
}

// R-0636, R-0637
test("three replies are voted on unnamed, then the coach's is headed Coach with the others folded", async ({
  page,
}) => {
  const cast = await serve(page);
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await expect(page.locator("#feedback span")).toHaveText("Conversation feedback enabled; Responses will be slower, vote on the best replies");
  await page.locator("#composer").fill("My dad called last night about mom's care.");
  await page.locator("#send").click();

  await expect(page.locator(".bub.coach .vt-wait")).toHaveText("Waiting for other replies");
  await expect(page.locator(".bub.coach.blind .words")).toBeHidden();
  const bubble = page.locator(".bub.coach").last();
  await expect(bubble.locator(".vt-reply")).toHaveCount(3);
  await expect(bubble.locator(".who").first()).toHaveText("3 replies");
  await expect(bubble.locator(":scope > .info")).toBeHidden();
  await expect(page.locator("#composer")).toHaveAttribute("data-ph", "Vote first, then type");
  await expect(page.locator("#send")).toBeDisabled();

  const reply = (key: string) => bubble.locator(`.vt-reply[data-key="${key}"]`);
  await reply("a").getByRole("button", { name: "✓ acceptable" }).click();
  await reply("b").getByRole("button", { name: "☆ best" }).click();
  await bubble.locator(".vt-note").fill("Third asks two things at once");
  await expect(bubble.locator(".vt-count")).toHaveText("29/200");
  await expect(page).toHaveScreenshot("vote-open.png");

  await bubble.getByRole("button", { name: "Vote" }).click();
  await expect(bubble.locator(".who")).toHaveText("Coach");
  await expect(bubble).toHaveClass(/\bfb\b/);
  await expect(bubble.locator(".vt-fold .n")).toHaveText("2");
  await expect(page.locator("#send")).toBeEnabled();
  await expect(page.locator("#composer")).toHaveAttribute("contenteditable", "true");
  expect(cast.sort((a, b) => Number(a.id) - Number(b.id))).toEqual([
    { id: 71, choice: "right", left_acceptable: true, right_acceptable: true, note: "Third asks two things at once", source: "chat" },
    { id: 72, choice: "right", left_acceptable: false, right_acceptable: true, note: "Third asks two things at once", source: "chat" },
  ]);

  await bubble.locator(".vt-fold").click();
  await expect(bubble.locator(".vt-shadow .who")).toHaveText(["Shadow reply", "Shadow reply"]);
  await expect(bubble.locator(".vt-voted")).toHaveText(["✓ acceptable · ★ best", "✓ acceptable", "not acceptable"]);
  await expect(bubble.locator(".vt-said")).toHaveText("Your note: Third asks two things at once");
  expect(await page.content()).not.toMatch(/sonnet|gemini/i);
  await expect(page).toHaveScreenshot("vote-folded-open.png");
});

// R-0637
test("a message 6 minutes after the last one gets the coach's reply alone, with the message box open", async ({
  page,
}) => {
  // the last message was 6 minutes ago, so the switch turned itself off a
  // minute ago, though the switch still reads on
  await serve(page, at(-MINUTE));
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await expect(page.locator("#feedback")).toBeHidden();
  await page.locator("#composer").fill("My dad called last night about mom's care.");
  await page.locator("#send").click();

  const bubble = page.locator(".bub.coach").last();
  await expect(bubble).toHaveClass("bub coach");
  await expect(bubble.locator(".words")).toContainText("That puts you between the two of them");
  await expect(bubble.locator(".vt-wait")).toHaveCount(0);
  await expect(bubble.locator(".vt-reply")).toHaveCount(0);
  await expect(page.locator("#send")).toBeEnabled();
  await expect(page.locator("#composer")).toHaveAttribute("contenteditable", "true");
});

// a family whose thread has coach replies before its newest message
test.describe("a thread read again", () => {
  test.use({ storageState: stateFor("sitting") });

  // R-0636
  test("after a reload a past reply voted on keeps its amber edge and its fold, and the fold shows how each was voted", async ({
    page,
  }) => {
    const asked = await voted(page);
    await page.goto("/app/");
    const bubble = page.locator(".bub.coach.fb");
    await expect(bubble).toHaveCount(1);
    await expect(bubble.locator(".vt-fold .n")).toHaveText("2");
    expect(asked()).toBe(0);
    await expect(page.locator("#send")).toBeEnabled();

    await bubble.locator(".vt-fold").click();
    await expect(bubble.locator(".vt-shadow .who")).toHaveText(["Shadow reply", "Shadow reply"]);
    await expect(bubble.locator(".vt-voted")).toHaveText(["✓ acceptable · ★ best", "✓ acceptable", "not acceptable"]);
    await expect(bubble.locator(".vt-said")).toHaveText("Your note: Third asks two things at once");
    expect(asked()).toBe(1);
  });

  // R-0636
  test("in dark mode a reply made with Conversation Feedback on has an amber edge", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await voted(page);
    await page.goto("/app/");
    const bubble = page.locator(".bub.coach.fb");
    await expect(bubble).toHaveCSS("border-left-width", "3px");
    await expect(bubble).toHaveCSS("border-left-color", "rgb(224, 168, 63)");
    await expect(page.locator(".bub.coach:not(.fb)").first()).toHaveCSS("border-left-width", "1px");
    await bubble.scrollIntoViewIfNeeded();
    await expect(bubble).toHaveScreenshot("vote-dark.png");
  });
});
