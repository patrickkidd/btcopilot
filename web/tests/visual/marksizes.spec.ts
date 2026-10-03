import { expect, test, type Page } from "@playwright/test";
import { stateFor, step } from "./setup";

/** Every mark the play-by-play draws, one step each, on the Pemberton stand-in
 * family (`everymark` in btcopilot/routes/fixtures.py), read off the real
 * drawer: its size on its own step in the emphasis colour, its grey once
 * carried to the next, and that no mark runs over a name or a word. */

/** Each step in order, and where its mark is found once drawn. Marks drawn
 * around a person (the death X, anxiety's spikes, an outline) take the
 * person's size, and an arrow, a couple's line or the fusion bands take the
 * distance between two people, so only the marks that stand on their own are
 * held to one size. A word is lit in the emphasis colour meant for words. */
const STEPS: { name: string; marks: string; sized?: boolean; word?: boolean }[] = [
  { name: "married", marks: '[data-bond="3|4"]' },
  { name: "birth", marks: '[data-mark^="hl:"]' },
  { name: "adopted", marks: '[data-mark^="hl:"]' },
  { name: "toward", marks: '[data-mark$=":toward"] :is(line, polygon)' },
  { name: "away", marks: '[data-mark$=":away"] :is(line, polygon)' },
  { name: "conflict", marks: '[data-mark$=":conflict"] .mv-burst', sized: true },
  { name: "distance", marks: '[data-mark$=":distance"] .mv-wall', sized: true },
  { name: "separated", marks: ".slash", sized: true },
  { name: "symptom up", marks: '[data-mark^="cross:"] :is(rect, line, polygon)', sized: true },
  { name: "anxiety up", marks: ".spikes line" },
  { name: "anxiety down", marks: ".evw", word: true },
  { name: "divorced", marks: ".slash", sized: true },
  { name: "cutoff", marks: '[data-mark$=":cutoff"] :is(.mv-wall, .mv-strike)', sized: true },
  { name: "projection", marks: '[data-mark$=":projection"] .s-out line' },
  { name: "fusion", marks: '[data-mark$=":fusion"] .mv-band' },
  { name: "overfunctioning", marks: '[data-mark$=":overfunctioning"] .mv-flank line' },
  { name: "underfunctioning", marks: '[data-mark$=":underfunctioning"] .mv-flank line' },
  { name: "functioning down", marks: '[data-mark^="fdown:"]' },
  { name: "functioning up", marks: '[data-mark^="fup:"]' },
  { name: "symptom down", marks: '[data-mark^="cross:"] :is(rect, line, polygon)', sized: true },
  { name: "defined self", marks: '[data-mark$=":defined-self"] .mv-clear' },
  { name: "inside", marks: ".evw", word: true },
  { name: "outside", marks: ".evw", word: true },
  { name: "noted", marks: ".evw", word: true },
  { name: "death", marks: ".xd" },
  { name: "bonded", marks: '[data-bond="5|7"]' },
  { name: "family", marks: '[data-mark^="hl:"]' },
];

/** What a move mark is drawn with, and what words are; the field's rings and
 * a couple's or a child's lines are ground, not marks. */
const MARKS = ".slash, .mvk line, .mvk polyline, .mvk polygon, .arr line, .arr polygon, .mk rect, .mk line, .mk polygon, .spikes line";
const WORDS = "text.lbn, text.lbd, text.evw";

interface Size {
  name: string;
  tone: string;
  w: number;
  h: number;
  colour: string;
}

/** Put one step's drawing in the drawer, every clock held at its start. */
const show = (page: Page, svg: string) =>
  page.evaluate((svg) => {
    const draw = document.querySelector("#pbp .draw")!;
    draw.querySelector("svg")!.outerHTML = svg;
    draw.querySelector("svg")!.pauseAnimations();
  }, svg);

/** The marks' union box in their own drawing frame, so a mark keeps its size
 * whatever angle it is drawn at, scaled to the screen; strokes included. */
const measure = (page: Page, name: string, selector: string, tone: "now" | "was") =>
  page.evaluate(
    ({ name, selector, tone }): Size => {
      const root = document.querySelector<SVGSVGElement>("#pbp .draw svg")!;
      // a divorce's two slashes are one mark, whichever of them is lit
      const els = [...root.querySelectorAll<SVGGraphicsElement>(selector)].filter(
        (el) => el.matches(".slash") || !!el.closest(".now, .pop") === (tone === "now"),
      );
      if (!els.length) throw new Error(`no ${selector} drawn for ${name} (${tone})`);
      const ctm = root.getScreenCTM()!;
      const scale = Math.hypot(ctm.a, ctm.b);
      const frame = els[0].parentElement as unknown as SVGGraphicsElement;
      let [x0, y0, x1, y1] = [Infinity, Infinity, -Infinity, -Infinity];
      els.forEach((el) => {
        const b = el.getBBox();
        const m = frame.getScreenCTM()!.inverse().multiply(el.getScreenCTM()!);
        const s = parseFloat(getComputedStyle(el).strokeWidth) || 0;
        [
          [b.x, b.y],
          [b.x + b.width, b.y],
          [b.x, b.y + b.height],
          [b.x + b.width, b.y + b.height],
        ].forEach(([x, y]) => {
          const p = new DOMPoint(x, y).matrixTransform(m);
          x0 = Math.min(x0, p.x - s / 2);
          y0 = Math.min(y0, p.y - s / 2);
          x1 = Math.max(x1, p.x + s / 2);
          y1 = Math.max(y1, p.y + s / 2);
        });
      });
      // the lit one of a divorce's two slashes is the second
      const paint = getComputedStyle(els[els.length - 1]);
      const r = (v: number) => Math.round(v * scale * 10) / 10;
      return {
        name,
        tone,
        w: r(x1 - x0),
        h: r(y1 - y0),
        colour: paint.stroke !== "none" ? paint.stroke : paint.fill,
      };
    },
    { name, selector, tone },
  );

/** Every mark's stroke that crosses a name or a word, in the drawing's own
 * units: each line, polyline and polygon edge against each word's box. */
const crossings = (page: Page, marks: string, words: string) =>
  page.evaluate(
    ({ marks, words }) => {
      const root = document.querySelector<SVGSVGElement>("#pbp .draw svg")!;
      const fore = root.querySelector(".fore")!;
      const boxes = [...root.querySelectorAll<SVGTextElement>(words)].map((t) => ({ text: t.textContent, b: t.getBBox(), lit: fore.contains(t) }));
      const cut = (a: DOMPoint, z: DOMPoint, b: DOMRect, pad: number) => {
        const [bx0, by0, bx1, by1] = [b.x - pad, b.y - pad, b.x + b.width + pad, b.y + b.height + pad];
        let [t0, t1] = [0, 1];
        const dx = z.x - a.x;
        const dy = z.y - a.y;
        for (const [p, q] of [
          [-dx, a.x - bx0],
          [dx, bx1 - a.x],
          [-dy, a.y - by0],
          [dy, by1 - a.y],
        ]) {
          if (p === 0) {
            if (q < 0) return false;
          } else if (p < 0) t0 = Math.max(t0, q / p);
          else t1 = Math.min(t1, q / p);
          if (t0 > t1) return false;
        }
        return true;
      };
      const out: string[] = [];
      for (const el of root.querySelectorAll<SVGGraphicsElement>(marks)) {
        if (getComputedStyle(el).opacity === "0" || getComputedStyle(el).visibility === "hidden") continue;
        const m = root.getScreenCTM()!.inverse().multiply(el.getScreenCTM()!);
        const at = (x: number, y: number) => new DOMPoint(x, y).matrixTransform(m);
        let pts: DOMPoint[] = [];
        let closed = false;
        if (el instanceof SVGLineElement) pts = [at(el.x1.baseVal.value, el.y1.baseVal.value), at(el.x2.baseVal.value, el.y2.baseVal.value)];
        else if (el instanceof SVGPolylineElement || el instanceof SVGPolygonElement) {
          pts = [...el.points].map((p) => at(p.x, p.y));
          closed = el instanceof SVGPolygonElement;
        } else {
          const b = el.getBBox();
          pts = [at(b.x, b.y), at(b.x + b.width, b.y), at(b.x + b.width, b.y + b.height), at(b.x, b.y + b.height)];
          closed = true;
        }
        const edges = pts.slice(1).map((p, i) => [pts[i], p]);
        if (closed) edges.push([pts[pts.length - 1], pts[0]]);
        const pad = (parseFloat(getComputedStyle(el).strokeWidth) || 0) / 2;
        // a lit word is drawn over the grey marks it crosses, which is allowed (R-0682)
        const under = !fore.contains(el);
        for (const { text, b, lit } of boxes)
          if (!(lit && under) && edges.some(([a, z]) => cut(a, z, b, pad))) {
            const mark = el.closest("[data-mark]")?.getAttribute("data-mark") ?? el.getAttribute("class");
            out.push(`${mark} over "${text}"`);
          }
      }
      return [...new Set(out)];
    },
    { marks, words },
  );

/** The case's stored play-by-play opened, and each of its steps' drawing. */
async function steps(page: Page, n: number): Promise<string[]> {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.locator(".bub.coach[data-play]").last().click();
  await expect.poll(() => step(page)).toBe(`1 of ${n}`);
  await page.addStyleTag({ content: "#pbp *, #pbp { animation: none !important; transition: none !important; }" });
  const svgs: string[] = [];
  for (let i = 0; i < n; i++) {
    if (i) await page.locator('#pbp [data-act="next"]').click();
    await expect.poll(() => step(page)).toBe(`${i + 1} of ${n}`);
    svgs.push(await page.locator("#pbp .draw svg").evaluate((svg) => svg.outerHTML));
  }
  return svgs;
}

/** The case's stored play-by-play opened with its animations running. */
async function live(page: Page) {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.locator(".bub.coach[data-play]").last().click();
  await expect(page.locator("#pbp .draw svg")).toBeVisible();
}

/** A colour the page names, as the browser writes a computed colour. */
const paint = (page: Page, name: string) =>
  page.evaluate((v) => {
    const probe = document.createElement("i");
    document.querySelector("#pbp")!.append(probe);
    probe.style.color = `var(${v})`;
    const out = getComputedStyle(probe).color;
    probe.remove();
    return out;
  }, name);

const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2;
};

/** Every step whose lit marks are not all in the layer drawn last, over the
 * grey ones carried from earlier steps. */
async function under(page: Page, svgs: string[]): Promise<string[]> {
  const found: string[] = [];
  for (const [i, svg] of svgs.entries()) {
    await show(page, svg);
    const wrong = await page.evaluate(() => {
      const root = document.querySelector<SVGSVGElement>("#pbp .draw svg")!;
      const fore = root.lastElementChild;
      if (!fore?.matches("g.fore")) return ["no layer drawn last"];
      const lit = [...root.querySelectorAll(".now, .pop")].filter((el) => !fore.contains(el));
      const grey = [...fore.querySelectorAll(".was")];
      return [...lit, ...grey].map((el) => el.closest("[data-mark], [data-bond]")?.outerHTML.slice(0, 60) ?? el.getAttribute("class")!);
    });
    wrong.forEach((w) => found.push(`step ${i + 1}: ${w}`));
  }
  return found;
}

/** How far apart the couple's two shapes stand, in widths of a shape. */
const apart = (page: Page, a: number, b: number) =>
  page.evaluate(
    ([a, b]) => {
      const at = (id: number) => document.querySelector<SVGGraphicsElement>(`#pbp .draw svg .p[data-id="${id}"] .shape`)!.getBBox();
      const [p, q] = [at(a), at(b)];
      return Math.abs(q.x - p.x) / p.width;
    },
    [a, b],
  );

/** A couple stands at the ruled three widths apart, and further only by what
 * their children under them need; a step's words find room of their own and
 * never push anyone apart. The Pembertons stood eleven apart while every word
 * took room at once. */
const COUPLE_MOST = 4;

/** Every crossing of a mark and a word, step by step. */
async function over(page: Page, svgs: string[]): Promise<string[]> {
  const found: string[] = [];
  for (const [i, svg] of svgs.entries()) {
    await show(page, svg);
    (await crossings(page, MARKS, WORDS)).forEach((c) => found.push(`step ${i + 1}: ${c}`));
  }
  return found;
}

test.describe("every mark", () => {
  test.use({ storageState: stateFor("everymark") });

  // R-0679, R-0552
  test("every mark the play-by-play draws is of one size, the current one in the emphasis colour", async ({ page }) => {
    const svgs = await steps(page, STEPS.length);
    const sizes: Size[] = [];
    for (const [i, s] of STEPS.entries()) {
      await show(page, svgs[i]);
      sizes.push(await measure(page, s.name, s.marks, "now"));
      if (s.word || s.name === "death" || i + 1 === STEPS.length) continue;
      await show(page, svgs[i + 1]);
      sizes.push(await measure(page, s.name, s.marks, "was"));
    }

    const sized = sizes.filter((s) => STEPS.find((x) => x.name === s.name)!.sized);
    const mid = median(sized.map((s) => Math.max(s.w, s.h)));
    const off = sized.filter((s) => Math.max(s.w, s.h) < 0.75 * mid || Math.max(s.w, s.h) > 1.33 * mid);
    expect(off.map((s) => `${s.name} ${s.tone} ${Math.max(s.w, s.h)} against ${mid}`)).toEqual([]);

    const lit = { mark: await paint(page, "--move"), word: await paint(page, "--move-text"), was: await paint(page, "--faint") };
    const wrong = sizes.filter((s) => {
      const want = s.tone === "was" ? lit.was : STEPS.find((x) => x.name === s.name)!.word ? lit.word : lit.mark;
      return s.colour !== want;
    });
    expect(wrong.map((s) => `${s.name} ${s.tone} ${s.colour}`)).toEqual([]);
  });

  // R-0679
  test("no mark runs over a name or a word", async ({ page }) => {
    expect(await over(page, await steps(page, STEPS.length))).toEqual([]);
  });

  // R-0679
  test("each step's lit marks are drawn over every grey one", async ({ page }) => {
    expect(await under(page, await steps(page, STEPS.length))).toEqual([]);
  });

  // R-0682, R-0681
  test("an event's words show on its own step only, the functioning ones too", async ({ page }) => {
    const svgs = await steps(page, STEPS.length);
    const words: string[][] = [];
    for (const svg of svgs) {
      await show(page, svg);
      words.push(await page.locator("#pbp .draw svg .evw").allTextContents());
    }
    const at = (name: string) => words[STEPS.findIndex((s) => s.name === name)];
    expect(at("functioning down")).toEqual(["Lost his job"]);
    // the whole title, never cut to three words (R-0681)
    expect(at("functioning up")).toEqual(["Opened his own shop"]);
    expect(at("noted")).toEqual(["Moved to Chicago"]);
    // the next step never still shows a word from the one before
    expect(words.slice(1).filter((w, i) => w.some((t) => words[i].includes(t)))).toEqual([]);
  });

  // R-0679
  test("an event on the years line jumps to its step, and the dots alone say where the reader is", async ({ page }) => {
    await steps(page, STEPS.length);
    await page.locator('#pbp .wire [data-act="jump"][data-i="20"]').click();
    await expect.poll(() => step(page)).toBe(`21 of ${STEPS.length}`);
    await page.locator('#pbp .wire [data-act="jump"][data-i="6"]').click();
    await expect.poll(() => step(page)).toBe(`7 of ${STEPS.length}`);
    await page.locator("#pbp .dots .dot").nth(15).click();
    await expect.poll(() => step(page)).toBe(`7 of ${STEPS.length}`);
    expect(await page.locator("#pbp .dots button, #pbp .dots [data-act]").count()).toBe(0);
    // no "7 of 27" beside Next: the lit dot is the only sign of where the reader is
    await expect(page.locator("#pbp div.step")).not.toContainText(" of ");
  });

  // R-0679
  test("a wall's loop runs in five seconds from the moment its step comes up, its own slide and the field's pace kept, the field on screen throughout", async ({ page }) => {
    await page.goto("/app/");
    await expect(page.locator("#view .ss")).toBeVisible();
    await page.locator(".bub.coach[data-play]").last().click();
    const wrong: string[] = [];
    for (const name of ["distance", "cutoff"]) {
      await page.locator(`#pbp .wire [data-act="jump"][data-i="${STEPS.findIndex((s) => s.name === name)}"]`).click();
      for (let ms = 0; ms < 5000; ms += 100) {
        const seen = await page.evaluate((at) => {
          for (const svg of document.querySelectorAll("svg")) {
            svg.pauseAnimations();
            svg.setCurrentTime(at / 1000);
          }
          for (const a of document.getAnimations()) {
            a.pause();
            a.currentTime = at;
          }
          const g = document.querySelector("#pbp .draw .fore .mvk")!;
          const wall = getComputedStyle(g.querySelector(".mv-wall")!);
          return {
            loop: getComputedStyle(g.querySelector(".mv-wall")!).animationDuration,
            pace: [...g.querySelectorAll("circle.fld animate[attributeName='r']")].map((a) => a.getAttribute("dur")),
            shift: new DOMMatrix(wall.transform).e,
            shown: +wall.opacity,
            rings: [...g.querySelectorAll("circle.fld")]
              .filter((c) => +getComputedStyle(c).opacity > 0.05)
              .map((c) => (c.classList.contains("postA") ? "shadowed" : "open")),
          };
        }, ms);
        const at = `${name} at ${ms}ms`;
        if (seen.loop !== "5s") wrong.push(`${at}: loop ${seen.loop}`);
        if (seen.pace.some((d) => d !== "1.65s")) wrong.push(`${at}: rings at ${seen.pace}`);
        // the wall sets off at once and takes its own 1.4s to slide in
        if (ms > 0 && ms < 1400 && !(seen.shift < 0 && seen.shown > 0)) wrong.push(`${at}: wall not sliding`);
        if (ms >= 1400 && Math.abs(seen.shift) > 0.01) wrong.push(`${at}: wall not landed`);
        if (!seen.rings.length) wrong.push(`${at}: no rings`);
        if (ms >= 1600 && seen.rings.includes("open")) wrong.push(`${at}: open rings behind the wall`);
      }
    }
    expect(wrong).toEqual([]);
  });

  // R-0679
  test("the health cross and its arrow sit in two square cells side by side", async ({ page }) => {
    const svgs = await steps(page, STEPS.length);
    for (const name of ["symptom up", "symptom down"]) {
      await show(page, svgs[STEPS.findIndex((s) => s.name === name)]);
      const [plus, arrow] = await Promise.all(
        [".fore .mv-sym", ".fore .sym-arrow"].map((sel) =>
          page.locator(`#pbp .draw svg ${sel}`).evaluate((el) => {
            const b = el.getBoundingClientRect();
            return { x: b.x + b.width / 2, w: b.width, h: b.height };
          }),
        ),
      );
      const side = plus.h;
      expect(Math.abs(plus.w - side)).toBeLessThan(0.5);
      expect(Math.abs(arrow.h - side)).toBeLessThan(0.5);
      expect(arrow.w).toBeLessThanOrEqual(side);
      // the arrow's cell starts where the cross's ends, so their middles are one cell apart
      expect(Math.abs(Math.abs(arrow.x - plus.x) - side)).toBeLessThan(0.5);
    }
  });

  // R-0679
  test("the projecting parent is lit on the projection step, over the grey marks", async ({ page }) => {
    const svgs = await steps(page, STEPS.length);
    const i = STEPS.findIndex((s) => s.name === "projection");
    await show(page, svgs[i]);
    // Rosa, who projects onto Leo
    const lit = page.locator('#pbp .draw svg > .fore [data-mark="hl:4"]');
    await expect(lit).toHaveCount(1);
    expect(await lit.evaluate((el) => getComputedStyle(el).stroke)).toBe(await paint(page, "--move"));
    await show(page, svgs[i + 1]);
    await expect(page.locator('#pbp .draw svg > .fore [data-mark="hl:4"]')).toHaveCount(0);
  });

  // R-0679
  test("every step's text shows its kind word in the data colour, as the list does", async ({ page }) => {
    await steps(page, STEPS.length);
    const data = await paint(page, "--data");
    const seen: string[] = [];
    for (let i = 0; i < STEPS.length; i++) {
      await page.locator(`#pbp .wire [data-act="jump"][data-i="${i}"]`).click();
      const kw = page.locator("#pbp .cap .fact .kw");
      // a noted event and an event about the whole family name no kind
      if (["noted", "family"].includes(STEPS[i].name)) {
        await expect(kw).toHaveCount(0);
        continue;
      }
      await expect(kw.first()).toBeVisible();
      const [text, colour] = await kw.first().evaluate((el) => [el.textContent!, getComputedStyle(el).color]);
      if (colour !== data) seen.push(`${STEPS[i].name}: ${text} in ${colour}`);
    }
    expect(seen).toEqual([]);
  });

  // R-0679
  test("Walter and Rosa sit within four shape widths of each other", async ({ page }) => {
    await steps(page, STEPS.length);
    const gap = await apart(page, 3, 4);
    expect(gap).toBeLessThanOrEqual(COUPLE_MOST);
  });

  // R-0121, R-0679
  test("fusion's bands grow out from the middle until they hold both people, never coming away from them", async ({ page }) => {
    await steps(page, STEPS.length);
    await page.locator(`#pbp .wire [data-act="jump"][data-i="${STEPS.findIndex((s) => s.name === "fusion")}"]`).click();
    const loop = 1000 * parseFloat((await page.locator("#pbp .draw svg .fore .mv-band animate").first().getAttribute("dur"))!);
    const gaps: number[][] = [];
    for (let ms = 0; ms < loop; ms += 400)
      gaps.push(
        await page.evaluate((at) => {
          const svg = document.querySelector<SVGSVGElement>("#pbp .draw svg")!;
          svg.pauseAnimations();
          svg.setCurrentTime(at / 1000);
          // each band's two ends against where they rest, at the people's edges
          return [...svg.querySelectorAll<SVGLineElement>(".fore .mv-band")].flatMap((b) => [
            Math.abs(b.x1.animVal.value - b.x1.baseVal.value),
            Math.abs(b.x2.animVal.value - b.x2.baseVal.value),
          ]);
        }, ms),
      );
    expect(gaps[0].length).toBe(6);
    expect(Math.min(...gaps[0])).toBeGreaterThan(5);
    // the bands set off the moment the step comes up
    expect(gaps[1].every((v, j) => v < gaps[0][j])).toBe(true);
    const grew = gaps.slice(1).every((g, i) => g.every((v, j) => v <= gaps[i][j] + 0.01));
    expect(grew).toBe(true);
    // joined once the shared grow time has run, and held there to its end
    expect(gaps.filter((_, i) => i * 400 >= 1400).flat().every((v) => v < 0.01)).toBe(true);
  });

  // R-0679
  test("every mark a step adds is animated, its words aside", async ({ page }) => {
    await live(page);
    const still: string[] = [];
    for (let i = 0; i < STEPS.length; i++) {
      await page.locator(`#pbp .wire [data-act="jump"][data-i="${i}"]`).click();
      const none = await page.evaluate(() => {
        const fore = document.querySelector("#pbp .draw svg > .fore")!;
        const moving = (el: Element | null): boolean =>
          !!el &&
          el !== fore &&
          (el.getAnimations().length > 0 || [...el.children].some((c) => c.tagName.startsWith("animate")) || moving(el.parentElement));
        return [...fore.querySelectorAll("line, polyline, polygon, path, circle, rect")]
          .filter((el) => !el.closest("defs") && !moving(el))
          .map((el) => el.closest("[data-mark], [data-bond]")?.getAttribute("data-mark") ?? el.getAttribute("class"));
      });
      if (none.length) still.push(`${STEPS[i].name}: ${[...new Set(none)].join(", ")}`);
    }
    expect(still).toEqual([]);
  });

  // R-0679
  test("every arrow's dashes travel at the one arrow speed, an away arrow's away from the other person", async ({ page }) => {
    await live(page);
    const speed = await page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--speed-arrow")) * 1000);
    const seen: string[] = [];
    for (const [name, sel] of [["toward", ".arr line"], ["away", ".arr line"], ["projection", ".mv-flow"]]) {
      await page.locator(`#pbp .wire [data-act="jump"][data-i="${STEPS.findIndex((s) => s.name === name)}"]`).click();
      const [ms, dir] = await page.locator(`#pbp .draw svg .fore ${sel}`).first().evaluate((el) => {
        const t = el.getAnimations()[0].effect!.getComputedTiming();
        return [t.duration, t.direction];
      });
      seen.push(`${name} ${ms} ${dir}`);
    }
    expect(seen).toEqual([`toward ${speed} normal`, `away ${speed} normal`, `projection ${speed} normal`]);
    // the away arrow is drawn from Walter outward, so normal dashes run away from Rosa
    await page.locator(`#pbp .wire [data-act="jump"][data-i="${STEPS.findIndex((s) => s.name === "away")}"]`).click();
    const ends = await page.evaluate(() => {
      const line = document.querySelector<SVGLineElement>("#pbp .draw svg .fore .arr line")!;
      const rosa = document.querySelector<SVGGraphicsElement>('#pbp .draw svg .p[data-id="4"] .shape')!.getBBox();
      const [cx, cy] = [rosa.x + rosa.width / 2, rosa.y + rosa.height / 2];
      const far = (x: number, y: number) => Math.hypot(x - cx, y - cy);
      return [far(line.x1.baseVal.value, line.y1.baseVal.value), far(line.x2.baseVal.value, line.y2.baseVal.value)];
    });
    expect(ends[1]).toBeGreaterThan(ends[0]);
  });

  // R-0679
  test("projection moves the anxiety from parent to child within the one grow time", async ({ page }) => {
    await live(page);
    await page.locator(`#pbp .wire [data-act="jump"][data-i="${STEPS.findIndex((s) => s.name === "projection")}"]`).click();
    const grow = await page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--speed-grow")) * 1000);
    const scale = (at: number) =>
      page.evaluate((at) => {
        for (const a of document.getAnimations()) {
          a.pause();
          a.currentTime = at;
        }
        const s = (sel: string) => new DOMMatrix(getComputedStyle(document.querySelector(`#pbp .draw svg .fore ${sel}`)!).transform).a;
        return [s(".spk.s-out"), s(".spk.s-in")];
      }, at);
    // the change starts the moment the step comes up and is done one grow time later
    expect(await scale(0)).toEqual([1, expect.closeTo(0.12, 2)]);
    const done = await scale(grow);
    expect(done[0]).toBeCloseTo(0.12, 2);
    expect(done[1]).toBeCloseTo(1, 2);
  });

  // R-0679
  test("only the step's own marks move; everything carried from before is still", async ({ page }) => {
    await live(page);
    const moving: string[] = [];
    for (let i = 0; i < STEPS.length; i++) {
      await page.locator(`#pbp .wire [data-act="jump"][data-i="${i}"]`).click();
      const found = await page.evaluate(() => {
        const svg = document.querySelector("#pbp .draw svg")!;
        return [...svg.children]
          .filter((el) => !el.matches(".fore"))
          .flatMap((el) => [el, ...el.querySelectorAll("*")])
          .filter((el) => el.tagName.startsWith("animate") || el.getAnimations().some((a) => a.playState === "running"))
          .map((el) => el.closest("[data-mark], [data-bond]")?.getAttribute("data-mark") ?? el.getAttribute("class") ?? el.tagName);
      });
      if (found.length) moving.push(`${STEPS[i].name}: ${[...new Set(found)].join(", ")}`);
    }
    expect(moving).toEqual([]);
  });

  // R-0679
  test("every mark a step adds is already moving a tenth of a second after the step comes up", async ({ page }) => {
    await live(page);
    const late: string[] = [];
    for (let i = 0; i < STEPS.length; i++) {
      await page.locator(`#pbp .wire [data-act="jump"][data-i="${i}"]`).click();
      const looks = (at: number) =>
        page.evaluate((at) => {
          const svg = document.querySelector<SVGSVGElement>("#pbp .draw svg")!;
          svg.pauseAnimations();
          svg.setCurrentTime(at / 1000);
          for (const a of document.getAnimations()) {
            a.pause();
            a.currentTime = at;
          }
          const fore = svg.querySelector(".fore")!;
          const marks: Record<string, string> = {};
          for (const el of fore.querySelectorAll<SVGGraphicsElement>("line, polyline, polygon, path, circle, rect")) {
            if (el.closest("defs")) continue;
            const key = el.closest("[data-mark], [data-bond]")?.getAttribute("data-mark") ?? el.closest("[data-bond]")?.getAttribute("data-bond") ?? "?";
            const chain: string[] = [];
            for (let e: Element | null = el; e && e !== fore; e = e.parentElement) {
              const cs = getComputedStyle(e);
              chain.push(`${cs.transform}|${cs.opacity}|${cs.strokeDashoffset}`);
            }
            const anim = (n: "r" | "x1" | "x2") => ((el as unknown as Record<string, SVGAnimatedLength>)[n]?.animVal.value ?? 0).toFixed(2);
            marks[key] = (marks[key] ?? "") + chain.join("/") + anim("r") + anim("x1") + anim("x2") + (el.getAttribute("opacity") ?? "");
          }
          return marks;
        }, at);
      const [a, b] = [await looks(0), await looks(100)];
      Object.keys(a)
        .filter((k) => a[k] === b[k])
        .forEach((k) => late.push(`${STEPS[i].name}: ${k}`));
    }
    expect(late).toEqual([]);
  });

  // R-0679
  test("anxiety flickers in place, a slash pops again and again, and defined self shows both people", async ({ page }) => {
    await live(page);
    const at = (name: string) => page.locator(`#pbp .wire [data-act="jump"][data-i="${STEPS.findIndex((s) => s.name === name)}"]`).click();
    await at("anxiety up");
    expect(await page.locator("#pbp .draw svg .fore .spikes .spk").evaluate((g) => g.getAnimations().length)).toBe(0);
    await at("separated");
    expect(await page.locator("#pbp .draw svg .fore .slash.now").evaluate((l) => l.getAnimations()[0].effect!.getComputedTiming().iterations)).toBe(Infinity);
    await at("defined self");
    // Ivy, who holds her ground, lit and clearing; Rosa's storm around her
    await expect(page.locator('#pbp .draw svg .fore [data-mark="hl:5"]')).toHaveCount(1);
    expect(await page.locator("#pbp .draw svg .fore .mv-clear animate").first().getAttribute("repeatCount")).toBe("indefinite");
  });

  // R-0679
  test("the one who died is lit on their death step with the cross, grey after", async ({ page }) => {
    const svgs = await steps(page, STEPS.length);
    const i = STEPS.findIndex((s) => s.name === "death");
    await show(page, svgs[i]);
    // Harold
    const lit = page.locator('#pbp .draw svg > .fore [data-mark="hl:1"]');
    await expect(lit).toHaveCount(1);
    expect(await lit.evaluate((el) => getComputedStyle(el).stroke)).toBe(await paint(page, "--move"));
    await expect(page.locator("#pbp .draw svg > .fore .xd.now")).toHaveCount(1);
    await show(page, svgs[i + 1]);
    await expect(page.locator('#pbp .draw svg > .fore [data-mark="hl:1"]')).toHaveCount(0);
    await expect(page.locator('#pbp .draw svg [data-mark="hl:1"].was')).toHaveCount(1);
  });

  // R-0679
  test("projection rests in the child twice as long as it drains from the parent", async ({ page }) => {
    await live(page);
    await page.locator(`#pbp .wire [data-act="jump"][data-i="${STEPS.findIndex((s) => s.name === "projection")}"]`).click();
    const [loop, drained] = await page.evaluate(() => {
      const out = document.querySelector("#pbp .draw svg .fore .spk.s-out")!;
      const a = out.getAnimations()[0];
      const loop = a.effect!.getComputedTiming().duration as number;
      a.pause();
      let t = 0;
      for (; t < loop; t += 10) {
        a.currentTime = t;
        if (new DOMMatrix(getComputedStyle(out).transform).a <= 0.121) break;
      }
      return [loop, t];
    });
    expect(drained).toBeGreaterThanOrEqual(1300);
    expect((loop - drained) / drained).toBeCloseTo(2, 0);
    expect(Math.abs((loop - drained) / drained - 2)).toBeLessThan(0.2);
  });

  // R-0679
  test("fusion holds half as long after its ring as it did: 2.5s, not 5s", async ({ page }) => {
    await live(page);
    await page.locator(`#pbp .wire [data-act="jump"][data-i="${STEPS.findIndex((s) => s.name === "fusion")}"]`).click();
    const [loop, ringEnd] = await page.evaluate(() => {
      const ring = document.querySelector("#pbp .draw svg .fore .mv-shared animate")!;
      const loop = parseFloat(ring.getAttribute("dur")!);
      const times = ring.getAttribute("keyTimes")!.split(";").map(Number);
      return [loop, times[3] * loop];
    });
    // the bands' grow time and the ring's spread, then the hold
    expect(ringEnd).toBeCloseTo(1.4 + 1.65, 2);
    expect(loop - ringEnd).toBeCloseTo((8 - 3.05) / 2, 2);
  });

  // R-0679
  test("defined self's loud storm lasts a third of the board's, the rest unchanged", async ({ page }) => {
    await live(page);
    await page.locator(`#pbp .wire [data-act="jump"][data-i="${STEPS.findIndex((s) => s.name === "defined self")}"]`).click();
    const at = await page.evaluate(() => {
      const loud = document.querySelector("#pbp .draw svg .fore .stormlong")!;
      const a = loud.getAnimations()[0];
      const loop = a.effect!.getComputedTiming().duration as number;
      a.pause();
      const opacity = (t: number) => ((a.currentTime = t), +getComputedStyle(loud).opacity);
      let fades = 0;
      while (opacity(fades) >= 0.999) fades += 10;
      let gone = fades;
      while (opacity(gone) > 0.001) gone += 10;
      return { loop, fades, gone };
    });
    // loud for 2.56s (was 7.68s), dying over 0.72s, then calm for 3.6s
    expect(at.fades).toBeGreaterThan(2500);
    expect(at.fades).toBeLessThan(2620);
    expect(at.gone - at.fades).toBeGreaterThan(650);
    expect(at.gone - at.fades).toBeLessThan(800);
    expect(at.loop - at.gone).toBeCloseTo(3600, -2);
  });

  // R-0546
  test("someone not yet born keeps their place with no age in their shape", async ({ page }) => {
    const svgs = await steps(page, STEPS.length);
    const ages: string[] = [];
    for (const svg of svgs) {
      await show(page, svg);
      ages.push(...(await page.locator("#pbp .draw svg text.age").allTextContents()));
    }
    expect(ages.filter((a) => a.startsWith("-"))).toEqual([]);
    await show(page, svgs[0]);
    // Ivy, Leo and Sam are drawn before they were born, and Walter, born 1948, is 24 at the wedding
    expect(await page.locator("#pbp .draw svg .p").count()).toBe(7);
    expect(await page.locator('#pbp .draw svg .p[data-id="5"] text.age').count()).toBe(0);
    expect(await page.locator('#pbp .draw svg .p[data-id="3"] text.age').textContent()).toBe("24");
  });
});

test.describe("the Whitlock family's years apart", () => {
  test.use({ storageState: stateFor("whitlock") });

  // R-0679
  test("no mark runs over a name or a word", async ({ page }) => {
    expect(await over(page, await steps(page, 5))).toEqual([]);
  });

  // R-0679
  test("each step's lit marks are drawn over every grey one", async ({ page }) => {
    expect(await under(page, await steps(page, 5))).toEqual([]);
  });

  // R-0679
  test("Marcus and Delphine sit within four shape widths of each other", async ({ page }) => {
    await steps(page, 5);
    const gap = await apart(page, 3, 4);
    expect(gap).toBeLessThanOrEqual(COUPLE_MOST);
  });
});
