import { expect, test } from "@playwright/test";
import { stateFor } from "./setup";
import { mockTurn } from "./turn";

/** Chips have to stay inside their bubble whatever the record calls things, and
 * the play-by-play has to light each chip as its move is drawn. A reply ends in
 * offered chips [Oracle: R-0074], and a chip is the primitive a reference is
 * drawn as in both speakers' messages [Oracle: R-0072]. */

test.describe("chips in a bubble", () => {
  test.use({ storageState: stateFor("hostile") });

  // R-0169, R-0072
  test("twelve long chips wrap inside the bubble", async ({ page }) => {
    await page.goto("/app/");
    await expect(page.locator(".bub").first()).toBeVisible();
    await page.waitForTimeout(400);
    const bubble = page.locator(".bub").filter({ hasText: "Twelve of them" });
    await bubble.scrollIntoViewIfNeeded();
    await expect(bubble).toHaveScreenshot("twelve-chips.png");
  });

  // R-0169
  test("no chip anywhere reaches past the edge of its bubble", async ({ page }) => {
    await page.goto("/app/");
    await expect(page.locator(".bub").first()).toBeVisible();
    await page.waitForTimeout(400);
    const escaped = await page.evaluate(() =>
      [...document.querySelectorAll(".bub")].flatMap((bubble) => {
        const box = bubble.getBoundingClientRect();
        return [...bubble.querySelectorAll(".chip")]
          .filter((chip) => {
            const at = chip.getBoundingClientRect();
            return at.right > box.right + 1 || at.left < box.left - 1;
          })
          .map((chip) => chip.textContent ?? "");
      }),
    );
    expect(escaped).toEqual([]);
  });

  // R-0169
  test("every chip shows its whole label, at one size", async ({ page }) => {
    await page.goto("/app/");
    await expect(page.locator(".bub").first()).toBeVisible();
    await page.waitForTimeout(400);
    // The owner ruled out the two-tap expand: labels are capped at the source,
    // so a chip is never cut and never has a second state to discover.
    const cut = await page.evaluate(() =>
      [...document.querySelectorAll(".bub .chip")]
        .filter((c) => {
          const words = c.textContent ?? "";
          // a chip wraps onto more lines rather than being cut, so what marks
          // a cut is the ellipsis and the label not matching what it names
          return /…/.test(words) || words.replace(/^\[|\]$/g, "") !== (c.getAttribute("data-full") ?? words);
        })
        .map((c) => c.textContent),
    );
    expect(cut).toEqual([]);
    expect(await page.locator(".bub .chip.clip").count()).toBe(0);
  });
});

test.describe("the question that closes a reply", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0358, R-0291
  test("it stands apart in amber", async ({ page }) => {
    await page.goto("/app/");
    await expect(page.locator(".bub").first()).toBeVisible();
    await page.waitForTimeout(400);
    const bubble = page.locator(".bub.coach").last();
    await expect(bubble.locator("> .ask")).toHaveText(
      "What do you remember about the winter it started?",
    );
    // offered answers are no longer written (Patrick, 2026-09-21); an old
    // transcript's run of them is still laid out under the question
    await expect(bubble.locator("> .offer .chip.ask")).toHaveCount(3);
    // the question is lifted out of the narration, not repeated in it
    expect(await bubble.locator("> .ask").evaluate((n) => getComputedStyle(n).fontWeight)).toBe("500");
  });
});

test.describe("the message box", () => {
  test.use({ storageState: stateFor("moves") });

  /** Type two lines with Return between them; the bubbles there were before,
   * and what was POSTed meanwhile. */
  const twoLines = async (page: import("@playwright/test").Page) => {
    await page.goto("/app/");
    await expect(page.locator(".bub").first()).toBeVisible();
    const bubbles = await page.locator(".bub").count();
    const posts: string[] = [];
    page.on("request", (r) => r.method() === "POST" && posts.push(r.url()));
    await page.locator("#composer").click();
    await page.keyboard.type("first");
    await page.keyboard.press("Enter");
    await page.keyboard.type("second");
    await page.waitForTimeout(400);
    return { bubbles, posts };
  };

  // R-0368
  test("Return sends nothing; only the send button sends", async ({ page }) => {
    const { bubbles, posts } = await twoLines(page);
    expect(posts.filter((u) => !/telemetry|collect|events/.test(u))).toEqual([]);
    await expect(page.locator(".bub")).toHaveCount(bubbles);
  });

  // R-0368
  test("Return starts a new line in the message", async ({ page }) => {
    await twoLines(page);
    // the message is sent trimmed, so a newline held open at the end is not part of it
    expect(
      await page.locator("#composer").evaluate((n) => n.textContent!.trimEnd()),
    ).toBe("first\nsecond");
    const [top, bottom] = await page.locator("#composer").evaluate((n) => {
      const texts = [...n.childNodes].filter((c): c is Text => c instanceof Text);
      const top = (word: string) => {
        const text = texts.find((t) => t.data.includes(word))!;
        const range = document.createRange();
        range.setStart(text, text.data.indexOf(word));
        range.setEnd(text, text.data.indexOf(word) + word.length);
        return range.getBoundingClientRect().top;
      };
      return [top("first"), top("second")];
    });
    expect(bottom).toBeGreaterThan(top);
  });
});

test.describe("the question's colour", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0358
  test("the closing question is drawn in the amber the app asks in, apart from the narration", async ({
    page,
  }) => {
    await page.goto("/app/");
    await expect(page.locator(".bub").first()).toBeVisible();
    const bubble = page.locator(".bub.coach").last();
    await expect(bubble.locator("> .ask")).toBeVisible();
    const look = await bubble.evaluate((b) => {
      const probe = document.createElement("span");
      probe.style.color = "var(--ask-text)";
      document.body.append(probe);
      const amber = getComputedStyle(probe).color;
      probe.remove();
      return {
        amber,
        ask: getComputedStyle(b.querySelector(":scope > .ask")!).color,
        words: getComputedStyle(b).color,
      };
    });
    expect(look.ask).toBe(look.amber);
    expect(look.ask).not.toBe(look.words);
  });
});

/** How far the newest bubble's foot is below the bottom edge of the thread;
 * zero or less is in view. */
const below = (page: import("@playwright/test").Page) =>
  page.evaluate(() => {
    const thread = document.getElementById("chat")!;
    const bubbles = thread.querySelectorAll(".bub");
    const last = bubbles[bubbles.length - 1].getBoundingClientRect();
    return last.bottom - thread.getBoundingClientRect().bottom;
  });

test.describe("the thread's place while the coach answers", () => {
  test.use({ storageState: stateFor("hostile") });

  const start = async (page: import("@playwright/test").Page) => {
    await page.goto("/app/");
    await expect(page.locator(".bub").first()).toBeVisible();
    await page.waitForTimeout(1200);
    expect(
      await page.locator("#chat").evaluate((t) => t.scrollHeight > t.clientHeight * 2),
    ).toBe(true);
  };

  // R-0172
  test("the waiting bubble stays in view at the foot of the thread", async ({ page }) => {
    await start(page);
    let answer: () => void = () => {};
    const held = new Promise<void>((go) => (answer = go));
    await mockTurn(page, { statement: "Noted.", statement_id: 9301, hold: held });
    await page.locator("#composer").fill("My dad moved out.");
    await page.locator("#send").click();
    await expect(page.locator(".bub.coach.typing")).toBeVisible();
    await page.waitForTimeout(300);
    expect(await below(page)).toBeLessThanOrEqual(1);
    answer();
  });

  // R-0172
  test("a long reply keeps its newest words in view as they are typed", async ({ page }) => {
    await start(page);
    const long = "This is one more sentence the coach is saying. ".repeat(40).trim();
    await mockTurn(page, { statement: long, statement_id: 9302 });
    await page.locator("#composer").fill("Tell me more.");
    await page.locator("#send").click();
    await expect(page.locator(".bub.coach").last()).toContainText("one more sentence");
    const samples: number[] = [];
    for (let i = 0; i < 8; i++) {
      samples.push(await below(page));
      await page.waitForTimeout(150);
    }
    await expect(page.locator(".bub.coach").last()).toContainText(long, { timeout: 20000 });
    await page.waitForTimeout(300);
    samples.push(await below(page));
    expect(samples.filter((gap) => gap > 1)).toEqual([]);
  });
});

test.describe("a thread reopened", () => {
  test.use({ storageState: stateFor("hostile") });

  // R-0231
  test("opens on the newest words, at the very bottom", async ({ page }) => {
    await page.goto("/app/");
    await expect(page.locator(".bub").first()).toBeVisible();
    await page.waitForTimeout(1500);
    const rest = await page.locator("#chat").evaluate((t) => t.scrollHeight - t.clientHeight - t.scrollTop);
    expect(rest).toBeLessThanOrEqual(1);
    expect(await below(page)).toBeLessThanOrEqual(1);
  });
});

test.describe("an empty session", () => {
  test.use({ storageState: stateFor("empty") });

  const help = (page: import("@playwright/test").Page) => page.locator("#chat .cta");

  // R-0350
  test("shows help where the bubbles will be, saying what to type", async ({ page }) => {
    await page.goto("/app/");
    await expect(help(page)).toBeVisible();
    await expect(page.locator("#chat .bub")).toHaveCount(0);
    await expect(help(page).locator(".cta-t")).not.toBeEmpty();
    const lines = await help(page).locator(".cta-p").allTextContents();
    expect(lines.length).toBeGreaterThan(0);
    // a call to action: it tells the reader what to write
    expect(lines.join(" ")).toMatch(/\b(start with|tell|say|talk)\b/i);
  });

  // R-0350
  test("the help goes on the first send", async ({ page }) => {
    await page.goto("/app/");
    await expect(help(page)).toBeVisible();
    await mockTurn(page, { statement: "Who is on your mind?", statement_id: 9401 });
    await page.locator("#composer").fill("My sister.");
    await page.locator("#send").click();
    await expect(page.locator("#chat .bub.user")).toHaveText("My sister.");
    await expect(help(page)).toHaveCount(0);
  });

  // R-0350
  test("a note says what a note is for, in words of its own", async ({ page }) => {
    await page.goto("/app/");
    await expect(help(page)).toBeVisible();
    const chatHelp = await help(page).innerText();
    // only a professional may start a note, which no fixture holds, so the
    // server's answer is the one a professional would get
    const NOTE = 99001;
    await page.route(/\/app\/sessions$/, (route) =>
      route.request().method() === "POST"
        ? route.fulfill({
            status: 201,
            json: {
              id: NOTE, title: null, kind: "note", date: null, title_set_by_user: false,
              summary: null, preview: null, last_activity: new Date().toISOString(),
              message_count: 0, turn: null,
            },
          })
        : route.fallback(),
    );
    await page.route(new RegExp(`/app/sessions/${NOTE}$`), (route) =>
      route.fulfill({ json: { id: NOTE, kind: "note", statements: [] } }),
    );
    await page.locator("#sessions-open").click();
    await expect(page.locator("#sessions-sheet")).toBeVisible();
    // the note button shows only for a professional licence, which no fixture holds
    const button = page.locator("#sessions-sheet .fs-note");
    await button.evaluate((b) => ((b as HTMLElement).hidden = false));
    await button.click();
    await expect(help(page)).toBeVisible();
    await expect(help(page)).not.toHaveText(chatHelp);
    // what a note is for: writing up a session that already happened
    await expect(help(page)).toContainText(/session you just had|write up/i);
  });
});
