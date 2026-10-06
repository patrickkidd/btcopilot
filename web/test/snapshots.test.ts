import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { arrange, bar, crosses, draw, Mark, Side, VIEW, layout, Sex, Tie, type Cast, type Layout } from "../src/diagram";
import { FIELD, Move } from "../src/moves";
import { among, family as wholeFamily, familyStart, gapText, Told, untold } from "../src/snapshots";
import type { Case, Timeline } from "../src/types";
import {
  apart,
  CORINNE,
  death,
  DELPHINE,
  ERROL,
  event,
  MARCUS,
  ODILE,
  PARTNER,
  THEO,
  timeline,
} from "./whitlock";

/** The play-by-play drawing, read off the markup each snapshot draws for the
 * Whitlock stand-in family. */

const ROOM = "Moved out";

type El = Record<string, string>;
const els = (svg: string, tag: string, klass?: string): El[] =>
  [...svg.matchAll(new RegExp(`<${tag}\\s([^>]*?)/?>`, "g"))]
    .map(([, body]) => Object.fromEntries([...body.matchAll(/([\w:-]+)="([^"]*)"/g)].map((m) => [m[1], m[2]])))
    .filter((e) => !klass || (e.class ?? "").split(" ").includes(klass));
const marks = (svg: string) => [...svg.matchAll(/data-mark="([^"]*)"/g)].map((m) => m[1]);
const markClass = (svg: string, mark: string) =>
  svg.match(new RegExp(`class="([^"]*)"[^>]*data-mark="${mark.replace(/[>]/g, "&gt;")}"`))?.[1] ?? "";

const told = (c: Case = apart(), tl: Timeline = timeline()) => new Told(tl, c);
const cast = (t: Told) => Object.keys(t.cast.people).map(Number).sort();

const base = (people: Cast["people"]): Cast => ({
  people,
  bonds: [{ a: "a", b: "b", st: Tie.Married, married: true }],
  kids: [{ of: ["a", "b"], kids: ["c", "d"] }],
  index: "c",
  marked: [],
  cross: [],
  words: {},
  moves: [],
  kin: [],
  places: [],
  anxious: [],
  assoc: {},
  until: 2000,
});
const shape = (name: string, g: Sex, born: number) => ({ name, g, born });

const family = () =>
  base({
    a: shape("Marcus Whitlock", Sex.Male, 1951),
    b: shape("Delphine Reyes", Sex.Female, 1953),
    c: { ...shape("Corinne Whitlock", Sex.Female, 1975), you: true },
    d: shape("Theo Whitlock", Sex.Male, 1979),
  });

describe("the cast", () => {
  // R-0545
  it("is you, everyone the case's events name, and the parents that connect them; nobody else", () => {
    // Theo's day care is in the case, though no snapshot shows it
    expect(cast(told(apart()))).toEqual([MARCUS, DELPHINE, CORINNE, THEO].sort());
  });

  // R-0545
  it("takes both partners of a couple whose line changes", () => {
    const c = apart();
    c.snapshots = c.snapshots.filter((s) => s.event_ids[0] !== 208);
    c.snapshots.push({ date: "1981-06-15", event_ids: [204], fact: "again", guess: null });
    expect(cast(told(c))).toContain(DELPHINE);
  });

  // R-0545
  it("follows descent up a generation to a grandparent, with both partners of the couple the child hangs from", () => {
    expect(cast(told(death()))).toEqual([ERROL, ODILE, MARCUS, DELPHINE, CORINNE].sort());
  });

  // R-0545
  it("takes both parents when two of their children are in it", () => {
    const tl = timeline();
    tl.events.push(event(300, "1998-04-01", "shift", THEO, { description: "Came home", relationship: "toward", relationshipTargets: [CORINNE] }));
    const c = death();
    c.snapshots[0].event_ids = [130, 300];
    expect(cast(told(c, tl))).toContain(THEO);
  });

  // R-0553
  it("draws a stand-in partner for a child with one recorded parent", () => {
    const tl = timeline();
    tl.pair_bonds.push({ id: 23, person_a: DELPHINE, person_b: null, married: false });
    tl.people.push({ ...tl.people[5], id: 8, name: "Lena", gender: "female", parents: 23, primary: false });
    tl.events.find((e) => e.id === 131)!.relationshipTargets = [8];
    const t = told(death(), tl);
    expect(t.cast.people[`unknown-${DELPHINE}`]).toMatchObject({ g: Sex.Unknown });
    expect(t.shot(1).svg).toMatch(/<text class="age"[^>]*>\?<\/text>/);
  });

  // R-0545
  it("never draws an unconnected partner", () => {
    expect(cast(told(apart()))).not.toContain(PARTNER);
  });
});

describe("the layout", () => {
  const L = told(death()).layout;
  const at = (id: number) => L.x[String(id)];

  // R-0545, R-0546, R-0187
  it("puts the generations in rows, oldest on top", () => {
    expect(L.y[String(ODILE)]).toBeLessThan(L.y[String(MARCUS)]);
    expect(L.y[String(MARCUS)]).toBeLessThan(L.y[String(CORINNE)]);
    expect(L.y[String(MARCUS)]).toBe(L.y[String(DELPHINE)]);
  });

  // R-0545, R-0187
  it("puts the man of a couple on the left", () => {
    expect(at(MARCUS)).toBeLessThan(at(DELPHINE));
  });

  // R-0545, R-0187
  it("puts siblings oldest on the left", () => {
    const tl = timeline();
    tl.events.push(event(300, "1998-04-01", "shift", THEO, { relationship: "toward", relationshipTargets: [CORINNE] }));
    const c = death();
    c.snapshots[0].event_ids = [130, 300];
    const S = told(c, tl).layout;
    expect(S.x[String(CORINNE)]).toBeLessThan(S.x[String(THEO)]);
  });

  // R-0559
  it("puts a later partner opposite the earlier one, so no couple line passes under a third person", () => {
    const partner = (a: string, b: string) => ({ a, b, st: Tie.Divorced, married: true });
    const L = layout({
      ...family(),
      people: {
        me: { name: "Rhea", g: Sex.Female, born: 1950, you: true },
        first: { name: "Abe", g: Sex.Male, born: 1948 },
        second: { name: "Ben", g: Sex.Male, born: 1949 },
        third: { name: "Cora", g: Sex.Female, born: 1955 },
      },
      bonds: [partner("first", "me"), partner("second", "me"), partner("second", "third")],
      kids: [],
      index: "me",
    });
    const [me, first, second, third] = ["me", "first", "second", "third"].map((id) => L.x[id]);
    expect(Math.sign(first - me)).toBe(-Math.sign(second - me));
    expect(Math.abs(third - me)).toBeGreaterThan(Math.abs(second - me));
    expect(Math.sign(third - me)).toBe(Math.sign(second - me));
  });

  // R-0550
  it("hangs each couple's children under its own bar, reaching half a width past the outer ones", () => {
    const S = layout(family());
    expect(Math.min(S.x.a, S.x.b)).toBeCloseTo(S.x.c - S.w / 2, 0);
    expect(Math.max(S.x.a, S.x.b)).toBeCloseTo(S.x.d + S.w / 2, 0);
  });

  // R-0558
  it("keeps the family inside a 24px side margin and a 20px top and bottom margin at 393 wide", () => {
    const MX = (24 * VIEW) / 393;
    const MY = (20 * VIEW) / 393;
    for (const t of [told(apart()), told(death())]) {
      const S = t.layout;
      const scale = S.vw / VIEW;
      S.names.forEach((b) => {
        expect(b.x0 + 2).toBeGreaterThanOrEqual(MX * scale - 0.5);
        expect(b.x1 - 2).toBeLessThanOrEqual(S.vw - MX * scale + 0.5);
      });
      Object.keys(S.P).forEach((id) => {
        expect(S.y[id] - S.w / 2).toBeGreaterThanOrEqual(MY * scale - 0.5);
        expect(S.y[id] + S.w / 2).toBeLessThanOrEqual(S.h - MY * scale + 0.5);
      });
    }
  });

  // R-0547
  it("draws people 44 across where the row fits", () => {
    expect(L.w).toBe(44);
  });
});

describe("names", () => {
  // R-0548
  it("are first names only", () => {
    const L = layout(family());
    expect(L.P.a.name).toBe("Marcus");
    expect(L.P.c.name).toBe("Corinne");
  });

  // R-0548
  it("carry a surname initial only for two people in one picture who share a first name, in one row or not", () => {
    const L = layout(
      base({
        a: shape("Anna Kerr", Sex.Male, 1950),
        b: shape("Anna Lowe", Sex.Female, 1952),
        c: { ...shape("Anna Kerr", Sex.Female, 1975), you: true },
        d: shape("Theo Kerr", Sex.Male, 1979),
      }),
    );
    expect([L.P.a.name, L.P.b.name, L.P.c.name, L.P.d.name]).toEqual(["Anna K.", "Anna L.", "Anna K.", "Theo"]);
  });

  // R-0766, R-0759
  it("name a stand-in by the nearest named person and the relation, in the record's own words", () => {
    const L = layout(
      base({
        a: shape("Delphine's mother's partner", Sex.Male, 1920),
        b: shape("Delphine's mother", Sex.Female, 1922),
        c: { ...shape("Delphine Moreau", Sex.Female, 1950), you: true },
        d: shape("Theo Moreau's partner", Sex.Female, 1954),
      }),
    );
    expect([L.P.a.name, L.P.b.name, L.P.c.name, L.P.d.name]).toEqual(["Delphine's mother's partner", "Delphine's mother", "Delphine", "Theo's partner"]);
  });



  // R-0549
  it("leave a person's cross close by, on the side away from the name", () => {
    const t = told(apart());
    const L = t.layout;
    const id = String(MARCUS);
    const [at, k, local] = t
      .shot(1)
      .svg.match(/transform="translate\(([\d.]+) [\d.]+\) scale\(([\d.]+)\)"><g class="mv-sym" transform="translate\((-?[\d.]+) /)!
      .slice(1)
      .map(Number);
    const cx = at + k * local;
    const away = L.side[id] === Side.Right ? -1 : 1;
    expect(Math.sign(cx - L.x[id])).toBe(away);
    const gap = Math.abs(cx - L.x[id]) - 8 * k - L.w / 2;
    expect(gap).toBeLessThanOrEqual(L.w / 8 + 0.1);
  });

  // R-0548, R-0566
  it("sit beside or above the shapes, and under them only as a last resort", () => {
    const L = told(death()).layout;
    Object.values(L.side).forEach((s) => expect([Side.Right, Side.Left, Side.Above, Side.Top]).toContain(s));
  });

  // R-0545, R-0555
  it("are never crossed by a move's arrow", () => {
    // Delphine toward Odile runs up through the row names unless they move off it
    const tl = timeline();
    tl.events.find((e) => e.id === 131)!.relationshipTargets = [ODILE];
    const t = told(death(), tl);
    const arrows = els(t.shot(4).svg, "line").filter((l) => !l.class);
    expect(arrows).toHaveLength(2);
    arrows.forEach((a) =>
      t.layout.names.forEach((box) =>
        expect(crosses([[Number(a.x1), Number(a.y1)], [Number(a.x2), Number(a.y2)]], box)).toBe(false),
      ),
    );
  });
});

describe("bonds", () => {
  // R-0560
  it("are solid when married and dashed when never married", () => {
    const t = told(apart());
    const b = els(t.shot(0).svg, "path", "tie");
    expect(b.every((e) => !e.class.includes("dash"))).toBe(true);
    const tl = timeline();
    tl.pair_bonds[1].married = false;
    tl.events = tl.events.filter((e) => ![109, 204].includes(e.id));
    tl.clusters[0].event_ids = tl.clusters[0].event_ids.filter((id) => id !== 204);
    const c = apart();
    c.snapshots[2] = { date: "1981-09-15", event_ids: [205], fact: "day care", guess: null };
    expect(els(told(c, tl).shot(0).svg, "path", "tie")[0].class).toContain("dash");
  });

  // R-0560
  it("take one upright slash when separated and two when divorced", () => {
    const t = told(apart());
    expect(els(t.shot(0).svg, "line", "slash")).toHaveLength(1);
    expect(els(t.shot(1).svg, "line", "slash")).toHaveLength(1);
    const two = els(t.shot(2).svg, "line", "slash");
    expect(two).toHaveLength(2);
    two.forEach((s) => expect(s.x1).toBe(s.x2));
  });

  // R-0552
  it("put the new slash in the emphasis colour on its date only", () => {
    const t = told(apart());
    expect(els(t.shot(2).svg, "line", "slash").filter((s) => s.class.includes("now"))).toHaveLength(1);
    expect(els(t.shot(3).svg, "line", "slash").filter((s) => s.class.includes("now"))).toHaveLength(0);
  });
});

describe("emphasis and carry", () => {
  // R-0552
  it("draws the current snapshot in the emphasis colour and everything earlier in grey", () => {
    const t = told(apart());
    expect(markClass(t.shot(1).svg, `cross:${MARCUS}`)).toContain("now");
    expect(markClass(t.shot(2).svg, `cross:${MARCUS}`)).toContain("was");
    expect(markClass(t.shot(0).svg, `hl:${MARCUS}`)).toContain("now");
    expect(markClass(t.shot(1).svg, `hl:${MARCUS}`)).toContain("was");
  });

  // R-0556, R-0682
  it("never loses anything already drawn across a tap", () => {
    for (const c of [apart(), death()]) {
      const t = told(c);
      for (let i = 1; i < t.length; i++) {
        // an event's words are the one exception: they show on their own step only (R-0682)
        const had = new Set(marks(t.shot(i - 1).svg).filter((m) => !m.startsWith("word:")));
        const has = new Set(marks(t.shot(i).svg));
        had.forEach((m) => expect(has, `${c.cluster_id} snapshot ${i + 1} lost ${m}`).toContain(m));
      }
    }
  });

  // R-0556
  it("carries functioning and anxiety marks in grey", () => {
    const tl = timeline();
    const scans = tl.events.find((e) => e.id === 131)!;
    scans.functioning = "down";
    scans.anxiety = "up";
    scans.relationship = null;
    scans.relationshipTargets = [];
    const t = told(death(), tl);
    expect(markClass(t.shot(1).svg, `fdown:${DELPHINE}`)).toContain("now");
    expect(markClass(t.shot(2).svg, `fdown:${DELPHINE}`)).toContain("was");
    expect(markClass(t.shot(2).svg, `anx:${DELPHINE}`)).toContain("was");
  });

  // R-0554
  it("draws no teal dot: the people and their marks carry the emphasis", () => {
    const t = told(death());
    for (let i = 0; i < t.length; i++) expect(t.shot(i).svg).not.toMatch(/<circle class="(wd|evdot|dot)/);
  });

  // R-0557
  it("flips a cross in place rather than drawing two", () => {
    const t = told(apart());
    expect(marks(t.shot(3).svg).filter((m) => m === `cross:${MARCUS}`)).toHaveLength(1);
  });

  // R-0552
  it("draws a death X in the emphasis colour on its date and in plain ink after", () => {
    const t = told(death());
    const x = (i: number) => els(t.shot(i).svg, "path", "xd").map((e) => e.class);
    expect(x(0)).toContain("xd now pop");
    expect(x(1).every((c) => c === "xd")).toBe(true);
  });

  // R-0136
  it("shows a move's direction: its arrow runs from the mover to whoever it reaches", () => {
    const t = told(death());
    const [line] = els(t.shot(1).svg, "line").filter((l) => !l.class);
    const d = (x: number, y: number, id: number) => Math.hypot(x - t.layout.x[String(id)], y - t.layout.y[String(id)]);
    expect(d(Number(line.x1), Number(line.y1), DELPHINE)).toBeLessThan(d(Number(line.x1), Number(line.y1), CORINNE));
    expect(d(Number(line.x2), Number(line.y2), CORINNE)).toBeLessThan(d(Number(line.x2), Number(line.y2), DELPHINE));
  });

  // R-0161
  it("never writes a symbol's name, only what people reported", () => {
    for (const c of [apart(), death()]) {
      const t = told(c);
      for (let i = 0; i < t.length; i++)
        expect(t.shot(i).svg.replace(/<[^>]*>/g, " ")).not.toMatch(/toward|away|distance|cutoff|conflict|symptom|functioning|anxiety/i);
    }
  });

  // R-0555, R-0556, R-0557
  it("carries earlier moves in grey and never animates them", () => {
    const t = told(death());
    expect(markClass(t.shot(1).svg, `move:${DELPHINE}>${CORINNE}:toward`)).toMatch(/\bpop\b/);
    const carried = markClass(t.shot(2).svg, `move:${DELPHINE}>${CORINNE}:toward`);
    expect(carried).toContain("was");
    expect(carried).not.toMatch(/\bpop\b/);
  });

  // R-0551
  it("gives an event with no drawing of its own a word and the person in the emphasis colour", () => {
    const svg = told(apart()).shot(0).svg;
    expect(marks(svg)).toEqual(expect.arrayContaining([`word:${MARCUS}:${ROOM}`, `hl:${MARCUS}`]));
  });

  // R-0681
  it("writes an event's whole title beside the person, never cut", () => {
    const c = apart();
    const tl = timeline();
    tl.events.find((e) => e.id === 202)!.title = "Moved to the coast";
    expect(marks(told(c, tl).shot(0).svg)).toContain(`word:${MARCUS}:Moved to the coast`);
  });

});

describe("the captions", () => {
  // R-0563
  it("date each snapshot and say the gap since the last", () => {
    const t = told(apart());
    expect(t.shot(0)).toMatchObject({ date: "Sep 1980", gap: null });
    expect(t.shot(1)).toMatchObject({ date: "Jan 1981", gap: "four months later" });
  });

  // R-0563
  it("show each date only as sure as the record is", () => {
    const tl = timeline();
    tl.events.find((e) => e.id === 203)!.dateCertainty = "approximate";
    tl.events.find((e) => e.id === 204)!.dateCertainty = "unknown";
    const t = told(apart(), tl);
    expect([t.shot(1).date, t.shot(2).date]).toEqual(["1981", "date unknown"]);
  });

  // R-0563
  it("end the last snapshot with the coach's question, and only the last", () => {
    const t = told(apart());
    expect(t.shot(3).question).toBeNull();
    expect(t.shot(4).question).toBe(apart().question);
  });

  // R-0563
  it("say gaps in plain words", () => {
    expect(gapText(2000, 2000 + 1 / 12)).toBe("one month later");
    expect(gapText(2000, 2000 + 7 / 12)).toBe("seven months later");
    expect(gapText(2000, 2001.1)).toBe("a year later");
  });
});


/** Parents and `n` sons in one row, the oldest the reader. */
/** A picture with nothing marked on it. */
const frame = (L: Layout) => ({
  t: 2000,
  bonds: L.bonds.map((b) => ({ ...b, fresh: false, hot: false })),
  marks: [],
  died: new Set<string>(),
  moves: [],
  kin: [],
  label: "",
});

/** The family's lines in a drawing, each as its two ends. */
const lines = (svg: string) =>
  els(svg, "path", "kin").map((p) => {
    const [x0, y0, x1, y1] = p.d.match(/^M(\S+) (\S+)L(\S+) (\S+)$/)!.slice(1).map(Number);
    return [[x0, y0], [x1, y1]] as [[number, number], [number, number]];
  });

const brood = (n: number): Cast => {
  const kids = Array.from({ length: n }, (_, i) => `k${i}`);
  const people: Cast["people"] = { a: shape("Abe", Sex.Male, 1940), b: shape("Bea", Sex.Female, 1942) };
  kids.forEach((id, i) => (people[id] = { ...shape(["Cy", "Di", "Ed", "Flo", "Gus"][i], Sex.Male, 1960 + i), you: i === 0 }));
  return { ...base(people), kids: [{ of: ["a", "b"], kids }], index: "k0" };
};

describe("a crowded row", () => {
  // R-0566, R-0744
  it("moves names above the shapes when beside them does not fit, and scrolls a row too wide for that", () => {
    const L = arrange(brood(4));
    expect(new Set(["k0", "k1", "k2", "k3"].map((id) => L.side[id]))).toEqual(new Set([Side.Above]));
    expect(L.vw).toBeGreaterThan(VIEW);
  });

  // R-0566, R-0759
  it("puts names under the shapes only when neither beside nor above fits", () => {
    const L = arrange(brood(3));
    expect(["k0", "k1", "k2"].every((id) => L.side[id] === Side.Under)).toBe(true);
    // the children's lines never run through their parents' names
    const drawn = lines(draw(L, frame(L)));
    expect(drawn.length).toBeGreaterThanOrEqual(3);
    drawn.forEach((sg) => L.names.forEach((b) => expect(crosses(sg, b)).toBe(false)));
    expect(L.vw).toBe(VIEW);
    expect(L.w).toBe(44);
  });

  // R-0547
  // re-ruled 2026-10-04, scroll below the floor
  it("keeps a row of five or more at the drawer's least size and scrolls its frame sideways", () => {
    const L = arrange(brood(5));
    expect(Object.keys(L.P)).toHaveLength(7);
    expect(L.vw).toBeGreaterThan(VIEW);
    expect(L.px).toBeGreaterThanOrEqual(36);
    const css = readFileSync(new URL("../src/drawer.css", import.meta.url), "utf8");
    expect(css).toMatch(/\.pbp \.draw \{[^}]*overflow-x: auto/);
  });

  // R-0558, R-0759, R-0744
  it("never shrinks the people against their names in a wide row, keeping the margin on the screen", () => {
    expect(arrange(brood(2))).toMatchObject({ w: 44, px: 44, vw: VIEW });
    const L = arrange(brood(5));
    expect(L).toMatchObject({ w: 44, px: 44 });
    expect(L.vw).toBeGreaterThan(VIEW);
    // the margin keeps its size on the screen, whatever the picture's scale
    const margin = ((24 * VIEW) / 393) * (L.w / L.px);
    L.names.forEach((b) => {
      expect(b.x0 + 2).toBeGreaterThanOrEqual(margin - 0.5);
      expect(b.x1 - 2).toBeLessThanOrEqual(L.vw - margin + 0.5);
    });
  });
});

// R-0546
it("keeps every person where they stand from the first snapshot to the last", () => {
  const at = (svg: string) =>
    [...svg.matchAll(/<g class="p" data-id="(\w+)"><(?:rect|circle) class="\w+" (?:x|cx)="([\d.]+)" (?:y|cy)="([\d.]+)"/g)].map((m) =>
      m.slice(1).join(" "),
    );
  for (const c of [apart(), death()]) {
    const t = told(c);
    const first = at(t.shot(0).svg);
    expect(first.length).toBe(Object.keys(t.layout.P).length);
    for (let i = 1; i < t.length; i++) expect(at(t.shot(i).svg)).toEqual(first);
  }
});

describe("the drawing's marks", () => {
  // R-0549
  it("writes an event's words beside the person, on the side away from the name", () => {
    const t = told(apart());
    const id = String(MARCUS);
    const word = els(t.shot(0).svg, "text", "evw")[0];
    expect(Math.sign(Number(word.x) - t.layout.x[id])).toBe(t.layout.side[id] === Side.Right ? -1 : 1);
  });

  // R-0550
  it("draws the couple line through to half a width past the outer children", () => {
    const S = layout(family());
    const tie = draw(S, {
      t: 2000,
      bonds: S.bonds.map((b) => ({ ...b, fresh: false, hot: false })),
      marks: [],
      died: new Set(),
      moves: [],
      kin: [],
      label: "",
    }).match(/<path class="tie" data-bond="a\|b" d="M([\d.]+) [\d.]+V[\d.]+H([\d.]+)/)!;
    expect(Number(tie[1])).toBeCloseTo(S.x.c - S.w / 2, 0);
    expect(Number(tie[2])).toBeCloseTo(S.x.d + S.w / 2, 0);
  });

  // R-0560
  it("sets a separation's slash on the couple line clear of any child's line", () => {
    const S = layout({
      ...base({ a: shape("Abe", Sex.Male, 1940), b: shape("Bea", Sex.Female, 1942), c: { ...shape("Cy", Sex.Male, 1960), you: true } }),
      kids: [{ of: ["a", "b"], kids: ["c"] }],
    });
    const svg = draw(S, {
      t: 2000,
      bonds: [{ a: "a", b: "b", st: Tie.Separated, married: true, fresh: true, hot: false }],
      marks: [],
      died: new Set(),
      moves: [],
      kin: [],
      label: "",
    });
    const slash = els(svg, "line", "slash");
    expect(slash).toHaveLength(1);
    expect(slash[0].class).toContain("now");
    const kin = [...svg.matchAll(/<path class="kin" d="M([\d.]+) /g)].map((m) => Number(m[1]));
    kin.forEach((x) => expect(Math.abs(Number(slash[0].x1) - x)).toBeGreaterThan(S.w / 4));
  });

  // R-0758
  it("draws a divorce's slashes two thirds as tall as a person, crossing the couple line where they always did", () => {
    const S = layout(family());
    const svg = draw(S, {
      t: 2000,
      bonds: [{ a: "a", b: "b", st: Tie.Divorced, married: true, fresh: false, hot: false }],
      marks: [],
      died: new Set(),
      moves: [],
      kin: [],
      label: "",
    });
    const line = Number(svg.match(/<path class="tie[^"]*"[^>]* d="M[\d.]+ [\d.]+V([\d.]+)H/)![1]);
    const slash = els(svg, "line", "slash");
    expect(slash).toHaveLength(2);
    slash.forEach((l) => {
      expect(Number(l.y1) - Number(l.y2)).toBeCloseTo((2 / 3) * S.w, 0);
      expect((Number(l.y1) - line) / (line - Number(l.y2))).toBeCloseTo(0.15 / 0.25, 1);
    });
  });

  // R-0551
  it("writes an event's word clear of the couple line", () => {
    for (const c of [apart(), death()]) {
      const t = told(c);
      for (let i = 0; i < t.length; i++) {
        const svg = t.shot(i).svg;
        const bars = [...svg.matchAll(/<path class="tie[^"]*" data-bond="[^"]*" d="M([\d.]+) ([\d.]+)V([\d.]+)H([\d.]+)V([\d.]+)"/g)].map((m) => m.slice(1).map(Number));
        els(svg, "text", "evw").forEach((w) => {
          const x0 = Number(w.x);
          const text = svg.match(new RegExp(`data-mark="${w["data-mark"]}"[^>]*>([^<]*)<`))![1];
          const [left, right] = w["text-anchor"] === "end" ? [x0 - text.length * 13 * 0.6, x0] : [x0, x0 + text.length * 13 * 0.6];
          const [top, bottom] = [Number(w.y) - 11, Number(w.y) + 4];
          bars.forEach(([bx0, , by, bx1]) => {
            const crosses = by >= top - 2 && by <= bottom + 2 && right >= bx0 && left <= bx1;
            expect(crosses, `${w["data-mark"]} touches the couple line`).toBe(false);
          });
        });
      }
    }
  });

  // R-0550
  it("centres an only child under its parents' line", () => {
    const S = layout({
      ...base({ a: shape("Abe", Sex.Male, 1940), b: shape("Bea", Sex.Female, 1942), c: { ...shape("Cy", Sex.Male, 1960), you: true } }),
      kids: [{ of: ["a", "b"], kids: ["c"] }],
    });
    expect((S.x.a + S.x.b) / 2).toBeCloseTo(S.x.c, 0);
  });

  // R-0553
  it("draws the stand-in partner as the spec's rounded shape with a question mark", () => {
    const tl = timeline();
    tl.pair_bonds.push({ id: 23, person_a: DELPHINE, person_b: null, married: false });
    tl.people.push({ ...tl.people[5], id: 8, name: "Lena", gender: "female", parents: 23, primary: false });
    tl.events.find((e) => e.id === 131)!.relationshipTargets = [8];
    const svg = told(death(), tl).shot(1).svg;
    expect(svg.match(/<g class="p" data-id="unknown-4">(.*?)<\/g>/)![1]).toMatch(/<rect class="shape"[^>]* rx="/);
    expect(svg.match(/<g class="pt" data-id="unknown-4">(.*?)<\/g>/)![1]).toContain(">?</text>");
  });

  // R-0554
  it("marks an event with the person and a word, never a dot", () => {
    const svg = told(apart()).shot(0).svg;
    expect(svg).toContain('class="evw');
    expect(svg).not.toMatch(/<circle (?!class="(shape|you|hl))/);
  });
});

// R-0555, R-0547
it("styles a move as the board's flowing dashed arrow, and every label at 13px or more", () => {
  const css = readFileSync(new URL("../src/drawer.css", import.meta.url), "utf8");
  expect(css).toMatch(/\.pbp \.arr line \{[^}]*stroke: var\(--move\);[^}]*stroke-dasharray: 10 8;[^}]*animation: pbp-flow/);
  const sizes = [...css.matchAll(/\.diagram \.(lbn|lbd|age|evw) \{[^}]*font-size: (\d+)px/g)].map((m) => Number(m[2]));
  expect(sizes).toHaveLength(4);
  sizes.forEach((s) => expect(s).toBeGreaterThanOrEqual(13));
});

describe("moves other than toward and away", () => {
  const moved = (kind: string, targets = [CORINNE]) => {
    const tl = timeline();
    const e = tl.events.find((e) => e.id === 131)!;
    e.relationship = kind;
    e.relationshipTargets = targets;
    return told(death(), tl);
  };
  const DRAWN: [string, RegExp][] = [
    ["distance", /class="mv-wall"/],
    ["cutoff", /class="mv-strike/],
    ["conflict", /class="mv-spark"/],
    ["fusion", /class="mv-band"/],
    ["projection", /class="mv-flow"/],
    ["overfunctioning", /class="mv-flank up"/],
    ["underfunctioning", /class="mv-flank down"/],
    ["defined-self", /class="mv-clear"/],
  ];

  // R-0555
  it.each(DRAWN)("draws %s in the moves board's own drawing", (kind, drawn) => {
    const svg = moved(kind).shot(1).svg;
    const group = svg.match(new RegExp(`<g class="mvk now" data-mark="move:${DELPHINE}&gt;${CORINNE}:${kind}">.*?</g>(?=<g class="mvk|</svg>)`))!;
    expect(group[0]).toMatch(drawn);
  });

  // R-0776
  it("runs every field's rings out to the one reach, however near its person stands to the picture's edge, the clearing of one who holds their ground too", () => {
    const reaches = ["distance", "cutoff", "defined-self"].flatMap((kind) =>
      [...moved(kind).shot(1).svg.matchAll(/<circle class="(fld[^"]*|mv-clear)"[^>]*><animate attributeName="r" values="[\d.]+;([\d.]+)"/g)].map((m) => `${kind} ${m[1]} ${m[2]}`),
    );
    expect(reaches.filter((r) => r.includes("mv-clear"))).toHaveLength(1);
    expect(reaches.filter((r) => !r.endsWith(` ${FIELD}`))).toEqual([]);
  });

  // R-0555, R-0556, R-0557
  it("carries an earlier move in grey and still", () => {
    const svg = moved("distance").shot(2).svg;
    const carried = svg.slice(svg.indexOf('<g class="mvk was"'));
    expect(carried).toContain('class="mv-wall"');
    expect(carried.slice(0, carried.indexOf("</svg>"))).not.toMatch(/<animate/);
  });

  // R-0728, R-0763, R-0764
  it.each(["inside", "outside"])("moves the three people of %s for its step over and over, all three lit, their family lines stretched, and has them home at once on the next", (kind) => {
    const tl = moved(kind).tl;
    tl.events.find((e) => e.id === 131)!.relationshipTriangles = [Number(MARCUS)];
    const three = told(death(), tl);
    const svg = three.shot(1).svg;
    expect(svg).not.toContain('class="mvk');
    expect(marks(svg)).not.toContain(`word:${DELPHINE}:Called Corinne nightly`);
    const lit = marks(svg).filter((m) => m.startsWith("hl:") && markClass(svg, m).includes("now"));
    expect(lit.sort()).toEqual([DELPHINE, CORINNE, MARCUS].map((id) => `hl:${id}`).sort());
    expect(svg).toContain('class="tie stretch"');
    // each loop starts again from home at a jump: from home, to the place, held there
    const slides = [...svg.matchAll(/<g class="slid" transform="translate\(([^)]*)\)"><animateTransform ([^>]*)\/>/g)];
    expect(slides.length).toBeGreaterThan(0);
    slides.forEach(([, at, attrs]) => {
      expect(attrs).toContain(`values="0.0 0.0;${at};${at}"`);
      expect(attrs).toContain('repeatCount="indefinite"');
    });
    expect([...svg.matchAll(/<animate [^>]*>/g)].filter((a) => a[0].includes("x2") && !a[0].includes('repeatCount="indefinite"'))).toEqual([]);
    // the next step has them home in one frame: nothing slides back
    const next = three.shot(2).svg;
    expect(next).not.toContain('class="slid"');
    expect(next).not.toContain('class="tie stretch"');
  });
});

// R-0682
it("shows an event's words on its own step only, and takes them away on the next", () => {
  const t = told(apart());
  expect(markClass(t.shot(0).svg, `word:${MARCUS}:${ROOM}`)).toContain("pop");
  expect(marks(t.shot(1).svg)).not.toContain(`word:${MARCUS}:${ROOM}`);
});

describe("an event about the whole family", () => {
  // R-0552, R-0681
  it("puts everyone alive then in the emphasis colour, and the event's title beside the reader", () => {
    const c = death();
    c.snapshots[3] = { date: "1998-09-15", event_ids: [133], fact: "The family left Bluff Street.", guess: null };
    const svg = told(c).shot(3).svg;
    const lit = marks(svg).filter((m) => m.startsWith("hl:") && markClass(svg, m).includes("now"));
    expect(lit.sort()).toEqual([MARCUS, DELPHINE, CORINNE].map((id) => `hl:${id}`).sort());
    expect(marks(svg).filter((m) => m.startsWith("word:"))).toEqual([`word:${CORINNE}:Left Bluff Street`]);
  });
});

// R-0681
it("refuses to draw a noted event or a shift that has no title, rather than cut its description", () => {
  const tl = timeline();
  tl.events.find((e) => e.id === 202)!.title = null;
  expect(() => told(apart(), tl)).toThrow("event 202 is a noted event with no title");
});

// R-0560
it("refuses a couple with a marriage or divorce in the record but no married mark, never drawing it solid", () => {
  const tl = timeline();
  tl.pair_bonds[1].married = false;
  expect(() => told(apart(), tl)).toThrow(/record fault: event \d+ is a (married|divorced) for a couple not marked married/);
});

// R-0545
it("draws a reader with no family recorded beside the person they move with", () => {
  const L = layout({
    ...base({ me: { ...shape("Ada", Sex.Female, 1960), you: true }, ben: shape("Ben", Sex.Male, 1958) }),
    bonds: [],
    kids: [],
    index: "me",
    moves: [{ k: Mark.Toward, from: "me", to: "ben" }],
    assoc: { me: "ben", ben: "me" },
  });
  expect(L.y.me).toBe(L.y.ben);
});

// R-0545
it("draws someone a case names only in words beside whoever the event names them with", () => {
  const tl = timeline();
  tl.pair_bonds = [];
  tl.people = [
    { ...tl.people[4], id: 1, name: "Ada", parents: null },
    { ...tl.people[1], id: 2, name: "Ben", gender: "male", parents: null, death_event: null },
    { ...tl.people[1], id: 3, name: "Cal", gender: "male", parents: null, death_event: null },
  ];
  tl.events = [
    event(20, "1990-04-01", "shift", 1, { relationship: "toward", relationshipTargets: [2] }),
    event(21, "1991-04-01", "shift", 1, { relationship: "inside", relationshipTargets: [2], relationshipTriangles: [3], title: "Close in with Ben" }),
    event(22, "1992-04-01", "shift", 1, { relationship: "distance", relationshipTargets: [2] }),
  ];
  tl.clusters = [{ ...tl.clusters[0], id: "walk", event_ids: [20, 21, 22] }];
  const walk: Case = {
    cluster_id: "walk",
    point: "Ada moved toward Ben, then kept her distance.",
    snapshots: [
      { date: "1990-04-01", event_ids: [20], fact: "Ada moved toward Ben.", guess: null },
      { date: "1991-04-01", event_ids: [21], fact: "Ada was close in with Ben.", guess: null },
      { date: "1992-04-01", event_ids: [22], fact: "Ada kept her distance.", guess: null },
    ],
    question: "Where was Cal?",
  };
  const t = told(walk, tl);
  expect(cast(t)).toEqual([1, 2, 3]);
  expect(t.layout.y["3"]).toBe(t.layout.y["1"]);
});

// R-0559
it("keeps a partner on the side away from the family when brothers or sisters stand beside", () => {
  const cast = brood(2);
  cast.people.m = shape("Mo", Sex.Female, 1961);
  cast.bonds.push({ a: "k1", b: "m", st: Tie.Married, married: true });
  const L = layout(cast);
  expect(L.x.k1).toBeGreaterThan(L.x.k0);
  expect(L.x.m).toBeGreaterThan(L.x.k1);
});

describe("a play-by-play nobody told", () => {
  // R-0570, R-0075
  it("is one picture per date of the events it is given, in their own words, with no point, guess or question", () => {
    const t = new Told(timeline(), untold(timeline(), [203, 201, 202]));
    expect(t.length).toBe(2);
    expect(t.told.point).toBe("");
    expect(t.told.snapshots.map((s) => s.event_ids)).toEqual([[201, 202], [203]]);
    expect(t.shot(0).fact).toBe("Took a room over the hardware store");
    expect(t.shot(1)).toMatchObject({ fact: "Drinking most nights", guess: null, question: null });
  });

  // R-0570
  it("leaves out an event with no date, which has nowhere to stand", () => {
    const tl = timeline();
    tl.events.find((e) => e.id === 203)!.dateTime = null;
    expect(untold(tl, [201, 203]).snapshots.map((s) => s.event_ids)).toEqual([[201]]);
  });

  // R-0570, R-0076
  it("tells a triangle by the events that name two or more of its three people", () => {
    const ids = among(timeline(), [MARCUS, DELPHINE, CORINNE]);
    expect(ids).toEqual(expect.arrayContaining([109, 201, 204]));
    expect(ids).not.toContain(203);
  });
});

// R-0729
it("draws anxiety going down as spikes that shorten to the rim on its step, and nothing once it is carried", () => {
  const tl = timeline();
  const e = tl.events.find((e) => e.id === 131)!;
  e.relationship = null;
  e.relationshipTargets = [];
  e.anxiety = "down";
  const t = told(death(), tl);
  expect(t.shot(1).svg).toContain(`data-mark="anxd:${DELPHINE}"`);
  expect(t.shot(2).svg).not.toContain(`data-mark="anxd:`);
});

describe("a couple where both partners' parents are in the record", () => {
  const wed = (a: string, b: string) => ({ a, b, st: Tie.Married, married: true });
  const joined = (extra: Partial<Cast> = {}, more: Cast["people"] = {}): Cast => ({
    ...family(),
    people: {
      hf: shape("Hal", Sex.Male, 1920),
      hm: shape("Hope", Sex.Female, 1922),
      wf: shape("Walt", Sex.Male, 1921),
      wm: shape("Wren", Sex.Female, 1923),
      h: shape("Hugo", Sex.Male, 1950),
      w: shape("Wanda", Sex.Female, 1952),
      c: { ...shape("Cleo", Sex.Female, 1975), you: true },
      ...more,
    },
    bonds: [wed("hf", "hm"), wed("wf", "wm"), wed("h", "w")],
    kids: [
      { of: ["hf", "hm"], kids: ["h"] },
      { of: ["wf", "wm"], kids: ["w"] },
      { of: ["h", "w"], kids: ["c"] },
    ],
    index: "c",
    ...extra,
  });
  const order = (L: ReturnType<typeof layout>, ids: string[]) => ids.slice().sort((a, b) => L.x[a] - L.x[b]);

  // R-0545, R-0187
  it("joins the two families in one picture, his on the left, hers on the right", () => {
    const L = layout(joined());
    const { x, y } = L;
    expect(Object.keys(x)).toHaveLength(7);
    const ids = Object.keys(x);
    ids.forEach((a) =>
      ids.forEach((b) => {
        if (a !== b && y[a] === y[b]) expect(Math.abs(x[a] - x[b])).toBeGreaterThanOrEqual(L.w);
      }),
    );
    expect(y.hf).toBe(y.wf);
    expect(y.h).toBe(y.w);
    expect(y.hf).toBeLessThan(y.h);
    expect(y.h).toBeLessThan(y.c);
    expect(x.hm).toBeLessThan(x.wf);
    expect(x.h).toBeLessThan(x.w);
    expect(ids.filter((id) => y[id] === y.h && x[id] > x.h && x[id] < x.w)).toEqual([]);
    expect(Math.min(x.hf, x.hm) <= x.h && x.h <= Math.max(x.hf, x.hm)).toBe(true);
    expect(Math.min(x.wf, x.wm) <= x.w && x.w <= Math.max(x.wf, x.wm)).toBe(true);
    expect(x.h <= x.c && x.c <= x.w).toBe(true);
  });

  // R-0545, R-0187
  it("stands each spouse at the inner end of their brothers and sisters, the rest oldest-left", () => {
    const L = layout(
      joined(
        {
          kids: [
            { of: ["hf", "hm"], kids: ["h1", "h", "h3"] },
            { of: ["wf", "wm"], kids: ["w", "w2"] },
            { of: ["h", "w"], kids: ["c"] },
          ],
        },
        {
          h1: shape("Ida", Sex.Female, 1948),
          h3: shape("Ivo", Sex.Male, 1955),
          w2: shape("Una", Sex.Female, 1956),
        },
      ),
    );
    expect(order(L, ["h1", "h", "h3", "w", "w2"])).toEqual(["h1", "h3", "h", "w", "w2"]);
  });

  // R-0545, R-0559
  it("puts a remarried parent's other partner on the outside", () => {
    const L = layout(
      joined(
        {
          bonds: [wed("hf", "hm"), wed("wf", "wm"), wed("h", "w"), wed("hf", "hs")],
          kids: [
            { of: ["hf", "hm"], kids: ["h"] },
            { of: ["wf", "wm"], kids: ["w"] },
            { of: ["h", "w"], kids: ["c"] },
            { of: ["hf", "hs"], kids: ["k"] },
          ],
        },
        { hs: shape("Sue", Sex.Female, 1925), k: shape("Kit", Sex.Male, 1945) },
      ),
    );
    expect(order(L, ["hs", "hf", "hm", "wf", "wm"])).toEqual(["hs", "hf", "hm", "wf", "wm"]);
    const row = order(L, ["k", "h", "w"]);
    expect(Math.abs(row.indexOf("h") - row.indexOf("w"))).toBe(1);
  });

  const sound = (L: ReturnType<typeof layout>, cast: Cast) => {
    const { x, y } = L;
    const ids = Object.keys(x);
    expect(ids.sort()).toEqual(Object.keys(cast.people).sort());
    ids.forEach((a) =>
      ids.forEach((b) => {
        if (a !== b && y[a] === y[b]) expect(Math.abs(x[a] - x[b])).toBeGreaterThanOrEqual(L.w);
      }),
    );
    cast.bonds.forEach(({ a, b }) => {
      expect(y[a]).toBe(y[b]);
      expect(ids.filter((id) => y[id] === y[a] && x[id] > Math.min(x[a], x[b]) && x[id] < Math.max(x[a], x[b]))).toEqual([]);
    });
    cast.kids.forEach(({ of, kids }) =>
      kids.forEach((k) => {
        expect(y[k]).toBeGreaterThan(y[of[0]]);
        expect(Math.min(...of.map((o) => x[o])) <= x[k] && x[k] <= Math.max(...of.map((o) => x[o]))).toBe(true);
      }),
    );
    expect(x.h).toBeLessThan(x.w);
  };
  const above = (sides: ("h" | "w")[]): Cast => {
    const c = joined();
    sides.forEach((s) => {
      const m = s === "h" ? "hm" : "wm";
      c.people[`${s}g`] = shape(`${s.toUpperCase()}gramps`, Sex.Male, 1890);
      c.people[`${s}n`] = shape(`${s.toUpperCase()}nana`, Sex.Female, 1892);
      c.bonds.push(wed(`${s}g`, `${s}n`));
      c.kids.push({ of: [`${s}g`, `${s}n`], kids: [m] });
    });
    return c;
  };

  // R-0545, R-0187
  it("joins the families with great-grandparents above the wife's side", () => {
    const c = above(["w"]);
    sound(layout(c), c);
  });

  // R-0545, R-0187
  it("joins the families with great-grandparents above the husband's side", () => {
    const c = above(["h"]);
    sound(layout(c), c);
  });

  // R-0545, R-0187, R-0747
  it("joins the families with great-grandparents above both sides", () => {
    const c = above(["h", "w"]);
    sound(layout(c), c);
  });

  /** Family test page F2: six brothers and sisters on each side of the couple. */
  const sixEach = () => {
    const sibs = (s: string, n: number) => Array.from({ length: n }, (_, i) => `${s}${i}`);
    const more: Cast["people"] = {};
    [...sibs("hs", 6), ...sibs("ws", 6)].forEach((id, i) => (more[id] = shape(`Sib${i}`, i % 2 ? Sex.Male : Sex.Female, 1940 + i)));
    return joined(
      {
        kids: [
          { of: ["hf", "hm"], kids: ["h", ...sibs("hs", 6)] },
          { of: ["wf", "wm"], kids: ["w", ...sibs("ws", 6)] },
          { of: ["h", "w"], kids: ["c"] },
        ],
      },
      more,
    );
  };

  // R-0547, R-0744, R-0749, R-0759
  // re-ruled 2026-10-04, scroll below the floor
  it("keeps a wide joined family at its people's full size, wider than the frame", () => {
    const L = arrange(sixEach());
    expect(L).toMatchObject({ w: 44, px: 44 });
    expect(L.vw).toBeGreaterThan(VIEW);
  });

  // R-0759, R-0744, R-0749
  it("draws a wide family's people, slashes, marks, names and lines the same size against each other as a small family's", () => {
    const sprawl = JSON.parse(readFileSync(new URL("./family50.json", import.meta.url), "utf8"));
    const measured = (c: Cast) => {
      const L = arrange(c);
      const [a, b] = L.bonds.map((x) => [x.a, x.b])[0];
      const svg = draw(L, {
        ...frame(L),
        bonds: L.bonds.map((x, i) => ({ ...x, st: i ? x.st : Tie.Divorced, married: true, fresh: false, hot: false })),
        kin: [{ k: Mark.Move, kind: Move.Cutoff, from: a, to: b }],
      });
      const shape = Number(svg.match(/<rect class="shape" x="[-\d.]+" y="[-\d.]+" width="([\d.]+)"/)![1]);
      const [y1, y2] = svg.match(/<line class="slash[^"]*" x1="[-\d.]+" y1="([-\d.]+)" x2="[-\d.]+" y2="([-\d.]+)"/)!.slice(1).map(Number);
      const w = svg.match(/<line class="mv-wall" x1="([-\d.]+)" y1="([-\d.]+)" x2="([-\d.]+)" y2="([-\d.]+)"/)!.slice(1).map(Number);
      // names, ages and line widths are sized in the drawing's own units by the
      // one rule set, so with the people the same size they stand the same
      expect(svg).toMatch(/<svg class="ss diagram"/);
      const r = (v: number) => Math.round(v * 1000) / 1000;
      return { shape, slash: r((y1 - y2) / shape), wall: r(Math.hypot(w[2] - w[0], w[3] - w[1]) / shape) };
    };
    const narrow = measured(family());
    expect(narrow.shape).toBe(44);
    for (const wide of [sixEach(), { ...base(sprawl.people), ...sprawl }]) expect(measured(wide)).toEqual(narrow);
  });

  // R-0749, R-0545
  it("keeps a joining couple at the usual distance when each has six brothers and sisters with partners", () => {
    const more: Cast["people"] = {};
    const bonds = [wed("hf", "hm"), wed("wf", "wm"), wed("h", "w")];
    const side = (s: string, joiner: string) =>
      Array.from({ length: 6 }, (_, i) => {
        if (i === 2) return joiner;
        const id = `${s}${i}`;
        more[id] = shape(`${s}${i}`, i % 2 ? Sex.Female : Sex.Male, 1960 + i);
        more[`${id}p`] = shape(`${s}${i}p`, i % 2 ? Sex.Male : Sex.Female, 1961 + i);
        bonds.push(i % 2 ? wed(`${id}p`, id) : wed(id, `${id}p`));
        return id;
      });
    const kids = [
      { of: ["hf", "hm"], kids: side("hs", "h") },
      { of: ["wf", "wm"], kids: side("ws", "w") },
      { of: ["h", "w"], kids: ["c"] },
    ];
    const L = arrange(joined({ bonds, kids }, more));
    expect(L.loose).toBe(false);
    const row = Object.keys(L.x).filter((id) => L.y[id] === L.y.h).sort((a, b) => L.x[a] - L.x[b]);
    expect(row[row.indexOf("h") + 1]).toBe("w");
    const gaps = row.slice(1).map((id, i) => L.x[id] - L.x[row[i]]);
    expect(L.x.w - L.x.h).toBeLessThanOrEqual(Math.max(...gaps.filter((_, i) => row[i] !== "h")));
  });

  // R-0545
  it("refuses two couples each joining two families", () => {
    expect(() =>
      layout(
        joined(
          {
            bonds: [wed("hf", "hm"), wed("wf", "wm"), wed("h", "w"), wed("h3", "w2")],
            kids: [
              { of: ["hf", "hm"], kids: ["h", "h3"] },
              { of: ["wf", "wm"], kids: ["w", "w2"] },
              { of: ["h", "w"], kids: ["c"] },
            ],
          },
          { h3: shape("Ivo", Sex.Male, 1955), w2: shape("Una", Sex.Female, 1956) },
        ),
        { fit: false },
      ),
    ).toThrow(/two couples each joining two families/);
  });

  // R-0545
  it("never reaches the fallback for a family the row rules place", () => {
    const casts = [family(), brood(2), brood(5), joined(), above(["h"]), above(["w"]), above(["h", "w"])];
    casts.forEach((c) => expect(arrange(c).loose).toBe(false));
    [death(), apart()].forEach((c) => expect(told(c).layout.loose).toBe(false));
  });
});

describe("a family the row rules cannot place", () => {
  const sh = shape;
  const { Male: M, Female: F } = Sex;
  const wed = (a: string, b: string) => ({ a, b, st: Tie.Married, married: true });
  const cast = (people: Cast["people"], bonds: Cast["bonds"], kids: Cast["kids"], index: string): Cast => ({
    ...base(people),
    bonds,
    kids,
    index,
  });
  const joined = (people: Cast["people"], bonds: Cast["bonds"], kids: Cast["kids"]) =>
    cast(
      { hf: sh("Hal", M, 1920), hm: sh("Hope", F, 1922), wf: sh("Walt", M, 1921), wm: sh("Wren", F, 1923), h: sh("Hugo", M, 1950), w: sh("Wanda", F, 1952), c: { ...sh("Cleo", F, 1975), you: true }, ...people },
      [wed("hf", "hm"), wed("wf", "wm"), wed("h", "w"), ...bonds],
      [{ of: ["hf", "hm"], kids: ["h"] }, { of: ["wf", "wm"], kids: ["w"] }, { of: ["h", "w"], kids: ["c"] }, ...kids],
      "c",
    );
  const families: Record<string, Cast> = {
    "three partners for one person with nothing beside": cast(
      { a: { ...sh("Al", M, 1950), you: true }, b: sh("Bea", F, 1951), c: sh("Cy", F, 1952), e: sh("Eve", F, 1953) },
      [wed("a", "b"), wed("a", "c"), wed("a", "e")],
      [],
      "a",
    ),
    "a couple across generations": cast(
      { g1: sh("Gus", M, 1900), g2: sh("Gia", F, 1902), b: sh("Bea", F, 1930), p: sh("Pat", M, 1932), q: sh("Quin", F, 1933), a: sh("Al", M, 1928), c: { ...sh("Cy", F, 1955), you: true }, n: sh("Nia", F, 1958) },
      [wed("g1", "g2"), wed("a", "b"), wed("p", "q"), wed("a", "n")],
      [{ of: ["g1", "g2"], kids: ["b", "p"] }, { of: ["p", "q"], kids: ["n"] }, { of: ["a", "b"], kids: ["c"] }],
      "c",
    ),
    "two separate families in one row": joined(
      { hs: sh("Sue", F, 1918), k: sh("Kit", M, 1945), s1: sh("Sam", M, 1890), s2: sh("Sal", F, 1892), w1: sh("Will", M, 1895), w2: sh("Wilma", F, 1897) },
      [wed("hf", "hs"), wed("s1", "s2"), wed("w1", "w2")],
      [{ of: ["hf", "hs"], kids: ["k"] }, { of: ["s1", "s2"], kids: ["hs"] }, { of: ["w1", "w2"], kids: ["wm"] }],
    ),
    "two joining couples": (() => {
      const c = joined({ h3: sh("Ivo", M, 1955), w2: sh("Una", F, 1956) }, [wed("h3", "w2")], []);
      c.kids[0].kids.push("h3");
      c.kids[1].kids.push("w2");
      return c;
    })(),
    "another family between a joining couple": joined({ q: sh("Quin", M, 1951) }, [wed("hm", "wf")], [{ of: ["hm", "wf"], kids: ["q"] }]),
    "a couple not connected to the reader's family": cast(
      { ...family().people, x: sh("Xan", M, 1960), y: sh("Yva", F, 1962) },
      [...family().bonds, wed("x", "y")],
      family().kids,
      "c",
    ),
  };

  const placed = (c: Cast) => {
    expect(() => layout(c)).toThrow(/cannot place/);
    const L = arrange(c);
    expect(L.loose).toBe(true);
    const svg = draw(L, frame(L));
    Object.keys(c.people).forEach((id) => expect(svg.split(`class="p" data-id="${id}"`)).toHaveLength(2));
    const ids = Object.keys(c.people);
    const e = (id: string) => (L.w / 2) * (L.P[id].you ? 1.2 : 1);
    ids.forEach((a) =>
      ids.forEach((b) => {
        if (a === b) return;
        const apart = Math.abs(L.x[a] - L.x[b]) >= e(a) + e(b) || Math.abs(L.y[a] - L.y[b]) >= e(a) + e(b);
        expect(apart, `${a} and ${b} overlap`).toBe(true);
      }),
    );
    const kin = els(svg, "path", "kin").map((p) => p.d.match(/^M(\S+) (\S+)L(\S+) (\S+)$/)!.slice(1).map(Number));
    c.kids.forEach((k) => {
      const b = bar(L, { a: k.of[0], b: k.of[1] });
      k.kids.forEach((id) => {
        const line = kin.find(([x0, y0]) => x0 === Number(L.x[id].toFixed(1)) && Math.abs(y0 - (L.y[id] - e(id))) < 0.2);
        expect(line, `${id} has a line`).toBeDefined();
        const [, , x1, y1] = line!;
        expect(y1).toBe(Number(b.y.toFixed(1)));
        expect(x1).toBeGreaterThanOrEqual(Number(b.x0.toFixed(1)));
        expect(x1).toBeLessThanOrEqual(Number(b.x1.toFixed(1)));
      });
    });
    expect(draw(arrange(c), frame(L))).toBe(svg);
  };

  // R-0545, R-0745, R-0752
  it("draws three partners for one person in rows, in order beside him, each child under their parents' line", () => {
    // R-0783, R-0545
    const c = families["three partners for one person with nothing beside"];
    const kids = cast(
      { ...c.people, k1: sh("Kit", F, 1975), k2: sh("Kai", M, 1978), k3: sh("Kim", F, 1981) },
      c.bonds,
      [{ of: ["a", "b"], kids: ["k1"] }, { of: ["a", "c"], kids: ["k2"] }, { of: ["a", "e"], kids: ["k3"] }],
      "a",
    );
    const L = layout(kids);
    expect(L.loose).toBe(false);
    const row = ["a", "b", "c", "e"].map((id) => L.x[id]);
    expect(new Set(["a", "b", "c", "e"].map((id) => L.y[id])).size).toBe(1);
    // the partners in order, all on one side of him
    expect([...row.slice(1)].sort((p, q) => p - q)).toEqual(Math.sign(row[1] - row[0]) > 0 ? row.slice(1) : row.slice(1).reverse());
    expect(row.slice(1).every((x) => Math.sign(x - row[0]) === Math.sign(row[1] - row[0]))).toBe(true);
    // each child stands within its own parents' line
    [["k1", "b"], ["k2", "c"], ["k3", "e"]].forEach(([k, p]) => {
      const [lo, hi] = [Math.min(L.x.a, L.x[p]), Math.max(L.x.a, L.x[p])];
      expect(L.x[k]).toBeGreaterThanOrEqual(lo - 1);
      expect(L.x[k]).toBeLessThanOrEqual(hi + 1);
    });
  });

  // R-0545, R-0745, R-0752
  it("draws a couple across generations, everyone once, no shapes overlapping, each child's line on their parents' bar", () => placed(families["a couple across generations"]));

  // R-0545, R-0745, R-0752
  it("draws two separate families in one row, everyone once, no shapes overlapping, each child's line on their parents' bar", () => placed(families["two separate families in one row"]));

  // R-0545, R-0745
  it("draws two joining couples, everyone once, no shapes overlapping, each child's line on their parents' bar", () => placed(families["two joining couples"]));

  // R-0545, R-0745, R-0752
  it("draws another family between a joining couple, everyone once, no shapes overlapping, each child's line on their parents' bar", () => placed(families["another family between a joining couple"]));

  // R-0545, R-0745, R-0750, R-0754
  it("draws a couple not connected to the reader's family, everyone once, no shapes overlapping, each child's line on their parents' bar", () => placed(families["a couple not connected to the reader's family"]));

  // R-0545
  it("draws a family with no tie to the reader's to the right of it", () => {
    const L = arrange(families["a couple not connected to the reader's family"]);
    expect(Math.min(L.x.x, L.x.y)).toBeGreaterThan(Math.max(L.x.a, L.x.b, L.x.c, L.x.d));
  });

  // R-0766, R-0779
  it("lays no name on a couple's line: a man with no family drawn, married to a woman with her parents and sister", () => {
    const L = arrange(
      cast(
        { h: { ...sh("Hank", M, 1980), you: true }, w: sh("Win", F, 1987), wf: sh("Wes", M, 1950), wm: sh("Wyn", F, 1952), ws: sh("Wren", F, 1989) },
        [wed("h", "w"), wed("wf", "wm")],
        [{ of: ["wf", "wm"], kids: ["w", "ws"] }],
        "h",
      ),
    );
    L.bonds.forEach((b) => {
      const yb = bar(L, b).y;
      const segs = [
        [[L.x[b.a], L.y[b.a]], [L.x[b.a], yb]],
        [[L.x[b.b], L.y[b.b]], [L.x[b.b], yb]],
        [[Math.min(L.x[b.a], L.x[b.b]), yb], [Math.max(L.x[b.a], L.x[b.b]), yb]],
      ] as [number, number][][];
      segs.forEach((sg) => L.names.forEach((box) => expect(crosses(sg as never, box), `${b.a}|${b.b} through a name`).toBe(false)));
    });
  });

  // R-0545
  it("stands a couple with no tie to the family on the row of the one of the family they are involved with, not the grandparents'", () => {
    const c = { ...families["a couple not connected to the reader's family"], assoc: { x: "c", c: "x" } };
    expect(() => layout(c)).toThrow(/cannot place/);
    const L = arrange(c);
    expect(L.loose).toBe(true);
    expect([L.y.x, L.y.y]).toEqual([L.y.c, L.y.c]);
    expect(L.y.c).toBeGreaterThan(Math.min(...Object.values(L.y)));
  });

  // R-0779, R-0545
  it("stands one who married in on their partner's row, their parents a row above, however few generations their own family reaches back", () => {
    // his family four generations deep, hers two; his mother's parents are in
    // the record too, two couples each joining two families, which the row
    // rules refuse
    const c = cast(
      { g1: sh("Gus", M, 1880), g2: sh("Gert", F, 1882), f1: sh("Fred", M, 1910), f2: sh("Fay", F, 1912), p1: sh("Paul", M, 1940), p2: sh("Pam", F, 1942), q1: sh("Quin", M, 1915), q2: sh("Quila", F, 1917), h: { ...sh("Hank", M, 1970), you: true }, w: sh("Win", F, 1972), wf: sh("Wes", M, 1945), wm: sh("Wyn", F, 1947), k: sh("Kai", M, 2000) },
      [wed("g1", "g2"), wed("f1", "f2"), wed("q1", "q2"), wed("p1", "p2"), wed("h", "w"), wed("wf", "wm")],
      [{ of: ["g1", "g2"], kids: ["f1"] }, { of: ["f1", "f2"], kids: ["p1"] }, { of: ["q1", "q2"], kids: ["p2"] }, { of: ["p1", "p2"], kids: ["h"] }, { of: ["wf", "wm"], kids: ["w"] }, { of: ["h", "w"], kids: ["k"] }],
      "h",
    );
    expect(() => layout(c)).toThrow(/cannot place/);
    const L = arrange(c);
    expect(L.loose).toBe(true);
    expect(L.y.w).toBe(L.y.h);
    expect([L.y.wf, L.y.wm]).toEqual([L.y.p1, L.y.p1]);
    expect(L.y.k).toBeGreaterThan(L.y.h);
  });

  // R-0747, R-0745, R-0754
  it("draws four generations on both sides with no line crossing and each man left of his wife", () => {
    const p: Cast["people"] = { c: { ...sh("Ivy", F, 1985), you: true }, h: sh("Gil", M, 1955), w: sh("Hope", F, 1957) };
    const bonds = [wed("h", "w")];
    const kids: Cast["kids"] = [{ of: ["h", "w"], kids: ["c"] }];
    ["p1", "p2", "p3", "p4"].forEach((k, i) => {
      p[k] = sh(`P${i}`, i % 2 ? F : M, 1930 + i);
      p[`${k}f`] = sh(`G${2 * i}`, M, 1900 + i);
      p[`${k}m`] = sh(`G${2 * i + 1}`, F, 1902 + i);
      bonds.push(wed(`${k}f`, `${k}m`));
      kids.push({ of: [`${k}f`, `${k}m`], kids: [k] });
    });
    bonds.push(wed("p1", "p2"), wed("p3", "p4"));
    kids.push({ of: ["p1", "p2"], kids: ["h"] }, { of: ["p3", "p4"], kids: ["w"] });
    const L = arrange(cast(p, bonds, kids, "c"));
    const { x, y } = L;
    bonds.forEach(({ a, b }) => {
      expect(x[a]).toBeLessThan(x[b]);
      expect(Object.keys(x).filter((id) => y[id] === y[a] && x[id] > x[a] && x[id] < x[b])).toEqual([]);
    });
    kids.forEach(({ of, kids }) => kids.forEach((k) => expect(x[of[0]] <= x[k] && x[k] <= x[of[1]]).toBe(true)));
  });

  // R-0750, R-0745
  it("stands a couple with no tie to the family twice as far off as two unrelated families in a row", () => {
    const L = arrange(joined({ q1: sh("Vince", M, 1960), q2: sh("Wendy", F, 1962) }, [wed("q1", "q2")], []));
    const { x } = L;
    expect(x.q1 - x.wm).toBeGreaterThanOrEqual(2 * (x.wf - x.hm));
    expect(x.hf <= x.h && x.h <= x.hm).toBe(true);
    expect(x.wf <= x.w && x.w <= x.wm).toBe(true);
  });

  const cuts = (a: number[][], b: number[][]) => {
    const [[px, py], [qx, qy]] = a;
    const [[rx, ry], [sx, sy]] = b;
    const dd = (qx - px) * (sy - ry) - (qy - py) * (sx - rx);
    if (!dd) return false;
    const t = ((rx - px) * (sy - ry) - (ry - py) * (sx - rx)) / dd;
    const u = ((rx - px) * (qy - py) - (ry - py) * (qx - px)) / dd;
    return t > 0.01 && t < 0.99 && u > 0.01 && u < 0.99;
  };
  const between = joined(
    { hs: sh("Ulla", F, 1971), ws: sh("Max", M, 1972), xf: sh("Rolf", M, 1943), xm: sh("Sara", F, 1945), x1: sh("Tom", M, 1969), x2: sh("Una", F, 1973) },
    [wed("xf", "xm"), wed("x1", "hs"), wed("ws", "x2")],
    [{ of: ["xf", "xm"], kids: ["x1", "x2"] }],
  );
  between.kids[0].kids.push("hs");
  between.kids[1].kids.push("ws");
  const prior = joined({ h0: sh("Clara", F, 1969), hc: sh("Tobias", M, 1990) }, [{ a: "h", b: "h0", st: Tie.Divorced, married: true }], [{ of: ["h", "h0"], kids: ["hc"] }]);
  const shapes: Record<string, Cast> = {
    "two couples each joining both families": cast(
      { af: sh("Abe", M, 1930), am: sh("Bea", F, 1932), bf: sh("Cal", M, 1931), bm: sh("Dot", F, 1933), a1: sh("Eddie", M, 1955), a2: sh("Flora", F, 1957), b1: sh("Gina", F, 1956), b2: sh("Hal", M, 1958), c1: { ...sh("Iris", F, 1982), you: true }, c2: sh("Jack", M, 1984) },
      [wed("af", "am"), wed("bf", "bm"), wed("a1", "b1"), wed("b2", "a2")],
      [{ of: ["af", "am"], kids: ["a1", "a2"] }, { of: ["bf", "bm"], kids: ["b1", "b2"] }, { of: ["a1", "b1"], kids: ["c1"] }, { of: ["b2", "a2"], kids: ["c2"] }],
      "c1",
    ),
    "three marriages, half-siblings and a cousin marriage": cast(
      { gf: sh("Alan", M, 1925), gm: sh("Bess", F, 1927), f: sh("Cliff", M, 1950), u: sh("Dale", M, 1953), ua: sh("Erin", F, 1955), w1: sh("Gail", F, 1951), w2: sh("Hana", F, 1958), w3: sh("Inez", F, 1962), h1: sh("Jake", M, 1972), h2: sh("Kara", F, 1980), y: { ...sh("Lola", F, 1988), you: true }, cz: sh("Milo", M, 1986), w3x: sh("Nate", M, 1960), hr: sh("Opal", F, 1984), yc: sh("Pip", M, 2012) },
      [wed("gf", "gm"), wed("u", "ua"), { a: "f", b: "w1", st: Tie.Divorced, married: true }, { a: "f", b: "w2", st: Tie.Divorced, married: true }, wed("f", "w3"), { a: "w3x", b: "w3", st: Tie.Divorced, married: true }, wed("cz", "y")],
      [{ of: ["gf", "gm"], kids: ["f", "u"] }, { of: ["u", "ua"], kids: ["cz"] }, { of: ["f", "w1"], kids: ["h1"] }, { of: ["f", "w2"], kids: ["h2"] }, { of: ["f", "w3"], kids: ["y"] }, { of: ["w3x", "w3"], kids: ["hr"] }, { of: ["cz", "y"], kids: ["yc"] }],
      "y",
    ),
    "another family between a joining couple, both families married into it": between,
  };

  const clear = (c: Cast) => {
    const L = arrange(c);
    expect(L.loose).toBe(true);
    lines(draw(L, frame(L))).forEach((sg) => L.names.forEach((b) => expect(crosses(sg, b)).toBe(false)));
  };

  // R-0745
  it("draws two couples each joining both families generation by generation with no child's line through a name", () =>
    clear(shapes["two couples each joining both families"]));

  // R-0748, R-0745
  it("draws three marriages, half-siblings and a cousin marriage generation by generation with no child's line through a name", () =>
    clear(shapes["three marriages, half-siblings and a cousin marriage"]));

  // R-0752, R-0745
  it("draws another family between a joining couple, both families married into it generation by generation with no child's line through a name", () =>
    clear(shapes["another family between a joining couple, both families married into it"]));

  // R-0752, R-0759
  it("keeps the child of a father's second marriage clear of his name, as approved", () => {
    const L = arrange(prior);
    expect(L.loose).toBe(false);
    lines(draw(L, frame(L))).forEach((sg) => L.names.forEach((b) => expect(crosses(sg, b)).toBe(false)));
    expect(L.x.c).toBeLessThan(L.x.w);
  });

  // R-0752, R-0745
  it("draws another family between a joining couple with no two children's lines crossing", () => {
    const L = arrange(between);
    const ls = lines(draw(L, frame(L)));
    ls.forEach((a, i) => ls.slice(i + 1).forEach((b) => expect(cuts(a, b)).toBe(false)));
    expect(L.x.h).toBeLessThan(L.x.w);
  });

  // R-0745, R-0744
  it("keeps a generated family of 50 near the width of its widest row and its margin fixed as it widens", () => {
    const sprawl = JSON.parse(readFileSync(new URL("./family50.json", import.meta.url), "utf8"));
    const L = arrange({ ...base(sprawl.people), ...sprawl });
    const rows = new Map<number, number>();
    Object.values(L.y).forEach((y) => rows.set(y, (rows.get(y) ?? 0) + 1));
    // each person a shape and at most the sibling gap of three widths beside it
    expect(L.vw).toBeLessThanOrEqual(2 * Math.max(...rows.values()) * 4 * L.w);
    expect(L.h).toBeLessThanOrEqual(rows.size * 3 * L.w + 100);
  });

  // R-0751
  it("says someone further up a loop is recorded as their own ancestor", () => {
    const c = cast(
      { a: sh("Al", M, 1950), b: sh("Bea", F, 1951), c: { ...sh("Cy", M, 1975), you: true }, e: sh("Eve", F, 2000) },
      [wed("a", "b")],
      [{ of: ["a", "b"], kids: ["c"] }, { of: ["c"], kids: ["e"] }, { of: ["e"], kids: ["a"] }],
      "c",
    );
    const L = arrange(c);
    expect(L.note!.lines.join(" ")).toBe("Al is recorded as their own ancestor");
  });

  // R-0751, R-0754
  it("draws someone recorded as their own forebear, the link closing the loop in the error colour with a note", () => {
    const c = cast(
      { a: sh("Al", M, 1950), b: sh("Bea", F, 1951), c: { ...sh("Cy", M, 1975), you: true }, d: sh("Di", F, 1976) },
      [wed("a", "b"), wed("c", "d")],
      [{ of: ["a", "b"], kids: ["c"] }, { of: ["c", "d"], kids: ["a"] }],
      "c",
    );
    const L = arrange(c);
    expect(L.cut).toEqual([{ kid: "a", parent: "c", up: 2 }]);
    const svg = draw(L, frame(L));
    Object.keys(c.people).forEach((id) => expect(svg.split(`class="p" data-id="${id}"`)).toHaveLength(2));
    const cuts = els(svg, "path", "cut");
    expect(cuts).toHaveLength(1);
    expect(els(svg, "text", "cutn").length).toBeGreaterThan(0);
    expect(svg.replace(/<\/text><text class="cutn"[^>]*>/g, " ")).toContain("Al is recorded as their own grandparent");
    const [x0, y0, cx, cy, x1, y1] = cuts[0].d.match(/^M(\S+) (\S+)Q(\S+) (\S+) (\S+) (\S+)$/)!.slice(1).map(Number);
    const at = (t: number) => [
      (1 - t) ** 2 * x0 + 2 * t * (1 - t) * cx + t ** 2 * x1,
      (1 - t) ** 2 * y0 + 2 * t * (1 - t) * cy + t ** 2 * y1,
    ];
    const normal = [...els(svg, "path", "kin"), ...els(svg, "path", "tie")].flatMap((p) => {
      const pts: number[][] = [];
      let cur = [0, 0];
      for (const [, op, a, b] of p.d.matchAll(/([MLVH])([-\d.]+)(?: ([-\d.]+))?/g)) {
        cur = op === "V" ? [cur[0], +a] : op === "H" ? [+a, cur[1]] : [+a, +b];
        pts.push(op === "M" ? [NaN, NaN, ...cur] : cur);
      }
      return pts.flatMap((q, i) => (i && !isNaN(q[0]) ? [[pts[i - 1].slice(-2), q]] : []));
    });
    const dist = ([px, py]: number[], [[ax, ay], [bx, by]]: number[][]) => {
      const l = (bx - ax) ** 2 + (by - ay) ** 2;
      const t = l ? Math.max(0, Math.min(1, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / l)) : 0;
      return Math.hypot(px - ax - t * (bx - ax), py - ay - t * (by - ay));
    };
    expect(normal.length).toBeGreaterThan(0);
    const near = Array.from({ length: 41 }, (_, i) => at(0.05 + (0.9 * i) / 40)).filter((q) => normal.some((sg) => dist(q, sg) < 2));
    expect(near.length).toBeLessThanOrEqual(1);
  });
});

describe("the whole family stepped through dates", () => {
  const record = (): Timeline => {
    const tl = timeline();
    tl.events.push(
      event(301, "1975-06-01", "birth", null, { child: CORINNE }),
      event(302, "1979-06-01", "birth", null, { child: THEO }),
      event(303, "2016-08-15", "shift", THEO, { relationship: "cutoff", relationshipTargets: [DELPHINE], title: "Cut off", description: "Stopped speaking to Delphine" }),
      event(304, null as unknown as string, "death", MARCUS),
    );
    return tl;
  };
  const whole = (tl = record()) => new Told(tl, wholeFamily(tl), true);

  // R-0783
  it("draws one frame of three generations around a person over every date, the same people and places on each", () => {
    const t = whole();
    const f = t.centred(String(DELPHINE));
    const drawn = Object.keys(f.cast.people).map(Number);
    expect(drawn).toEqual(expect.arrayContaining([DELPHINE, CORINNE, THEO]));
    expect(drawn).not.toContain(ERROL);
    // Theo's cutoff of his mother plays on the frame on its own date, in place
    const at = stepOf(t, 303);
    expect(f.shot(at).svg).toContain(`data-mark="move:${THEO}&gt;${DELPHINE}:cutoff"`);
    const place = (i: number) => group(f.shot(i).svg, DELPHINE).slice(2).join(",");
    expect(place(0)).toBe(place(at));
  });

  // R-0783
  it("names whom a date's events touch outside the frame", () => {
    const t = whole();
    const f = t.centred(String(ERROL));
    const at = stepOf(t, 303);
    expect(t.outside(at, f)).toEqual([String(THEO), String(DELPHINE)]);
    expect(t.outside(at, t.centred(String(DELPHINE)))).toEqual([]);
  });
  const stepOf = (t: Told, id: number) => t.told.snapshots.findIndex((s) => s.event_ids.includes(id));
  const group = (svg: string, id: number) =>
    svg.match(new RegExp(`<g class="(p[^"]*)" data-id="${id}">(?:(?!</g>).)*?class="shape" (?:x|cx)="([\\d.]+)" (?:y|cy)="([\\d.]+)"`))!;

  // R-0742
  it("steps through every dated birth, couple, death and relationship shift in date order, and nothing else", () => {
    expect(wholeFamily(record()).snapshots.map((s) => s.event_ids)).toEqual([
      [103], [109], [301], [302], [201], [204], [119], [130], [131], [132], [303],
    ]);
  });

  const fact = (tl: Timeline, id: number) => wholeFamily(tl).snapshots.find((s) => s.event_ids.includes(id))!.fact;

  // R-0742
  it("says what happened with who first and no date: a birth, a marriage, a couple's start, a shift", () => {
    const tl = record();
    tl.events.push(event(305, "2001-06-01", "bonded", PARTNER, { spouse: CORINNE }));
    expect(fact(tl, 301)).toBe("Corinne was born");
    expect(fact(tl, 103)).toBe("Errol and Odile married");
    expect(fact(tl, 305)).toBe("partner and Corinne got together");
    expect(fact(tl, 303)).toBe("Theo stopped speaking to Delphine");
  });

  // R-0742
  it("says two people's same words on one date once each, by name, and an event recorded twice once", () => {
    const tl = record();
    const words = { relationship: "cutoff", relationshipTargets: [DELPHINE], title: "Cut off", description: "Stopped speaking to Delphine" };
    tl.events.push(event(306, "2016-08-15", "shift", CORINNE, words), event(307, "2016-08-15", "shift", THEO, words));
    expect(fact(tl, 303)).toBe("Theo stopped speaking to Delphine; Corinne stopped speaking to Delphine");
  });

  // R-0742
  it("draws everyone in the record, the ones no step names too", () => {
    expect(cast(whole())).toEqual([ERROL, ODILE, MARCUS, DELPHINE, CORINNE, THEO, PARTNER]);
  });

  // R-0756, R-0742
  it("fades someone not yet born at a step, in the place they keep, and draws them plainly from their birth", () => {
    const t = whole();
    const before = t.shot(stepOf(t, 109)).svg;
    const born = t.shot(stepOf(t, 301)).svg;
    const [, was, x, y] = group(before, CORINNE);
    const [, now, x2, y2] = group(born, CORINNE);
    expect(was).toBe("p yet");
    expect(now).toBe("p");
    expect([x2, y2]).toEqual([x, y]);
    expect(before).toContain(`<g class="pt yet" data-id="${CORINNE}">`);
    // someone with no birth date is there from the first step
    expect(group(t.shot(0).svg, PARTNER)[1]).toBe("p");
  });

  // R-0742
  it("crosses out the dead on their death's date in the emphasis colour, and plainly after", () => {
    const t = whole();
    const on = t.shot(stepOf(t, 119)).svg;
    const after = t.shot(stepOf(t, 130)).svg;
    expect(els(on, "path", "xd").filter((e) => e.class.includes("now"))).toHaveLength(1);
    expect(els(after, "path", "xd").filter((e) => e.class.includes("now"))).toHaveLength(1);
    expect(els(after, "path", "xd").filter((e) => !e.class.includes("now"))).toHaveLength(1);
  });

  // R-0775
  it("opens on the first date holding more than births, past the early births alone, and on today when every date is births", () => {
    const tl = record();
    tl.events.push(event(308, "1920-02-01", "birth", null, { child: ERROL }), event(309, "1922-02-01", "birth", null, { child: ODILE }));
    const c = wholeFamily(tl);
    expect(c.snapshots[familyStart(tl, c)].event_ids).toEqual([103]);
    const births = { ...c, snapshots: c.snapshots.slice(0, 2) };
    expect(familyStart(tl, births)).toBe(1);
  });

  // R-0777, R-0763
  it("moves the three people of an inside step over and over, as the play-by-play does", () => {
    const tl = record();
    tl.events.push(event(310, "2017-03-01", "shift", THEO, { relationship: "inside", relationshipTargets: [DELPHINE], relationshipTriangles: [CORINNE], title: "Sided with her", description: "Sided with Delphine" }));
    const t = whole(tl);
    const svg = t.shot(stepOf(t, 310)).svg;
    const slides = [...svg.matchAll(/<g class="slid" transform="translate\(([^)]*)\)"><animateTransform ([^>]*)\/>/g)];
    expect(slides.length).toBeGreaterThan(0);
    slides.forEach(([, at, attrs]) => {
      expect(at).not.toBe("0.0 0.0");
      expect(attrs).toContain('repeatCount="indefinite"');
    });
  });

  // R-0742
  it("draws a relationship shift's still mark on its own step and carries it grey after, with no one lit from before", () => {
    const t = whole();
    const cut = t.shot(stepOf(t, 303)).svg;
    expect(markClass(cut, `move:${THEO}>${DELPHINE}:cutoff`)).toMatch(/\bnow\b/);
    expect(markClass(cut, `move:${DELPHINE}>${CORINNE}:toward`)).toMatch(/\bwas\b/);
    expect(marks(cut).filter((m) => m.startsWith("hl:"))).toEqual([]);
  });

  // R-0742, R-0552
  it("carries a cutoff from an earlier date with the line from its person to the wall, so its strike never stands alone", () => {
    const tl = record();
    tl.events.push(event(305, "2020-01-01", "death", MARCUS));
    const t = whole(tl);
    const svg = t.shot(stepOf(t, 305)).svg;
    expect(markClass(svg, `move:${THEO}>${DELPHINE}:cutoff`)).toMatch(/\bwas\b/);
    const carried = svg.slice(svg.indexOf(`move:${THEO}&gt;${DELPHINE}:cutoff`));
    expect(/<line class="mv-trace"[^>]*opacity="([^"]*)"/.exec(carried)![1]).not.toBe("0");
  });
});
