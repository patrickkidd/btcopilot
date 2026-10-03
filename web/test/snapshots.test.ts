import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { arrange, crosses, draw, Mark, Side, VIEW, layout, Sex, Tie, type Cast } from "../src/diagram";
import { among, gapText, Told, untold } from "../src/snapshots";
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
  it("carry a surname initial only for two people in one row who share a first name", () => {
    const L = layout(
      base({
        a: shape("Anna Kerr", Sex.Male, 1950),
        b: shape("Anna Lowe", Sex.Female, 1952),
        c: { ...shape("Anna Kerr", Sex.Female, 1975), you: true },
        d: shape("Theo Kerr", Sex.Male, 1979),
      }),
    );
    expect([L.P.a.name, L.P.b.name, L.P.c.name]).toEqual(["Anna K.", "Anna L.", "Anna"]);
  });

  // R-0549
  it("leave a person's cross close by, on the side away from the name", () => {
    const t = told(apart());
    const L = t.layout;
    const id = String(MARCUS);
    const [cx] = t.shot(1).svg.match(/<g class="mv-sym" transform="translate\(([\d.]+) /)!.slice(1).map(Number);
    const away = L.side[id] === Side.Right ? -1 : 1;
    expect(Math.sign(cx - L.x[id])).toBe(away);
    const gap = Math.abs(cx - L.x[id]) - 8 - L.w / 2;
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
const brood = (n: number): Cast => {
  const kids = Array.from({ length: n }, (_, i) => `k${i}`);
  const people: Cast["people"] = { a: shape("Abe", Sex.Male, 1940), b: shape("Bea", Sex.Female, 1942) };
  kids.forEach((id, i) => (people[id] = { ...shape(["Cy", "Di", "Ed", "Flo", "Gus"][i], Sex.Male, 1960 + i), you: i === 0 }));
  return { ...base(people), kids: [{ of: ["a", "b"], kids }], index: "k0" };
};

describe("a crowded row", () => {
  // R-0566
  it("moves names above the shapes when beside them does not fit", () => {
    const L = arrange(brood(3));
    expect(new Set(["k0", "k1", "k2"].map((id) => L.side[id]))).toEqual(new Set([Side.Above]));
  });

  // R-0566
  it("puts names under the shapes only when neither beside nor above fits", () => {
    const L = arrange(brood(4));
    expect(Object.values(L.side).every((s) => s === Side.Under)).toBe(true);
    expect(L.vw).toBe(VIEW);
  });

  // R-0547
  it("shrinks a row of five or more to the phone's width, never scrolling sideways", () => {
    const L = arrange(brood(5));
    expect(Object.keys(L.P)).toHaveLength(7);
    expect(L.vw).toBeGreaterThan(VIEW);
    const css = readFileSync(new URL("../src/drawer.css", import.meta.url), "utf8");
    expect(css).toMatch(/\.pbp \.draw svg \{[^}]*width: 100%/);
  });

  // R-0547, R-0558
  it("scales down only when nothing else fits, keeping the margin on the screen", () => {
    expect(arrange(brood(2))).toMatchObject({ w: 44, px: 44, vw: VIEW });
    const L = arrange(brood(5));
    expect(L.px).toBeLessThan(44);
    const margin = (24 * L.vw) / 393;
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
    const stand = told(death(), tl).shot(1).svg.match(/<g class="p" data-id="unknown-4">(.*?)<\/g>/)![1];
    expect(stand).toMatch(/<rect class="shape"[^>]* rx="/);
    expect(stand).toContain(">?</text>");
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
  const sizes = [...css.matchAll(/\.pbp \.(lbn|lbd|age|evw) \{[^}]*font-size: (\d+)px/g)].map((m) => Number(m[2]));
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

  // R-0558, R-0555
  it("keeps every ring of a move inside the picture's edges", () => {
    for (const kind of ["distance", "cutoff", "defined-self"]) {
      const t = moved(kind);
      const svg = t.shot(1).svg;
      const rings = [...svg.matchAll(/<circle class="fld[^"]*" cx="([\d.-]+)" cy="([\d.-]+)"[^>]*>(?:<animate attributeName="r" values="[\d.]+;([\d.]+)")?/g)];
      expect(rings.length).toBeGreaterThan(0);
      const frames = [...svg.matchAll(/<g class="mv" transform="translate\(([\d.-]+) ([\d.-]+)\) rotate\(([\d.-]+)\)">/g)];
      // a ring's centre is drawn in the move's own frame: back to the picture's
      const [tx, ty, deg] = frames.length ? frames[0].slice(1).map(Number) : [0, 0, 0];
      const a = (deg * Math.PI) / 180;
      rings.forEach(([, cx, cy, reach]) => {
        const [x, y] = frames.length
          ? [tx + Number(cx) * Math.cos(a) - Number(cy) * Math.sin(a), ty + Number(cx) * Math.sin(a) + Number(cy) * Math.cos(a)]
          : [Number(cx), Number(cy)];
        const r = Number(reach ?? 24);
        expect(x - r).toBeGreaterThanOrEqual(-0.5);
        expect(y - r).toBeGreaterThanOrEqual(-0.5);
        expect(x + r).toBeLessThanOrEqual(t.layout.vw + 0.5);
        expect(y + r).toBeLessThanOrEqual(t.layout.h + 0.5);
      });
    }
  });

  // R-0555, R-0556, R-0557
  it("carries an earlier move in grey and still", () => {
    const svg = moved("distance").shot(2).svg;
    const carried = svg.slice(svg.indexOf('<g class="mvk was"'));
    expect(carried).toContain('class="mv-wall"');
    expect(carried.slice(0, carried.indexOf("</svg>"))).not.toMatch(/<animate/);
  });

  // R-0555, R-0551
  it("writes inside and outside as words, since they have no still drawing", () => {
    const svg = moved("inside").shot(1).svg;
    expect(svg).not.toContain('class="mvk');
    expect(marks(svg)).toContain(`word:${DELPHINE}:Called Corinne nightly`);
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
    expect(marks(svg).filter((m) => m.startsWith("hl:")).sort()).toEqual([MARCUS, DELPHINE, CORINNE].map((id) => `hl:${id}`).sort());
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
