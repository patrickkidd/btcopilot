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

async function serve(page: Page): Promise<Record<string, unknown>[]> {
  const cast: Record<string, unknown>[] = [];
  await page.route(/\/app\/preferences$/, async (route: Route) => {
    const answer = await route.fetch();
    const prefs = await answer.json();
    await route.fulfill({ json: { ...prefs, shadow_models: ["sonnet", "gemini-pro"] } });
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

// R-0636
test("three replies are voted on unnamed, then the coach's is headed Coach with the others folded", async ({
  page,
}) => {
  const cast = await serve(page);
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.locator("#composer").fill("My dad called last night about mom's care.");
  await page.locator("#send").click();

  await expect(page.locator(".bub.coach .vt-wait")).toHaveText("Waiting for shadow replies");
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
