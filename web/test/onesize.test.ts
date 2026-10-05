import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { picture } from "../src/case";
import { caseView } from "../src/caseview";
import { kindMark } from "../src/rows";
import { family, Told } from "../src/snapshots";
import { drawVersion } from "../src/structure";
import { ItemKind } from "../src/types";
import { apart, CORINNE, death, MARCUS, timeline } from "./whitlock";

/** The divorced couple, their children, and a daughter who cuts off from her
 * father, drawn through every view that draws a family. */
const record = () => {
  const tl = timeline();
  const away = tl.events.find((e) => e.id === 132)!;
  away.relationship = "cutoff";
  away.relationshipTargets = [MARCUS];
  return tl;
};

const num = (svg: string, re: RegExp) => [...svg.matchAll(re)].map((m) => m.slice(1).map(Number));

/** What R-0759 holds equal, in the drawing's own units: a man's square, the
 * slash's height, the cutoff's wall, and every mark's line width and every
 * label's size as the one rule set gives them. */
const sizes = (svg: string) => {
  const shape = num(svg, /<rect class="shape[^"]*" x="[-\d.]+" y="[-\d.]+" width="([\d.]+)"/g).map(([w]) => w);
  // a lit slash stands where a resting one does, as tall: the same box
  const ends = num(svg, /<line class="slash[^"]*" x1="[-\d.]+" y1="([-\d.]+)" x2="[-\d.]+" y2="([-\d.]+)"/g);
  expect(new Set(ends.map((e) => e.join(" "))).size).toBe(1);
  const slash = ends.map(([a, b]) => Math.abs(a - b));
  const wall = num(svg, /<line class="mv-wall" x1="([-\d.]+)" y1="([-\d.]+)" x2="([-\d.]+)" y2="([-\d.]+)"/g).map(
    ([x1, y1, x2, y2]) => Math.hypot(x2 - x1, y2 - y1),
  );
  expect(new Set(shape).size).toBe(1);
  return {
    shape: shape[0],
    slash: slash[0] / shape[0],
    wall: wall.length ? wall[0] / shape[0] : null,
    lit: svg.includes('class="slash now'),
  };
};

const css = ["drawer.css", "theme.css", "casereport.css"]
  .map((f) => readFileSync(new URL(`../src/${f}`, import.meta.url), "utf8"))
  .join("\n")
  .replace(/\/\*[\s\S]*?\*\//g, "");

const DRAWN = "shape|you|tie|kin|slash|xd|lbn|lbd|age|evw";

const rule = (cls: string, prop: string) =>
  Number(css.match(new RegExp(`\\.diagram \\.${cls} \\{[^}]*${prop}: ([\\d.]+)`))![1]);

const drawn = () => {
  const tl = record();
  const shots = (told: Told) => Array.from({ length: told.length }, (_, i) => told.shot(i).svg);
  const v = caseView(tl, [], null);
  const views: Record<string, string[]> = {
    "play-by-play": [...shots(new Told(tl, apart())), ...shots(new Told(tl, death()))],
    "Family drawer": shots(new Told(tl, family(tl), true)),
    "case report": [v.household, ...v.sides.map((s) => s.still)].map((s) => picture(v, s, "")),
    "event row": [kindMark(tl.events.find((e) => e.kind === "divorced")!, tl)],
    review: [
      drawVersion(
        new Map([[1, { coding_id: 1, people: tl.people, pair_bonds: tl.pair_bonds, events: tl.events }]]),
        ItemKind.Person,
        { coding_id: 1, item: { ...tl.people.find((p) => p.id === CORINNE)! } },
      ),
    ],
  };
  const seen = Object.entries(views).flatMap(([view, svgs]) =>
    svgs
      .filter((svg) => svg.includes('class="slash'))
      .map((svg) => {
        expect(svg, view).toMatch(/<svg class="[^"]*\bdiagram\b/);
        expect(svg, view).not.toMatch(new RegExp(`class="(${DRAWN})\\b[^>]*(stroke-width|font-size)=`));
        return { view, ...sizes(svg) };
      }),
  );
  expect(new Set(seen.map((s) => s.view))).toEqual(new Set(Object.keys(views)));
  return seen;
};

// R-0759
it("draws the slashes two thirds of a person, lit or resting, and the cutoff's wall a person tall, in every view", () => {
  const seen = drawn();
  seen.forEach((s) => expect(s.slash, s.view).toBeCloseTo(2 / 3, 2));
  expect(seen.filter((s) => s.lit).map((s) => s.view)).toContain("play-by-play");
  // lit, only its colour and its pop differ
  expect(css).not.toMatch(/\.slash\.now \{[^}]*stroke-width/);
  const walls = seen.filter((s) => s.wall !== null);
  expect(walls.map((s) => s.view)).toContain("play-by-play");
  walls.forEach((s) => expect(s.wall, s.view).toBe(1));
});

// Fails today: a family too wide for people 44 across is laid out with people
// 40 or 36 across, and its names, ages and line widths keep their size, so
// they stand larger against those people than in any other picture. Whitlock's
// whole family is one such. Waiting on Patrick's ruling on what gives.
// R-0759
it.fails("draws line widths and names the same size against the people in every view", () => {
  const seen = drawn();
  seen.forEach((s) => expect(s.shape, s.view).toBe(seen[0].shape));
  // line widths and label sizes come from the one rule set, so with the shape
  // the same they stand the same against it in every view
  expect(rule("shape", "stroke-width") / seen[0].shape).toBeCloseTo(1.6 / 44);
  expect(rule("lbn", "font-size") / seen[0].shape).toBeCloseTo(13 / 44);
});

// R-0759
it("sizes the drawing's marks and labels from one rule set, never per view", () => {
  const own = [...css.matchAll(/(^|\})\s*([^{}]+)\{([^}]*)\}/g)]
    .filter(([, , sel, body]) =>
      new RegExp(`\\.(${DRAWN})\\b`).test(sel) && /stroke-width|font-size|stroke-dasharray/.test(body),
    )
    .flatMap(([, , sel]) => sel.split(",").map((s) => s.trim()))
    .filter((s) => new RegExp(`\\.(${DRAWN})\\b`).test(s) && !s.startsWith(".diagram "));
  expect(own).toEqual([]);
});
