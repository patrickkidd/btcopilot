import { expect, test, type Page } from "@playwright/test";
import { stateFor, boxOf, step } from "./setup";
import { colours, cutInFrame, leastName, wordsOutside } from "./gate";
import { mockTurn } from "./turn";

/** The play-by-play drawer (R-0542, R-0562, R-0563). The `play` record holds
 * one moment per move in one stored cluster, and its session holds a play-by-
 * play about that cluster told in four snapshots. Explaining again is answered
 * with that stored case, so no coach turn is involved and it is deterministic.
 *
 * What the old chip walk tested is gone with it: chips stepping the board
 * (R-0170's first half) and the typed pacing of a play-through (R-0171) are
 * replaced by a drawer tapped through by hand. What R-0170 kept, the play
 * message stored with its kind and cluster, is what reopens the drawer here. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(400);
};

const drawer = (page: Page) => page.locator("#pbp");

/** The stored play message, the one the session already holds. */
const stored = (page: Page) => page.locator(".bub.coach[data-play]").last();

test.describe("the play-by-play drawer", () => {
  test.use({ storageState: stateFor("play") });

  // R-0170, R-0563
  test("the stored play message opens its case again on the first snapshot", async ({ page }) => {
    await settle(page);
    await expect(drawer(page)).toBeHidden();
    await stored(page).click();
    await expect(drawer(page)).toBeVisible();
    await expect.poll(() => step(page)).toBe("1 of 4");
    await expect(drawer(page).locator(".point")).toContainText("Ada moved toward Ben");
    await expect(drawer(page).locator(".path .here")).toHaveText("explain");
  });

  // R-0768
  test("comes down from the top like a drawer and goes back up, never in from the side", async ({ page }) => {
    await settle(page);
    await stored(page).click();
    await expect(drawer(page)).toBeVisible();
    // where it stands when put away, read with its slide held still
    const away = await drawer(page).evaluate((p) => {
      p.style.transition = "none";
      p.classList.remove("in");
      const m = new DOMMatrix(getComputedStyle(p).transform);
      const out = { x: m.e, y: m.f, h: p.getBoundingClientRect().height };
      p.classList.add("in");
      p.style.transition = "";
      return out;
    });
    expect(away.x).toBe(0);
    expect(away.y).toBeLessThanOrEqual(-away.h + 1);
  });

  // R-0590, R-0545, R-0563
  test("the teal cluster chip in the play message replays its stored telling, with no call to the coach", async ({ page }) => {
    await settle(page);
    const plays: string[] = [];
    page.on("request", (r) => {
      if (/\/app\/play$/.test(r.url())) plays.push(r.url());
    });
    const chip = stored(page).locator('button.chip[data-kind="cluster"]');
    await expect(chip).toHaveClass(/\bdata\b/);
    await expect(chip).toHaveText("The walk");
    await chip.click();
    await expect(drawer(page)).toBeVisible();
    await expect.poll(() => step(page)).toBe("1 of 4");
    await expect(drawer(page).locator(".point")).toContainText("Ada moved toward Ben");
    expect(plays).toEqual([]);
  });

  // R-0590, R-0576, R-0563
  test("the teal cluster chip of a play whose cluster has changed since tells it again through explain", async ({ page }) => {
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, async (route) => {
      const json = await (await route.fetch()).json();
      for (const cluster of json.clusters) cluster.digest = "changed since";
      await route.fulfill({ json });
    });
    await settle(page);
    const play = await page.evaluate(async () => {
      const sessions = await (await fetch("/app/sessions")).json();
      const { statements } = await (await fetch(`/app/sessions/${sessions[0].id}`)).json();
      return statements.find((s: { case: unknown }) => s.case);
    });
    const plays: string[] = [];
    await page.route(/\/app\/play(\?diagram_id=\d+)?$/, (route) => {
      plays.push(route.request().postData() ?? "");
      return route.fulfill({
        json: { statement: play.text, statement_id: play.id, kind: "play", cluster_id: play.cluster_id, case: play.case, digest: "changed since" },
      });
    });
    await stored(page).locator('button.chip[data-kind="cluster"]').click();
    await expect(drawer(page)).toBeVisible();
    await expect.poll(() => step(page)).toBe("1 of 4");
    expect(plays).toEqual([JSON.stringify({ cluster_id: play.cluster_id })]);
  });

  // R-0542, R-0540, R-0223
  test("reopened from its message, the path's years step opens that cluster", async ({ page }) => {
    await settle(page);
    await expect(page.locator("#path .here")).toHaveText("Timeline");
    await stored(page).click();
    const years = await drawer(page).locator('.path [data-step="1"]').innerText();
    await drawer(page).locator('.path [data-step="1"]').click();
    await expect(drawer(page)).toBeHidden();
    await expect(page.locator("#path .here")).toHaveText(years);
  });

  /** What the page shows once the drawer has gone: where the picture is, what
   * is selected in it, its caption and where the timeline's line sits. */
  const shown = async (page: Page) => {
    await expect(drawer(page)).toBeHidden();
    await page.waitForTimeout(400);
    return page.evaluate(() => ({
      path: document.querySelector("#path")!.textContent,
      on: [...document.querySelectorAll("#view .on")].map((e) => e.getAttribute("class")),
      caption: document.querySelector("#caption")!.textContent,
      line: document.querySelector("#view svg")!.getBoundingClientRect().toJSON(),
    }));
  };

  // R-0542, R-0540, R-0588, R-0023, R-0589
  test("the close button is teal in light and dark, sits in the top-right corner and goes back to the case's cluster, as the path's years step does", async ({ page }) => {
    await settle(page);
    await stored(page).click();
    await drawer(page).locator('.path [data-step="1"]').click();
    const byYears = await shown(page);
    await stored(page).click();
    const x = drawer(page).locator(".cardx");
    await expect(x).toHaveCount(1);
    await expect(x).toHaveText("×");
    const { light, dark } = await colours(page, x);
    expect(light.drawn).toBe(light.token);
    expect(dark.drawn).toBe(dark.token);
    expect(dark.token).not.toBe(light.token);
    const [b, p] = [await boxOf(x), await boxOf(drawer(page))];
    expect(p.x + p.width - (b.x + b.width)).toBeLessThanOrEqual(8);
    expect(b.y - p.y).toBeLessThanOrEqual(8);
    await x.click();
    expect(await shown(page)).toEqual(byYears);
  });

  // R-0545, R-0540
  test("opens with the path row, then the coach's point, then the snapshot line", async ({ page }) => {
    await settle(page);
    await stored(page).click();
    const tops = await drawer(page).evaluate((p) =>
      [".path", ".point", ".wire"].map((sel) => p.querySelector(sel)!.getBoundingClientRect().top),
    );
    expect(tops).toEqual([...tops].sort((a, b) => a - b));
    expect(new Set(tops).size).toBe(3);
  });

  // R-0113, R-0161
  test("is a drawing, with no legend, no table and no name for a symbol", async ({ page }) => {
    await settle(page);
    await stored(page).click();
    await expect(drawer(page).locator(".draw svg")).toBeVisible();
    await expect(drawer(page).locator("table")).toHaveCount(0);
    // the words are the people's own; the drawing names no symbol
    await expect(drawer(page).locator(".draw")).not.toContainText(/legend|toward|distance|cutoff|conflict|symptom|functioning|anxiety/i);
  });

  // R-0562, R-0071
  test("steps only when tapped, and Back and the years line step it too", async ({ page }) => {
    await settle(page);
    await stored(page).click();
    await page.waitForTimeout(3000);
    await expect.poll(() => step(page)).toBe("1 of 4");
    await drawer(page).locator('[data-act="next"]').click();
    await expect.poll(() => step(page)).toBe("2 of 4");
    await drawer(page).locator('[data-act="jump"][data-i="3"]').first().click();
    await expect.poll(() => step(page)).toBe("4 of 4");
    await expect(drawer(page).locator("p.ask")).toHaveText("Where was Cal in the year Ada stopped speaking to Ben?");
    await drawer(page).locator('[data-act="back"]').click();
    await expect.poll(() => step(page)).toBe("3 of 4");
    await expect(drawer(page).locator(".guess")).toHaveText(/^My guess: /);
  });

  // R-0546, R-0561
  test("the picture keeps its height from the first snapshot to the last", async ({ page }) => {
    await settle(page);
    await stored(page).click();
    const height = () => drawer(page).locator(".draw").evaluate((d) => d.getBoundingClientRect().height);
    const first = await height();
    for (let i = 1; i < 4; i++) {
      await drawer(page).locator('[data-act="next"]').click();
      expect(await height()).toBe(first);
    }
  });

  // R-0542, R-0563, R-0071
  test("the cluster's explain opens the told case straight away, never the board", async ({ page }) => {
    await settle(page);
    const statements = await page.evaluate(async () => {
      const sessions = await (await fetch("/app/sessions")).json();
      return (await (await fetch(`/app/sessions/${sessions[0].id}`)).json()).statements;
    });
    const play = statements.find((s: { case: unknown }) => s.case);
    await page.route(/\/app\/play(\?diagram_id=\d+)?$/, (route) =>
      route.fulfill({
        json: { statement: play.text, statement_id: play.id, kind: "play", cluster_id: play.cluster_id, case: play.case },
      }),
    );
    const cluster = page.locator('.ss-hit[data-target="cluster"]');
    if (await cluster.first().isVisible().catch(() => false)) await cluster.first().click();
    await page.locator("#cap-play").click();
    await expect(drawer(page)).toBeVisible();
    await expect(page.locator("#view .ss.board")).toHaveCount(0);
    await expect(drawer(page).locator(".path")).toHaveText(/^Timeline › .+ › explain$/);
    await expect.poll(() => step(page)).toBe("1 of 4");
    await drawer(page).locator('.path [data-step="1"]').click();
    await expect(drawer(page)).toBeHidden();
    await expect(page.locator("#path .here")).not.toHaveText("Timeline");
  });
});

test.describe("the drawer on a small phone", () => {
  test.use({ storageState: stateFor("whitlock"), viewport: { width: 375, height: 667 } });

  // R-0547, R-0558, R-0561
  test("stops shrinking at 13px labels, 36px shapes and a 20px margin, and scrolls instead", async ({ page }) => {
    await settle(page);
    await stored(page).click();
    await drawer(page).locator('[data-act="jump"]').last().click();
    const seen = await drawer(page).evaluate((p) => {
      const svg = p.querySelector<SVGSVGElement>(".draw svg")!;
      const top = p.querySelector(".draw")!.getBoundingClientRect().top;
      const drawn = [...svg.querySelectorAll(".p")].map((g) => g.getBoundingClientRect());
      const lv = p.querySelector(".lv")!;
      return {
        label: 13 * svg.getScreenCTM()!.a,
        shape: Math.min(...[...svg.querySelectorAll(".shape")].map((s) => s.getBoundingClientRect().width)),
        margin: Math.min(...drawn.map((r) => r.top)) - top,
        scrolls: lv.scrollHeight > lv.clientHeight,
      };
    });
    expect(seen.label).toBeGreaterThanOrEqual(13);
    expect(seen.shape).toBeGreaterThanOrEqual(36);
    expect(seen.margin).toBeGreaterThanOrEqual(20);
    expect(seen.scrolls).toBe(true);
  });
});

test.describe("an event's words at the drawing's edge", () => {
  test.use({ storageState: stateFor("whitlock") });

  // R-0558, R-0551, R-0744
  test("beside the rightmost person keep the family's margin from the drawing's side", async ({ page }) => {
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, async (route) => {
      const tl = await (await route.fetch()).json();
      const e = tl.events.find((e: { title?: string }) => e.title === "Moved out");
      const right = tl.people.find((p: { name: string }) => p.name === "Delphine");
      Object.assign(e, { title: "Started prerequisites at", person: right.id, person_name: right.name });
      await route.fulfill({ json: tl });
    });
    await settle(page);
    await stored(page).click();
    const words = drawer(page).locator(".draw .evw", { hasText: "Started prerequisites at" });
    await expect(words).toBeVisible();
    // the word pops in; measured once it has landed
    await page.waitForTimeout(400);
    // the ruled 24px at 393 wide, in the drawing's own units: a wide family
    // scrolls at that scale rather than shrinking (R-0759, R-0744). The word is
    // measured by its letters, not the halo painted round them.
    const [x, width, view] = await words.evaluate((t) => {
      const b = (t as SVGTextElement).getBBox();
      return [b.x, b.width, (t.ownerSVGElement as SVGSVGElement).viewBox.baseVal.width];
    });
    const margin = (24 * 360) / 393;
    expect(view - (x + width)).toBeGreaterThanOrEqual(margin - 1);
    expect(x).toBeGreaterThanOrEqual(margin - 1);
  });
});

test.describe("a new snapshot's marks", () => {
  test.use({ storageState: stateFor("whitlock") });

  // R-0557
  test("are at full strength within 300ms of the tap", async ({ page }) => {
    await settle(page);
    await stored(page).click();
    await page.waitForTimeout(600);
    await drawer(page).locator('[data-act="next"]').click();
    await page.waitForTimeout(300);
    const faint = await drawer(page).evaluate((p) =>
      [...p.querySelectorAll(".draw .now, .draw .pop")]
        .map((m) => Number(getComputedStyle(m).opacity))
        .filter((o) => o < 0.99),
    );
    expect(faint).toEqual([]);
  });
});

test.describe("a chip in a walk told the old way", () => {
  test.use({ storageState: stateFor("play") });

  // R-0501, R-0570, R-0543
  test("selects its event on the timeline, in place, and opens nothing", async ({
    page,
  }) => {
    await settle(page);
    const old = page.locator(".bub.coach[data-play]").first();
    await old.locator(".chip.data").first().click();
    // every event of this record is in the one cluster, so the chip opens the
    // cluster with the event picked and its title at the end of the path
    await expect(page.locator("#path .here")).toHaveText("Ada reached out");
    await expect(page.locator("#path .here.on")).toHaveCount(1);
    await expect(page.locator("#view rect.pill.on")).toHaveCount(1);
    await expect(drawer(page)).toBeHidden();
  });
});

test.describe("what the coach aims at with people and moves", () => {
  test.use({ storageState: stateFor("moves") });

  const aim = async (page: Page, view: Record<string, unknown>) => {
    await mockTurn(page, { statement: "Look at these.", statement_id: 9501, did: [{ type: "view", view }] });
    await settle(page);
    await page.locator("#composer").fill("Show me.");
    await page.locator("#send").click();
    await expect(drawer(page)).toBeVisible();
  };

  // R-0570, R-0075
  test("a sequence opens the play-by-play told by nobody: the events' own words, no point and no question", async ({ page }) => {
    await aim(page, { kind: "sequence", events: [20, 22, 23] });
    await expect.poll(() => step(page)).toBe("1 of 3");
    await expect(drawer(page).locator(".point")).toHaveCount(0);
    await drawer(page).locator('[data-act="jump"]').last().click();
    await expect(drawer(page).locator(".ask")).toHaveCount(0);
    await expect(page.locator(".bub.coach").last()).toContainText("Look at these.");
  });

  // R-0570, R-0076
  test("a triangle opens the play-by-play of the events between its people", async ({ page }) => {
    await aim(page, { kind: "triangle", persons: [1, 2, 3] });
    await expect(drawer(page).locator(".dots .dot.on")).toHaveCount(1);
    await expect(page.locator("#view .ss.board")).toHaveCount(0);
  });
});

/** The `play` record's timeline with its people swapped for a joined family:
 * his parents' children on the left, hers on the right, their daughter the
 * reader; each pair is [his side's child, her side's child] married to each
 * other; the cluster's events are about `about`, toward `toward`, and name
 * everyone, so the whole family is drawn. With `loop`, Hal is recorded as the
 * first couple's child, so he is his own forebear. */
/** A family of two joined lines laid into the record `tl`; the ids by name. */
const joined = (tl: Record<string, any>, pairs: [string, string][], sibs: number, about: string, toward: string, loop = false) => {
    let id = 9000;
    const ids: Record<string, number> = {};
    const people: Record<string, unknown>[] = [];
    const pair_bonds: Record<string, unknown>[] = [];
    const bond = (a: string, b: string) => {
      const pb = { id: id++, person_a: ids[a], person_b: ids[b], married: true };
      pair_bonds.push(pb);
      return pb.id;
    };
    const add = (k: string, gender: string, year: number, parents: number | null = null, primary = false) => {
      ids[k] = id++;
      people.push({ ...tl.people[0], id: ids[k], name: k, last_name: null, gender, primary, parents, birth: `${year}-01-01`, birth_event: null, death_event: null });
    };
    add("Hal", "male", 1920);
    add("Hope", "female", 1922);
    add("Walt", "male", 1921);
    add("Wren", "female", 1923);
    const his = bond("Hal", "Hope");
    const hers = bond("Walt", "Wren");
    pairs.forEach(([h, w], i) => {
      add(h, "male", 1950 + i, his);
      add(w, "female", 1951 + i, hers);
    });
    for (let i = 0; i < sibs; i++) {
      add(`Hs${i}`, i % 2 ? "male" : "female", 1940 + i, his);
      add(`Ws${i}`, i % 2 ? "female" : "male", 1940 + i, hers);
    }
    const pbs = pairs.map(([h, w]) => bond(h, w));
    add("Cleo", "female", 1975, pbs[0], true);
    if (loop) people.find((p) => p.name === "Hal")!.parents = pbs[0];
    for (const e of tl.events) Object.assign(e, { person: ids[about], person_name: about, spouse: null, child: null, relationshipTargets: [ids[toward]], relationshipTriangles: Object.values(ids) });
    Object.assign(tl, { people, pair_bonds });
    return ids;
  };

const joinedFamily = (pairs: [string, string][], sibs: number, about: string, toward: string, loop = false) =>
  async (route: import("@playwright/test").Route) => {
    const tl = await (await route.fetch()).json();
    joined(tl, pairs, sibs, about, toward, loop);
    await route.fulfill({ json: tl });
  };

test.describe("a family the row rules cannot place", () => {
  test.use({ storageState: stateFor("play") });

  const opened = async (page: Page, route: ReturnType<typeof joinedFamily>) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, route);
    await settle(page);
    await stored(page).click();
    await expect(drawer(page)).toBeVisible();
    return errors;
  };

  // R-0545
  // ruled 2026-10-04: laid out generation by generation instead of refused
  test("draws two couples each joining two families, everyone once", async ({ page }) => {
    const errors = await opened(page, joinedFamily([["Hugo", "Wanda"], ["Ivo", "Una"]], 0, "Hugo", "Wanda"));
    const draw = drawer(page).locator(".draw");
    await expect(draw.locator("svg")).toBeVisible();
    await expect(draw.locator(".none")).toHaveCount(0);
    const ids = await draw.locator("svg .p").evaluateAll((gs) => gs.map((g) => (g as SVGGElement).dataset.id));
    expect(ids).toHaveLength(9);
    expect(new Set(ids).size).toBe(ids.length);
    await expect.poll(() => step(page)).toBe("1 of 4");
    await drawer(page).locator('[data-act="next"]').click();
    await expect.poll(() => step(page)).toBe("2 of 4");
    await expect(draw.locator("svg")).toBeVisible();
    expect(errors).toEqual([]);
  });

  // R-0751
  test("draws someone recorded as their own forebear, the link closing the loop in the error colour with a note", async ({ page }) => {
    const errors = await opened(page, joinedFamily([["Hugo", "Wanda"]], 0, "Hugo", "Wanda", true));
    const draw = drawer(page).locator(".draw");
    await expect(draw.locator("svg")).toBeVisible();
    const ids = await draw.locator("svg .p").evaluateAll((gs) => gs.map((g) => (g as SVGGElement).dataset.id));
    expect(ids).toHaveLength(7);
    expect(new Set(ids).size).toBe(ids.length);
    await expect(draw.locator("svg path.cut")).toHaveCount(1);
    const note = (await draw.locator("svg text.cutn").allTextContents()).join(" ");
    expect(note).toBe("Hal is recorded as their own grandparent");
    const colour = await draw.locator("svg path.cut").evaluate((p) => getComputedStyle(p).stroke);
    const red = await page.evaluate(() => {
      const probe = document.createElementNS("http://www.w3.org/2000/svg", "path");
      probe.style.stroke = "var(--remove)";
      document.querySelector(".pbp svg")!.append(probe);
      const c = getComputedStyle(probe).stroke;
      probe.remove();
      return c;
    });
    expect(colour).toBe(red);
    await expect.poll(() => step(page)).toBe("1 of 4");
    const words = await drawer(page).locator(".scroll").innerText();
    await drawer(page).locator('[data-act="next"]').click();
    await expect.poll(() => step(page)).toBe("2 of 4");
    expect(await drawer(page).locator(".scroll").innerText()).not.toBe(words);
    expect(errors).toEqual([]);
  });
});

test.describe("a family wider than the phone", () => {
  test.use({ storageState: stateFor("play"), viewport: { width: 390, height: 844 } });

  // R-0547, R-0744, R-0749
  // re-ruled 2026-10-04, scroll below the floor
  test("keeps its least size, scrolls in its own frame and centres the step's person", async ({ page }) => {
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, joinedFamily([["Hugo", "Wanda"]], 6, "Hs5", "Hugo"));
    await settle(page);
    await stored(page).click();
    await expect(drawer(page)).toBeVisible();
    const seen = () =>
      drawer(page).evaluate((p) => {
        const draw = p.querySelector<HTMLElement>(".draw")!;
        const svg = draw.querySelector<SVGSVGElement>("svg")!;
        const name = [...svg.querySelectorAll<SVGGElement>(".pt")].find((g) => g.textContent?.includes("Hs5"))!;
        const r = svg.querySelector(`.p[data-id="${name.dataset.id}"]`)!.getBoundingClientRect();
        const f = draw.getBoundingClientRect();
        return {
          page: document.documentElement.scrollWidth,
          frame: draw.scrollWidth > draw.clientWidth,
          label: 13 * svg.getScreenCTM()!.a,
          inside: r.left >= f.left && r.right <= f.right,
        };
      });
    await page.waitForTimeout(800);
    const first = await seen();
    expect(first.page).toBeLessThanOrEqual(390);
    expect(first.frame).toBe(true);
    expect(first.label).toBeGreaterThanOrEqual(13);
    expect(first.inside).toBe(true);
    await drawer(page).locator('[data-act="next"]').click();
    await page.waitForTimeout(800);
    const next = await seen();
    expect(next.page).toBeLessThanOrEqual(390);
    expect(next.inside).toBe(true);
  });
});

/** The play record with a lifetime around its moves: births for its three
 * people and a fourth born after them, and a death, so the whole family has
 * births, a death and relationship shifts to step through. */
const lifetime = async (route: import("@playwright/test").Route) => {
  const tl = await (await route.fetch()).json();
  const [ada, ben, cal] = tl.people;
  const dot = { ...ada, id: 9100, name: "Dot", primary: false, gender: "female", parents: null, birth_event: null, death_event: null };
  const born: [Record<string, unknown>, string][] = [[ada, "1960-03-01"], [ben, "1958-07-01"], [cal, "1975-05-01"], [dot, "2001-09-01"]];
  const blank = { ...tl.events[0], relationship: null, relationshipTargets: [], relationshipTriangles: [], symptom: null, anxiety: null, functioning: null, title: null, description: null, spouse: null, codedInDiscussion: null, codedInStatement: null };
  born.forEach(([p, date], i) => {
    p.birth = date;
    tl.events.push({ ...blank, id: 9200 + i, kind: "birth", label: "Born", dateTime: date, person: null, child: p.id, person_name: p.name, sentence: `${p.name} was born` });
  });
  tl.events.push({ ...blank, id: 9300, kind: "death", label: "Died", dateTime: "2010-02-01", person: ben.id, child: null, person_name: ben.name, sentence: "Ben died" });
  tl.people.push(dot);
  await route.fulfill({ json: tl });
};

const watched = (page: Page) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("requestfailed", (r) => errors.push(`failed ${r.url()}`));
  page.on("response", (r) => r.status() >= 400 && errors.push(`${r.status()} ${r.url()}`));
  return errors;
};

const sideways = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);

test.describe("the whole family stepped through dates", () => {
  test.use({ storageState: stateFor("play") });

  // R-0755
  test("offers its Family button at the end of the row when nothing is picked, next to the lists", async ({ page }) => {
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, lifetime);
    await settle(page);
    const family = page.locator("#caption #cap-family");
    await expect(family).toHaveText("Family");
    await expect(family).toBeEnabled();
    const row = await page.locator("#caption").boundingBox();
    const at = (await family.boundingBox())!;
    const list = page.locator("#caption #menu-open");
    if (await list.count()) {
      const by = (await list.boundingBox())!;
      expect(at.x + at.width).toBeLessThanOrEqual(by.x);
      expect(by.x - (at.x + at.width)).toBeLessThan(24);
    } else expect(row!.x + row!.width - (at.x + at.width)).toBeLessThan(24);
  });

  // R-0755
  test("has no Family button on a record with no dated birth, couple, death or relationship shift", async ({ page }) => {
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, async (route) => {
      const tl = await (await route.fetch()).json();
      tl.events.forEach((e: Record<string, unknown>) => Object.assign(e, { kind: "noted", relationship: null, spouse: null, title: e.title ?? "Noted" }));
      await route.fulfill({ json: tl });
    });
    await settle(page);
    await expect(page.locator("#caption .cta")).toBeVisible();
    await expect(page.locator("#caption #cap-family")).toHaveCount(0);
  });

  // R-0742, R-0755, R-0756, R-0775
  test("steps on to the record today and back through its history, the not yet born faded, and browser back returns to the timeline", async ({ page }) => {
    const errors = watched(page);
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, lifetime);
    await settle(page);
    await page.locator("#cap-family").click();
    await expect(drawer(page)).toBeVisible();
    await expect(page).toHaveURL(/\/app\/family$/);
    await expect(drawer(page).locator(".path")).toHaveText("Timeline › Family");
    await expect(drawer(page).locator(".dots")).toHaveCount(0);
    const next = drawer(page).locator('[data-act="next"]');
    while (await next.isEnabled()) await next.click();
    const top = drawer(page).locator(".when");
    await expect(top).toHaveText("Ben died");
    await expect(drawer(page).locator(".wire .wlab")).toHaveText("February 2010");
    const picture = () => drawer(page).locator(".draw").innerHTML();
    const dot = drawer(page).locator('.draw .p[data-id="9100"]');
    await expect(dot).not.toHaveClass(/\byet\b/);
    let was = await picture();
    const tap = async (act: string, said: string) => {
      const before = await top.innerText();
      await drawer(page).locator(`[data-act="${act}"]`).click();
      if (said) await expect(top).toHaveText(said);
      else await expect(top).not.toHaveText(before);
      const now = await picture();
      expect(now).not.toBe(was);
      was = now;
    };
    await tap("back", "Dot was born");
    // the last move before Dot was born
    await tap("back", "");
    await expect(dot).toHaveClass(/\byet\b/);
    expect(Number(await dot.evaluate((g) => getComputedStyle(g).opacity))).toBeCloseTo(0.3);
    await tap("next", "Dot was born");
    await expect(dot).not.toHaveClass(/\byet\b/);
    expect(await sideways(page)).toBe(false);
    await page.goBack();
    await expect(drawer(page)).toBeHidden();
    await expect(page).toHaveURL(/\/app\/$/);
    expect(errors).toEqual([]);
  });
  // R-0742
  test("keeps its picture still while the words above it run to three lines, and its first date whole inside the frame", async ({ page }) => {
    const errors = watched(page);
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, async (route) => {
      const tl = await (await route.fetch()).json();
      const [ada, ben] = tl.people;
      const blank = { ...tl.events[0], relationshipTargets: [], relationshipTriangles: [], symptom: null, anxiety: null, functioning: null, spouse: null, child: null, codedInDiscussion: null, codedInStatement: null };
      ada.birth = "1940-02-01";
      tl.events.push({ ...blank, id: 9400, kind: "birth", label: "Born", dateTime: ada.birth, relationship: null, person: null, child: ada.id, title: null, description: null, person_name: ada.name, sentence: `${ada.name} was born` });
      const long = "started calling every night after the move and kept on through the winter, the spring and the long summer that followed it";
      tl.events.push({ ...blank, id: 9401, kind: "shift", label: "Toward", dateTime: "1941-03-01", relationship: "toward", relationshipTargets: [ben.id], person: ada.id, title: long, description: long, person_name: ada.name, sentence: long });
      await route.fulfill({ json: tl });
    });
    await settle(page);
    await page.locator("#cap-family").click();
    await expect(drawer(page)).toBeVisible();
    // the drawer comes down from the top (R-0768): read the picture once it has landed
    await drawer(page).evaluate((p) => Promise.all(p.getAnimations().map((a) => a.finished)));
    const top = drawer(page).locator(".when");
    const at = async () => (await boxOf(drawer(page).locator(".draw")))!.y;
    const still = await at();
    const back = drawer(page).locator('[data-act="back"]');
    while (await back.isEnabled()) {
      const before = await top.innerText();
      await back.click();
      await expect(top).not.toHaveText(before);
      expect(await at()).toBe(still);
    }
    await expect(drawer(page).locator(".wire .wlab")).toHaveText("February 1940");
    const [label, wire] = [await boxOf(drawer(page).locator(".wire .wlab")), await boxOf(drawer(page).locator(".wire svg"))];
    expect(label!.x).toBeGreaterThanOrEqual(wire!.x);
    expect(label!.x + label!.width).toBeLessThanOrEqual(wire!.x + wire!.width);
    await drawer(page).locator('[data-act="next"]').click();
    await expect(top).toContainText("started calling every night");
    expect(await at()).toBe(still);
    expect(errors).toEqual([]);
  });
});


test.describe("the whole family wider than the phone", () => {
  test.use({ storageState: stateFor("play"), viewport: { width: 390, height: 844 } });

  // R-0744, R-0742
  test("scrolls inside its own frame, never the page", async ({ page }) => {
    const errors = watched(page);
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, joinedFamily([["Hugo", "Wanda"]], 6, "Hs5", "Hugo"));
    await settle(page);
    await page.locator("#cap-family").click();
    await expect(drawer(page)).toBeVisible();
    const frame = drawer(page).locator(".draw");
    expect(await frame.evaluate((d) => d.scrollWidth > d.clientWidth)).toBe(true);
    expect(await sideways(page)).toBe(false);
    await drawer(page).locator('[data-act="next"]').click();
    expect(await sideways(page)).toBe(false);
    expect(errors).toEqual([]);
  });

  // R-0744, R-0742
  test("glides its frame to each step's person on Back and Next", async ({ page }) => {
    const errors = watched(page);
    let ids: Record<string, number> = {};
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, async (route) => {
      const tl = await (await route.fetch()).json();
      ids = joined(tl, [["Hugo", "Wanda"]], 6, "Hs5", "Hugo");
      const blank = { ...tl.events[0], relationship: null, relationshipTargets: [], relationshipTriangles: [], symptom: null, anxiety: null, functioning: null, title: null, description: null, person: null, spouse: null };
      // two births, and two shifts that light no one
      ["Hs0", "Ws5", "Hs1", "Ws4"].forEach((k, i) =>
        tl.events.push(
          i % 2
            ? { ...blank, id: 9500 + i, kind: "shift", label: "Cut off", dateTime: `203${i}-01-01`, person: ids[k], relationship: "cutoff", relationshipTargets: [ids.Hugo], title: "Cut off", description: "Left home", person_name: k, sentence: `${k} left home` }
            : { ...blank, id: 9500 + i, kind: "birth", label: "Born", dateTime: `203${i}-01-01`, child: ids[k], person_name: k, sentence: `${k} was born` },
        ),
      );
      await route.fulfill({ json: tl });
    });
    await settle(page);
    await page.locator("#cap-family").click();
    await expect(drawer(page)).toBeVisible();
    const frame = drawer(page).locator(".draw");
    expect(await frame.evaluate((d) => d.scrollWidth > d.clientWidth)).toBe(true);
    const inFrame = (id: number) =>
      page.evaluate((id) => {
        const d = document.querySelector(".pbp .draw")!.getBoundingClientRect();
        const p = document.querySelector(`.pbp .draw .p[data-id="${id}"] .shape`)!.getBoundingClientRect();
        return p.left >= d.left && p.right <= d.right;
      }, id);
    const shown = async (name: string, what: string) => {
      await expect(drawer(page).locator(".when")).toContainText(`${name} ${what}`);
      await expect.poll(() => inFrame(ids[name])).toBe(true);
    };
    const next = drawer(page).locator('[data-act="next"]');
    while (await next.isEnabled()) await next.click();
    await shown("Ws4", "left home");
    for (const [name, what] of [["Hs1", "was born"], ["Ws5", "left home"], ["Hs0", "was born"]]) {
      await drawer(page).locator('[data-act="back"]').click();
      await shown(name, what);
    }
    await drawer(page).locator('[data-act="next"]').click();
    await shown("Ws5", "left home");
    expect(await sideways(page)).toBe(false);
    expect(errors).toEqual([]);
  });
});

/** The `case-report-dense` record: a family many phones wide, the step's
 * person far from either end. */
test.describe("the whole family of a family many phones wide", () => {
  test.use({ storageState: stateFor("case-report-dense"), viewport: { width: 393, height: 852 } });

  // R-0759, R-0744, R-0749, R-0766
  test("opens with the step's person in the frame, names at 13px or more and short, every word inside what the frame scrolls to", async ({ page }) => {
    const errors = watched(page);
    await settle(page);
    await page.locator("#cap-family").click();
    await expect(drawer(page)).toBeVisible();
    // opened, not glided: the frame is already on the step's person
    const at = await drawer(page).evaluate((p) => {
      const draw = p.querySelector<HTMLElement>(".draw")!;
      const shape = draw.querySelector(`.p[data-id="${draw.dataset.who}"] .shape`)!.getBoundingClientRect();
      const f = draw.getBoundingClientRect();
      return { wide: draw.scrollWidth > 4 * draw.clientWidth, inside: shape.left >= f.left && shape.right <= f.right };
    });
    expect(at).toEqual({ wide: true, inside: true });
    // R-0766: everyone is named as briefly as the Pembertons are, so no name takes more width than the longest of the record's own people's
    const names = await drawer(page).locator(".draw .pt .lbn").allTextContents();
    expect(names.filter((n) => n.length > "Francis-Xavier".length)).toEqual([]);
    expect(await leastName(page, "#pbp .draw svg")).toBeGreaterThanOrEqual(13);
    expect(await wordsOutside(page, "#pbp .draw svg")).toEqual([]);
    expect(await sideways(page)).toBe(false);
    expect(errors).toEqual([]);
  });
});

/** The `everymark` record's play-by-play is wider than the phone at every step. */
test.describe("a play-by-play wider than the phone", () => {
  test.use({ storageState: stateFor("everymark"), viewport: { width: 393, height: 852 } });

  // R-0759, R-0744
  test("keeps every word inside what its frame scrolls to, at every step", async ({ page }) => {
    await settle(page);
    await stored(page).click();
    await expect(drawer(page)).toBeVisible();
    const draw = drawer(page).locator(".draw");
    expect(await draw.evaluate((d) => d.scrollWidth > d.clientWidth)).toBe(true);
    for (;;) {
      expect(await wordsOutside(page, "#pbp .draw svg")).toEqual([]);
      const next = drawer(page).locator('[data-act="next"]:not([disabled])');
      if (!(await next.count())) break;
      await next.click();
    }
  });
});

/** The `everymark` record's play-by-play, each step settled: the glide landed
 * and the step's people slid to their places. */
for (const viewport of [{ width: 393, height: 852 }, { width: 1280, height: 800 }])
  test.describe(`a play-by-play at ${viewport.width} wide`, () => {
    test.use({ storageState: stateFor("everymark"), viewport });

    // R-0759, R-0744
    test("opens each step with its people's names and ages whole inside the frame, or the step's person's when they reach wider", async ({ page }, info) => {
      test.skip(info.project.name !== "phone", "the size is the describe's own");
      await settle(page);
      await stored(page).click();
      await expect(drawer(page)).toBeVisible();
      const draw = drawer(page).locator(".draw");
      const steps: string[] = [];
      for (;;) {
        await draw.evaluate((d) => d.querySelector<SVGSVGElement>("svg")!.setCurrentTime(10));
        let last = -1;
        await expect.poll(async () => {
          const at = await draw.evaluate((d) => d.scrollLeft);
          const still = at === last;
          last = at;
          return still;
        }, { intervals: [400] }).toBe(true);
        const who = (await draw.getAttribute("data-who"))!;
        const lit = await draw.evaluate((d) => [...d.querySelectorAll<SVGElement>('.hl.now[data-mark^="hl:"]')].map((m) => m.dataset.mark!.slice(3)));
        const seen = await cutInFrame(page, "#pbp .draw", [...new Set([who, ...lit])]);
        const at = (await step(page)) ?? "";
        expect(seen.cut[who], `${at}: the step's person`).toBeUndefined();
        if (seen.fits) expect(seen.cut, at).toEqual({});
        steps.push(at);
        const next = drawer(page).locator('[data-act="next"]:not([disabled])');
        if (!(await next.count())) break;
        await next.click();
      }
      expect(steps.length).toBeGreaterThan(1);
      expect(await sideways(page)).toBe(false);
    });
  });

/** Patrick's own way through on a phone, on the Pemberton stand-in family
 * (`everymark`): the drawer opened from its button or its message and stepped
 * with Next, never opened straight on a step, and what moves watched over
 * seconds rather than read off the markup. */
test.describe("stepped by hand on a phone", () => {
  test.use({ storageState: stateFor("everymark"), viewport: { width: 393, height: 852 } });

  const family = async (page: Page) => {
    await settle(page);
    await page.locator("#cap-family").click();
    await expect(drawer(page)).toBeVisible();
  };
  const played = async (page: Page) => {
    await settle(page);
    await stored(page).click();
    await expect(drawer(page)).toBeVisible();
  };
  const nextTo = async (page: Page, words: string) => {
    for (let i = 0; i < 60 && !(await drawer(page).innerText()).includes(words); i++) {
      await drawer(page).locator('[data-act="next"]').click();
      await page.waitForTimeout(150);
    }
    await expect(drawer(page)).toContainText(words);
  };

  // R-0775
  test("the Family button opens on the first date holding more than births, Harold and June's marriage", async ({ page }) => {
    await family(page);
    await expect(drawer(page).locator(".when")).toHaveText("Harold and June married");
    await expect(drawer(page).locator(".wire .wlab")).toHaveText("June 1946");
  });

  /** Where each moved person stands in the drawing, sampled over seven seconds. */
  const watch = (page: Page) =>
    page.evaluate(async () => {
      const svg = () => document.querySelector("#pbp .draw svg")!.getBoundingClientRect();
      const at = () => [...document.querySelectorAll("#pbp .draw svg .slid .shape")].map((s) => Math.round(s.getBoundingClientRect().x - svg().x));
      const seen: number[][] = [];
      for (let k = 0; k < 28; k++) {
        seen.push(at());
        await new Promise((r) => setTimeout(r, 250));
      }
      return seen;
    });

  for (const [view, open, words] of [
    ["the Family view", family, "Leo sided with Rosa"],
    ["the Family view", family, "Leo stayed out of their fight"],
    ["the play-by-play", played, "Inside: Leo sided with Rosa"],
    ["the play-by-play", played, "Outside: Leo stayed out of it"],
  ] as const)
    // R-0777, R-0763
    test(`${view} moves the three people of "${words}" when stepped to with Next, and moves them again and again`, async ({ page }) => {
      await open(page);
      await nextTo(page, words);
      const seen = await watch(page);
      expect(seen[0].length).toBeGreaterThan(0);
      const xs = seen.map((s) => s[0]);
      // out from home, home again at the next loop's start, and out again
      const out = (i: number) => Math.abs(xs[i] - xs[0]) > 20;
      const first = xs.findIndex((_, i) => out(i));
      const back = xs.findIndex((x, i) => i > first && Math.abs(x - xs[0]) <= 3);
      expect(first).toBeGreaterThan(0);
      expect(back).toBeGreaterThan(first);
      expect(xs.some((_, i) => i > back && out(i))).toBe(true);
    });

  /** The furthest a step's field rings reach, against its person's width, on the screen. */
  const reach = (page: Page) =>
    page.evaluate(() => {
      const ring = [...document.querySelectorAll<SVGCircleElement>("#pbp .draw svg .mvk.now circle.fld")].find((c) => c.querySelector("animate"))!;
      const r = Math.max(...ring.querySelector('animate[attributeName="r"]')!.getAttribute("values")!.split(";").map(Number));
      const m = ring.getScreenCTM()!;
      const harold = document.querySelector('#pbp .draw svg .p[data-id="1"] .shape')!.getBoundingClientRect();
      return { ring: r * Math.hypot(m.a, m.b), person: harold.width, width: parseFloat(getComputedStyle(ring).strokeWidth) * Math.hypot(m.a, m.b) };
    });

  // R-0776, R-0765
  test("Walter's cutoff runs Harold's rings out as far against him in the Family view as in the play-by-play, past the wall", async ({ page }) => {
    await played(page);
    await nextTo(page, "Cutoff:");
    const told = await reach(page);
    await family(page);
    await nextTo(page, "Walter stopped calling his father");
    const whole = await reach(page);
    expect(told.ring / told.person).toBeCloseTo(whole.ring / whole.person, 1);
    expect(told.ring / told.person).toBeGreaterThan(3);
    expect(told.width / told.person).toBeCloseTo(whole.width / whole.person, 2);
  });
});

/** A family many phones wide, stepped with Next as Patrick steps it. */
test.describe("the frame's travel to a step's people", () => {
  test.use({ storageState: stateFor("case-report-dense"), viewport: { width: 393, height: 852 } });

  // R-0778
  test("sets off from where the frame stood, eases to exactly where it lands without passing it, and takes most of a second", async ({ page }) => {
    await settle(page);
    await page.locator("#cap-family").click();
    await expect(drawer(page)).toBeVisible();
    const trips: number[][][] = [];
    for (const act of ["next", "next", "back", "next"]) {
      const button = drawer(page).locator(`[data-act="${act}"]`);
      if (!(await button.isEnabled())) continue;
      await page.evaluate(() => {
        const d = document.querySelector<HTMLElement>("#pbp .draw")!;
        const seen: number[][] = [[0, d.scrollLeft]];
        (window as unknown as { seen: number[][] }).seen = seen;
        const t0 = performance.now();
        const tick = () => {
          seen.push([performance.now() - t0, document.querySelector<HTMLElement>("#pbp .draw")!.scrollLeft]);
          if (performance.now() - t0 < 1800) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      });
      await button.click();
      await page.waitForTimeout(1900);
      trips.push(await page.evaluate(() => (window as unknown as { seen: number[][] }).seen));
    }
    const moving = trips.filter((t) => Math.abs(t.at(-1)![1] - t[0][1]) > 40);
    expect(moving.length).toBeGreaterThan(0);
    for (const t of moving) {
      const [from, to] = [t[0][1], t.at(-1)![1]];
      const dir = Math.sign(to - from);
      // never back to the start of the drawing, never past where it lands
      expect(t.every(([, x]) => dir * (x - from) >= -1 && dir * (to - x) >= -1)).toBe(true);
      // each frame on from the last, never back
      expect(t.slice(1).every(([, x], i) => dir * (x - t[i][1]) >= -1)).toBe(true);
      const landed = t.find(([, x]) => Math.abs(x - to) <= 1)![0];
      expect(landed).toBeGreaterThan(700);
    }
  });
});
