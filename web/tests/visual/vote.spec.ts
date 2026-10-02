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
/** Polls that step the page's clock want no pause of their own. */
const FAST = { timeout: 30_000, intervals: [50] };
const at = (ms: number) => new Date(Date.now() + ms).toISOString();

/** The switch on, turning itself off at `expires`; the second shadow
 * finishes on the `second`th ask, the first before the first ask. Answers the
 * votes cast and how often the replies were asked for. */
async function serve(
  page: Page,
  expires = at(5 * MINUTE),
  second = 2,
): Promise<{ cast: Record<string, unknown>[]; asked: () => number }> {
  const cast: Record<string, unknown>[] = [];
  await page.route(/\/app\/preferences$/, async (route: Route) => {
    const answer = await route.fetch();
    const prefs = await answer.json();
    await route.fulfill({
      json: { ...prefs, shadow_models: ["sonnet", "gemini-pro"], shadow_expires_at: expires },
    });
  });
  await mockTurn(page, { statement: REAL, statement_id: 9601 });
  let asked = 0;
  await page.route(/\/review\/picks\?turn=t1$/, (route) => {
    asked += 1;
    const running = asked < second ? 1 : 0;
    const picks = PICKS.slice(0, 2 - running);
    const keys = new Set(picks.flatMap((p) => [p.left_key, p.right_key]));
    return route.fulfill({
      json: {
        replies: REPLIES.filter((r) => keys.has(r.key)),
        real_key: "b",
        picks,
        pending: running,
        expected: 2,
      },
    });
  });
  await page.route(/\/review\/picks\/\d+$/, async (route) => {
    const id = Number(route.request().url().split("/").pop());
    cast.push({ id, ...route.request().postDataJSON() });
    await route.fulfill({ json: { id, choice: "right", note: null, left: "x", right: "y" } });
  });
  return { cast, asked: () => asked };
}

test.use({ storageState: stateFor("moves") });

const VOTED = [
  { ...PICKS[0], choice: "right", left_acceptable: true, right_acceptable: true, note: "Third asks two things at once" },
  { ...PICKS[1], choice: "right", left_acceptable: false, right_acceptable: true, note: "Third asks two things at once" },
];

/** The thread as a reload finds it after a vote: the coach reply before the
 * newest message was made with two shadow replies, voted on. Answers how
 * often its replies were asked for. */
async function voted(page: Page, picks = VOTED, newest = false): Promise<() => number> {
  let asked = 0;
  await page.route(/\/review\/picks\?turn=t9$/, (route) => {
    asked += 1;
    return route.fulfill({ json: { replies: REPLIES, real_key: "b", picks, pending: 0, expected: 2 } });
  });
  await page.addInitScript((newest) => {
    let boot: { statements: { id: number; role: string; turn_id: string | null; feedback: number }[] };
    Object.defineProperty(window, "BOOTSTRAP", {
      get: () => boot,
      set: (value) => {
        const past = value.statements.slice(0, newest ? undefined : -1).filter((s: { role: string }) => s.role === "coach").at(-1);
        if (newest) value.statements.length = value.statements.indexOf(past) + 1;
        Object.assign(past, { turn_id: "t9", feedback: 2 });
        boot = value;
      },
    });
  }, newest);
  return () => asked;
}

// R-0636, R-0637
test("three replies are voted on unnamed, then the coach's is headed Coach with the others folded", async ({
  page,
}) => {
  const { cast } = await serve(page);
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
  // R-0636
  await expect
    .poll(() => page.locator("#chat").evaluate((list) => list.scrollHeight - list.clientHeight - list.scrollTop))
    .toBeLessThanOrEqual(24);
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

// R-0636
test("a shadow reply that finishes 70 seconds after the coach's is still voted on", async ({ page }) => {
  await page.clock.install();
  // polled every 2 seconds from the coach's reply, the 32nd ask is past the
  // old 60-second cut-off and the 36th at 70 seconds
  const { asked } = await serve(page, at(5 * MINUTE), 36);
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.locator("#composer").fill("My dad called last night about mom's care.");
  await page.locator("#send").click();
  const bubble = page.locator(".bub.coach").last();
  await expect(bubble.locator(".vt-wait")).toHaveText("Waiting for other replies");
  // the mocked reply is not in the record, so the thread read once a minute
  // would draw the thread again without it; that read finds no signal instead
  await page.route(/\/app\/statements\?diagram_id=\d+$/, (route) => route.abort("internetdisconnected"));

  await expect
    .poll(async () => {
      await page.clock.runFor(2000);
      return asked();
    }, FAST)
    .toBeGreaterThanOrEqual(32);
  await expect(bubble.locator(".vt-wait")).toBeVisible();
  await expect(bubble.locator(".vt-reply")).toHaveCount(0);

  await expect
    .poll(async () => {
      await page.clock.runFor(2000);
      return bubble.locator(".vt-reply").count();
    }, FAST)
    .toBe(3);
  expect(asked()).toBe(36);
});

// R-0637
test("a message 6 minutes after the coach's last reply gets the coach's reply alone, with the message box open", async ({
  page,
}) => {
  // the coach's last reply was done 6 minutes ago, so the switch turned itself
  // off a minute ago, though the switch still reads on
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
  // R-0636
  await expect(page.locator("#composer")).toHaveText("");
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
  test("after a reload with the vote open the coach's own text is hidden and each reply shows once", async ({
    page,
  }) => {
    const open = VOTED.map((p) => ({ ...p, choice: null }));
    await voted(page, open as typeof VOTED, true);
    await page.goto("/app/");
    const bubble = page.locator(".bub.coach.fb").last();
    await expect(bubble.locator(".vt-reply")).toHaveCount(3);
    await expect(bubble.locator(":scope > .words")).toBeHidden();
    const seen = await bubble.innerText();
    for (const reply of REPLIES) expect(seen.split(reply.text.slice(0, 30)).length - 1).toBe(1);
    const shown = await bubble.evaluate((e) => {
      const own = [...e.childNodes].filter((n) => n.nodeType === Node.TEXT_NODE && n.textContent!.trim());
      return own.length;
    });
    expect(shown).toBe(0);
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

// a family whose thread is long enough to scroll well past the vote
test.describe("the vote read with a thumb", () => {
  test.use({ storageState: stateFor("hostile"), hasTouch: true });

  // R-0636
  test("a drag up and down on the open vote at the foot of the thread leaves the picture as it is until the finger lifts, and nothing jumps under the thumb", async ({
    page,
    context,
  }) => {
    await page.addInitScript(() => localStorage.setItem("fd-home-screen-asked", String(Date.now())));
    await serve(page);
    await page.goto("/app/");
    await expect(page.locator(".bub").first()).toBeVisible();
    await page.locator("#composer").fill("My dad called last night about mom's care.");
    await page.locator("#send").click();
    const bubble = page.locator(".bub.coach").last();
    await expect(bubble.locator(".vt-reply")).toHaveCount(3);
    await page.waitForTimeout(1000);
    await bubble.evaluate((voting) => {
      const seen = { folds: 0, ys: [] as number[] };
      Object.assign(window, { seen });
      new MutationObserver(() => seen.folds++).observe(document.querySelector("#chat-screen")!, {
        attributes: true,
        attributeFilter: ["class"],
      });
      const tick = () => {
        seen.ys.push(voting.getBoundingClientRect().y);
        requestAnimationFrame(tick);
      };
      tick();
    });
    const cdp = await context.newCDPSession(page);
    let y = 560;
    const touch = (type: string) =>
      cdp.send("Input.dispatchTouchEvent", { type, touchPoints: type === "touchEnd" ? [] : [{ x: 150, y }] });
    await touch("touchStart");
    // up from the foot of the thread, back down to it, and up again, twice
    for (const way of [1, -1, 1, -1])
      for (let i = 0; i < 40; i++) {
        y += way * 6;
        await touch("touchMove");
        await page.waitForTimeout(16);
      }
    const seen = await page.evaluate(() => (window as unknown as { seen: { folds: number; ys: number[] } }).seen);
    await touch("touchEnd");
    expect(seen.folds).toBe(0);
    const jumps = seen.ys.slice(1).map((at, i) => Math.abs(at - seen.ys[i]));
    expect(Math.max(...jumps)).toBeLessThan(10);
  });
});
