import { describe, expect, it } from "vitest";
import { triangle } from "../src/board";
import { draw, figure, Move, ring, type Drawn, type Figure } from "../src/moves";
import type { Person } from "../src/types";

/** The move language as drawn: what each move puts on the board, read off the
 * markup `draw` returns for two or three people standing on the stage ring. */

const W = 390;
const CY = 100;
const H = 220;
const ann = { id: 1, name: "Ann", gender: "female" };
const bo = { id: 2, name: "Bo", gender: "male" };
const cy = { id: 3, name: "Cy", gender: "female" };
const pair = ring([ann, bo], W, CY, 17, H);
const trio = ring([ann, bo, cy], W, CY, 17, H);
const still: Record<"symptom" | "anxiety" | "functioning", string | null> = {
  symptom: null,
  anxiety: null,
  functioning: null,
};

const move = (kind: string, [a, b, c]: Figure[] = pair) =>
  draw(kind, a, b ?? null, still, c ?? null);
const shift = (over: Partial<typeof still>) =>
  draw(null, pair[0], pair[1], { ...still, ...over });

type El = Record<string, string>;

/** Every element carrying a class, with its attributes. */
const els = (svg: string, klass: string): El[] =>
  [...svg.matchAll(/<(\w+)\s([^>]*?)\/?>/g)]
    .map(
      ([, tag, body]): El => ({
        tag,
        ...Object.fromEntries(
          [...body.matchAll(/([\w:-]+)="([^"]*)"/g)].map((m) => [m[1], m[2]]),
        ),
      }),
    )
    .filter((el) => (el.class ?? "").split(" ").includes(klass));

/** The first animation of an attribute on the first element with a class. */
const animated = (svg: string, klass: string, attr: string) => {
  const from = svg.search(new RegExp(`class="${klass}[" ]`));
  const m = svg
    .slice(from)
    .match(new RegExp(`<animate attributeName="${attr}" values="([^"]*)" keyTimes="([^"]*)"`));
  return { values: m![1].split(";").map(Number), keyTimes: m![2] };
};

/** Where someone stands once their walk is over. */
const landed = (drawn: Drawn, who: Figure) => {
  const step = drawn.steps[who.id];
  if (!step) return { x: who.x, y: who.y };
  const [dx, dy] = step.values.split(";").at(-1)!.split(" ").map(Number);
  return { x: who.x + dx, y: who.y + dy };
};

const apart = (p: { x: number; y: number }, q: { x: number; y: number }) =>
  Math.hypot(p.x - q.x, p.y - q.y);

const numbers = (text: string) => (text.match(/-?\d+(\.\d+)?/g) ?? []).map(Number);

/** The distance, along the stage, between the two a pair move is drawn across. */
const span = Math.hypot(pair[1].x - pair[0].x, pair[1].y - pair[0].y);

describe("toward", () => {
  // R-0115
  it("ends with the mover standing beside the other, not on them", () => {
    const [a, b] = pair;
    const gap = apart(landed(move(Move.Toward), a), b);
    expect(gap).toBeGreaterThan(a.r! + b.r!);
    expect(gap).toBeLessThan(a.r! + b.r! + 12);
  });

  // R-0115
  it("carries the arrow's tail along with the mover, on the mover's own clock", () => {
    const drawn = move(Move.Toward);
    const [a] = pair;
    const tail = animated(drawn.marks, "mv-arrow", "x1");
    const end = landed(drawn, a);
    expect(tail.keyTimes).toBe(drawn.steps[a.id].keyTimes);
    expect(tail.values.at(-1)! - tail.values[0]).toBeCloseTo(apart(end, a), 0);
  });
});

describe("cutoff and distance", () => {
  // R-0116
  it("keeps the other's field behind the wall rather than taking it away", () => {
    const marks = move(Move.Cutoff).marks;
    const field = (phase: string) => els(marks, phase).filter((el) => el.class.includes("fld"));
    const walled = field("postA");
    expect(walled).toHaveLength(field("preA").length);
    const clip = /url\(#(\w+)\)/.exec(walled[0]["clip-path"] ?? "")?.[1];
    expect(marks).toContain(`<clipPath id="${clip}">`);
    expect(walled.every((ring) => ring["clip-path"] === `url(#${clip})`)).toBe(true);
  });

  // R-0117
  it("stands the wall nearer the one who puts it up", () => {
    const [wall] = els(move(Move.Cutoff).marks, "mv-wall");
    expect(Number(wall.x1)).toBeLessThan(span / 2);
  });

  // R-0117
  it("casts a shadow that widens behind the wall instead of a straight cut", () => {
    const d = /<clipPath[^>]*><path[^>]* d="([^"]*)"/.exec(move(Move.Cutoff).marks)![1];
    const [, armTop, , armBottom, , spread] = numbers(d.split("M")[2]);
    expect(Math.abs(spread)).toBeGreaterThan(Math.abs(armBottom - armTop) / 2);
  });

  // R-0137
  it("shows whose wall it is: a trace from the actor to the wall between them", () => {
    const [a] = pair;
    const marks = move(Move.Cutoff).marks;
    const [trace] = els(marks, "mv-trace");
    const [wall] = els(marks, "mv-wall");
    expect(marks).toContain(`translate(${a.x.toFixed(1)} ${a.y.toFixed(1)})`);
    expect(Number(trace.x1)).toBeLessThanOrEqual(a.r! + 3);
    expect(Number(trace.x2)).toBeLessThan(Number(wall.x1));
    expect(Number(wall.x1)).toBeGreaterThan(0);
    expect(Number(wall.x1)).toBeLessThan(span);
  });

  // R-0118
  it("strikes a line through the wall for cutoff and none for distance", () => {
    expect(els(move(Move.Distance).marks, "mv-strike")).toHaveLength(0);
    expect(els(move(Move.Cutoff).marks, "mv-strike")).toHaveLength(1);
  });

  // R-0118
  it("draws distance as the cutoff drawing with the strike taken out", () => {
    const same = (svg: string) => svg.replace(/csh\d+/g, "csh");
    const cutoff = move(Move.Cutoff);
    const distance = move(Move.Distance);
    expect(same(cutoff.marks.replace(/<line class="mv-strike[^>]*\/>/, ""))).toBe(
      same(distance.marks),
    );
    expect(cutoff.actor).toBe(distance.actor);
  });

  /** The rings of the other's field before the wall lands and after it. */
  const phases = () => {
    const rings = [
      ...move(Move.Cutoff).marks.matchAll(
        /<circle class="fld (preA|postA)"[^>]*>(.*?)<\/circle>/g,
      ),
    ];
    const of = (phase: string) => rings.filter((r) => r[1] === phase).map((r) => r[2]);
    return { before: of("preA"), after: of("postA") };
  };

  // R-0148
  it("keeps the field's beat when the wall lands", () => {
    const beat = (inner: string) =>
      [...inner.matchAll(/dur="([^"]*)" begin="([^"]*)"/g)].map((m) => m.slice(1));
    const { before, after } = phases();
    expect(after.map(beat)).toEqual(before.map(beat));
  });

  // R-0148
  it("keeps the field's reach and fading when the wall lands", () => {
    const shape = (inner: string) =>
      [...inner.matchAll(/attributeName="(\w+)" values="([^"]*)"/g)].map((m) => m.slice(1));
    const { before, after } = phases();
    expect(after.map(shape)).toEqual(before.map(shape));
  });
});

describe("conflict", () => {
  // R-0114
  it("reads as static, not a couple of segments: a many-kinked line and a burst", () => {
    const marks = move(Move.Conflict).marks;
    const [line] = els(marks, "mv-spark");
    expect(line.points.trim().split(/\s+/).length).toBeGreaterThanOrEqual(6);
    expect(els(marks, "mv-burst").length).toBeGreaterThanOrEqual(6);
  });
});

describe("over- and underfunctioning", () => {
  /** The arrow on someone's flank: where it stands and which end its head is. */
  const flank = (svg: string, dir: "up" | "down") => {
    const m = new RegExp(
      `class="mv-flank ${dir}"><line x1="([^"]*)" y1="([^"]*)" x2="[^"]*" y2="([^"]*)"/>` +
        `<line x1="[^"]*" y1="([^"]*)"`,
    ).exec(svg)!;
    const [x, top, bottom, head] = m.slice(1).map(Number);
    return { x, top, bottom, head };
  };
  const beside = (arrow: { x: number; top: number; bottom: number }, who: Figure) =>
    Math.abs(arrow.x - who.x) > who.r! &&
    Math.abs(arrow.x - who.x) < who.r! * 3 &&
    Math.abs((arrow.top + arrow.bottom) / 2 - who.y) < 1;

  // R-0119
  it("puts an up arrow beside the over-functioner and a down arrow beside the other", () => {
    const [a, b] = pair;
    const marks = move(Move.Overfunctioning).marks;
    const up = flank(marks, "up");
    const down = flank(marks, "down");
    expect(beside(up, a)).toBe(true);
    expect(up.head).toBe(up.top);
    expect(beside(down, b)).toBe(true);
    expect(down.head).toBe(down.bottom);
  });

  // R-0119
  it("puts the down arrow beside the under-functioner and the up arrow beside the other", () => {
    const [a, b] = pair;
    const marks = move(Move.Underfunctioning).marks;
    expect(beside(flank(marks, "down"), a)).toBe(true);
    expect(beside(flank(marks, "up"), b)).toBe(true);
  });
});

describe("the triangle moves", () => {
  // R-0120
  it("brings the inside mover in to overlap the one they want, with no glow", () => {
    const [a, b] = trio;
    const drawn = move(Move.Inside, trio);
    expect(apart(landed(drawn, a), b)).toBeLessThan(a.r! + b.r!);
    expect(drawn.marks + drawn.actor).not.toMatch(/filter|glow/);
  });

  // R-0288
  it("pushes the old insider out with the same motion", () => {
    const [, b, c] = trio;
    const drawn = move(Move.Inside, trio);
    expect(apart(landed(drawn, c), b)).toBeGreaterThan(apart(c, b));
    expect(drawn.steps[c.id].keyTimes).toBe(drawn.steps[trio[0].id].keyTimes);
  });

  // R-0120
  it("draws nothing between the two who stay when someone walks out", () => {
    const [, b, c] = trio;
    const near = (x: number, y: number, who: Figure) => Math.hypot(x - who.x, y - who.y) < who.r! + 6;
    const ends = [...move(Move.Outside, trio).marks.matchAll(/points="([^"]*)"/g)].map((m) => {
      const points = m[1].trim().split(/\s+/).map((p) => p.split(",").map(Number));
      return [points[0], points.at(-1)!];
    });
    for (const [[x0, y0], [x1, y1]] of ends) {
      const joins = (p: Figure, q: Figure) =>
        (near(x0, y0, p) && near(x1, y1, q)) || (near(x0, y0, q) && near(x1, y1, p));
      expect(joins(b, c)).toBe(false);
    }
  });

  // R-0286, R-0288
  it.fails("draws no zigzag on the outside move", () => {
    expect(els(move(Move.Outside, trio).marks, "mv-tension")).toHaveLength(0);
  });

  // R-0291
  it.fails("moves both who stay toward each other in the outside move", () => {
    const [, b, c] = trio;
    const drawn = move(Move.Outside, trio);
    expect(apart(landed(drawn, b), c)).toBeLessThan(apart(b, c));
    expect(apart(landed(drawn, c), b)).toBeLessThan(apart(c, b));
  });

  // R-0291
  it.fails("ends the outside move with the two who stay overlapped", () => {
    const [, b, c] = trio;
    const drawn = move(Move.Outside, trio);
    expect(apart(landed(drawn, b), landed(drawn, c))).toBeLessThan(b.r! + c.r!);
  });

  const view = () =>
    triangle(
      [ann, bo, cy].map((p) => ({ ...p, primary: false }) as unknown as Person),
      W,
    ).svg;

  // R-0286
  it.fails("draws no zigzag on the triangle view", () => {
    expect(els(view(), "mv-tension")).toHaveLength(0);
  });

  // R-0288, R-0292
  it.fails("stands two close together and one apart on the triangle view", () => {
    const centres = els(view(), "disc").map((d) =>
      d.tag === "circle"
        ? { x: Number(d.cx), y: Number(d.cy) }
        : { x: Number(d.x) + Number(d.width) / 2, y: Number(d.y) + Number(d.height) / 2 },
    );
    const gaps = [
      apart(centres[0], centres[1]),
      apart(centres[1], centres[2]),
      apart(centres[0], centres[2]),
    ].sort((p, q) => p - q);
    expect(gaps[0]).toBeLessThan(gaps[1] / 2);
  });
});

describe("fusion", () => {
  // R-0121
  it("holds the pair with three straight bars from the first frame", () => {
    const marks = move(Move.Fusion).marks;
    const bars = els(marks, "mv-band");
    expect(bars).toHaveLength(3);
    for (const bar of bars) {
      expect(bar.y1).toBe(bar.y2);
      expect(bar.opacity).toBeUndefined();
    }
    expect(marks).not.toMatch(/mv-band[^>]*>(?:(?!<\/line>).)*attributeName="opacity"/);
  });

  // R-0121
  it("shrinks the bars into their final place as the pair is drawn in", () => {
    const drawn = move(Move.Fusion);
    const from = animated(drawn.marks, "mv-band", "x1");
    const to = animated(drawn.marks, "mv-band", "x2");
    expect(from.values.at(-1)!).toBeGreaterThan(from.values[0]);
    expect(to.values.at(-1)!).toBeLessThan(to.values[0]);
    expect(from.keyTimes).toBe(drawn.steps[pair[0].id].keyTimes);
  });
});

describe("projection and anxiety", () => {
  // R-0123
  it("shows the parent's own sharp outline with a blurred double over it", () => {
    const [a] = pair;
    const drawn = move(Move.Projection);
    const person = figure(a, drawn.actor, drawn.ghosts.actor);
    expect(els(person, "disc")).toHaveLength(1);
    expect(els(person, "gh")).toHaveLength(1);
    expect(person).toMatch(/<filter id="(\w+)"[^>]*><feGaussianBlur[^>]*\/><\/filter>/);
    expect(drawn.ghosts.target).toBeTruthy();
  });

  // R-0123
  it.fails("carries the agitation along the arrow as a smooth gradient", () => {
    expect(move(Move.Projection).marks).toMatch(/<linearGradient/);
  });

  const spikes = (svg: string) =>
    els(svg, "mv-spike")
      .slice(0, 8)
      .map((s) => [s.x1, s.y1, s.x2, s.y2]);

  // R-0124
  it("draws a shift in anxiety with projection's own static", () => {
    expect(spikes(shift({ anxiety: "up" }).marks)).toEqual(spikes(move(Move.Projection).marks));
  });

  // R-0124
  it("shakes a shift in anxiety with projection's blurred double", () => {
    const anxious = shift({ anxiety: "up" });
    expect(anxious.actor.split(" ")).toContain("pshake");
    expect(move(Move.Projection).actor.split(" ")).toContain("pshake");
    expect(anxious.ghosts.actor).toBeTruthy();
  });
});

describe("the health cross", () => {
  /** The arrow beside the cross: its tail, its head, and its whole height. */
  const arrow = (svg: string, which: "worse" | "better") => {
    const m = new RegExp(
      `class="sym-arrow ${which}"><line class="mv-dir" x1="[^"]*" y1="([^"]*)" x2="[^"]*" y2="([^"]*)"/>` +
        `<polygon class="tipfill" points="([^"]*)"`,
    ).exec(svg)!;
    const ys = [
      Number(m[1]),
      Number(m[2]),
      ...m[3].split(" ").map((p) => Number(p.split(",")[1])),
    ];
    const head = Number(m[3].split(" ")[0].split(",")[1]);
    return { tail: Number(m[1]), head, height: Math.max(...ys) - Math.min(...ys) };
  };
  const cross = (svg: string) =>
    Math.max(...els(svg, "tipfill").filter((r) => r.tag === "rect").map((r) => Number(r.height)));

  // R-0125
  it("says worse with an up arrow beside the cross", () => {
    const marks = shift({ symptom: "up" }).marks;
    expect(els(marks, "mv-sym")).toHaveLength(1);
    const up = arrow(marks, "worse");
    expect(up.head).toBeLessThan(up.tail);
    expect(marks).not.toContain("sym-arrow better");
  });

  // R-0125
  it("says better with a down arrow beside the cross", () => {
    const marks = shift({ symptom: "down" }).marks;
    expect(els(marks, "mv-sym")).toHaveLength(1);
    const down = arrow(marks, "better");
    expect(down.head).toBeGreaterThan(down.tail);
    expect(marks).not.toContain("sym-arrow worse");
  });

  // R-0190
  it("stands the worse arrow exactly as tall as the cross", () => {
    const marks = shift({ symptom: "up" }).marks;
    expect(arrow(marks, "worse").height).toBeCloseTo(cross(marks), 5);
  });

  // R-0190
  it("stands the better arrow exactly as tall as the cross", () => {
    const marks = shift({ symptom: "down" }).marks;
    expect(arrow(marks, "better").height).toBeCloseTo(cross(marks), 5);
  });
});

describe("functioning", () => {
  // R-0126
  it.fails("draws on the person's own outline, adding no circle of its own", () => {
    expect(shift({ functioning: "down" }).marks).not.toContain("<circle");
  });
});
