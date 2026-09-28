import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";
import { mockTurn, SEND } from "./turn";

/** A question the coach asked is an amber chip that goes into the message box
 * as a reference to where it was asked (R-0587), and each chip tapped into the
 * message box comes with the words Patrick gave it, which the reader may still
 * change before sending (R-0586). */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(400);
};

const composer = (page: Page) => page.locator("#composer");

/** The words before the chip in the message box, and the chip's reference. */
const drafted = (page: Page) =>
  composer(page).evaluate((box) => {
    const chip = box.querySelector<HTMLElement>(".chip")!;
    return {
      before: [...box.childNodes].slice(0, [...box.childNodes].indexOf(chip)).map((n) => n.textContent).join(""),
      kind: chip.dataset.kind,
      target: chip.dataset.target,
      tone: chip.classList.contains("ask") ? "amber" : "teal",
    };
  });

/** What the page posts when the reader sends; the send goes no further. */
const sent = async (page: Page) => {
  await page.route(SEND, (route) => route.abort());
  const [request] = await Promise.all([page.waitForRequest(SEND), page.locator("#send").click()]);
  return (request.postDataJSON() as { statement: string }).statement;
};

/** The chip's colour is the amber of the question it replaces. */
const amber = (chip: ReturnType<Page["locator"]>) =>
  chip.evaluate((c) => {
    const probe = document.createElement("span");
    probe.style.color = "var(--ask-text)";
    document.body.append(probe);
    const want = getComputedStyle(probe).color;
    probe.remove();
    return getComputedStyle(c).color === want && c.classList.contains("ask");
  });

test.describe("the question that closes a coach reply", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0587, R-0586
  test("is an amber chip that goes into the message box after its words, and is sent as a reference to its message", async ({ page }) => {
    await mockTurn(page, { statement: "Ada moved toward Ben. Who did you turn to then?", statement_id: 9501 });
    await settle(page);
    await composer(page).fill("Tell me more.");
    await page.locator("#send").click();
    const chip = page.locator('.bub.coach[data-statement="9501"] > .ask .chip');
    await expect(chip).toHaveText("Who did you turn to then?");
    expect(await amber(chip)).toBe(true);
    await chip.click();
    expect(await drafted(page)).toEqual({ before: "To answer your question ", kind: "message", target: "9501", tone: "amber" });
    expect(await sent(page)).toBe("To answer your question [[message:9501|Who did you turn to then?]]");
  });
});

test.describe("the play-by-play's question", () => {
  test.use({ storageState: stateFor("whitlock") });

  // R-0587, R-0586
  test("is an amber chip that closes the drawer and goes into the message box as a reference to the play", async ({ page }) => {
    await settle(page);
    const play = page.locator(".bub.coach[data-play]").last();
    const id = await play.getAttribute("data-statement");
    await play.click();
    const drawer = page.locator("#pbp");
    await drawer.locator('[data-act="dot"]').last().click();
    const chip = drawer.locator(".ask .chip");
    await expect(chip).toHaveText("Theo started day care that autumn. Who was looking after the two of you?");
    expect(await amber(chip)).toBe(true);
    await chip.click();
    await expect(drawer).toBeHidden();
    expect(await drafted(page)).toEqual({ before: "To answer your question ", kind: "message", target: id, tone: "amber" });
    expect(await sent(page)).toBe(
      `To answer your question [[message:${id}|Theo started day care that autumn. Who was looking after the two of you?]]`,
    );
  });
});

test.describe("a question on the list of what the coach asked", () => {
  test.use({ storageState: stateFor("moves") });

  const asked = (kind: string, id: string, text: string) => ({
    id, text, kind, open: true, asked_at: "2026-09-20", asked_in: null, evidence: [], pushback: null,
  });

  const tapFrom = async (page: Page, kind: string, text: string) => {
    await page.route(/\/app\/timeline$/, async (route) => {
      const tl = await (await route.fetch()).json();
      tl.asked_questions = [asked(kind, "q901", text)];
      await route.fulfill({ json: tl });
    });
    await settle(page);
    await page.locator("#menu-open").click();
    await page.locator("#tab-questions").click();
    await page.locator(".qrow .chip").filter({ hasText: text }).click();
  };

  // R-0586
  test("from food for thought goes in after \"About your question\"", async ({ page }) => {
    await tapFrom(page, "thought", "What did Ada want from Ben?");
    expect(await drafted(page)).toEqual({ before: "About your question ", kind: "question", target: "q901", tone: "amber" });
  });

  // R-0586
  test("from facts to find goes in after \"Here's what I know about\"", async ({ page }) => {
    await tapFrom(page, "fact", "When did Cal leave home?");
    expect(await drafted(page)).toEqual({ before: "Here's what I know about ", kind: "question", target: "q901", tone: "amber" });
  });
});

test.describe("the ask under the timeline", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0586
  test("puts a teal chip in the message box after \"I want to ask about\"", async ({ page }) => {
    await settle(page);
    await page.locator("#cap-chip").click();
    const got = await drafted(page);
    expect(got.before).toBe("I want to ask about ");
    expect(got.tone).toBe("teal");
  });
});
