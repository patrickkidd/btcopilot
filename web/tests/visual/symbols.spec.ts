import { expect, test, type Page } from "@playwright/test";
import { drawings, freeze } from "./drawings";

/** How each move looks and moves over its loop, read off the real `moves.ts`
 * and `theme.css` as the browser computes them: colours, what is on screen at
 * an instant, and how long each animation runs. No pixels are compared. */

const url = drawings();

test.beforeEach(async ({ page }) => {
  // the drawings do not change with the window, so one size is the story
  test.skip(test.info().project.name !== "phone");
  await page.goto(url);
});

/** A colour the theme names, as the browser writes a computed colour. */
const token = (page: Page, name: string) =>
  page.evaluate((variable) => {
    const probe = document.createElement("div");
    probe.style.color = `var(${variable})`;
    document.body.append(probe);
    const colour = getComputedStyle(probe).color;
    probe.remove();
    return colour;
  }, name);

/** One computed property of the first element a selector finds. */
const computed = (page: Page, selector: string, property: string) =>
  page.evaluate(
    ([sel, prop]) => getComputedStyle(document.querySelector(sel)!).getPropertyValue(prop),
    [selector, property],
  );

/** How visible an element is once every ancestor's opacity is counted. */
const seen = (page: Page, selector: string) =>
  page.evaluate((sel) => {
    const all = [...document.querySelectorAll(sel)];
    return all.map((el) => {
      let opacity = 1;
      for (let at: Element | null = el; at; at = at.parentElement)
        opacity *= Number(getComputedStyle(at).opacity);
      const box = el.getBoundingClientRect();
      return { opacity, drawn: box.width > 0 || box.height > 0 };
    });
  }, selector);

/** The length of every animation under a selector, CSS and SVG alike, in ms. */
const lengths = (page: Page, selector: string) =>
  page.evaluate((sel) => {
    const root = document.querySelector(sel)!;
    const css = root
      .getAnimations({ subtree: true })
      .map((a) => Number(a.effect!.getTiming().duration));
    const svg = [...root.querySelectorAll("animate, animateTransform")].map(
      (a) => parseFloat(a.getAttribute("dur")!) * 1000,
    );
    return [...css, ...svg];
  }, selector);

const LOOP = [0, 1000, 2400, 4000, 5200, 6800, 7900];

// R-0114
test("conflict buzzes both people and pulses its sparks faster than once a second", async ({
  page,
}) => {
  for (const sel of ["#m-conflict .body.mover", '#m-conflict .node[data-person="2"] .body', "#m-conflict .mv-sparks"]) {
    const times = await lengths(page, sel);
    expect(times.length).toBeGreaterThan(0);
    for (const ms of times) expect(ms).toBeLessThan(1000);
  }
});

// R-0115
test("the toward arrow shows while the mover walks and is gone once they arrive", async ({
  page,
}) => {
  await freeze(page, 2500);
  expect(Number(await computed(page, "#m-toward .tarrow", "opacity"))).toBe(1);
  for (const at of [5500, 7500]) {
    await freeze(page, at);
    expect(Number(await computed(page, "#m-toward .tarrow", "opacity"))).toBe(0);
  }
});

// R-0116
test("once the wall is up, the other's field stays on screen behind it and never fades", async ({
  page,
}) => {
  for (const at of [5000, 7000, 9900]) {
    await freeze(page, at);
    const walled = await page.evaluate(() =>
      [...document.querySelectorAll("#m-cutoff .fld.postA")].map((el) =>
        Number(getComputedStyle(el).opacity),
      ),
    );
    expect(walled).toEqual([1, 1, 1]);
  }
});

// R-0117
test("the one who cuts off never disappears", async ({ page }) => {
  for (const at of [0, 2500, 5000, 7500, 9900]) {
    await freeze(page, at);
    for (const sel of ['#m-cutoff .node[data-person="1"] .disc', '#m-distance .node[data-person="1"] .disc'])
      expect(await seen(page, sel)).toEqual([{ opacity: 1, drawn: true }]);
  }
});

// R-0120
test("once the mover has walked out, no heat is left on the outside move", async ({ page }) => {
  for (const at of [6000, 9000]) {
    await freeze(page, at);
    for (const mark of await seen(page, "#m-outside .mv-tension")) expect(mark.opacity).toBe(0);
  }
});

// R-0122
test("defined self is drawn in ink while battered and turns green", async ({ page }) => {
  const disc = '#m-defined-self .node[data-person="1"] .disc';
  await freeze(page, 1000);
  expect(await computed(page, disc, "stroke")).toBe(await token(page, "--ink"));
  await freeze(page, 5000);
  expect(await computed(page, disc, "stroke")).toBe(await token(page, "--move"));
});

// R-0122
test("defined self turns the same green every other move is drawn in", async ({ page }) => {
  await freeze(page, 5000);
  const green = await computed(page, '#m-defined-self .node[data-person="1"] .disc', "stroke");
  expect(green).toBe(await computed(page, "#m-toward .mv-arrow", "stroke"));
  expect(green).toBe(await computed(page, "#m-conflict .mv-spark", "stroke"));
});

// R-0122
test("defined self turns green only once the one who acts holds still", async ({ page }) => {
  test.skip(true, "unbuilt ruling, needs a design: when defined self turns green against the loop the other is battered on");
  // the ratified loops run the colour on 8 seconds and the battering on 12
  const disc = '#m-defined-self .node[data-person="1"] .disc';
  const body = '#m-defined-self .node[data-person="1"] .body';
  const green = await token(page, "--move");
  for (let at = 0; at < 12000; at += 100) {
    await freeze(page, at);
    if ((await computed(page, disc, "stroke")) !== green) continue;
    expect(await computed(page, body, "transform")).toMatch(/^(none|matrix\(1, 0, 0, 1, 0, 0\))$/);
  }
});

// R-0149, R-0122
test("after defined self turns green the other stays stirred up for a while", async ({ page }) => {
  await freeze(page, 5000);
  expect(await computed(page, '#m-defined-self .node[data-person="1"] .disc', "stroke")).toBe(
    await token(page, "--move"),
  );
  expect(Number(await computed(page, "#m-defined-self .stormlong", "opacity"))).toBe(1);
  expect(Number(await computed(page, "#m-defined-self .stormcalm", "opacity"))).toBe(0);
});

// R-0149
test("the other settles later in the same loop", async ({ page }) => {
  await freeze(page, 9000);
  expect(Number(await computed(page, "#m-defined-self .stormlong", "opacity"))).toBe(0);
  expect(Number(await computed(page, "#m-defined-self .stormcalm", "opacity"))).toBe(1);
  expect(
    await computed(page, '#m-defined-self .node[data-person="2"] .body', "transform"),
  ).toMatch(/^(none|matrix\(1, 0, 0, 1, 0, 0\))$/);
});

// R-0126
test("functioning fades back to green by the end of its loop", async ({ page }) => {
  const green = await token(page, "--move");
  await freeze(page, 4000);
  expect(await computed(page, "#m-functioning-down .mv-func", "stroke")).not.toBe(green);
  await freeze(page, 7900);
  expect(await computed(page, "#m-functioning-down .mv-func", "stroke")).toBe(green);
  expect(await computed(page, "#m-functioning-up .mv-func", "stroke")).toBe(green);
});

// R-0127
test("every move's marks are drawn in the one green", async ({ page }) => {
  await freeze(page, 0);
  const green = await token(page, "--move");
  const colours = await page.evaluate(() =>
    [...document.querySelectorAll(".cell:not(#m-triangle-board) .cast *")]
      .filter((el) => /(^| )(mv-|fld|tipfill)/.test(el.getAttribute("class") ?? "") || el.closest(".mv-flank"))
      .filter((el) => el.tagName !== "g")
      .map((el) => {
        const style = getComputedStyle(el);
        return style.stroke !== "none" ? style.stroke : style.fill;
      }),
  );
  expect(colours.length).toBeGreaterThan(40);
  expect(new Set(colours)).toEqual(new Set([green]));
});

// R-0127
test("every move's animation runs the same length", async ({ page }) => {
  test.skip(true, "unbuilt ruling, needs a design: the one loop length every move animation runs");
  // the ratified loops run 8, 10 and 12 seconds
  const loops = new Set<number>();
  for (const cell of await page.locator(".cell:not(#m-triangle-board)").all()) {
    const id = await cell.getAttribute("id");
    for (const ms of await lengths(page, `#${id} .cast`)) if (ms >= 5000) loops.add(ms);
  }
  expect([...loops]).toHaveLength(1);
});

// R-0163
test("the over- and underfunctioning arrows are on screen for the whole loop", async ({
  page,
}) => {
  for (const at of LOOP) {
    await freeze(page, at);
    for (const cell of ["#m-overfunctioning", "#m-underfunctioning"])
      expect(await seen(page, `${cell} .mv-flank`)).toEqual([
        { opacity: 1, drawn: true },
        { opacity: 1, drawn: true },
      ]);
  }
});
