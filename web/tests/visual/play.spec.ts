import { expect, test, type Page } from "@playwright/test";
import { stateFor, boxOf, step } from "./setup";
import { colours } from "./gate";
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

  // R-0558, R-0551
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
    const [w, d] = [await boxOf(words), await boxOf(drawer(page).locator(".draw svg"))];
    // the ruled 24px at 393 wide, at this phone's width
    const margin = (24 * d.width) / 393;
    expect(d.x + d.width - (w.x + w.width)).toBeGreaterThanOrEqual(margin - 1);
    expect(w.x - d.x).toBeGreaterThanOrEqual(margin - 1);
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
const joinedFamily = (pairs: [string, string][], sibs: number, about: string, toward: string, loop = false) =>
  async (route: import("@playwright/test").Route) => {
    const tl = await (await route.fetch()).json();
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
