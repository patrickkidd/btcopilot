import { readFileSync } from "node:fs";
import { expect, test, type Page } from "./fixtures";
import { cutInFrame, leastName, wordsOutside } from "./gate";
import { stateFor, type Key } from "./setup";

/** The case report on the three case report fixtures at a phone's and a
 * desktop's size, in both schemes: the cards and the strip one to one, every
 * chip one line inside its card, nothing scrolling sideways, no console error;
 * and its taps: a strip item glides to its card, a chip lights the timeline,
 * a book raises its passages. Geometry and words only, no golden pictures. */

const FIXTURES: Key[] = ["case-report", "case-report-thin", "case-report-dense"];
const SIZES = [
  { width: 393, height: 852 },
  { width: 1280, height: 800 },
];
const SCHEMES = ["light", "dark"] as const;

/** The passages are private and CI has no key to the corpus, so the page is
 * answered with made-up ones for every book, keyed as the corpus keys them,
 * or with the corpus's own file when PASSAGES_FILE names it; `fail` refuses
 * that many reads first. */
const PASSAGES: Record<string, { text: string; by: string }[]> = process.env.PASSAGES_FILE
  ? JSON.parse(readFileSync(process.env.PASSAGES_FILE, "utf8"))
  : Object.fromEntries(
      ["why", "1", "2", "3", "3s", "4", "6", "7a", "9a", "10", "order"].map((book) => [book, [{ text: `A made-up passage for ${book}.`, by: "A made-up author" }]]),
    );

async function answer(page: Page, fail = 0): Promise<void> {
  await page.route("**/case-report-passages*", (route) =>
    fail-- > 0 ? route.fulfill({ status: 503, body: "" }) : route.fulfill({ json: PASSAGES }),
  );
}

/** The report opened at its address, every console error kept. */
async function open(page: Page, fail = 0): Promise<string[]> {
  await answer(page, fail);
  const errors: string[] = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto("/app/case-report");
  await expect(page.locator("#case-body .level").first()).toBeVisible();
  await page.waitForTimeout(400);
  return errors;
}

for (const key of FIXTURES)
  for (const size of SIZES)
    for (const scheme of SCHEMES)
      test.describe(`${key} at ${size.width} in ${scheme}`, () => {
        test.use({ storageState: stateFor(key), viewport: size, colorScheme: scheme });

        // R-0702, R-0689, R-0690
        test("draws every card with its strip item, each chip whole and inside its card, nothing sideways", async ({ page }) => {
          const errors = await open(page);
          const seen = await page.evaluate(() => {
            const out = (inner: DOMRect, outer: DOMRect) =>
              inner.left < outer.left - 0.5 || inner.right > outer.right + 0.5 || inner.top < outer.top - 0.5 || inner.bottom > outer.bottom + 0.5;
            const chips = [...document.querySelectorAll<HTMLElement>("#case-body .chips .chip")];
            return {
              strip: [...document.querySelectorAll<HTMLElement>("#case-rail [data-jump]")].map((b) => b.dataset.jump),
              cards: [...document.querySelectorAll<HTMLElement>("#case-body .level, #case-dash .level")].map((l) => l.dataset.card),
              // a stored title shows whole: no chip cut short, none with an ellipsis
              ellipsis: chips.filter((c) => getComputedStyle(c).textOverflow === "ellipsis").length,
              cut: chips
                .filter((c) => {
                  const words = document.createRange();
                  words.selectNodeContents(c);
                  const pad = parseFloat(getComputedStyle(c).paddingLeft) + parseFloat(getComputedStyle(c).paddingRight);
                  return words.getBoundingClientRect().width > c.clientWidth - pad + 1;
                })
                .map((c) => c.textContent),
              outside: chips.filter((c) => out(c.getBoundingClientRect(), c.closest(".level")!.getBoundingClientRect())).length,
              sideways: document.documentElement.scrollWidth > window.innerWidth,
              stripRows: new Set([...document.querySelectorAll<HTMLElement>("#case-rail [data-jump]")].map((b) => b.offsetTop)).size,
              text: document.querySelector("#case-screen")!.textContent ?? "",
              folds: document.querySelectorAll("#case-body details").length,
              sides: document.querySelectorAll("#case-body details.side").length,
              sideCount: document.querySelectorAll("#case-body details.side").length,
              sidePictures: document.querySelectorAll("#case-body details.side .fam").length,
            };
          });
          expect([...seen.cards].sort()).toEqual([...seen.strip].sort());
          expect(seen.strip).toHaveLength(10);
          expect(seen.stripRows).toBe(1);
          expect(seen.cut).toEqual([]);
          expect(seen.ellipsis).toBe(0);
          expect(seen.outside).toBe(0);
          expect(seen.sideways).toBe(false);
          expect(seen.text).not.toMatch(/NaN|undefined|not in the record|From the record/);
          // stored words show as written: an apostrophe is never escaped code
          expect(seen.text).not.toMatch(/&#39;|&#x27;|&apos;|&amp;|&quot;/);
          // every family picture is drawn; each side is one picture (R-0733)
          expect(seen.text).not.toContain("cannot be drawn");
          expect(seen.sidePictures).toEqual(seen.sideCount);
          // only each side of the family folds (R-0689)
          expect(seen.folds).toBe(seen.sides);
          expect(errors).toEqual([]);
        });
      });

test.describe("the case report with little in the record", () => {
  test.use({ storageState: stateFor("case-report-thin"), viewport: SIZES[0] });

  // R-0740
  test("what to work on says the person has not said yet what they are working on", async ({ page }) => {
    await open(page);
    const record = await (await page.request.get("/app/timeline")).json();
    expect(record.asked_questions.filter((q: { open: boolean; kind: string; case_report_card: string | null }) => q.open && q.kind === "impression" && q.case_report_card === "work_on")).toEqual([]);
    const card = page.locator('#case-body .level[data-card="work_on"]');
    await expect(card.locator(".bub.coach")).toHaveText(/You haven't said yet what you're working on\. Chat more with me about it\./);
    await expect(card).not.toContainText("Not enough in the diagram to make a guess yet");
  });
});

test.describe("the case report's words", () => {
  test.use({ storageState: stateFor("case-report"), viewport: SIZES[0] });

  // R-0740
  test("a guess with an apostrophe shows the apostrophe, never escaped code", async ({ page }) => {
    await open(page);
    const card = page.locator('#case-body .level[data-card="guesses"]');
    await expect(card.locator(".bub.coach").first()).toContainText("Your father's drinking got heavy");
    await expect(card).not.toContainText("&#39;");
  });
});

test.describe("the case report's taps", () => {
  test.use({ storageState: stateFor("case-report"), viewport: SIZES[0] });

  // R-0702
  test("a strip item glides the cards to its card and lights its item", async ({ page }) => {
    await open(page);
    const body = page.locator("#case-body");
    const tops: number[] = [];
    await page.locator('#case-rail [data-jump="effort"]').click();
    for (let i = 0; i < 12; i++) {
      tops.push(await body.evaluate((b) => b.scrollTop));
      await page.waitForTimeout(40);
    }
    await page.waitForTimeout(600);
    const end = await body.evaluate((b) => b.scrollTop);
    // sampled on the way: at least one stop strictly between the start and the end
    expect(tops.some((t) => t > 0 && t < end)).toBe(true);
    const card = await page.locator('#case-body .level[data-card="effort"]').boundingBox();
    const bodyBox = await body.boundingBox();
    expect(card!.y).toBeLessThan(bodyBox!.y + bodyBox!.height);
    await expect(page.locator('#case-rail [data-jump="effort"]')).toHaveClass(/on/);
  });

  // R-0702
  test("the strip is one button high and scrolls sideways", async ({ page }) => {
    await open(page);
    const strip = await page.locator("#case-rail").evaluate((rail) => {
      const button = rail.querySelector<HTMLElement>("[data-jump]")!;
      const pad = parseFloat(getComputedStyle(rail).paddingTop) + parseFloat(getComputedStyle(rail).paddingBottom);
      const tops = new Set([...rail.querySelectorAll<HTMLElement>("[data-jump]")].map((b) => b.offsetTop));
      return { inner: rail.clientHeight - pad, button: button.offsetHeight, rows: tops.size, wider: rail.scrollWidth > rail.clientWidth };
    });
    expect(strip.rows).toBe(1);
    expect(strip.inner).toBe(strip.button);
    expect(strip.wider).toBe(true);
  });

  // R-0696
  test("the timeline folds to the chat's strip while the cards are read, and opens at their top and on a chip", async ({ page }) => {
    await open(page);
    const pic = page.locator("#case-screen > .pic");
    const full = (await pic.boundingBox())!.height;
    await page.locator("#case-body").evaluate((b) => (b.scrollTop = 600));
    await expect.poll(async () => (await pic.boundingBox())!.height).toBeLessThan(full);
    await expect(page.locator("#case-screen")).toHaveClass(/folded/);
    // still on screen, pinned at the top
    expect((await pic.boundingBox())!.y).toBeLessThan(120);
    await page.locator('#case-body .chip[data-kind="event"]:visible').first().click();
    await expect(page.locator("#case-screen")).not.toHaveClass(/folded/);
    await page.locator("#case-body").evaluate((b) => (b.scrollTop = 600));
    await expect(page.locator("#case-screen")).toHaveClass(/folded/);
    await page.locator("#case-body").evaluate((b) => (b.scrollTop = 0));
    await expect(page.locator("#case-screen")).not.toHaveClass(/folded/);
  });

  // R-0700
  test("putting the cluster away closes its play-by-play", async ({ page }) => {
    await open(page);
    await page.locator('#case-view .ss-hit[data-target="cluster"]').first().click();
    await page.locator("#case-caption #cap-play").click();
    await expect(page.locator("#case-pbp")).toHaveClass(/in/);
    await page.locator('#case-path [data-step="0"]').click();
    await expect(page.locator("#case-pbp")).not.toHaveClass(/in/);
  });

  // R-0698
  test("a guess is the chat's coach bubble with no guess heading over it", async ({ page }) => {
    await open(page);
    const main = page.locator('#case-body .level[data-card="main"]');
    await expect(main.locator(".bub.coach .who")).toHaveText("Coach");
    await expect(page.locator("#case-body")).not.toContainText(/A guess, yours to reject|Rests on|The record covers|open questions|Left off this page/i);
  });

  // R-0702
  test("the family card is one button, the same as the strip's family item", async ({ page }) => {
    await open(page);
    const card = page.locator('#case-body .level[data-card="family"]');
    await expect(card.locator("> *")).toHaveCount(1);
    await expect(card.locator("button.famcard")).toHaveText((await page.locator('#case-rail [data-jump="family"]').textContent())!);
    await card.locator("button.famcard").click();
    await expect(page.locator("#case-famout")).toHaveClass(/in/);
  });

  // R-0700, R-0696
  test("a person's chip lights that person's events on the timeline", async ({ page }) => {
    await open(page);
    const before = await page.locator("#case-view").innerHTML();
    await page.locator('#case-body .chip[data-kind="person"]').first().click();
    await expect.poll(() => page.locator("#case-view").innerHTML()).not.toBe(before);
    await expect(page.locator("#case-view .ss-t.on").first()).toBeVisible();
  });

  // R-0700
  test("a cluster opened on the timeline offers explain, and explain opens the play-by-play", async ({ page }) => {
    await open(page);
    await page.locator('#case-view .ss-hit[data-target="cluster"]').first().click();
    await expect(page.locator("#case-caption #cap-play")).toBeEnabled();
    await page.locator("#case-caption #cap-play").click();
    await expect(page.locator("#case-pbp")).toHaveClass(/in/);
    // a strip tap puts the play-by-play away so the scroll is seen (R-0702)
    await page.locator('#case-rail [data-jump="sides"]').click();
    await expect(page.locator("#case-pbp")).not.toHaveClass(/in/);
  });

  // R-0700
  test("a cluster's chip on a card opens it on the timeline with explain offered, and explain opens the play-by-play", async ({ page }) => {
    await open(page);
    await page.locator('#case-body .chip[data-kind="cluster"]').first().click();
    await expect(page.locator("#case-path [data-step]").first()).toBeVisible();
    await page.locator("#case-caption #cap-play").click();
    await expect(page.locator("#case-pbp")).toHaveClass(/in/);
  });

  // R-0715
  test("the header names who presents by first name, never by email", async ({ page }) => {
    await open(page);
    await expect(page.locator("#case-title")).toHaveText("Nora · Case report");
    await expect(page.locator("#case-by")).toHaveText("presented by Nora");
  });

  // R-0700
  test("a card's chip naming an event inside a cluster opens that cluster as a tap on it does, explain offered", async ({ page }) => {
    await open(page);
    const record = await (await page.request.get("/app/timeline")).json();
    const inside: number[] = record.clusters.flatMap((c: { event_ids: number[] }) => c.event_ids);
    const target = await page.locator("#case-body .chip[data-kind=\"event\"]").evaluateAll(
      (els, inside) => els.map((e) => (e as HTMLElement).dataset.target).find((t) => inside.includes(Number(t))),
      inside,
    );
    expect(target).toBeTruthy();
    await page.locator(`#case-body .chip[data-kind="event"][data-target="${target}"]`).first().click();
    await expect(page.locator("#case-caption #cap-play")).toBeEnabled();
    await page.locator("#case-caption #cap-play").click();
    await expect(page.locator("#case-pbp")).toHaveClass(/in/);
  });

  // R-0691, R-0692
  test("a card's book raises its passages and puts them away", async ({ page }) => {
    await open(page);
    await page.locator('#case-body .level[data-card="main"] .book').click();
    const sheet = page.locator("#case-screen .fs-sheet.bk");
    await expect(sheet).toHaveClass(/in/);
    await expect(sheet.locator("blockquote").first()).toBeVisible();
    await sheet.locator(".cardx").click();
    await expect(sheet).not.toHaveClass(/in/);
  });

  // R-0691
  test("a book opens within a second once the screen has been open a few seconds", async ({ page }) => {
    await open(page);
    await page.waitForTimeout(3000);
    const tapped = Date.now();
    await page.locator('#case-body .level[data-card="brought"] .book').click();
    await expect(page.locator("#case-screen .fs-sheet.bk")).toHaveClass(/in/, { timeout: 1000 });
    expect(Date.now() - tapped).toBeLessThan(1000);
  });

  // R-0691
  test("a book whose passages could not be read asks again at its tap", async ({ page }) => {
    await open(page, 1);
    await page.locator('#case-body .level[data-card="main"] .book').click();
    await expect(page.locator("#case-screen .fs-sheet.bk blockquote").first()).toBeVisible();
  });

  // R-0691
  test("Escape puts the book's passages away", async ({ page }) => {
    await open(page);
    await page.locator('#case-body .level[data-card="main"] .book').click();
    await expect(page.locator("#case-screen .fs-sheet.bk")).toHaveClass(/in/);
    await page.keyboard.press("Escape");
    await expect(page.locator("#case-screen .fs-sheet.bk")).not.toHaveClass(/in/);
  });

  // R-0709
  test("the coach's guess card holds only the guesses the coach chose for it", async ({ page }) => {
    await open(page);
    const record = await (await page.request.get("/app/timeline")).json();
    const chosen = record.asked_questions.filter((q: { open: boolean; kind: string; case_report_card: string | null }) => q.open && q.kind === "impression" && q.case_report_card === "coach_guess");
    const card = page.locator('#case-body .level[data-card="guesses"]');
    const words = await card.locator(".bub.coach").allTextContents();
    for (const q of record.asked_questions.filter((q: { kind: string; case_report_card: string | null }) => q.kind === "impression" && q.case_report_card === null))
      expect(words.join(" ")).not.toContain(q.text);
    if (!chosen.length) await expect(card).toContainText("Not enough in the diagram to make a guess yet");
    else for (const q of chosen.slice(-3)) await expect(card).toContainText(q.text);
  });

  // R-0697
  test("on the phone the family button slides the family out over the report", async ({ page }) => {
    await open(page);
    await page.locator("#case-family").click();
    await expect(page.locator("#case-famout")).toHaveClass(/in/);
    await expect(page.locator("#case-famout .fam svg").first()).toBeVisible();
    await page.locator("#case-famout-close").click();
    await expect(page.locator("#case-famout")).not.toHaveClass(/in/);
  });
});

test.describe("the case report's family pictures of a family many phones wide", () => {
  test.use({ storageState: stateFor("case-report-dense"), viewport: SIZES[0] });

  // R-0759, R-0744
  test("draw names at 13px or more and pan in their own frames, every word inside what the frame scrolls to", async ({ page }) => {
    const errors = await open(page);
    const pictures = "#case-body .fam svg";
    expect(await leastName(page, pictures)).toBeGreaterThanOrEqual(13);
    expect(await wordsOutside(page, pictures)).toEqual([]);
    expect(await page.locator("#case-body .fam").evaluateAll((f) => f.some((d) => d.scrollWidth > d.clientWidth))).toBe(true);
    await page.locator("#case-family").click();
    await expect(page.locator("#case-famout")).toHaveClass(/in/);
    const slid = "#case-famout .fam svg";
    // R-0759: the record's own person and their words whole in the frame, as the Family drawer opens
    const own = await page.locator("#case-famout .fam[data-who]").first().getAttribute("data-who");
    expect(await page.locator(`#case-famout .fam .pt[data-id="${own}"]`).first().textContent()).toContain("Margaret-Anne");
    expect(await cutInFrame(page, "#case-famout .fam[data-who]", [own!])).toEqual({ fits: true, cut: {} });
    expect(await leastName(page, slid)).toBeGreaterThanOrEqual(13);
    expect(await wordsOutside(page, slid)).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  });
});

/** The couple card on the Halloran fixture (Nora and Daniel, married, one
 * daughter, Nora's parents in the record and Daniel's not), at a phone's and a
 * desktop's size. */
for (const size of [SIZES[0], { width: 1440, height: 900 }])
  test.describe(`the couple card at ${size.width}`, () => {
    test.use({ storageState: stateFor("case-report"), viewport: size });

    // R-0833, R-0834, R-0835
    test("groups the couple's events under Bowen's stage heads in date order, each head a chip, and says what it still needs", async ({ page }) => {
      const errors = await open(page);
      const card = page.locator('#case-body .level[data-card="couple"]');
      await card.scrollIntoViewIfNeeded();
      await expect(card.locator("p.label")).toHaveText("4 · The couple since they met");
      await expect(card.locator("p.lead").first()).toHaveText("Nora and Daniel are married.");
      const rows = card.locator(".stage .chips");
      await expect(rows).toHaveCount(2);
      expect(await rows.locator(".chip:first-child").allTextContents()).toEqual(["Jun 2009 · married", "May 2012 · Lily born"]);
      // under married: Nora's fights with Daniel; under Lily born: Daniel's job, named; and her mother's illness, always
      await expect(rows.nth(0)).toContainText("Jun 2011 · Fights over money");
      await expect(rows.nth(1)).toContainText("Feb 2014 · Daniel · Lost his job");
      await expect(rows.nth(1)).toContainText("Apr 2018 · Elaine · Hospitalized with pneumonia");
      await expect(rows.nth(1)).toContainText("Jan 2019 · Stopped visiting her mother");
      // nothing of hers from before the marriage
      await expect(card).not.toContainText("Stopped sleeping well");
      await expect(card.locator("p.lead").last()).toHaveText("This card still needs where Daniel stands among his brothers and sisters.");
      // every chip whole and inside the card, nothing sideways
      const geometry = await card.evaluate((level) => {
        const box = level.getBoundingClientRect();
        const chips = [...level.querySelectorAll<HTMLElement>(".chips .chip")];
        return {
          outside: chips.filter((c) => c.getBoundingClientRect().right > box.right + 0.5 || c.getBoundingClientRect().left < box.left - 0.5).length,
          sideways: document.documentElement.scrollWidth > window.innerWidth,
        };
      });
      expect(geometry).toEqual({ outside: 0, sideways: false });
      expect(errors).toEqual([]);
    });

    // R-0835, R-0691
    test("its book raises the passages behind the stages and the selection rule, each with its book and chapter", async ({ page }) => {
      await open(page);
      const card = page.locator('#case-body .level[data-card="couple"]');
      await card.scrollIntoViewIfNeeded();
      await card.locator(".book").click();
      const sheet = page.locator("#case-screen .fs-sheet.bk");
      await expect(sheet).toHaveClass(/in/);
      await expect(sheet.locator(".cf-t")).toHaveText("The couple since they met");
      const want = PASSAGES["3"];
      await expect(sheet.locator("blockquote")).toHaveCount(want.length);
      expect(await sheet.locator("blockquote").allTextContents()).toEqual(want.map((p) => p.text));
      expect(await sheet.locator(".bk-by").allTextContents()).toEqual(want.map((p) => p.by));
      // every passage names its book and where in it
      for (const by of want.map((p) => p.by)) expect(by).toMatch(/(ch\. \d|p\. \d|lines \d|Basic Series \d)/);
      await sheet.locator(".cardx").click();
      await expect(sheet).not.toHaveClass(/in/);
    });
  });
