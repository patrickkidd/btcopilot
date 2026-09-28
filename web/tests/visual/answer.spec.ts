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

/** What Patrick saw on his iPhone after tapping the play-by-play's question:
 * the keyboard came up over the chat box, the chip filled the box, and a tap
 * meant for just after it took it out again (R-0586, R-0587). */
test.describe("the chat box once a chip is in it", () => {
  test.use({ storageState: stateFor("whitlock") });

  /** iOS brings the keyboard up without shrinking the page: only the part of
   * the screen the reader can see shrinks, and iOS may pan it. This stands in
   * for that, so a spec can put the keyboard up and move it. */
  const phone = (page: Page) =>
    page.addInitScript(() => {
      const seen = Object.assign(new EventTarget(), {
        width: window.innerWidth,
        height: window.innerHeight,
        offsetTop: 0,
        offsetLeft: 0,
        pageTop: 0,
        pageLeft: 0,
        scale: 1,
      });
      Object.defineProperty(window, "visualViewport", { value: seen });
    });

  /** The keyboard over the lower part of the screen, the visible part panned
   * down by `pan`, and where the chat box and the question's words then sit. */
  const keyboard = (page: Page, height: number, pan = 0) =>
    page.evaluate(
      ([height, pan]) => {
        const seen = window.visualViewport as unknown as Record<string, number> & EventTarget;
        seen.height = height;
        seen.offsetTop = pan;
        seen.pageTop = pan;
        seen.dispatchEvent(new Event("resize"));
        seen.dispatchEvent(new Event("scroll"));
        return new Promise<{ top: number; bottom: number; box: DOMRect }>((done) =>
          requestAnimationFrame(() =>
            done({
              top: pan,
              bottom: pan + height,
              box: document.querySelector(".field")!.getBoundingClientRect().toJSON(),
            }),
          ),
        );
      },
      [height, pan],
    );

  const question = "Theo started day care that autumn. Who was looking after the two of you?";

  const tapQuestion = async (page: Page) => {
    await settle(page);
    const play = page.locator(".bub.coach[data-play]").last();
    await play.click();
    await page.locator("#pbp").locator('[data-act="dot"]').last().click();
    await page.locator("#pbp .ask .chip").click();
    await expect(page.locator("#pbp")).toBeHidden();
    return composer(page).locator(".chip");
  };

  // R-0587, R-0586
  test("stays in view above the keyboard after the question goes in, even when iOS pans the screen", async ({ page }) => {
    await phone(page);
    await tapQuestion(page);
    for (const pan of [0, 180]) {
      const at = await keyboard(page, 464, pan);
      expect(at.box.bottom).toBeLessThanOrEqual(at.bottom);
      expect(at.box.top).toBeGreaterThanOrEqual(at.top);
    }
    // the thread shrinks with it and stays on the newest words
    const last = await page.locator(".chat > .bub").last().boundingBox();
    const thread = await page.locator("#chat").boundingBox();
    expect(last!.y + last!.height).toBeLessThanOrEqual(thread!.y + thread!.height + 1);
  });

  // R-0368
  test("stays in view above the keyboard when it opens from a tap in the chat box", async ({ page }) => {
    await phone(page);
    await settle(page);
    await composer(page).click();
    const at = await keyboard(page, 464);
    expect(at.box.bottom).toBeLessThanOrEqual(at.bottom);
    expect(at.box.top).toBeGreaterThanOrEqual(at.top);
  });

  // R-0587, R-0586
  test("keeps the question's chip compact, cut with an ellipsis, and sends its whole words", async ({ page }) => {
    const chip = await tapQuestion(page);
    const [width, field] = await Promise.all([
      chip.evaluate((c) => c.getBoundingClientRect().width),
      composer(page).evaluate((c) => c.clientWidth),
    ]);
    expect(width).toBeLessThanOrEqual(field * 0.6 + 0.5);
    expect(await chip.evaluate((c) => getComputedStyle(c).textOverflow)).toBe("ellipsis");
    expect(await chip.evaluate((c) => c.scrollWidth > c.clientWidth)).toBe(true);
    expect(await sent(page)).toContain(`|${question}]]`);
  });

  // R-0587, R-0586
  test("a tap on the chip leaves it in place with the caret just after it", async ({ page }) => {
    const chip = await tapQuestion(page);
    await composer(page).evaluate((box) => {
      const range = document.createRange();
      range.setStart(box, 0);
      range.collapse(true);
      getSelection()!.removeAllRanges();
      getSelection()!.addRange(range);
    });
    await chip.click();
    await expect(chip).toHaveCount(1);
    expect(await drafted(page)).toMatchObject({ before: "To answer your question ", kind: "message" });
    const caret = await composer(page).evaluate((box) => {
      const range = getSelection()!.getRangeAt(0);
      const chip = box.querySelector(".chip")!;
      const probe = document.createRange();
      probe.setStartAfter(chip);
      return range.collapsed && range.compareBoundaryPoints(Range.START_TO_START, probe) === 0;
    });
    expect(caret).toBe(true);
    await page.keyboard.type("my aunt");
    const id = await chip.getAttribute("data-target");
    expect(await sent(page)).toBe(`To answer your question [[message:${id}|${question}]]my aunt`);
  });

  // R-0586
  test("backspace still takes the chip out", async ({ page }) => {
    const chip = await tapQuestion(page);
    await composer(page).evaluate((box) => {
      const range = document.createRange();
      range.setStartAfter(box.querySelector(".chip")!);
      range.collapse(true);
      getSelection()!.removeAllRanges();
      getSelection()!.addRange(range);
    });
    await page.keyboard.press("Backspace");
    await expect(chip).toHaveCount(0);
  });
});
