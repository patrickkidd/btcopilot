import { test, type Page } from "./fixtures";
import { need, sandboxOnly, walker } from "./sandbox";

// A coder's own sentence about a marriage and about a parent: the scribe adds
// the people and the bond, and writes what it did under the coder's words.

/** Open the coder's task from their sign-in link, on the one card or from the
 * account view; the test skips when the task on the fixture is the vote. */
async function openCoding(
  page: Page,
  invite: string,
  { say, text, visible }: ReturnType<typeof walker>,
): Promise<void> {
  await page.goto(invite, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  if (await visible("#task-screen")) {
    say(`the one card says: ${(await text("#task-body")).replace(/\s+/g, " ")}`);
    // A card with nothing to open is the vote that is waiting on Patrick;
    // the skip below is what says so, and clicking nothing gets there.
    const open = page.locator("#task-screen .addbtn").first();
    if ((await open.count()) && (await open.isEnabled())) await open.click();
    await page.waitForTimeout(2500);
  } else {
    await page.locator("#account").click();
    await page.waitForTimeout(800);
    const card = page.locator(".sn-pane.in .sn-row", { hasText: "Your coding task" });
    say(`the card says: ${(await card.innerText()).replace(/\s+/g, " ")}`);
    await card.click();
    await page.waitForTimeout(2000);
  }
  // The coder's one card is the vote once Patrick has opened it, and there is
  // no coding to do; that state is the ballot walk's, not this one's.
  test.skip(
    !(await visible("#coding-screen")),
    "the coder's task on this fixture is the vote, not a coding",
  );
}

test.describe(() => {
  sandboxOnly("coder");
  test.describe.configure({ timeout: 600_000 });

  // R-0270, R-0326, R-0940, R-0942
  test("a coder's sentence adds a person and a bond", async ({ page }, info) => {
    const w = walker(page, info);
    const { say, check, shot, text, visible, gates, changed, quiet } = w;
    const invite = need("coder");

    /** Tap a line of the frozen thread, type what it tells you happened, and
     * read back what the scribe wrote under your words. */
    const code = async (turn: number, sentence: string) => {
      await page.locator("#coding-chat .bub.line").nth(turn).click();
      await page.waitForTimeout(400);
      await page.locator("#coding-composer").click();
      await page.keyboard.type(sentence);
      say(
        `typed into the box: "${await page.locator("#coding-composer").innerText()}"` +
          ` send enabled=${await page.locator("#coding-send").isEnabled()}`,
      );
      await page.locator("#coding-send").click();
      await page.waitForTimeout(25000);
      return page.locator("#coding-chat .did").allInnerTexts();
    };

    await openCoding(page, invite, w);
    await shot("1-thread");
    check(await visible("#coding-screen"), "the coding thread opens");
    // The copy starts with the subject's name and birth from their own diagram,
    // which the coder did not code; it heads the thread above every line.
    const facts = page.locator("#coding-chat > :first-child.given");
    const head = (await facts.count()) ? await facts.innerText() : "";
    say(`the thread opens on: "${head}"`);
    check(
      /^Given: \S.*, born \S/.test(head),
      "the subject's name and birth head the thread as given",
    );

    const married = await code(6, "Marcus and Delphine married in 1970.");
    say(`after the marriage sentence: ${JSON.stringify(married.slice(-3))}`);
    check(
      married.some((l) => /Marcus & Delphine/.test(l) && /married/.test(l)),
      "a sentence about a marriage is written as a bond line",
    );

    const born = await code(7, "Corinne is the daughter of Marcus and Delphine.");
    say(`after the parent sentence: ${JSON.stringify(born.slice(-3))}`);
    check(
      born.some((l) => /Corinne/.test(l) && /Marcus & Delphine/.test(l)),
      "a sentence about a parent is written as a birth line",
    );
    check(
      (await page.locator("#coding-chat .bub.said").count()) >= 2,
      "what the coder typed is saved and attached to that line (R-0270)",
    );
    await shot("2-written");

    // A question to the scribe is answered in words, as its own row, and
    // nothing is written from it.
    const asks = page.locator("#coding-chat .did.ask");
    const before = await asks.count();
    const asked = await code(7, "Do you have a birthdate for her yet?");
    say(`after the question: ${JSON.stringify(asked.slice(-2))}`);
    check(
      (await asks.count()) > before,
      "a question gets the scribe's words as a row",
    );
    check(
      !asked.slice(-2).some((l) => /^Added/.test(l)),
      "a question writes nothing into the diagram",
    );
    await shot("3-answered");

    // Opened again, the thread picks up where the coder left off: the line
    // after the last one they coded sits at the top, or the thread is as far
    // down as it goes when that line is near the cut.
    await page.reload({ waitUntil: "networkidle" });
    await page.locator("#account").click();
    await page.waitForTimeout(800);
    await page.locator(".sn-pane.in .sn-row", { hasText: "Your coding task" }).click();
    await page.waitForTimeout(1500);
    await page.locator("#task-screen .addbtn").first().click();
    await page.waitForTimeout(2500);
    const resumed = await page.evaluate(() => {
      const list = document.querySelector<HTMLElement>("#coding-chat")!;
      const coded = new Set(
        [...list.querySelectorAll<HTMLElement>(".bub.said")].map((n) => n.dataset.turn),
      );
      const lines = [...list.querySelectorAll<HTMLElement>(".bub.line")];
      const next = lines[lines.map((l) => coded.has(l.dataset.turn)).lastIndexOf(true) + 1];
      const bottom = list.scrollTop + list.clientHeight >= list.scrollHeight - 2;
      if (!next) return bottom;
      const gap = next.getBoundingClientRect().top - list.getBoundingClientRect().top;
      return Math.abs(gap) < 4 || (gap > 0 && bottom);
    });
    check(resumed, "the thread reopens on the line after the last one coded");
    await shot("4-resumed");

    await quiet();
  });

  test.describe(() => {
    test.use({ hasTouch: true });

    // R-0949
    test("on a phone the keyboard shrinks the timeline to the strip and the message box sits on it", async ({ page }, info) => {
      test.skip(info.project.name !== "sandbox-phone", "the keyboard is a phone's");
      const w = walker(page, info);
      const { say, check, shot, quiet } = w;
      await openCoding(page, need("coder"), w);
      const size = page.viewportSize()!;
      const measure = () =>
        page.evaluate(() => {
          const height = (sel: string) => document.querySelector<HTMLElement>(sel)!.getBoundingClientRect().height;
          const bar = document.querySelector<HTMLElement>("#coding-inbar")!;
          const label = document.querySelector<HTMLElement>("#coding-screen .pin-label")!.getBoundingClientRect();
          const pic = document.querySelector<HTMLElement>("#coding-screen .pic")!.getBoundingClientRect();
          return {
            pic: height("#coding-screen .pic"),
            lines: height("#coding-chat"),
            under: getComputedStyle(bar).paddingBottom,
            label: label.bottom > pic.top + 1,
          };
        });
      const open = await measure();
      say(`keyboard down: timeline ${open.pic}px, lines ${open.lines}px, room under the box ${open.under}`);
      await page.locator("#coding-chat .bub.line").first().click();
      await page.locator("#coding-composer").click();
      // a phone keyboard takes the lower part of the visible area
      await page.setViewportSize({ width: size.width, height: 460 });
      await page.waitForTimeout(450);
      const typing = await measure();
      say(`keyboard up: timeline ${typing.pic}px, lines ${typing.lines}px, room under the box ${typing.under}`);
      check(typing.pic >= 38 && typing.pic <= 42, "the timeline shrinks to the 40px strip");
      check(!typing.label, "the timeline's label goes with it");
      check(typing.under === "8px", "the message box sits on the keyboard with no blank band under it");
      // what the keyboard took is the room it covers; the strip gives back the rest
      check(
        typing.lines - (open.lines - (size.height - 460)) >= open.pic - typing.pic - 2,
        "the lines get the room the timeline gave up",
      );
      await shot("k1-keyboard-up");
      await page.locator("#coding-screen .pic").click({ position: { x: 8, y: 4 } });
      await page.setViewportSize(size);
      await page.waitForTimeout(450);
      const back = await measure();
      say(`strip tapped, keyboard down: timeline ${back.pic}px, focus on the box=${await page.locator("#coding-composer").evaluate((box) => box === document.activeElement)}`);
      check(back.pic === open.pic, "a tap on the strip brings the full timeline back");
      check(
        !(await page.locator("#coding-composer").evaluate((box) => box === document.activeElement)),
        "a tap on the strip puts the keyboard away",
      );
      await quiet();
    });
  });
});
