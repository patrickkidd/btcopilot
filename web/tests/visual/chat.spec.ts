import { expect, test } from "@playwright/test";
import { boxOf, inside, stateFor } from "./setup";
import { mockTurn, SEND, STREAM } from "./turn";

/** Chips have to stay inside their bubble whatever the record calls things, and
 * the play-by-play has to light each chip as its move is drawn. A reply ends in
 * offered chips [Oracle: R-0074], and a chip is the primitive a reference is
 * drawn as in both speakers' messages [Oracle: R-0072]. */

test.describe("chips in a bubble", () => {
  test.use({ storageState: stateFor("hostile") });

  // R-0654, R-0072
  test("twelve long chips wrap inside the bubble", async ({ page }) => {
    await page.goto("/app/");
    await expect(page.locator(".bub").first()).toBeVisible();
    await page.waitForTimeout(400);
    const bubble = page.locator(".bub").filter({ hasText: "Twelve of them" });
    await bubble.scrollIntoViewIfNeeded();
    await expect(bubble).toHaveScreenshot("twelve-chips.png");
  });

  // R-0654
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

  // R-0654
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

test.describe("the message box on a touch screen", () => {
  test.use({ storageState: stateFor("moves"), hasTouch: true });

  /** Type two lines with Return between them; the bubbles there were before,
   * and what was POSTed meanwhile. */
  const twoLines = async (page: import("@playwright/test").Page) => {
    // a phone that already answered the add-to-home-screen card
    await page.addInitScript(() => localStorage.setItem("fd-home-screen-asked", String(Date.now())));
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

  // R-0610
  test("Return sends nothing; only the send button sends", async ({ page }) => {
    const { bubbles, posts } = await twoLines(page);
    expect(posts.filter((u) => !/telemetry|collect|events/.test(u))).toEqual([]);
    await expect(page.locator(".bub")).toHaveCount(bubbles);
  });

  // R-0610
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

  // R-0636
  test("the coach bubble shows the three moving dots, not a blinking bar, before the reply streams", async ({
    page,
  }) => {
    await start(page);
    let answer: () => void = () => {};
    const held = new Promise<void>((go) => (answer = go));
    await mockTurn(page, { statement: "Noted.", statement_id: 9303, hold: held });
    await page.locator("#composer").fill("My dad moved out.");
    await page.locator("#send").click();
    const wait = page.locator(".bub.coach.typing");
    await expect(wait).toBeVisible();
    const motion = await wait.evaluate((b) => getComputedStyle(b, "::after").animationName);
    expect(motion).toBe("think");
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

  test.describe("read with a thumb", () => {
    test.use({ hasTouch: true });

    // R-0636
    test("a drag of 300px up the thread folds the picture at most once and no bubble jumps under the thumb", async ({
      page,
      context,
    }) => {
      await page.addInitScript(() => localStorage.setItem("fd-home-screen-asked", String(Date.now())));
      await page.goto("/app/");
      await expect(page.locator(".bub").first()).toBeVisible();
      await page.waitForTimeout(1500);
      await page.evaluate(() => {
        const screen = document.querySelector("#chat-screen")!;
        const bubble = document.querySelectorAll("#chat .bub")[document.querySelectorAll("#chat .bub").length - 3];
        const seen = { folds: 0, ys: [] as number[] };
        Object.assign(window, { seen });
        new MutationObserver(() => seen.folds++).observe(screen, { attributes: true, attributeFilter: ["class"] });
        const tick = () => {
          seen.ys.push(bubble.getBoundingClientRect().y);
          requestAnimationFrame(tick);
        };
        tick();
      });
      const cdp = await context.newCDPSession(page);
      const touch = (type: string, y: number) =>
        cdp.send("Input.dispatchTouchEvent", { type, touchPoints: type === "touchEnd" ? [] : [{ x: 200, y }] });
      await touch("touchStart", 250);
      for (let i = 1; i <= 50; i++) {
        await touch("touchMove", 250 + i * 6);
        await page.waitForTimeout(16);
      }
      await touch("touchEnd", 550);
      await page.waitForTimeout(600);
      const seen = await page.evaluate(
        () => (window as unknown as { seen: { folds: number; ys: number[] } }).seen,
      );
      expect(seen.folds).toBeLessThanOrEqual(1);
      const jumps = seen.ys.slice(1).map((y, i) => Math.abs(y - seen.ys[i]));
      expect(Math.max(...jumps)).toBeLessThan(20);
    });
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
    const note = {
      id: 99001, title: null, kind: "note", date: null, title_set_by_user: false,
      summary: null, preview: null, last_activity: new Date().toISOString(),
      message_count: 0, turn: null,
    };
    // once made, the note heads the family's sessions, as the server lists it
    let made = false;
    await page.route(/\/app\/sessions(\?diagram_id=\d+)?$/, async (route) => {
      if (route.request().method() === "POST") {
        made = true;
        return route.fulfill({ status: 201, json: note });
      }
      const real = await (await route.fetch()).json();
      return route.fulfill({ json: made ? [note, ...real] : real });
    });
    // the door, like the note button, shows only for a professional
    await page.locator("#sessions-open").evaluate((b) => ((b as HTMLElement).hidden = false));
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

test.describe("the coach's notes", () => {
  test.use({ storageState: stateFor("moves") });

  const noted = {
    statement: "I put that down.",
    statement_id: 9301,
    did: [
      {
        type: "tool_call",
        name: "coach_notes",
        args: {
          register: "coaching",
          lane: "the move",
          why: "to hear more",
          holding: "none",
          plateau: { reached: false, biggest_gap: "dates" },
          hunch: "she pulled back",
          person: "calm",
          variable: "anxiety",
        },
      },
      {
        type: "tool_call",
        name: "edit_event",
        args: { description: "she stopped calling her mother every Sunday", dateTime: "1992-04-01" },
        names: { it: "she stopped calling her mother every Sunday" },
      },
    ],
  };

  // R-0520, R-0317
  test("the (i), the tool line and the cross stay inside their boxes", async ({ page }) => {
    await page.goto("/app/");
    await expect(page.locator("#view .ss")).toBeVisible();
    await mockTurn(page, noted);
    await page.locator("#composer").fill("She stopped calling.");
    await page.locator("#send").click();
    const bubble = page.locator(".bub.coach").last();
    await expect(bubble.locator(":scope > .info")).toBeVisible();
    await inside(bubble.locator(":scope > .info"), bubble);
    await inside(bubble.locator(".did"), bubble);
    await bubble.locator(":scope > .info").click();
    await inside(page.locator(".notes-head > .cardx"), page.locator(".notes-head"));
  });
});

test.describe("the message box while the coach replies", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0636, R-0674
  test("a message sent during a reply waits in the box and goes after Done", async ({ page }) => {
    await page.goto("/app/");
    await expect(page.locator("#view .ss")).toBeVisible();
    let answer: () => void = () => {};
    const held = new Promise<void>((go) => (answer = go));
    await mockTurn(page, { statement: "Noted.", statement_id: 9301, hold: held });
    const sent: string[] = [];
    page.on("request", (r) => {
      if (SEND.test(r.url()) && r.method() === "POST") sent.push(r.postDataJSON().statement);
    });
    await page.locator("#composer").fill("My dad moved out.");
    await page.locator("#send").click();
    await expect(page.locator(".bub.coach.typing")).toBeVisible();
    await expect(page.locator("#send")).toHaveAttribute("aria-label", "Stop");

    await page.locator("#composer").fill("He took the dog.");
    await expect(page.locator("#send")).toHaveAttribute("aria-label", "Send");
    await page.locator("#composer").press("Enter");
    await expect(page.locator("#composer")).toHaveText("He took the dog.");
    await expect(page.locator(".field > .held")).toHaveText("Sends when the coach finishes");
    await expect(page.locator("#send")).toHaveAttribute("aria-label", "Stop");
    expect(sent).toEqual(["My dad moved out."]);

    answer();
    await expect(page.locator(".bub.user").last()).toHaveText("He took the dog.");
    expect(sent).toEqual(["My dad moved out.", "He took the dog."]);
    await expect(page.locator(".field > .held")).toBeHidden();
  });

  // R-0636
  test("a Stop that arrives after the reply has ended leaves the reply and says nothing", async ({ page }) => {
    await page.goto("/app/");
    await expect(page.locator("#view .ss")).toBeVisible();
    let answer: () => void = () => {};
    const held = new Promise<void>((go) => (answer = go));
    await mockTurn(page, { statement: "Noted.", statement_id: 9305, hold: held });
    await page.route(/\/app\/turns\/[^/]+\/stop$/, async (route) => {
      answer();
      await expect(page.locator(".bub.coach:not(.typing)").last()).toContainText("Noted.");
      await route.fulfill({ status: 409, body: "turn t1 is not running" });
    });
    await page.locator("#composer").fill("My dad moved out.");
    await page.locator("#send").click();
    await expect(page.locator(".bub.coach.typing")).toBeVisible();
    const refused = page.waitForResponse(/\/stop$/);
    await page.locator("#send").click();
    await refused;
    // a notice goes by itself after a moment, so it is looked for once, now
    await page.waitForTimeout(200);
    expect(await page.locator(".toast").count()).toBe(0);
    await expect(page.locator(".bub.coach").last()).toContainText("Noted.");
    await expect(page.locator("#chat .sys")).toHaveCount(0);
    await expect(page.locator("#send")).toHaveAttribute("aria-label", "Send");
  });

  // R-0636, R-0674
  test("a stopped turn that added a person leaves no reply, and the person is gone from the picture", async ({
    page,
  }) => {
    // what the turn put in the record, until it is stopped and takes it back
    let added = false;
    await page.route("**/app/timeline*", async (route) => {
      const response = await route.fetch();
      const json = await response.json();
      if (added) {
        json.people.push({ ...json.people[0], id: 901, name: "Nell" });
        json.events.push({ ...json.events[0], id: 9901, person: 901, person_name: "Nell", label: "Nell was born" });
      }
      await route.fulfill({ response, json });
    });
    await page.goto("/app/");
    await expect(page.locator("#view .ss")).toBeVisible();
    const dot = page.locator('#view circle.dot[data-event="9901"]');
    await expect(dot).toHaveCount(0);

    await page.route(SEND, (route) => {
      added = true;
      return route.fulfill({ status: 202, json: { turn_id: "t1", discussion_id: 1, statement_id: 9300 } });
    });
    let stopped = false;
    await page.route(/\/app\/turns\/t1\/stop$/, (route) => {
      stopped = true;
      added = false;
      return route.fulfill({ json: { turn_id: "t1" } });
    });
    const events = [
      { type: "tool_call", name: "edit_person", args: { name: "Nell" }, names: { it: "Nell" }, refusal: null },
      {
        type: "record_patch",
        deltas: [{ item_kind: "person", item_id: "901", field: null, before: null, after: { id: 901 } }],
        turn_id: "t1",
      },
      { type: "text", text: "I added" },
      {
        type: "done",
        stopped: true,
        version: 7,
        statement: null,
        statement_id: 9300,
        discussion_id: 1,
        kind: "turn",
        views: [],
        events: [],
        turn_id: "t1",
      },
    ];
    // what the turn did, then nothing until the stop; the browser comes back
    // every 100ms saying where it got to
    await page.route(STREAM, (route) => {
      const last = Number(route.request().headers()["last-event-id"] ?? 0);
      return route.fulfill({
        status: 200,
        headers: { "content-type": "text/event-stream", "cache-control": "no-cache" },
        body:
          "retry: 100\n\n" +
          events
            .slice(last, stopped ? 4 : 3)
            .map((event, at) => `id: ${last + at + 1}\ndata: ${JSON.stringify(event)}\n\n`)
            .join(""),
      });
    });
    await page.locator("#composer").fill("My sister is Nell.");
    await page.locator("#send").click();
    await expect(page.locator(".bub.coach.typing .words")).toHaveText("I added");
    await expect(dot).toHaveCount(1);
    await expect(page.locator("#send")).toHaveAttribute("aria-label", "Stop");

    await page.locator("#send").click();
    await expect(page.locator("#chat > :last-child")).toHaveText("Stopped");
    await expect(page.locator("#chat > :last-child")).toHaveClass("sys");
    // in a thread longer than its box the line keeps its height
    await page.setViewportSize({ width: 390, height: 520 });
    expect(await page.locator("#chat").evaluate((t) => t.scrollHeight > t.clientHeight)).toBe(true);
    expect((await boxOf(page.locator("#chat > :last-child"))).height).toBeGreaterThan(12);
    await expect(page.locator(".bub.coach.typing")).toHaveCount(0);
    await expect(dot).toHaveCount(0);
    await expect(page.locator("#send")).toHaveAttribute("aria-label", "Send");
    await expect(page.locator(".vt-wait")).toHaveCount(0);
  });

  // R-0636
  test("the grey line under a stopped turn's words is still there after a reload", async ({ page }) => {
    // two turns the reader stopped, the second with edits that stayed, in the
    // thread the server hands the page as it opens, which is what a reload
    // reads, and in the thread the page reads again once it is shown: left out
    // of that one, the two are drawn and then wiped when it comes back
    const stops = (statements: Record<string, unknown>[]) => {
      const words = statements.find((s) => s.role === "user");
      const ended = { ...words, sitting: undefined, tools: [], feedback: 0, stopped: true };
      statements.push(
        { ...ended, id: 9401, turn_id: "s1", text: "My sister is Nell.", conflict: null },
        { ...ended, id: 9402, turn_id: "s2", text: "My brother is Finn.", conflict: "Finn was renamed since" },
      );
    };
    await page.addInitScript(`
      Object.defineProperty(window, "BOOTSTRAP", {
        configurable: true,
        set(boot) {
          (${stops})(boot.statements);
          Object.defineProperty(window, "BOOTSTRAP", { value: boot, writable: true });
        },
      });
    `);
    await page.route(/\/app\/statements\?diagram_id=\d+$/, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      const response = await route.fetch();
      const json = await response.json();
      stops(json);
      await route.fulfill({ response, json });
    });
    const read = page.waitForResponse(/\/app\/statements\?diagram_id=\d+$/);
    await page.goto("/app/");
    await expect(page.locator("#view .ss")).toBeVisible();
    await read;

    const lines = page.locator("#chat .bub.user + .sys");
    await expect(lines).toHaveText(["Stopped", "Stopped; its changes stayed"]);
    await expect(page.locator("#chat > :last-child")).toHaveText("Stopped; its changes stayed");
    expect((await boxOf(lines.first())).height).toBeGreaterThan(12);
    await expect(page.locator("#send")).toHaveAttribute("aria-label", "Send");
    // a read still on its way when the test ends is not a failure
    await page.unrouteAll({ behavior: "ignoreErrors" });
  });
});
