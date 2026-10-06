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

/** A tap on someone in the Family view, in the middle of their shape, swiped
 * into sight first as a finger would, and the frame given time to move. */
const tapPerson = async (page: Page, id: number | string) => {
  const shape = drawer(page).locator(`.draw svg .p[data-id="${id}"] .shape`);
  await shape.scrollIntoViewIfNeeded();
  const b = (await shape.boundingBox())!;
  await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2);
  await page.waitForTimeout(700);
};

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

  // R-0782
  test("keeps Next in one place, so Next tapped again and again at one spot steps on each time", async ({ page }) => {
    await settle(page);
    await stored(page).click();
    await expect.poll(() => step(page)).toBe("1 of 4");
    await page.waitForTimeout(600);
    const next = (await drawer(page).locator('[data-act="next"]').boundingBox())!;
    for (const at of ["2 of 4", "3 of 4", "4 of 4"]) {
      await page.mouse.click(next.x + next.width / 2, next.y + next.height / 2);
      await expect.poll(() => step(page)).toBe(at);
      const again = (await drawer(page).locator('[data-act="next"]').boundingBox())!;
      expect([Math.round(again.x), Math.round(again.y)]).toEqual([Math.round(next.x), Math.round(next.y)]);
    }
  });

  // R-0768
  test("lands where it rests without passing it and settling back", async ({ page }) => {
    await settle(page);
    await page.evaluate(() => {
      const seen: number[] = [];
      (window as unknown as { SEEN: number[] }).SEEN = seen;
      const read = () => {
        const p = document.querySelector<HTMLElement>("#pbp");
        if (p && !p.hidden) seen.push(new DOMMatrix(getComputedStyle(p).transform).f);
        if (seen.length < 60) requestAnimationFrame(read);
      };
      requestAnimationFrame(read);
    });
    await stored(page).click();
    await page.waitForTimeout(1000);
    const seen = await page.evaluate(() => (window as unknown as { SEEN: number[] }).SEEN);
    expect(seen.filter((y) => y < -1).length).toBeGreaterThan(2);
    expect(Math.max(...seen)).toBeLessThanOrEqual(0.5);
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

  // R-0456
  test("a move that also names a child is drawn from its person, never from the child", async ({ page }) => {
    let ids = { ada: 0, ben: 0, kid: 0 };
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, async (route) => {
      const tl = await (await route.fetch()).json();
      const e = tl.events.find((e: { title: string | null }) => e.title?.startsWith("Ada moved toward Ben") || e.relationship === "toward");
      const kid = tl.people.find((p: { id: number }) => p.id !== e.person && !e.relationshipTargets.includes(p.id));
      ids = { ada: e.person, ben: e.relationshipTargets[0], kid: kid.id };
      e.child = kid.id;
      await route.fulfill({ json: tl });
    });
    await settle(page);
    await stored(page).click();
    await expect.poll(() => step(page)).toBe("1 of 4");
    const svg = drawer(page).locator(".draw svg");
    await expect(svg.locator(`[data-mark="move:${ids.ada}>${ids.ben}:toward"]`)).toHaveCount(1);
    await expect(svg.locator(`[data-mark^="move:${ids.kid}>"]`)).toHaveCount(0);
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

/** Whether the person is whole in the Family view's frame, or else shown by
 * an arrow at its edge (R-0785). */
const inSight = (page: Page, id: number | string) =>
  page.evaluate((id) => {
    const d = document.querySelector("#pbp .draw")!.getBoundingClientRect();
    const p = document.querySelector(`#pbp .draw .p[data-id="${id}"] .shape`)!.getBoundingClientRect();
    return (p.left >= d.left - 0.5 && p.right <= d.right + 0.5) || !!document.querySelector(`#pbp .edge[data-slide="${id}"]`);
  }, String(id));

test.describe("a move between two people further apart than the screen is wide", () => {
  // since R-0790 a phone held upright fits the frame whole, so this is a phone turned sideways
  test.use({ storageState: stateFor("play"), viewport: { width: 852, height: 393 } });

  // R-0759, R-0744, R-0785
  test("shows whoever moves on each step, whole in the frame or by an arrow at its edge, the picture never sliding", async ({ page }) => {
    let ids: Record<string, number> = {};
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, async (route) => {
      const tl = await (await route.fetch()).json();
      ids = joined(tl, [["Hugo", "Wanda"]], WIDE, "Hs0", "Hs15");
      // the first move's date also holds a divorce, told first, as "Louann and
      // Wally divorced; Wally estranged from family" is
      const first = tl.events
        .filter((e: { dateTime: string | null }) => e.dateTime)
        .sort((a: { dateTime: string }, b: { dateTime: string }) => a.dateTime.localeCompare(b.dateTime))[0];
      tl.events.unshift({
        ...first, id: 9700, kind: "divorced", label: "Divorced", relationship: null, relationshipTargets: [], relationshipTriangles: [],
        symptom: null, anxiety: null, functioning: null, title: null, description: null,
        person: ids.Hal, spouse: ids.Hope, person_name: "Hal", sentence: "Hal and Hope divorced",
      });
      await route.fulfill({ json: tl });
    });
    await settle(page);
    await page.locator("#cap-family").click();
    await expect(drawer(page)).toBeVisible();
    // the frame walked up to Hugo, whose parents and brothers and sisters it holds
    await tapPerson(page, ids.Hugo);
    const draw = drawer(page).locator(".draw");
    const [mover, target] = [String(ids.Hs0), String(ids.Hs15)];
    const far = await draw.evaluate((d, [a, b]) => {
      const x = (id: string) => d.querySelector(`.p[data-id="${id}"] .shape`)!.getBoundingClientRect().left;
      return Math.abs(x(a) - x(b)) > d.clientWidth;
    }, [mover, target]);
    expect(far).toBe(true);
    // the view opens on the record's own person; every step is then reached
    // with Back and Next, from the first
    await drawer(page).locator('[data-act="next"]').click();
    const back = drawer(page).locator('[data-act="back"]:not([disabled])');
    while (await back.count()) await back.click();
    let moved = 0;
    let divorced = false;
    for (;;) {
      let last = -1;
      await expect.poll(async () => {
        const at = await draw.evaluate((d) => d.scrollLeft);
        const still = at === last;
        last = at;
        return still;
      }, { intervals: [400] }).toBe(true);
      const mark = `.fore [data-mark^="move:${mover}>"]`;
      if (await draw.locator(mark).count()) {
        moved++;
        const at = await drawer(page).locator(".when").innerText();
        divorced ||= at.includes("divorced");
        expect(await inSight(page, mover), `${at}: the one who moves`).toBe(true);
      }
      const next = drawer(page).locator('[data-act="next"]:not([disabled])');
      if (!(await next.count())) break;
      await next.click();
    }
    expect(moved).toBeGreaterThan(1);
    expect(divorced).toBe(true);
  });
});

test.describe("the Family view's three generations", () => {
  test.use({ storageState: stateFor("play"), viewport: { width: 393, height: 852 } });

  /** The `play` record laid as a joined family, its moves Ws1 toward Hs1:
   * Cleo, the reader, is Hugo and Wanda's daughter. */
  const opened = async (page: Page) => {
    let ids: Record<string, number> = {};
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, async (route) => {
      const tl = await (await route.fetch()).json();
      ids = joined(tl, [["Hugo", "Wanda"]], 2, "Ws1", "Hs1");
      await route.fulfill({ json: tl });
    });
    await settle(page);
    await page.locator("#cap-family").click();
    await expect(drawer(page)).toBeVisible();
    await drawer(page).evaluate((p) => Promise.all(p.getAnimations().map((a) => a.finished)));
    await page.waitForTimeout(300);
    const drawn = () => drawer(page).locator(".draw svg .p").evaluateAll((gs) => gs.map((g) => (g as SVGGElement).dataset.id!).sort());
    const of = (...names: string[]) => names.map((n) => String(ids[n])).sort();
    return { ids: () => ids, drawn, of };
  };

  // R-0783
  test("keeps one frame, the reader's three generations, in one place over every date, naming who a date touches outside it", async ({ page }) => {
    const errors = watched(page);
    const { ids, drawn, of } = await opened(page);
    await expect(drawer(page).locator(".path")).toHaveText("Timeline › Family › Cleo's family");
    const frame = of("Cleo", "Hugo", "Wanda", "Hal", "Hope", "Walt", "Wren");
    expect(await drawn()).toEqual(frame);
    const place = () => drawer(page).locator(`.draw svg .p[data-id="${ids().Hugo}"] .shape`).evaluate((s) => [s.getAttribute("x"), s.getAttribute("y")].join(","));
    const at = await place();
    const date = drawer(page).locator(".wire .wlab");
    for (let i = 0; i < 2; i++) {
      const was = (await date.textContent())!;
      await drawer(page).locator('[data-act="next"]').click();
      await expect(date).not.toHaveText(was);
      expect(await drawn()).toEqual(frame);
      expect(await place()).toBe(at);
      // Ws1 and Hs1 move on this date, outside Cleo's frame
      await expect(drawer(page).locator(".also")).toHaveText("Also on this date: Ws1, Hs1");
    }
    expect(errors).toEqual([]);
  });

  // R-0783, R-0775
  test("opens on the first date that touches the reader's own frame, not on dates about people outside it", async ({ page }) => {
    let ids: Record<string, number> = {};
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, async (route) => {
      const tl = await (await route.fetch()).json();
      ids = joined(tl, [["Hugo", "Wanda"]], 2, "Ws1", "Hs1");
      tl.events.forEach((e: Record<string, unknown>) => (e.relationshipTriangles = []));
      // the early dates are her aunt's and uncle's; a later one her father's
      const last = tl.events.filter((e: { dateTime: string | null }) => e.dateTime).sort((a: { dateTime: string }, b: { dateTime: string }) => a.dateTime.localeCompare(b.dateTime)).pop();
      tl.events.push({ ...last, id: 9870, dateTime: "2031-05-01", person: ids.Hugo, person_name: "Hugo", relationship: "toward", relationshipTargets: [ids.Wanda], relationshipTriangles: [], title: "Called Wanda", description: "Called Wanda every night", sentence: "Hugo called Wanda every night" });
      await route.fulfill({ json: tl });
    });
    await settle(page);
    await page.locator("#cap-family").click();
    await expect(drawer(page)).toBeVisible();
    await expect(drawer(page).locator(".when")).toContainText("Hugo called Wanda every night");
    await expect(drawer(page).locator(".also")).toHaveText("");
  });

  // R-0783
  test("puts the frame on someone named outside it, at the same date", async ({ page }) => {
    const { ids, drawn, of } = await opened(page);
    const date = (await drawer(page).locator(".wire .wlab").textContent())!;
    await drawer(page).locator(`.also [data-centre="${ids().Hs1}"]`).click();
    await expect(drawer(page).locator(".path")).toHaveText("Timeline › Family › Hs1's family");
    await expect.poll(drawn).toEqual(of("Hs1", "Hal", "Hope", "Hugo", "Hs0"));
    await expect(drawer(page).locator(".wire .wlab")).toHaveText(date);
    // Ws1 still moves toward Hs1 from outside his frame
    await expect(drawer(page).locator(".also")).toHaveText("Also on this date: Ws1");
  });

  // R-0783
  test("walks up to a parent, across to a partner and down to a child, sliding to each, and Family goes back to the reader", async ({ page }) => {
    const { ids, drawn, of } = await opened(page);
    const path = drawer(page).locator(".path");
    // up: Cleo's father, his parents and brothers, his wife and daughter; the frame slides there
    const hugo = drawer(page).locator(`.draw svg .p[data-id="${ids().Hugo}"] .shape`);
    const b = (await hugo.boundingBox())!;
    await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2);
    expect(await drawer(page).locator(".draw svg").evaluate((s) => s.getAnimations().length)).toBeGreaterThan(0);
    await expect(path).toHaveText("Timeline › Family › Hugo's family");
    await expect.poll(drawn).toEqual(of("Hugo", "Hal", "Hope", "Hs0", "Hs1", "Wanda", "Cleo"));
    // across: his wife, her parents and sisters
    await tapPerson(page, ids().Wanda);
    await expect(path).toHaveText("Timeline › Family › Wanda's family");
    await expect.poll(drawn).toEqual(of("Wanda", "Walt", "Wren", "Ws0", "Ws1", "Hugo", "Cleo"));
    // down: her daughter, the reader, whose frame is the one the view opens on
    await tapPerson(page, ids().Cleo);
    await expect(path).toHaveText("Timeline › Family › Cleo's family");
    await expect.poll(drawn).toEqual(of("Cleo", "Hugo", "Wanda", "Hal", "Hope", "Walt", "Wren"));
    // and Family in the path goes back to the reader from anywhere
    await tapPerson(page, ids().Hugo);
    await tapPerson(page, ids().Hal);
    await expect(path).toHaveText("Timeline › Family › Hal's family");
    await drawer(page).locator('.path [data-step="1"]').click();
    await expect(path).toHaveText("Timeline › Family › Cleo's family");
    await expect.poll(drawn).toEqual(of("Cleo", "Hugo", "Wanda", "Hal", "Hope", "Walt", "Wren"));
    await expect(drawer(page)).toBeVisible();
  });

  // R-0779, R-0785
  test("shows both partners on a couple's step, whole in the frame or by an arrow at its edge", async ({ page }) => {
    let ids: Record<string, number> = {};
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, async (route) => {
      const tl = await (await route.fetch()).json();
      ids = joined(tl, [["Hugo", "Wanda"]], 2, "Ws1", "Hs1");
      // three children spread the couple further apart than half the frame
      const cleo = tl.people.find((p: { id: number }) => p.id === ids.Cleo);
      ["Kip", "Lux"].forEach((name, i) => tl.people.push({ ...cleo, id: 9900 + i, name, primary: false, birth: `197${7 + i}-01-01` }));
      const first = tl.events.filter((e: { dateTime: string | null }) => e.dateTime).sort((a: { dateTime: string }, b: { dateTime: string }) => a.dateTime.localeCompare(b.dateTime))[0];
      tl.events.unshift({
        ...first, id: 9800, kind: "married", label: "Married", dateTime: "1974-06-01", relationship: null, relationshipTargets: [], relationshipTriangles: [],
        symptom: null, anxiety: null, functioning: null, title: null, description: null,
        person: ids.Hugo, spouse: ids.Wanda, person_name: "Hugo", sentence: "Hugo and Wanda married",
      });
      await route.fulfill({ json: tl });
    });
    await settle(page);
    await page.locator("#cap-family").click();
    await expect(drawer(page)).toBeVisible();
    await expect(drawer(page).locator(".when")).toContainText("Hugo and Wanda married");
    await page.waitForTimeout(1500);
    // under their own parents the couple stand further apart than the phone is
    // wide: each is whole in the frame or shown by an arrow at its edge (R-0785)
    for (const id of [ids.Hugo, ids.Wanda]) expect(await inSight(page, id)).toBe(true);
  });

  // R-0779, R-0742, R-0784
  test("keeps a long step title to its three lines above the years line, so the picture never moves", async ({ page }) => {
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, async (route) => {
      const tl = await (await route.fetch()).json();
      joined(tl, [["Hugo", "Wanda"]], 2, "Ws1", "Hs1");
      const first = tl.events.filter((e: { dateTime: string | null }) => e.dateTime).sort((a: { dateTime: string }, b: { dateTime: string }) => a.dateTime.localeCompare(b.dateTime))[0];
      first.description =
        "kept her distance from her brother at every family gathering for years, finding him more difficult than positive, always chasing approval and trying to gain the attention of their father";
      first.title = first.description;
      await route.fulfill({ json: tl });
    });
    await settle(page);
    await page.locator("#cap-family").click();
    await expect(drawer(page)).toBeVisible();
    // the first date, met by stepping back to it
    const back = drawer(page).locator('[data-act="back"]:not([disabled])');
    while (await back.count()) await back.click();
    await expect(drawer(page).locator(".when")).toContainText("kept her distance");
    const title = await drawer(page).locator(".when").evaluate((w) => ({ height: w.clientHeight, bottom: w.getBoundingClientRect().bottom }));
    const label = (await drawer(page).locator(".wire .wlab").boundingBox())!;
    // three lines of 18 and the padding under them
    expect(title.height).toBe(3 * 18 + 8);
    expect(title.bottom).toBeLessThanOrEqual(label.y + 1);
  });

  // R-0783, R-0759
  // R-0785
  test("shows everyone a date involves, the second mover too, in the frame or by an arrow at its edge", async ({ page }) => {
    let ids: Record<string, number> = {};
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, async (route) => {
      const tl = await (await route.fetch()).json();
      ids = joined(tl, [["Hugo", "Wanda"]], 2, "Hugo", "Wanda");
      // on the same date Wanda's sister, at the far end of the family, takes on
      // too much, a move that reaches no one
      tl.people.find((p: { id: number }) => p.id === ids.Ws1).name = "Wilhelmina";
      const first = tl.events.filter((e: { dateTime: string | null }) => e.dateTime).sort((a: { dateTime: string }, b: { dateTime: string }) => a.dateTime.localeCompare(b.dateTime))[0];
      // Hugo moves away from Wanda, and his own words beside him widen the
      // drawing past the phone on his side
      Object.assign(first, { relationship: "away", relationshipTargets: [ids.Wanda], relationshipTriangles: [], functioning: "up", title: "Took on the whole farm alone", description: "Took on the whole farm alone" });
      tl.events.push({ ...first, id: 9850, person: ids.Ws1, person_name: "Wilhelmina", relationship: "overfunctioning", relationshipTargets: [], functioning: null, title: "Did everything", description: "Did everything", sentence: "Wilhelmina did everything" });
      await route.fulfill({ json: tl });
    });
    await settle(page);
    await page.locator("#cap-family").click();
    await expect(drawer(page)).toBeVisible();
    await drawer(page).evaluate((p) => Promise.all(p.getAnimations().map((a) => a.finished)));
    // the frame walked up to Wanda, whose family holds Hugo and her sister
    await tapPerson(page, ids.Wanda);
    // from the start of the dates, stepped with Next to the first move
    const back = drawer(page).locator('[data-act="back"]:not([disabled])');
    while (await back.count()) await back.click();
    const draw = drawer(page).locator(".draw");
    for (let i = 0; i < 20 && !(await draw.locator(`.fore [data-mark^="move:${ids.Ws1}>"]`).count()); i++)
      await drawer(page).locator('[data-act="next"]').click();
    // stepped onto from the next date, as a reader stepping back meets it
    await drawer(page).locator('[data-act="next"]').click();
    await drawer(page).locator('[data-act="back"]').click();
    // the frame's travel takes up to two seconds
    await page.waitForTimeout(2300);
    for (const id of [ids.Hugo, ids.Wanda, ids.Ws1]) expect(await inSight(page, id)).toBe(true);
  });

  // R-0782
  test("keeps Back and Next in one place, so Next tapped again and again at one spot steps on each time", async ({ page }) => {
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, lifetime);
    await settle(page);
    await page.locator("#cap-family").click();
    await expect(drawer(page)).toBeVisible();
    const back = drawer(page).locator('[data-act="back"]:not([disabled])');
    while (await back.count()) await back.click();
    await page.waitForTimeout(600);
    const next = (await drawer(page).locator('[data-act="next"]').boundingBox())!;
    const [x, y] = [next.x + next.width / 2, next.y + next.height / 2];
    const top = drawer(page).locator(".when");
    const seen = [await top.innerText()];
    for (let i = 0; i < 4; i++) {
      await page.mouse.click(x, y);
      await expect(top).not.toHaveText(seen[seen.length - 1]);
      seen.push(await top.innerText());
      const again = (await drawer(page).locator('[data-act="next"]').boundingBox())!;
      expect([Math.round(again.x), Math.round(again.y)]).toEqual([Math.round(next.x), Math.round(next.y)]);
    }
    expect(new Set(seen).size).toBe(5);
  });

  // R-0779, R-0691
  test("raises the passages on what the family diagram is for from its book", async ({ page }) => {
    await page.route(/\/app\/case-report-passages(\?.*)?$/, (route) =>
      route.fulfill({ json: { family: [{ text: "it is usually not necessary for a therapist to put so much information on his or her diagram", by: "Kerr & Bowen, Family Evaluation, ch. 10" }] } }),
    );
    await settle(page);
    await page.locator("#cap-family").click();
    await expect(drawer(page)).toBeVisible();
    await drawer(page).locator(".path .book").click();
    const sheet = page.locator("#chat-screen .fs-sheet.bk");
    await expect(sheet).toHaveClass(/in/);
    await expect(sheet.locator(".cf-t")).toHaveText("What the family diagram is for");
    await expect(sheet.locator("blockquote")).toHaveText("it is usually not necessary for a therapist to put so much information on his or her diagram");
    await page.keyboard.press("Escape");
    await expect(sheet).not.toHaveClass(/in/);
  });

  // R-0779, R-0691
  test("puts the book's passages away on a tap of the dimmed page above them, and scrolls to the last of them on a phone", async ({ page }) => {
    const long = "This type of change occurs over a period of years, and a person who can see four or five generations of their own family as one living thing is beyond blaming self or others. ".repeat(3);
    const five = Array.from({ length: 5 }, (_, i) => ({ text: `${i + 1}. ${long}`, by: "Kerr & Bowen, Family Evaluation, ch. 8" }));
    await page.route(/\/app\/case-report-passages(\?.*)?$/, (route) => route.fulfill({ json: { family: five } }));
    await settle(page);
    await page.locator("#cap-family").click();
    await expect(drawer(page)).toBeVisible();
    await drawer(page).locator(".path .book").click();
    const sheet = page.locator("#chat-screen .fs-sheet.bk");
    await expect(sheet).toHaveClass(/in/);
    await page.waitForTimeout(400);
    // swiped to its end, the last passage stands whole on the screen
    const list = sheet.locator(".bk-list");
    expect(await list.evaluate((l) => l.scrollHeight > l.clientHeight)).toBe(true);
    await list.hover();
    for (let i = 0; i < 12; i++) await page.mouse.wheel(0, 400);
    await page.waitForTimeout(300);
    const last = (await sheet.locator(".bk-by").last().boundingBox())!;
    expect(last.y + last.height).toBeLessThanOrEqual(page.viewportSize()!.height);
    // the dimmed page above the sheet
    const top = (await sheet.boundingBox())!;
    await page.mouse.click(top.x + 20, Math.max(top.y - 30, 70));
    await expect(sheet).not.toHaveClass(/in/);
  });
});

/** The Family view of the `play` record laid as a joined family, Cleo the
 * reader, at the size of the screen it is opened on. */
const familyOf = async (page: Page, sibs: number, tweak: (tl: Record<string, any>, ids: Record<string, number>) => void = () => {}) => {
  let ids: Record<string, number> = {};
  await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, async (route) => {
    const tl = await (await route.fetch()).json();
    ids = joined(tl, [["Hugo", "Wanda"]], sibs, "Hugo", "Wanda");
    tweak(tl, ids);
    await route.fulfill({ json: tl });
  });
  await settle(page);
  await page.locator("#cap-family").click();
  await expect(drawer(page)).toBeVisible();
  await drawer(page).evaluate((p) => Promise.all(p.getAnimations().map((a) => a.finished)));
  await page.waitForTimeout(300);
  return () => ids;
};
const drawnIds = (page: Page) => drawer(page).locator(".draw svg .p").evaluateAll((gs) => gs.map((g) => (g as SVGGElement).dataset.id!));

/** Hugo's brothers and sisters, enough that his frame is wider than a phone
 * turned sideways with names at their readable size. */
const WIDE = 16;

/** Since R-0790 a phone held upright fits the frame whole, so a frame wider
 * than the screen is one wider than a phone turned sideways. */
test.describe("the Family view's frame wider than a phone turned sideways", () => {
  test.use({ storageState: stateFor("play"), viewport: { width: 852, height: 393 } });

  // R-0784
  test("holds still between dates while the date's people are in sight, and draws three generations", async ({ page }) => {
    const ids = await familyOf(page, WIDE, (tl, ids) => {
      // Hugo moves toward Wanda, she toward their daughter, the daughter toward him:
      // three people who stand side by side
      const dated = tl.events.filter((e: { dateTime: string | null }) => e.dateTime).sort((a: { dateTime: string }, b: { dateTime: string }) => a.dateTime.localeCompare(b.dateTime));
      dated.forEach((e: Record<string, unknown>, i: number) =>
        Object.assign(e, [
          { person: ids.Hugo, relationship: "toward", relationshipTargets: [ids.Wanda], relationshipTriangles: [] },
          { person: ids.Wanda, relationship: "toward", relationshipTargets: [ids.Cleo], relationshipTriangles: [] },
          { person: ids.Cleo, relationship: "toward", relationshipTargets: [ids.Hugo], relationshipTriangles: [] },
        ][i % 3]),
      );
    });
    // Hugo's frame: his parents and his brothers and sisters, wider than the screen
    await tapPerson(page, ids().Hugo);
    expect(await drawnIds(page)).not.toContain(String(ids().Walt));
    const draw = drawer(page).locator(".draw");
    expect(await draw.evaluate((d) => d.scrollWidth > d.clientWidth)).toBe(true);
    const back = drawer(page).locator('[data-act="back"]:not([disabled])');
    while (await back.count()) await back.click();
    // the first date met by stepping, not as the tap left it
    await drawer(page).locator('[data-act="next"]').click();
    await drawer(page).locator('[data-act="back"]').click();
    await page.waitForTimeout(2300);
    const at = await draw.evaluate((d) => d.scrollLeft);
    for (let i = 0; i < 2; i++) {
      await drawer(page).locator('[data-act="next"]').click();
      await page.waitForTimeout(800);
      expect(await draw.evaluate((d) => d.scrollLeft)).toBe(at);
    }
  });

  // R-0785
  test("never slides the picture on a step, showing who the date involves off the screen by an arrow at its edge that glows and slides the picture to them", async ({ page }) => {
    const ids = await familyOf(page, WIDE, (tl, ids) => {
      const dated = tl.events.filter((e: { dateTime: string | null }) => e.dateTime).sort((a: { dateTime: string }, b: { dateTime: string }) => a.dateTime.localeCompare(b.dateTime));
      // Hugo's eldest sister and youngest brother move toward each other, then Hugo toward Wanda
      dated.forEach((e: Record<string, unknown>, i: number) =>
        Object.assign(e, i % 2
          ? { person: ids.Hugo, relationship: "toward", relationshipTargets: [ids.Wanda], relationshipTriangles: [], functioning: null }
          : { person: ids.Hs0, relationship: "toward", relationshipTargets: [ids.Hs5], relationshipTriangles: [], functioning: null }),
      );
    });
    // Hugo's frame, his parents and his brothers and sisters, is wider than the screen
    await tapPerson(page, ids().Hugo);
    await page.waitForTimeout(600);
    const draw = drawer(page).locator(".draw");
    const back = drawer(page).locator('[data-act="back"]:not([disabled])');
    while (await back.count()) await back.click();
    const at = await draw.evaluate((d) => d.scrollLeft);
    const name = { [ids().Hs0]: "Hs0", [ids().Hs5]: "Hs5", [ids().Hugo]: "Hugo", [ids().Wanda]: "Wanda" };
    let seen = 0;
    for (let i = 0; i < 4; i++) {
      await drawer(page).locator('[data-act="next"]').click();
      await page.waitForTimeout(700);
      expect(await draw.evaluate((d) => d.scrollLeft)).toBe(at);
      const marks = await drawer(page).locator(".edge").evaluateAll((es, box) =>
        es.map((e) => {
          const id = (e as HTMLElement).dataset.slide!;
          const s = document.querySelector(`#pbp .draw .p[data-id="${id}"] .shape`)!.getBoundingClientRect();
          const d = document.querySelector("#pbp .draw")!.getBoundingClientRect();
          const r = e.getBoundingClientRect();
          // in the gutter beside the drawing, covering no one
          const over = [...document.querySelectorAll("#pbp .draw :is(.p .shape, .pt text)")].some((x) => {
            // what the frame shows of it: the frame clips the rest
            const q = x.getBoundingClientRect();
            const [ql, qr] = [Math.max(q.left, d.left), Math.min(q.right, d.right)];
            return ql < qr && ql < r.right && r.left < qr && q.top < r.bottom && r.top < q.bottom;
          });
          const beside = r.right <= d.left + 1 || r.left >= d.right - 1;
          return { id, text: e.textContent, on: e.classList.contains("on"), clear: !over && beside, side: r.left <= d.left + 1 ? "left" : "right", where: s.left + s.width / 2 < d.left + d.width / 2 ? "left" : "right", off: s.left < d.left || s.right > d.right };
        }), null);
      for (const m of marks) {
        expect(m.off).toBe(true);
        expect(m.clear).toBe(true);
        expect(m.side).toBe(m.where);
        expect(m.text).toContain(name[Number(m.id)]);
      }
      // the one who moves glows while the move plays
      if (marks.some((m) => Number(m.id) === ids().Hs0)) expect(marks.find((m) => Number(m.id) === ids().Hs0)!.on).toBe(true);
      seen += marks.length;
    }
    expect(seen).toBeGreaterThan(0);
    const edge = drawer(page).locator(".edge").first();
    if (!(await edge.count())) await drawer(page).locator('[data-act="back"]').click();
    const id = (await drawer(page).locator(".edge").first().getAttribute("data-slide"))!;
    await drawer(page).locator(".edge").first().click();
    await page.waitForTimeout(2300);
    const inView = await drawer(page).evaluate((p, id) => {
      const s = p.querySelector(`.draw .p[data-id="${id}"] .shape`)!.getBoundingClientRect();
      const d = p.querySelector(".draw")!.getBoundingClientRect();
      return s.left >= d.left - 0.5 && s.right <= d.right + 0.5;
    }, id);
    expect(inView).toBe(true);
  });

  // R-0783, R-0785
  test("puts a re-centred person near the middle and rests every edge between people, never through one", async ({ page }) => {
    const ids = await familyOf(page, WIDE, (tl, ids) => {
      const dated = tl.events.filter((e: { dateTime: string | null }) => e.dateTime).sort((a: { dateTime: string }, b: { dateTime: string }) => a.dateTime.localeCompare(b.dateTime));
      dated.forEach((e: Record<string, unknown>) =>
        Object.assign(e, { person: ids.Hs0, relationship: "toward", relationshipTargets: [ids.Hs5], relationshipTriangles: [], functioning: null }),
      );
    });
    const cut = () =>
      drawer(page).evaluate((p) => {
        const d = p.querySelector(".draw")!.getBoundingClientRect();
        return [...p.querySelectorAll(".draw .p[data-id] .shape")]
          .map((s) => s.getBoundingClientRect())
          .filter((s) => (s.left < d.left - 0.5 && s.right > d.left + 0.5) || (s.left < d.right - 0.5 && s.right > d.right + 0.5)).length;
      });
    await tapPerson(page, ids().Hugo);
    await page.waitForTimeout(600);
    const off = await drawer(page).evaluate((p, id) => {
      const d = p.querySelector(".draw")!.getBoundingClientRect();
      const s = p.querySelector(`.draw .p[data-id="${id}"] .shape`)!.getBoundingClientRect();
      return Math.abs(s.left + s.width / 2 - (d.left + d.width / 2)) / d.width;
    }, String(ids().Hugo));
    expect(off).toBeLessThan(0.25);
    expect(await cut()).toBe(0);
    await drawer(page).locator(".edge").first().click();
    await page.waitForTimeout(2300);
    expect(await cut()).toBe(0);
  });

  // R-0744, R-0742
  test("scrolls inside its own frame, never the page", async ({ page }) => {
    const errors = watched(page);
    let ids: Record<string, number> = {};
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, async (route) => {
      const tl = await (await route.fetch()).json();
      ids = joined(tl, [["Hugo", "Wanda"]], WIDE, "Hs5", "Hugo");
      await route.fulfill({ json: tl });
    });
    await settle(page);
    await page.locator("#cap-family").click();
    await expect(drawer(page)).toBeVisible();
    await drawer(page).evaluate((p) => Promise.all(p.getAnimations().map((a) => a.finished)));
    // Hugo's three generations: he and his brothers and sisters are wider than the screen
    await tapPerson(page, ids.Hugo);
    await expect(drawer(page).locator(".path")).toContainText("Hugo's family");
    const frame = drawer(page).locator(".draw");
    expect(await frame.evaluate((d) => d.scrollWidth > d.clientWidth)).toBe(true);
    expect(await sideways(page)).toBe(false);
    await drawer(page).locator('[data-act="next"]').click();
    expect(await sideways(page)).toBe(false);
    expect(errors).toEqual([]);
  });
});

/** Hugo's family moving among themselves, one date's move reaching his
 * brother, outside Cleo's frame, and one carrying a long title and words. */
const moving = (long: boolean) => (tl: Record<string, any>, ids: Record<string, number>) => {
  const dated = tl.events.filter((e: { dateTime: string | null }) => e.dateTime).sort((a: { dateTime: string }, b: { dateTime: string }) => a.dateTime.localeCompare(b.dateTime));
  dated.forEach((e: Record<string, unknown>, i: number) =>
    Object.assign(e, { person: ids.Hugo, relationship: "toward", relationshipTargets: [i === 1 ? ids.Hs1 : ids.Wanda], relationshipTriangles: [], functioning: null }),
  );
  if (long)
    Object.assign(dated[2], {
      functioning: "up",
      title: "Kept every promise he had made his brothers and sisters",
      description: "Hugo kept every promise he had made to his brothers and sisters that winter, and wrote each of them a long letter about the farm and the debts",
    });
};

/** Where every name of the Family view's drawing stands on the screen. */
const namesAt = (page: Page) =>
  drawer(page).locator(".draw svg .pt .lbn").evaluateAll((ts) => ts.map((t) => (t as SVGTextElement).getBoundingClientRect()).map((r) => [r.left, r.right]));

/** How see-through the drawer's marks from earlier dates, its not yet born,
 * and its date's own marks stand. */
const faded = (page: Page) =>
  page.evaluate(() => {
    const op = (e: Element) => Number(getComputedStyle(e).opacity);
    const draw = document.querySelector("#pbp .draw")!;
    return {
      was: [...draw.querySelectorAll(".was")].map(op),
      yet: [...draw.querySelectorAll(".yet")].map(op),
      now: [...draw.querySelectorAll(".fore > *")].filter((e) => !e.closest(".was, .yet")).map((e) => `${e.getAttribute("class")}:${op(e)}`),
    };
  });

test.describe("the Family view as Patrick looked at it on his own record", () => {
  test.use({ storageState: stateFor("play"), viewport: { width: 393, height: 852 } });

  // R-0784
  test("frames only what it draws, keeps the drawing at one height through a long title, and says whose family it is", async ({ page }) => {
    const ids = await familyOf(page, 6, moving(true));
    await expect(drawer(page).locator(".path")).toHaveText("Timeline › Family › Cleo's family");
    await tapPerson(page, ids().Hugo);
    await page.waitForTimeout(600);
    const svg = (await drawer(page).locator(".draw svg").boundingBox())!;
    const names = await namesAt(page);
    // no band of empty frame beside the family: the names reach to its margin on both sides
    expect(Math.min(...names.map((n) => n[0])) - svg.x).toBeLessThan(40);
    expect(svg.x + svg.width - Math.max(...names.map((n) => n[1]))).toBeLessThan(40);
    // the person the frame is around is marked, and the path names them
    expect(await drawer(page).locator(".draw svg .p.mid").getAttribute("data-id")).toBe(String(ids().Hugo));
    await expect(drawer(page).locator(".path")).toHaveText("Timeline › Family › Hugo's family");
    const back = drawer(page).locator('[data-act="back"]:not([disabled])');
    while (await back.count()) await back.click();
    const top = async () => Math.round((await drawer(page).locator(".draw svg").boundingBox())!.y);
    const at = await top();
    const titles = [];
    for (let i = 0; i < 3; i++) {
      await drawer(page).locator('[data-act="next"]').click();
      expect(await top()).toBe(at);
      titles.push(await drawer(page).locator(".when").textContent());
    }
    expect(titles.some((t) => t!.includes("Hugo kept every promise"))).toBe(true);
  });

  // R-0786
  test("never zooms the page, by a double tap or a pinch", async ({ page }) => {
    await settle(page);
    expect(await page.locator('meta[name="viewport"]').getAttribute("content")).toContain("maximum-scale=1, user-scalable=no");
    expect(await page.evaluate(() => getComputedStyle(document.documentElement).touchAction)).toBe("pan-x pan-y");
  });

  // R-0790
  test("scales a frame wider than the phone whole to its width, however small the names, with no arrows at its edges", async ({ page }) => {
    const ids = await familyOf(page, 6, moving(false));
    // Hugo's frame: his parents and his six brothers and sisters
    await tapPerson(page, ids().Hugo);
    const draw = drawer(page).locator(".draw");
    for (let i = 0; i < 3; i++) {
      expect(await draw.evaluate((d) => d.scrollWidth <= d.clientWidth + 1)).toBe(true);
      await expect(drawer(page).locator(".edge")).toHaveCount(0);
      await drawer(page).locator('[data-act="next"]').click();
    }
    // scaled as one: every person's shape the same size, smaller than at the 9px names it stopped at before
    const sizes = await draw.locator("svg .p .shape").evaluateAll((ss) => ss.map((s) => Math.round(s.getBoundingClientRect().width)));
    expect(new Set(sizes).size).toBe(1);
    expect(sizes[0]).toBeLessThan(44 * (9 / 13));
  });

  // R-0779
  test("draws three generations on the phone around someone with no children, their grandparents above their parents", async ({ page }) => {
    const ids = await familyOf(page, 2);
    const drawn = await drawnIds(page);
    expect(drawn).toEqual(expect.arrayContaining([ids().Hal, ids().Hope, ids().Walt, ids().Wren, ids().Hugo, ids().Wanda, ids().Cleo].map(String)));
  });

  // R-0793
  test("in the Family view, gives a grey mark from an earlier date the see-through look of the not yet born, this date's marks solid", async ({ page }) => {
    await familyOf(page, 2, (tl, ids) => {
      moving(false)(tl, ids);
      // Cleo's grandmother Hope is drawn faded, born after every date
      tl.people.find((p: Record<string, unknown>) => p.id === ids.Hope).birth = "2090-01-01";
    });
    const back = drawer(page).locator('[data-act="back"]:not([disabled])');
    while (await back.count()) await back.click();
    for (let i = 0; i < 3; i++) await drawer(page).locator('[data-act="next"]').click();
    // the date's own marks have popped in
    await page.waitForTimeout(800);
    const family = await faded(page);
    expect(family.was.length).toBeGreaterThan(0);
    expect(family.yet.length).toBeGreaterThan(0);
    expect(new Set([...family.was, ...family.yet])).toEqual(new Set([family.yet[0]]));
    expect(family.yet[0]).toBeLessThan(1);
    expect(family.now.filter((o) => !o.endsWith(":1"))).toEqual([]);
  });

  // R-0793
  test("in the play-by-play, gives the first step's move, carried to the second, the same see-through look, the second's own move solid", async ({ page }) => {
    await settle(page);
    await stored(page).click();
    await expect.poll(() => step(page)).toBe("1 of 4");
    await drawer(page).locator('[data-act="next"]').click();
    await page.waitForTimeout(800);
    const play = await faded(page);
    expect(play.was.length).toBeGreaterThan(0);
    // the one value the Family view gives the not yet born
    const yet = await drawer(page).evaluate((p) => Number(getComputedStyle(p).getPropertyValue("--faded")));
    expect(yet).toBeLessThan(1);
    expect(new Set(play.was)).toEqual(new Set([yet]));
    expect(play.now.filter((o) => !o.endsWith(":1"))).toEqual([]);
  });

  // R-0786
  test("holds the page's scale against Safari's own pinch, which ignores the viewport", async ({ page }) => {
    await settle(page);
    const held = await page.evaluate(() => {
      const pinch = new Event("gesturestart", { cancelable: true, bubbles: true });
      document.querySelector("#view")!.dispatchEvent(pinch);
      return pinch.defaultPrevented;
    });
    expect(held).toBe(true);
  });

  // R-0788
  test("outlines the play-by-play's names thinly in the page's colour too, with no box behind them", async ({ page }) => {
    await settle(page);
    await stored(page).click();
    await expect.poll(() => step(page)).toBe("1 of 4");
    const names = await drawer(page).locator(".draw svg .pt").evaluateAll((gs) =>
      gs.flatMap((g) =>
        [...g.querySelectorAll<SVGTextElement>(".lbn")].map((t) => {
          const s = getComputedStyle(t);
          return { boxed: !!g.querySelector("rect"), under: s.paintOrder.startsWith("stroke"), page: s.stroke === getComputedStyle(document.querySelector("#pbp")!).backgroundColor, thin: parseFloat(s.strokeWidth) <= 3 };
        }),
      ),
    );
    expect(names.length).toBeGreaterThan(0);
    for (const n of names) expect(n).toEqual({ boxed: false, under: true, page: true, thin: true });
  });

  // R-0788
  test("outlines every name thinly in the page's colour, with no box behind it to hide the lines it meets", async ({ page }) => {
    await familyOf(page, 2, moving(true));
    const names = await drawer(page).locator(".draw svg .pt").evaluateAll((gs) =>
      gs.flatMap((g) =>
        [...g.querySelectorAll<SVGTextElement>(".lbn, .lbd")].map((t) => {
          const s = getComputedStyle(t);
          const page = getComputedStyle(document.querySelector("#pbp")!).backgroundColor;
          return { boxed: !!g.querySelector("rect"), under: s.paintOrder.startsWith("stroke"), page: s.stroke === page, width: parseFloat(s.strokeWidth) };
        }),
      ),
    );
    expect(names.length).toBeGreaterThan(0);
    for (const n of names) expect(n).toEqual({ boxed: false, under: true, page: true, width: expect.any(Number) });
    expect(Math.max(...names.map((n) => n.width))).toBeLessThanOrEqual(3);
  });

  // R-0548, R-0783
  test("tells two people of one first name apart wherever both are drawn or named together, never where only one is, and cuts the path a whole word at a time", async ({ page }) => {
    let ids: () => Record<string, number> = () => ({});
    ids = await familyOf(page, 2, (tl, ids) => {
      moving(false)(tl, ids);
      // Hugo's brother is a Hugo too, and dies on a date of his own; Hugo's name is long
      tl.people.forEach((p: Record<string, unknown>) => {
        if (p.id === ids.Hs1) Object.assign(p, { name: "Hugo", last_name: "Vale" });
        if (p.id === ids.Hugo) Object.assign(p, { name: "Hugo", last_name: "Bartholomew-Ashcombe" });
      });
      const last = tl.events.filter((e: { dateTime: string | null }) => e.dateTime).sort((a: { dateTime: string }, b: { dateTime: string }) => a.dateTime.localeCompare(b.dateTime)).pop();
      tl.events.push({ ...last, id: 9890, kind: "death", label: "Died", dateTime: "2040-01-01", person: ids.Hs1, person_name: "Hugo", relationship: null, relationshipTargets: [], relationshipTriangles: [], title: null, description: null, spouse: null, child: null, sentence: "Hugo died" });
    });
    const hugo = drawer(page).locator(`.draw svg .pt[data-id="${ids().Hugo}"] .lbn`);
    const back = drawer(page).locator('[data-act="back"]:not([disabled])');
    while (await back.count()) await back.click();
    // a date naming no other Hugo: the one drawn is plain Hugo
    await expect(drawer(page).locator(".also")).toHaveText("");
    await expect(hugo).toHaveText("Hugo");
    while (!(await drawer(page).locator(".also").textContent())) await drawer(page).locator('[data-act="next"]').click();
    // his brother named beside the drawing: both carry their initials, in the words and the picture
    await expect(drawer(page).locator(".also")).toHaveText("Also on this date: Hugo V.");
    await expect(drawer(page).locator(".when")).toContainText("Hugo B.");
    await expect(hugo).toHaveText("Hugo B.");
    // the brother's death, though he is not drawn
    const next = drawer(page).locator('[data-act="next"]:not([disabled])');
    while (await next.count()) await next.click();
    await expect(drawer(page).locator(".when")).toHaveText("Hugo V. died");
    await expect(hugo).toHaveText("Hugo B.");
    await drawer(page).locator('[data-act="back"]').click();
    while (!(await drawer(page).locator(".also").textContent())) await drawer(page).locator('[data-act="back"]').click();
    await drawer(page).locator('.also [data-centre]').click();
    // "Timeline › Family › Hugo V.'s family" is cut only between words
    const path = (await drawer(page).locator(".path").textContent())!;
    expect(path).toMatch(/^Timeline › (Family|…) › Hugo V\.'s( family|…)$/);
  });
});

test.describe("the Family view on a short phone held upright", () => {
  test.use({ storageState: stateFor("play"), viewport: { width: 393, height: 660 } });

  // R-0779, R-0787
  test("still draws three generations around someone with no children", async ({ page }) => {
    const ids = await familyOf(page, 2);
    expect(await drawnIds(page)).toEqual(expect.arrayContaining([ids().Hal, ids().Hope, ids().Walt, ids().Wren].map(String)));
  });
});

/** What stands at a point of the screen: inside the Family view or not. */
const covers = (page: Page, x: number, y: number) => page.evaluate(([x, y]) => !!document.elementFromPoint(x, y)?.closest("#pbp"), [x, y]);
const placeOf = (page: Page) => page.evaluate(() => [document.querySelector("#pbp .wlab")!.textContent, document.querySelector("#pbp .path")!.textContent]);

test.describe("the Family view on a phone, turned", () => {
  test.use({ storageState: stateFor("play"), viewport: { width: 393, height: 852 }, hasTouch: true, isMobile: true });

  // R-0791, R-0790
  test("turned sideways over the chat, shows the Family view alone over the whole screen, and turned back keeps its date and person", async ({ page }, info) => {
    test.skip(info.project.name !== "phone", "the size is the describe's own");
    const errors = watched(page);
    let ids: Record<string, number> = {};
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, async (route) => {
      const tl = await (await route.fetch()).json();
      ids = joined(tl, [["Hugo", "Wanda"]], 2, "Hugo", "Wanda");
      await route.fulfill({ json: tl });
    });
    await settle(page);
    await expect(drawer(page)).toBeHidden();
    await page.setViewportSize({ width: 852, height: 393 });
    await expect(drawer(page)).toBeVisible();
    await drawer(page).evaluate((p) => Promise.all(p.getAnimations().map((a) => a.finished)));
    // the picture alone: no app header, no timeline, no list beside it
    expect(await drawer(page).boundingBox()).toEqual({ x: 0, y: 0, width: 852, height: 393 });
    for (const [x, y] of [[20, 20], [200, 150], [830, 200]]) expect(await covers(page, x, y)).toBe(true);
    await tapPerson(page, ids.Hugo);
    await drawer(page).locator('[data-act="next"]').click();
    const at = await placeOf(page);
    expect(at[1]).toContain("Hugo's family");
    await page.setViewportSize({ width: 393, height: 852 });
    await page.waitForTimeout(400);
    expect(await placeOf(page)).toEqual(at);
    expect(await drawer(page).locator(".draw").evaluate((d) => d.scrollWidth <= d.clientWidth + 1)).toBe(true);
    expect((await drawer(page).boundingBox())!.y).toBeGreaterThan(0);
    expect(errors).toEqual([]);
  });

  // R-0792
  test("puts the Family view full screen from a button between Back and Next, the whole page where the browser gives no full screen, and back again", async ({ page }, info) => {
    test.skip(info.project.name !== "phone", "the size is the describe's own");
    await familyOf(page, 2);
    const full = drawer(page).locator(".foot .full");
    // between Back and Next, covering neither, nor anyone drawn
    const [b, f, n] = await Promise.all(['[data-act="back"]', ".full", '[data-act="next"]'].map((s) => drawer(page).locator(`.foot ${s}`).boundingBox()));
    expect(b!.x + b!.width).toBeLessThanOrEqual(f!.x);
    expect(f!.x + f!.width).toBeLessThanOrEqual(n!.x);
    const draw = (await drawer(page).locator(".draw").boundingBox())!;
    expect(f!.y).toBeGreaterThanOrEqual(draw.y + draw.height);
    await full.click();
    await expect.poll(() => page.evaluate(() => document.fullscreenElement?.contains(document.querySelector("#pbp")) ?? false)).toBe(true);
    await full.click();
    await expect.poll(() => page.evaluate(() => document.fullscreenElement)).toBe(null);
    // iPhone Safari gives full screen to a video only: the Family view covers the whole page instead
    await page.evaluate(() => Object.defineProperty(document, "fullscreenEnabled", { value: false, configurable: true }));
    const was = (await drawer(page).boundingBox())!;
    expect(was.y).toBeGreaterThan(0);
    await full.click();
    await expect.poll(async () => (await drawer(page).boundingBox())!.y).toBe(0);
    expect(await covers(page, 20, 20)).toBe(true);
    await page.keyboard.press("Escape");
    await expect.poll(async () => (await drawer(page).boundingBox())!.y).toBe(was.y);
    await full.click();
    await expect.poll(async () => (await drawer(page).boundingBox())!.y).toBe(0);
    await full.click();
    await expect.poll(async () => (await drawer(page).boundingBox())!.y).toBe(was.y);
  });
});

test.describe("the Family view on a desktop window", () => {
  test.use({ storageState: stateFor("play"), viewport: { width: 1440, height: 900 } });

  // R-0791, R-0792
  test("never opens by itself in a short wide window, and goes full screen from its button", async ({ page }, info) => {
    test.skip(info.project.name !== "phone", "the size is the describe's own");
    await settle(page);
    // a desktop window as short as a phone turned sideways is not one
    await page.setViewportSize({ width: 1440, height: 400 });
    await page.waitForTimeout(600);
    await expect(drawer(page)).toBeHidden();
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.locator("#cap-family").click();
    await expect(drawer(page)).toBeVisible();
    await drawer(page).locator(".foot .full").click();
    await expect.poll(() => page.evaluate(() => !!document.fullscreenElement)).toBe(true);
    await drawer(page).locator(".foot .full").click();
    await expect.poll(() => page.evaluate(() => !!document.fullscreenElement)).toBe(false);
  });
});

test.describe("the Family view's frame on a phone turned sideways", () => {
  test.use({ storageState: stateFor("play"), viewport: { width: 852, height: 393 } });

  // R-0784
  test("keeps the drawing in one place on dates with and without someone outside the frame, and whole on the screen", async ({ page }, info) => {
    test.skip(info.project.name !== "phone", "the size is the describe's own");
    await familyOf(page, 2, moving(false));
    const back = drawer(page).locator('[data-act="back"]:not([disabled])');
    while (await back.count()) await back.click();
    const where = async () => [Math.round((await drawer(page).locator(".draw svg").boundingBox())!.y), (await drawer(page).locator(".also").textContent())!];
    const seen = [await where()];
    for (let i = 0; i < 2; i++) {
      await drawer(page).locator('[data-act="next"]').click();
      seen.push(await where());
    }
    // one date names Hs1, outside Cleo's frame, the others no one
    expect(seen.map((s) => s[1])).toContain("Also on this date: Hs1");
    expect(seen.map((s) => s[1])).toContain("");
    expect(new Set(seen.map((s) => s[0])).size).toBe(1);
    expect(await drawer(page).locator(".lv").evaluate((lv) => lv.scrollHeight <= lv.clientHeight + 1)).toBe(true);
  });
});

for (const [w, h, what] of [[852, 393, "a phone turned sideways"], [768, 1024, "an iPad held upright"], [1024, 768, "an iPad turned sideways"], [1440, 900, "a desktop"]] as const)
  test.describe(`the Family view on ${what}`, () => {
    test.use({ storageState: stateFor("play"), viewport: { width: w, height: h } });

    // R-0784
    test("fills the screen, draws four generations where they fit, holds the frame whole, and keeps Back, Next and the title in place", async ({ page }, info) => {
      test.skip(info.project.name !== "phone", "the size is the describe's own");
      const ids = await familyOf(page, 2);
      const box = (await drawer(page).boundingBox())!;
      expect([box.x, box.y, box.width, box.height]).toEqual([0, 0, w, h]);
      // Cleo's four generations, her grandparents on both sides, where four
      // rows fit the height at a readable size; a phone turned sideways has three
      const drawn = await drawnIds(page);
      const grand = [ids().Hal, ids().Hope, ids().Walt, ids().Wren].map(String);
      if (h > 500) expect(drawn).toEqual(expect.arrayContaining(grand));
      else expect(drawn.filter((id) => grand.includes(id))).toEqual([]);
      // walked up to Hugo: his parents and his brothers and sisters, whole without panning
      await tapPerson(page, ids().Hugo);
      expect(await drawer(page).locator(".draw").evaluate((d) => d.scrollWidth <= d.clientWidth)).toBe(true);
      const place = async () => {
        const [n, t] = [await drawer(page).locator('[data-act="next"]').boundingBox(), await drawer(page).locator(".when").boundingBox()];
        return [n!.x, n!.y, t!.y].map(Math.round);
      };
      const before = await place();
      await drawer(page).locator('[data-act="next"]').click();
      expect(await place()).toEqual(before);
      const next = (await drawer(page).locator('[data-act="next"]').boundingBox())!;
      expect(next.y + next.height).toBeLessThanOrEqual(h);
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
    await expect(drawer(page).locator(".path")).toHaveText("Timeline › Family › Ada's family");
    await expect(drawer(page).locator(".dots")).toHaveCount(0);
    const next = drawer(page).locator('[data-act="next"]');
    while (await next.isEnabled()) await next.click();
    const top = drawer(page).locator(".when");
    await expect(top).toHaveText("Ben died");
    await expect(drawer(page).locator(".wire .wlab")).toHaveText("February 2010");
    const picture = () => drawer(page).locator(".draw").innerHTML();
    const dot = drawer(page).locator('.draw .p[data-id="9100"]');
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
    // Dot, who is no one's daughter in this record, stands outside the
    // reader's frame and is named under the title on her own date (R-0783)
    const also = drawer(page).locator(".also");
    await expect(dot).toHaveCount(0);
    await expect(also).toContainText("Dot");
    await tap("back", "");
    await expect(also).not.toContainText("Dot");
    await tap("next", "Dot was born");
    await expect(also).toContainText("Dot");
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

  // R-0742, R-0783, R-0785
  test("shows each step's person on Back and Next, in the frame or by an arrow at its edge", async ({ page }) => {
    const errors = watched(page);
    let ids: Record<string, number> = {};
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, async (route) => {
      const tl = await (await route.fetch()).json();
      ids = joined(tl, [["Hugo", "Wanda"]], 6, "Hs5", "Hugo");
      const blank = { ...tl.events[0], relationship: null, relationshipTargets: [], relationshipTriangles: [], symptom: null, anxiety: null, functioning: null, title: null, description: null, person: null, spouse: null };
      // two births, and two shifts that light no one
      ["Hs0", "Hs5", "Hs1", "Hs4"].forEach((k, i) =>
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
    await drawer(page).evaluate((p) => Promise.all(p.getAnimations().map((a) => a.finished)));
    // the frame walked up to Hugo, whose brothers and sisters these dates are about
    await tapPerson(page, ids.Hugo);
    const shown = async (name: string, what: string) => {
      await expect(drawer(page).locator(".when")).toContainText(`${name} ${what}`);
      await expect.poll(() => inSight(page, ids[name])).toBe(true);
    };
    const next = drawer(page).locator('[data-act="next"]');
    while (await next.isEnabled()) await next.click();
    await shown("Hs4", "left home");
    for (const [name, what] of [["Hs1", "was born"], ["Hs5", "left home"], ["Hs0", "was born"]]) {
      await drawer(page).locator('[data-act="back"]').click();
      await shown(name, what);
    }
    await drawer(page).locator('[data-act="next"]').click();
    await shown("Hs5", "left home");
    expect(await sideways(page)).toBe(false);
    expect(errors).toEqual([]);
  });
});

/** The `case-report-dense` record: a family many phones wide, the step's
 * person far from either end. */
test.describe("the whole family of a family many phones wide", () => {
  test.use({ storageState: stateFor("case-report-dense"), viewport: { width: 393, height: 852 } });

  // R-0759, R-0744, R-0749, R-0766, R-0775, R-0779, R-0787
  test("opens on the first date holding more than births, its person in the frame, names at 9px or more and short, every word inside what the frame scrolls to", async ({ page }) => {
    const errors = watched(page);
    await settle(page);
    await page.locator("#cap-family").click();
    await expect(drawer(page)).toBeVisible();
    // her grandparents' wedding is not hers: it opens on a date among her own three generations
    await expect(drawer(page).locator(".when")).not.toHaveText("Harold and Ruth married");
    await expect(drawer(page).locator(".also")).toHaveText("");
    // opened, not glided: the frame is already on the step's person
    const at = await drawer(page).evaluate((p) => {
      const draw = p.querySelector<HTMLElement>(".draw")!;
      const shape = draw.querySelector(`.p[data-id="${draw.dataset.who}"] .shape`)!.getBoundingClientRect();
      const f = draw.getBoundingClientRect();
      return shape.left >= f.left && shape.right <= f.right;
    });
    expect(at).toBe(true);
    // R-0766: everyone is named as briefly as the Pembertons are, so no name takes more width than the longest of the record's own people's
    const names = await drawer(page).locator(".draw .pt .lbn").allTextContents();
    expect(names.filter((n) => n.length > "Francis-Xavier".length)).toEqual([]);
    expect(await leastName(page, "#pbp .draw svg")).toBeGreaterThanOrEqual(9);
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

test.describe("a play-by-play a little wider than the phone", () => {
  test.use({ storageState: stateFor("everymark"), viewport: { width: 393, height: 852 } });

  // R-0759
  test("lands each step where no name or word is cut by the frame, whenever they all fit in it", async ({ page }) => {
    await settle(page);
    await stored(page).click();
    await expect(drawer(page)).toBeVisible();
    const draw = drawer(page).locator(".draw");
    expect(await draw.evaluate((d) => d.scrollWidth > d.clientWidth)).toBe(true);
    const cut: string[] = [];
    let fitting = 0;
    for (;;) {
      let last = -1;
      await expect.poll(async () => {
        const at = await draw.evaluate((d) => d.scrollLeft);
        const still = at === last;
        last = at;
        return still;
      }, { intervals: [400] }).toBe(true);
      const seen = await draw.evaluate((d) => {
        const f = d.getBoundingClientRect();
        const [left, right] = [f.left + d.clientLeft, f.left + d.clientLeft + d.clientWidth];
        const marks = [...d.querySelectorAll(".pt text, text.evw")].map((t) => ({ t: t.textContent!, b: t.getBoundingClientRect() })).filter((m) => m.b.width);
        const lo = Math.min(...marks.map((m) => m.b.left));
        const hi = Math.max(...marks.map((m) => m.b.right));
        return { fits: hi - lo <= d.clientWidth, cut: marks.filter((m) => m.b.left < left - 0.5 || m.b.right > right + 0.5).map((m) => m.t) };
      });
      if (seen.fits) {
        fitting++;
        const at = await step(page);
        cut.push(...seen.cut.map((t) => `${at}: ${t}`));
      }
      const next = drawer(page).locator('[data-act="next"]:not([disabled])');
      if (!(await next.count())) break;
      await next.click();
    }
    expect(fitting).toBeGreaterThan(10);
    expect(cut).toEqual([]);
  });
});

/** Margaret-Anne's wide family (`case-report-dense`), its whole family opened
 * from the Family button at the phone's width and the desktop's. */
for (const viewport of [{ width: 393, height: 852 }, { width: 1440, height: 900 }])
  test.describe(`the whole family of a wide record at ${viewport.width} wide`, () => {
    test.use({ storageState: stateFor("case-report-dense"), viewport });

    // R-0759, R-0766, R-0775, R-0783
    test("opens on the first date holding more than births, on the record's own person whole in the frame, and no name touches another", async ({ page }, info) => {
      test.skip(info.project.name !== "phone", "the size is the describe's own");
      await settle(page);
      await page.locator("#cap-family").click();
      await expect(drawer(page)).toBeVisible();
      await drawer(page).evaluate((p) => Promise.all(p.getAnimations().map((a) => a.finished)));
      // it opens on a date among her own generations: on a phone her
      // grandparents' wedding is outside her frame, on a wide screen inside it (R-0784)
      if (viewport.width < 700) await expect(drawer(page).locator(".when")).not.toHaveText("Harold and Ruth married");
      else await expect(drawer(page).locator('.draw .pt:has(text:text-is("Harold"))')).toHaveCount(1);
      await expect(drawer(page).locator(".also")).toHaveText("");
      // the frame is hers; the opening date's own person stands whole in it
      const who = (await drawer(page).locator(".draw").getAttribute("data-who"))!;
      expect((await cutInFrame(page, "#pbp .draw", [who])).cut).toEqual({});
      const touching = await drawer(page).evaluate((p) => {
        const boxes = [...p.querySelectorAll<SVGGElement>(".draw .pt")]
          .map((g) => ({ name: g.textContent!.slice(0, 16), b: g.getBoundingClientRect() }))
          .filter((n) => n.b.width);
        return boxes.flatMap((a, i) =>
          boxes
            .slice(i + 1)
            .filter((c) => a.b.left < c.b.right && c.b.left < a.b.right && a.b.top < c.b.bottom + 4 && c.b.top < a.b.bottom + 4)
            .map((c) => `${a.name} / ${c.name}`),
        );
      });
      expect(touching).toEqual([]);
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
    // the frame walked up to Walter, whose father the cutoff is about
    await tapPerson(page, 3);
    await nextTo(page, "Walter stopped calling his father");
    const whole = await reach(page);
    expect(told.ring / told.person).toBeCloseTo(whole.ring / whole.person, 1);
    expect(told.ring / told.person).toBeGreaterThan(3);
    expect(told.width / told.person).toBeCloseTo(whole.width / whole.person, 2);
  });
});

/** A play-by-play many phones wide, stepped with Next as Patrick steps it. */
test.describe("the frame's travel to a step's people", () => {
  test.use({ storageState: stateFor("play"), viewport: { width: 393, height: 852 } });

  // R-0778
  test("sets off from where the frame stood, eases to exactly where it lands without passing it, taking longer the further it goes", async ({ page }) => {
    // the moves go back and forth between the two ends of the family
    await page.route(/\/app\/timeline(\?diagram_id=\d+)?$/, async (route) => {
      const tl = await (await route.fetch()).json();
      const ids = joined(tl, [["Hugo", "Wanda"]], 6, "Ws5", "Hs5");
      tl.events
        .filter((e: { dateTime: string | null }) => e.dateTime)
        .sort((a: { dateTime: string }, b: { dateTime: string }) => a.dateTime.localeCompare(b.dateTime))
        .forEach((e: Record<string, unknown>, i: number) => Object.assign(e, i % 2 ? { person: ids.Hs5, relationshipTargets: [ids.Ws5] } : {}));
      await route.fulfill({ json: tl });
    });
    await settle(page);
    await stored(page).click();
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
          if (performance.now() - t0 < 2800) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      });
      await button.click();
      await page.waitForTimeout(2900);
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
      // about 1,200 px a second, never under half a second nor over two
      const set = t.find(([, x]) => Math.abs(x - from) > 0)![0];
      const landed = t.find(([, x]) => Math.abs(x - to) <= 1)![0] - set;
      const ms = Math.min(Math.max(Math.abs(to - from) / 1.2, 500), 2000);
      // the ease is within a pixel of its end for its last few hundredths
      expect(landed).toBeGreaterThan(ms * 0.85);
      expect(landed).toBeLessThan(ms + 150);
    }
  });
});
