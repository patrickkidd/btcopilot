import { esc } from "./dom";
import { CROSS, cross as healthCross, DEMO, draw as moveMarks, FIELD, FLANK, Move, Shift, SPIKES, spikes as anxious, WALL } from "./moves";

/** A small family diagram generated from a cast, to FAMILY_DIAGRAM_VISUAL_SPEC.md,
 * ported from the approved play-by-play reference (design/playbyplay-snapshots,
 * diagram.js). `layout` runs once per case; `draw` runs per snapshot on the same
 * positions, so between snapshots only marks, ages, bond status and the death X
 * change. */

export enum Sex {
  Male = "m",
  Female = "f",
  Unknown = "?",
}

export const sexOf = (gender: string | null): Sex =>
  gender === "female" ? Sex.Female : gender === "male" ? Sex.Male : Sex.Unknown;

export interface Shape {
  name: string;
  g: Sex;
  born: number | null;
  died?: number | null;
  you?: boolean;
}

export enum Tie {
  Together = "together",
  Married = "married",
  Separated = "sep",
  Divorced = "div",
}

export interface Bond {
  a: string;
  b: string;
  st: Tie;
  /** Only a marriage makes the line solid, and only a marriage can be divorced. */
  married: boolean;
}

export interface Brood {
  of: string[];
  kids: string[];
}

export enum Mark {
  Up = "up",
  Down = "down",
  FnUp = "fup",
  FnDown = "fdown",
  Anxiety = "anx",
  Event = "event",
  Emphasis = "hl",
  Couple = "couple",
  Separated = "sep",
  Divorced = "div",
  Died = "died",
  Toward = "toward",
  Away = "away",
  /** Any other relationship move, drawn the moves board's own way. */
  Move = "move",
  /** An event about the whole family: everyone alive then, emphasised. */
  Family = "family",
}

/** Drawn in the emphasis colour on its own date, grey once carried. */
export enum Tone {
  Now = "now",
  Was = "was",
}

export interface Arrow {
  k: Mark.Toward | Mark.Away;
  from: string;
  to: string;
  cls?: Tone;
}

/** A move other than toward or away: the moves board's own drawing, its still
 * parts only, on shapes that stay where they stand (Q1b). */
export interface Kin {
  k: Mark.Move;
  kind: Move;
  from: string;
  to: string | null;
  cls?: Tone;
}

export interface Placed {
  k: Mark;
  who: string;
  word?: string;
  cls?: Tone;
  row?: number;
}

export interface Cast {
  people: Record<string, Shape>;
  bonds: Bond[];
  kids: Brood[];
  index: string;
  /** Who carries a mark beside them, who carries the health cross, and the
   * longest event word each is given: the room kept beside a shape. */
  marked: string[];
  cross: string[];
  words: Record<string, number>;
  moves: Arrow[];
  /** The moves drawn the moves board's way, and who shows anxiety, so names and
   * words stand clear of their marks. */
  kin: Kin[];
  anxious: string[];
  /** A person with no family tie stands on the row of the one they move with. */
  assoc: Record<string, string>;
  until: number;
}

export enum Names {
  Widen = "widen",
  Above = "above",
  Under = "under",
}

export interface Options {
  w: number;
  inset: boolean | "auto";
  names: Names;
  steps: boolean;
  fit: boolean;
  compact: boolean;
}

/** Where a name sits: right, left, above beside the line up to the parents,
 * above centred, or under. */
export enum Side {
  Right = "r",
  Left = "l",
  Above = "a",
  Top = "t",
  Under = "u",
}

/** How far past a person's shape to count: the shape and name, those and the
 * event words, or those and every mark. */
enum Reach {
  Bare,
  Words,
  /** The marks that stay beside a shape, the health cross; not a step's words,
   * which find their own room on their step. */
  Marks,
  All,
}

export interface Box {
  x0: number;
  x1: number;
  y0: number;
  y1: number;
}

export interface Layout {
  P: Record<string, Shape>;
  x: Record<string, number>;
  y: Record<string, number>;
  side: Record<string, Side>;
  zone: Record<string, number>;
  bonds: Bond[];
  kids: Brood[];
  gen: Record<string, number>;
  w: number;
  level: Record<string, number>;
  below: Record<string, number>;
  names: Box[];
  h: number;
  vw: number;
  px: number;
  wide: number;
  /** The margin kept above and below the family, in the drawing's own units. */
  my: number;
  /** How far past each shape the person's own marks reach all round: anxiety's
   * spikes. Their name stands clear of it. */
  ring: Record<string, number>;
  /** How far past each shape the person's event words start: clear of the
   * spikes and of the flank arrow beside them. */
  inset: Record<string, number>;
}

export interface DrawnBond {
  a: string;
  b: string;
  st: Tie;
  fresh: boolean;
  hot: boolean;
  married: boolean;
}

export interface Frame {
  t: number;
  bonds: DrawnBond[];
  marks: Placed[];
  died: Set<string>;
  moves: Arrow[];
  kin: Kin[];
  label: string;
}

/** The drawing is laid out in a box this wide; the page scales it to the phone. */
export const VIEW = 360;
/** Clearance kept between any two things in a row. */
const PAD = 10;
/** Ruled 2026-09-26: labels at least 13px. */
export const NAME = 13;
const CH = 0.6;
const LEAD = 15;
/** How far a label's box reaches above its line. */
const ASCENT = 18;

/** How far a name stands from its shape, clear of what the person's own marks reach. */
const offset = (d: Dims, ring: number) => Math.max(d.OFF, ring + 2);
/** How far above its shape a name above it ends, clear of the same. */
const rise = (ring: number) => Math.max(4, ring + 4);
/** The spec's size steps, largest first. Ruled 2026-09-26: people 44 across
 * where a row fits, never below 36. */
const STEPS = [44, 40, 36];

class Dims {
  W: number;
  E: number;
  RIM: number;
  DROP: number;
  SIB: number;
  LOOSE: number;
  COUPLE: number;
  OFF: number;
  GAP: number;
  MARK: number;
  ZONE: number;

  constructor(w: number, compact = false) {
    this.W = w;
    this.E = w / 2;
    // the index outline: the Pro app adds a tenth of the width on each side
    this.RIM = w * 0.1;
    this.DROP = w / 2.2;
    this.SIB = (compact ? 2 : 3) * w;
    this.LOOSE = (compact ? 2 : 2.5) * w;
    this.COUPLE = this.SIB;
    this.OFF = 0.2 * w;
    // ruled 2026-09-26: a mark sits within an eighth of a width of its person
    this.GAP = w / 8;
    // a mark that stands on its own, a slash or a wall, is as tall as a person
    this.MARK = w;
    // how far the cross and its arrow reach past the shape: two square cells
    this.ZONE = this.GAP + 2 * CROSS;
  }

  half(p: Shape): number {
    return p.you ? this.E + this.RIM : this.E;
  }
}

class Unplaceable extends Error {
  constructor(
    rule: string,
    readonly wide = false,
  ) {
    super(`cannot place: ${rule}`);
  }
}

const f = (v: number) => v.toFixed(1);
const yr = (t: number) => Math.floor(t);

function lines(p: Shape, t: number): string[] {
  const l = [p.name];
  if (p.born != null) l.push(`b. ${yr(p.born)}`);
  if (p.died != null && p.died <= t + 1e-6) l.push(`d. ${yr(p.died)}`);
  return l;
}

const textWidth = (l: string[]) => Math.max(...l.map((s) => s.length * NAME * CH));

export const DEFAULTS: Options = {
  w: 44,
  inset: "auto",
  names: Names.Widen,
  steps: true,
  fit: true,
  compact: false,
};

/** The layout the approved page uses: names beside or above, and under the
 * shapes only when nothing else fits; scaled down as the last resort. */
export function arrange(cast: Cast): Layout {
  const L = layout(cast);
  if (L.vw <= VIEW) return L;
  try {
    return layout(cast, { names: Names.Under, compact: true, fit: false });
  } catch (e) {
    if (!(e instanceof Unplaceable)) throw e;
    return L;
  }
}

export function layout(cast: Cast, given: Partial<Options> = {}): Layout {
  const opts: Options = { ...DEFAULTS, ...given };
  if (opts.steps) {
    // the largest size that fits; at each size the couple line reaches past the
    // children (ruled 4a) unless that is what makes it collide, then it ends
    // above them (4b)
    let last: Unplaceable | null = null;
    const insets = opts.inset === "auto" ? [true, false] : [opts.inset];
    for (let st = 0; st < STEPS.length; st++) {
      for (let si = 0; si < insets.length; si++) {
        const end = st === STEPS.length - 1 && si === insets.length - 1;
        try {
          return layout(cast, {
            ...opts,
            w: STEPS[st],
            inset: insets[si],
            steps: false,
            fit: opts.fit && end,
          });
        } catch (e) {
          if (!(e instanceof Unplaceable) || !e.wide) throw e;
          last = e;
        }
      }
    }
    throw new Unplaceable(
      `even with people ${STEPS[STEPS.length - 1]} across, ${last!.message.replace("cannot place: ", "")}`,
      true,
    );
  }
  const d = new Dims(opts.w, opts.compact);
  const { E } = d;
  const tight = opts.names === Names.Above;
  const under = opts.names === Names.Under;
  let P = cast.people;
  const ids = Object.keys(P);
  const assoc = cast.assoc;
  const gen: Record<string, number> = {};
  const parents: Record<string, string[]> = {};
  const bondsOf: Record<string, Bond[]> = {};
  ids.forEach((id) => (bondsOf[id] = []));
  cast.bonds.forEach((b) => {
    bondsOf[b.a].push(b);
    bondsOf[b.b].push(b);
  });
  cast.kids.forEach((k) => k.kids.forEach((id) => (parents[id] = k.of)));
  const other = (b: Bond, id: string) => (b.a === id ? b.b : b.a);
  const tied = (id: string) =>
    bondsOf[id].length > 0 || !!parents[id] || cast.kids.some((k) => k.of.includes(id));
  const half = (id: string) => d.half(P[id]);

  gen[cast.index] = 0;
  for (let pass = 0; pass <= ids.length; pass++) {
    cast.bonds.forEach((b) => {
      if (gen[b.a] != null && gen[b.b] == null) gen[b.b] = gen[b.a];
      if (gen[b.b] != null && gen[b.a] == null) gen[b.a] = gen[b.b];
    });
    cast.kids.forEach((k) => {
      let g: number | null = null;
      k.of.forEach((id) => {
        if (gen[id] != null) g = gen[id] + 1;
      });
      k.kids.forEach((id) => {
        if (gen[id] != null) g = gen[id];
      });
      if (g == null) return;
      const at: number = g;
      k.of.forEach((id) => {
        if (gen[id] == null) gen[id] = at - 1;
      });
      k.kids.forEach((id) => {
        if (gen[id] == null) gen[id] = at;
      });
    });
  }
  // spec 8.4: someone with no family tie stands on the row of the person they
  // relate to, and failing anyone placed, at the end of the reader's row: a
  // sparse record's missing link is the coach's question, not a failed drawing
  const loose: Record<string, string> = {};
  ids.forEach((id) => {
    // the reader stands on row 0 even with no family drawn beside them
    if (tied(id) || gen[id] != null) return;
    loose[id] = assoc[id] != null && gen[assoc[id]] != null ? assoc[id] : cast.index;
    gen[id] = gen[loose[id]];
  });
  let lo = Infinity;
  let hi = -Infinity;
  ids.forEach((id) => {
    if (gen[id] == null) throw new Unplaceable(`a person not connected to the rest of the family (${P[id].name})`);
    lo = Math.min(lo, gen[id]);
    hi = Math.max(hi, gen[id]);
  });
  cast.bonds.forEach((b) => {
    if (gen[b.a] !== gen[b.b]) throw new Unplaceable("a couple across generations");
  });

  // ruled 2026-09-26: first names; a surname initial only for two people in one
  // row who share a first name. A stand-in such as "Delphine's mother" is kept whole.
  const shown: Record<string, string> = {};
  ids.forEach((id) => {
    const n = P[id].name;
    shown[id] = /'s /.test(n) ? n : n.split(" ")[0];
  });
  P = { ...P };
  ids.forEach((id) => {
    const parts = P[id].name.split(" ");
    const twin =
      parts.length > 1 &&
      ids.some((o) => o !== id && gen[o] === gen[id] && shown[o] === shown[id]);
    P[id] = {
      ...P[id],
      name: twin ? `${shown[id]} ${parts[parts.length - 1].charAt(0)}.` : shown[id],
    };
  });
  const x: Record<string, number> = {};
  const y: Record<string, number> = {};
  const side: Record<string, Side> = {};
  const zone: Record<string, number> = {};
  const lw: Record<string, number> = {};
  const nl: Record<string, number> = {};
  const rows: string[][] = [];
  const ROW = Math.max(3 * d.W, under ? 100 : 66);
  ids.forEach((id) => {
    gen[id] -= lo;
    y[id] = gen[id] * ROW;
    const l = lines(P[id], cast.until);
    lw[id] = textWidth(l);
    nl[id] = l.length;
  });
  const marked = new Set(cast.marked);
  const crossed = new Set(cast.cross);
  const whoIn = (kinds: Move[]) =>
    cast.kin.filter((k) => kinds.includes(k.kind)).flatMap((k) => (k.to ? [k.from, k.to] : [k.from]));
  const spiked = new Set([...cast.anxious, ...whoIn([Move.Projection])]);
  const flanked = new Set(whoIn([Move.Overfunctioning, Move.Underfunctioning]));
  const ring: Record<string, number> = {};
  const inset: Record<string, number> = {};
  ids.forEach((id) => {
    ring[id] = spiked.has(id) ? SPIKES + 1 : 0;
    inset[id] = Math.max(d.GAP, ring[id] + 2, flanked.has(id) ? FLANK.at + FLANK.wing + 3 : 0);
  });
  const off = (id: string) => offset(d, ring[id]);
  const words = cast.words;
  // how far a person's longest event word reaches past the shape
  const ww = (id: string) => (words[id] ? inset[id] + words[id] * NAME * CH : 0);
  // how far a person's marks reach past the shape: the cross and its arrow, or the word
  const zw = (id: string, reach: Reach) => Math.max(crossed.has(id) ? d.ZONE : 0, reach === Reach.All ? ww(id) : 0);

  // ---- the order of each row, top to bottom ----
  const placed = new Set<string>();
  const at: Record<string, number> = {};
  // spec 5: siblings oldest-left; with no dates, the record's order
  const sibOrder = (kids: string[]) =>
    kids.every((id) => P[id].born != null)
      ? kids.slice().sort((a, b) => P[a].born! - P[b].born!)
      : kids.slice();
  /* spec 5, multiple partnerships: a person with no brothers or sisters in the
   * row keeps the first partner on one side and the next on the other; with
   * family beside them, every partner goes on the side away from it. Each
   * partner's own other partners continue outward from that couple, so no
   * couple line passes under anyone outside it. */
  function lay(anchor: string, dir: number, seq: string[], split: boolean): void {
    const sides: Record<number, string[]> = { 1: [], [-1]: [] };
    const queue: [string, number][] = [];
    const put = (q: string, s: number) => {
      placed.add(q);
      sides[s].push(q);
      queue.push([q, s]);
    };
    bondsOf[anchor]
      .map((b) => other(b, anchor))
      .filter((q) => !placed.has(q) && gen[q] === gen[anchor])
      .forEach((q, i) => {
        if (parents[q] && parents[anchor])
          throw new Unplaceable("a couple where both partners’ parents are in the record");
        if (split && i > 1) throw new Unplaceable("three or more partners for one person with no family beside them");
        put(q, split && i === 1 ? -dir : dir);
      });
    while (queue.length) {
      const [p, s] = queue.shift()!;
      bondsOf[p].forEach((b) => {
        const q = other(b, p);
        if (placed.has(q) || gen[q] !== gen[p]) return;
        if (parents[q] && parents[p])
          throw new Unplaceable("a couple where both partners’ parents are in the record");
        put(q, s);
      });
    }
    seq.push(...sides[-1].reverse(), anchor, ...sides[1]);
  }
  // men on the left, so a woman's partners go to her left
  const manSide = (id: string) => (P[id].g === Sex.Female ? -1 : 1);
  for (let g = 0; g <= hi - lo; g++) {
    const seq: string[] = [];
    cast.kids
      .filter((k) => gen[k.kids[0]] === g)
      .map((k) => ({ k, key: k.of.reduce((s, id) => s + at[id], 0) / k.of.length }))
      .sort((a, b) => a.key - b.key)
      .forEach(({ k }) => {
        const sibs = sibOrder(k.kids);
        sibs.forEach((s) => placed.add(s));
        const n = sibs.length;
        sibs.forEach((s, i) =>
          lay(s, n > 1 && i === 0 ? -1 : n > 1 && i === n - 1 ? 1 : manSide(s), seq, n === 1),
        );
      });
    const roots = ids.filter((id) => gen[id] === g && !placed.has(id) && tied(id));
    if (roots.length) {
      if (seq.length)
        throw new Unplaceable("a couple in a row beside another family, with nothing to say which side it goes on");
      const anchor = roots
        .slice()
        .sort(
          (a, b) =>
            bondsOf[b].length - bondsOf[a].length ||
            cast.bonds.indexOf(bondsOf[a][0]) - cast.bonds.indexOf(bondsOf[b][0]),
        )[0];
      placed.add(anchor);
      lay(anchor, P[anchor].g === Sex.Female ? -1 : 1, seq, true);
      if (roots.some((id) => !placed.has(id))) throw new Unplaceable("two separate families side by side in one row");
    }
    // a reader with no family drawn stands first, the others at the end beside them
    if (gen[cast.index] === g && !tied(cast.index)) {
      seq.push(cast.index);
      placed.add(cast.index);
    }
    ids
      .filter((id) => gen[id] === g && !tied(id) && id !== cast.index)
      .forEach((id) => {
        const a = loose[id];
        const i = seq.indexOf(a);
        const right = bondsOf[a].some((b) => seq.indexOf(other(b, a)) > i);
        if (right) seq.unshift(id);
        else seq.push(id);
        placed.add(id);
      });
    seq.forEach((id, i) => (at[id] = i));
    rows.push(seq);
  }
  ids.forEach((id) => {
    if (!placed.has(id)) throw new Unplaceable(`a person the row rules do not reach (${P[id].name})`);
  });

  // how far past a person's shape the given reach runs, on the marks' side
  const marks = (id: string, reach: Reach) =>
    reach === Reach.All || reach === Reach.Marks ? zw(id, reach) : reach === Reach.Words ? ww(id) : 0;
  function rightExt(id: string, reach = Reach.All): number {
    const e = half(id);
    let r = e;
    if (side[id] === Side.Under || side[id] === Side.Top) r = Math.max(r, lw[id] / 2);
    if (side[id] === Side.Right) r = Math.max(r, e + off(id) + lw[id]);
    if (side[id] === Side.Above) r = Math.max(r, 5 + lw[id]);
    if (zone[id] === 1) r = Math.max(r, e + marks(id, reach));
    return r;
  }
  function leftExt(id: string, reach = Reach.All): number {
    const e = half(id);
    let r = e;
    if (side[id] === Side.Under || side[id] === Side.Top) r = Math.max(r, lw[id] / 2);
    if (side[id] === Side.Left) r = Math.max(r, e + off(id) + lw[id]);
    if (zone[id] === -1) r = Math.max(r, e + marks(id, reach));
    return r;
  }
  // a step's words never push neighbours apart: each finds room of its own on
  // its step (word placement in draw), so only names and lasting marks count
  const between = (a: string, b: string) => rightExt(a, Reach.Marks) + leftExt(b, Reach.Marks);
  function gapFor(a: string, b: string): number {
    if (cast.bonds.some((k) => (k.a === a && k.b === b) || (k.a === b && k.b === a))) return d.COUPLE;
    if (parents[a] && parents[a] === parents[b]) return d.SIB;
    return d.LOOSE;
  }
  // a move along the row runs on this side; keep the name off it
  function along(id: string): number {
    let s = 0;
    cast.moves.forEach((m) => {
      const o = m.from === id ? m.to : m.to === id ? m.from : null;
      if (o != null && gen[o] === gen[id]) s = x[o] > x[id] ? 1 : -1;
    });
    return s;
  }
  const markSide = (id: string) => (marked.has(id) ? (side[id] === Side.Right ? -1 : 1) : 0);
  /* spec 6: name to the right; left if the right neighbour is too close; above
   * if both sides are tight and there is a line up to parents; then the
   * rightmost person may tuck its name left to save width. */
  function labels(row: string[]): void {
    for (let i = row.length - 1; i >= 0; i--) {
      const id = row[i];
      const e = half(id);
      const q = row[i + 1];
      const l = row[i - 1];
      const edge = q ? x[q] - leftExt(q, Reach.Marks) : Infinity;
      const need = off(id) + lw[id] + PAD;
      if (under) {
        side[id] = Side.Under;
        zone[id] = marked.has(id) ? (!l && q ? -1 : 1) : 0;
        continue;
      }
      if (tight) {
        // ruled: the row would not fit, so names go above
        side[id] = parents[id] ? Side.Above : Side.Top;
        zone[id] = marked.has(id) ? 1 : 0;
        continue;
      }
      const mv = along(id);
      if (mv !== 1 && x[id] + e + need <= edge) side[id] = Side.Right;
      else if (mv !== -1 && (!l || x[id] - e - need >= x[l] + half(l))) side[id] = Side.Left;
      else if (mv && parents[id]) side[id] = Side.Above;
      else side[id] = mv === -1 ? Side.Right : Side.Left;
      zone[id] = markSide(id);
    }
    const last = row[row.length - 1];
    const prev = row[row.length - 2];
    if (prev && side[last] === Side.Right && !marked.has(last)) {
      const dist = x[last] - x[prev];
      const T = d.SIB + E;
      if (
        dist >= T &&
        dist <= 2 * T &&
        x[last] - half(last) - off(last) - lw[last] - PAD >= x[prev] + rightExt(prev, Reach.Marks)
      )
        side[last] = Side.Left;
    }
  }
  const shift = (row: string[], from: string, by: number) => {
    for (let j = row.indexOf(from); j < row.length; j++) x[row[j]] += by;
  };
  // spec 8, collision step 1: widen the spacing until nothing in the row touches
  function widen(row: string[]): void {
    for (let i = 1; i < row.length; i++) {
      const a = row[i - 1];
      const b = row[i];
      // a mark between two people stays nearer its own
      const facing = zone[a] === 1 || zone[b] === -1 ? 2 * PAD : 0;
      const need = Math.max(gapFor(a, b), between(a, b) + PAD + facing) - (x[b] - x[a]);
      if (need > 0) shift(row, b, need);
    }
  }
  const rowWith = (id: string) => rows[gen[id]];

  // spec 8.3: children under their parents' bar. Everything only ever moves right, so this settles.
  const units = [
    ...cast.bonds.flatMap((b) => {
      const k = cast.kids.find((k) => k.of.length === 2 && k.of.includes(b.a) && k.of.includes(b.b));
      return k
        ? [{ of: [b.a, b.b], kids: k.kids, alone: bondsOf[b.a].length === 1 && bondsOf[b.b].length === 1 }]
        : [];
    }),
    ...cast.kids
      .filter((k) => k.of.length === 1)
      .map((k) => ({ of: k.of, kids: k.kids, alone: bondsOf[k.of[0]].length === 0 })),
  ];
  function settle(): void {
    for (let it = 0; it < 200; it++) {
      let moved = false;
      for (const u of units) {
        const px = u.of.map((id) => x[id]);
        const kx = u.kids.map((id) => x[id]);
        const b0 = Math.min(...px);
        const b1 = Math.max(...px);
        const k0 = Math.min(...kx);
        const k1 = Math.max(...kx);
        const first = u.kids.find((id) => x[id] === k0)!;
        const last = u.of.find((id) => x[id] === b1)!;
        const lead = u.of.find((id) => x[id] === b0)!;
        const inset = u.of.length === 2 && opts.inset && (u.kids.length > 1 || !u.alone) ? E : 0;
        if (u.alone || u.of.length === 1) {
          const w = u.of.length === 2 ? Math.max(b1 - b0, k1 - k0 + 2 * inset) : 0;
          const to = (k0 + k1) / 2 - w / 2;
          if (to - b0 > 0.5) {
            shift(rowWith(lead), lead, to - b0);
            moved = true;
          } else if (b0 - to > 0.5) {
            shift(rowWith(first), first, b0 - to);
            moved = true;
          } else if (w - (b1 - b0) > 0.5) {
            shift(rowWith(last), last, w - (b1 - b0));
            moved = true;
          }
          continue;
        }
        if (b0 - (k0 - inset) > 0.5) {
          shift(rowWith(first), first, b0 - (k0 - inset));
          moved = true;
        } else if (k1 + inset - b1 > 0.5) {
          shift(rowWith(last), last, k1 + inset - b1);
          moved = true;
        }
      }
      if (!moved) return;
    }
    throw new Unplaceable("children under their parents’ bar: the rows keep pushing each other apart");
  }

  rows.forEach((row) =>
    row.forEach((id, i) => (x[id] = i ? x[row[i - 1]] + gapFor(row[i - 1], id) : 0)),
  );
  settle();
  rows
    .slice()
    .reverse()
    .forEach((row) => {
      labels(row);
      widen(row);
    });
  for (let round = 0; round < 3; round++) {
    settle();
    rows.forEach(widen);
  }
  settle();

  /* a couple's bar drops a step further for each other bar it would lie on top
   * of (spec 5: partners may be offset); names under the shape sit below the
   * person's lowest couple line */
  let level: Record<string, number> = {};
  let below: Record<string, number> = {};
  function levels(): void {
    level = {};
    below = {};
    rows.forEach((_, g) => {
      cast.bonds
        .filter((b) => gen[b.a] === g)
        .map((b) => ({ key: `${b.a}|${b.b}`, x0: Math.min(x[b.a], x[b.b]), x1: Math.max(x[b.a], x[b.b]) }))
        .sort((a, b) => a.x1 - a.x0 - (b.x1 - b.x0))
        .forEach((r, i, all) => {
          let l = 0;
          while (all.slice(0, i).some((o) => level[o.key] === l && o.x0 <= r.x1 && r.x0 <= o.x1)) l++;
          level[r.key] = l;
        });
    });
    ids.forEach((id) => {
      const lv = Math.max(-1, ...bondsOf[id].map((b) => level[`${b.a}|${b.b}`]));
      below[id] = half(id) + Math.max(lv < 0 ? 11 : d.DROP + lv * 6 + 13, ring[id] + ASCENT);
    });
  }
  levels();

  function nameBox(id: string, sd: Side): Box {
    const e = half(id);
    const w = lw[id];
    let base: number;
    let x0: number;
    if (sd === Side.Right) {
      x0 = x[id] + e + off(id);
      base = y[id] - e + 9;
    } else if (sd === Side.Left) {
      x0 = x[id] - e - off(id) - w;
      base = y[id] - e + 9;
    } else if (sd === Side.Above) {
      x0 = x[id] + 5;
      base = y[id] - e - rise(ring[id]) - LEAD * (nl[id] - 1);
    } else if (sd === Side.Top) {
      x0 = x[id] - w / 2;
      base = y[id] - e - rise(ring[id]) - LEAD * (nl[id] - 1);
    } else {
      x0 = x[id] - w / 2;
      base = y[id] + below[id];
    }
    return { x0: x0 - 2, x1: x0 + w + 2, y0: base - 12, y1: base + LEAD * (nl[id] - 1) + 4 };
  }
  // no move crosses a name: each name takes the first side, right, left,
  // above, below, that no move of the case crosses; the rows then widen and settle again
  const where = { P, x, y, d };
  for (let pass = 0; pass < 4; pass++) {
    const segs = [...cast.moves.map((mv) => ends(where, mv)), ...cast.kin.flatMap((k) => across(where, k))];
    let moved = false;
    ids.forEach((id) => {
      if (!segs.some((s) => crosses(s, nameBox(id, side[id])))) return;
      const pick =
        [Side.Right, Side.Left, parents[id] ? Side.Above : Side.Top, Side.Under].find(
          (sd) => !segs.some((s) => crosses(s, nameBox(id, sd))),
        ) ?? Side.Under;
      if (pick === side[id]) return;
      side[id] = pick;
      zone[id] = marked.has(id) ? (pick === Side.Right ? -1 : 1) : 0;
      moved = true;
    });
    if (!moved) break;
    rows.forEach(widen);
    settle();
    levels();
  }

  // how far everything reaches, so the whole case fits one fixed box
  const box: Box = { x0: Infinity, x1: -Infinity, y0: Infinity, y1: -Infinity };
  const core: Box = { x0: Infinity, x1: -Infinity, y0: Infinity, y1: -Infinity };
  const said = { x0: Infinity, x1: -Infinity };
  const grow = (ax: number, ay: number) => {
    box.x0 = Math.min(box.x0, ax);
    box.x1 = Math.max(box.x1, ax);
    box.y0 = Math.min(box.y0, ay);
    box.y1 = Math.max(box.y1, ay);
  };
  const fam = (ax: number, ay: number) => {
    core.y0 = Math.min(core.y0, ay);
    core.y1 = Math.max(core.y1, ay);
    grow(ax, ay);
  };
  ids.forEach((id) => {
    const e = half(id);
    grow(x[id] - leftExt(id), y[id] - e);
    fam(x[id] + rightExt(id), y[id] + e);
    fam(x[id], y[id] - e);
    core.x0 = Math.min(core.x0, x[id] - leftExt(id, Reach.Bare));
    core.x1 = Math.max(core.x1, x[id] + rightExt(id, Reach.Bare));
    said.x0 = Math.min(said.x0, x[id] - leftExt(id, Reach.Words));
    said.x1 = Math.max(said.x1, x[id] + rightExt(id, Reach.Words));
    if (zone[id]) grow(x[id], y[id] - 16);
    // room under the person for a step's word that finds none beside them
    if (words[id]) fam(x[id], y[id] + below[id] + (side[id] === Side.Under ? LEAD * nl[id] : 0) + 4);
    if (side[id] === Side.Above || side[id] === Side.Top) fam(x[id], y[id] - e - rise(ring[id]) - LEAD * (nl[id] - 1) - 14);
    else if (side[id] === Side.Under) fam(x[id], y[id] + below[id] + LEAD * (nl[id] - 1) + 3);
    else {
      fam(x[id], y[id] - e - 5);
      fam(x[id], y[id] - e + LEAD * (nl[id] - 1) + 4);
    }
  });
  const L: Layout = {
    P, x, y, side, zone, bonds: cast.bonds, kids: cast.kids, gen, w: opts.w, level, below,
    names: [], h: 0, vw: VIEW, px: d.W, wide: 0, my: 0, ring, inset,
  };
  cast.bonds.forEach((b) => fam(x[b.a], bar(L, b).y + 4));
  cast.moves.forEach((mv) => awayTip(L, mv).forEach(([ax, ay]) => grow(ax, ay)));

  // ruled 2026-09-26: the people and their names are centred; marks and arrows may reach into the
  // margin, and the words keep out of it as the names do, so no word runs to the phone's edge
  const mid = (core.x0 + core.x1) / 2;
  const reach = 2 * Math.max(mid - box.x0, box.x1 - mid);
  const span = 2 * Math.max(mid - said.x0, said.x1 - mid);
  // ruled 2026-09-27: the family's margin at 393 wide
  let MX = (24 * VIEW) / 393;
  let MY = (20 * VIEW) / 393;
  const wide = Math.max(span + 2 * MX, reach);
  // no room to widen: names may go above
  if (wide > VIEW && !tight && !under) return layout(cast, { ...opts, names: Names.Above });
  L.wide = wide;
  if (wide > VIEW && opts.fit) {
    // scaled down to fit the phone, the margin kept at its size on the screen
    L.vw = Math.max(reach, span / (1 - (2 * MX) / VIEW));
    L.px = (d.W * VIEW) / L.vw;
    MX *= L.vw / VIEW;
    MY *= L.vw / VIEW;
  } else if (wide > VIEW)
    throw new Unplaceable(`the drawing is ${Math.round(wide)} wide, wider than the phone’s ${VIEW}`, true);
  const dx = L.vw / 2 - mid;
  const dy = Math.max(MY - core.y0, 2 - box.y0);
  ids.forEach((id) => {
    x[id] += dx;
    y[id] += dy;
  });
  L.names = ids.map((id) => nameBox(id, side[id]));
  L.h = Math.ceil(Math.max(core.y1 + dy + MY, box.y1 + dy + 2));
  L.my = MY;
  return L;
}

type Point = [number, number];
type Segment = [Point, Point];
interface Where {
  P: Record<string, Shape>;
  x: Record<string, number>;
  y: Record<string, number>;
  d: Dims;
}

const dimsOf = (L: Layout) => new Dims(L.w);

function ray(o: Point, to: Point, dist: number): Point {
  const a = to[0] - o[0];
  const b = to[1] - o[1];
  const c = Math.hypot(a, b);
  const p = c > 0 ? dist / c : 0;
  return [o[0] + p * a, o[1] + p * b];
}
const seg = (p: Point, q: Point) => `M${f(p[0])} ${f(p[1])}L${f(q[0])} ${f(q[1])}`;

/** moves.ts arrow(): toward runs mover to target; away leads out behind the mover. */
function awayTip(L: Layout, mv: Arrow): Point[] {
  if (mv.k !== Mark.Away) return [];
  const d = dimsOf(L);
  const A: Point = [L.x[mv.from], L.y[mv.from]];
  const B: Point = [L.x[mv.to], L.y[mv.to]];
  return [ray(A, B, -(d.half(L.P[mv.from]) + 2 + 44 + 12))];
}

/** Where a move's arrow starts and where its tip lands. */
export function ends(L: Where, mv: Arrow): Segment {
  const A: Point = [L.x[mv.from], L.y[mv.from]];
  const B: Point = [L.x[mv.to], L.y[mv.to]];
  const n = Math.hypot(B[0] - A[0], B[1] - A[1]);
  const u = [(B[0] - A[0]) / n, (B[1] - A[1]) / n];
  const at = (t: number): Point => [A[0] + u[0] * t, A[1] + u[1] * t];
  if (mv.k === Mark.Toward) return [at(L.d.half(L.P[mv.from]) + 3), at(n - L.d.half(L.P[mv.to]) - 4)];
  const s = -(L.d.half(L.P[mv.from]) + 2);
  return [at(s), at(s - 56)];
}

/** Where along a segment, from 0 to 1, it first enters a box; null if it never does. */
/** Where a move drawn the moves board's way runs (moves.ts): the line between
 * the two, as wide as the zigzag or the bands along it, and the wall across it. */
function across(L: Where, k: Kin): Segment[] {
  if (!k.to) return [];
  const A: Point = [L.x[k.from], L.y[k.from]];
  const B: Point = [L.x[k.to], L.y[k.to]];
  const n = Math.hypot(B[0] - A[0], B[1] - A[1]);
  const u = [(B[0] - A[0]) / n, (B[1] - A[1]) / n];
  const at = (t: number, s = 0): Point => [A[0] + u[0] * t - u[1] * s, A[1] + u[1] * t + u[0] * s];
  const a = L.d.half(L.P[k.from]);
  const b = n - L.d.half(L.P[k.to]);
  const out: Segment[] = [-7, 0, 7].map((s) => [at(a, s), at(b, s)]);
  if (k.kind === Move.Distance || k.kind === Move.Cutoff)
    out.push([at(n * WALL, -L.d.MARK / 2), at(n * WALL, L.d.MARK / 2)]);
  return out;
}

function enter(sg: Segment, bx: Box): number | null {
  let t0 = 0;
  let t1 = 1;
  const dx = sg[1][0] - sg[0][0];
  const dy = sg[1][1] - sg[0][1];
  const pq = [
    [-dx, sg[0][0] - bx.x0],
    [dx, bx.x1 - sg[0][0]],
    [-dy, sg[0][1] - bx.y0],
    [dy, bx.y1 - sg[0][1]],
  ];
  for (const [p, q] of pq) {
    if (p === 0) {
      if (q < 0) return null;
      continue;
    }
    const r = q / p;
    if (p < 0) {
      if (r > t1) return null;
      if (r > t0) t0 = r;
    } else {
      if (r < t0) return null;
      if (r < t1) t1 = r;
    }
  }
  return t0;
}
export const crosses = (sg: Segment, bx: Box) => enter(sg, bx) !== null;

/** The moves board's way (Q1b): the flowing dashed arrow from mover to target.
 * The last resort: an arrow whose every name side is taken stops short of the name. */
function boardMove(L: Layout, mv: Arrow): string {
  let [a, tip] = ends({ ...L, d: dimsOf(L) }, mv);
  L.names.forEach((bx) => {
    const t = enter([a, tip], bx);
    if (t !== null && t > 0.2) tip = [a[0] + (tip[0] - a[0]) * t, a[1] + (tip[1] - a[1]) * t];
  });
  const n = Math.hypot(tip[0] - a[0], tip[1] - a[1]);
  const u = [(tip[0] - a[0]) / n, (tip[1] - a[1]) / n];
  const v = [-u[1], u[0]];
  const b: Point = [tip[0] - u[0] * 12, tip[1] - u[1] * 12];
  const cls = `arr${mv.k === Mark.Away ? " back" : ""}${mv.cls === Tone.Was ? " was" : " pop"}`;
  return (
    `<g class="${cls}" data-mark="move:${esc(`${mv.from}>${mv.to}:${mv.k}`)}">` +
    `<line x1="${f(a[0])}" y1="${f(a[1])}" x2="${f(b[0])}" y2="${f(b[1])}"/>` +
    `<polygon points="${f(tip[0])},${f(tip[1])} ${f(b[0] + v[0] * 7)},${f(b[1] + v[1] * 7)} ${f(b[0] - v[0] * 7)},${f(b[1] - v[1] * 7)}"/></g>`
  );
}

/** The app's health cross, unscaled. The app places it 29 past a person of
 * radius r; the ruled gap here is an eighth of the width, so the call passes
 * the radius that lands it there. Nothing inside the mark changes. */
function cross(L: Layout, id: string, dir: Shift, cls: Tone): string {
  const d = dimsOf(L);
  const fig = {
    id: 0,
    name: L.P[id].name,
    x: L.x[id],
    y: L.y[id],
    r: d.half(L.P[id]) + d.GAP + CROSS / 2 - 29,
    mirror: L.zone[id] < 0,
  };
  return (
    `<g class="mk ${cls}${cls === Tone.Now ? " pop" : ""}" data-mark="cross:${esc(id)}">` +
    healthCross(fig, dir) +
    `</g>`
  );
}

export function outline(p: Shape, x: number, y: number, e: number, cls: string): string {
  if (p.g === Sex.Female) return `<circle class="${cls}" cx="${f(x)}" cy="${f(y)}" r="${f(e)}"/>`;
  return (
    `<rect class="${cls}" x="${f(x - e)}" y="${f(y - e)}" width="${f(2 * e)}" height="${f(2 * e)}"` +
    (p.g === Sex.Male ? "" : ` rx="${f(e * 0.45)}"`) +
    `/>`
  );
}

/** A couple's line down from each of the two and across: solid only for a
 * marriage (ruled 2026-09-26). */
export const tie = (x0: number, y0: number, x1: number, y1: number, y: number, married: boolean, cls = "", attrs = "") =>
  `<path class="tie${married ? "" : " dash"}${cls}"${attrs} d="M${f(x0)} ${f(y0)}V${f(y)}H${f(x1)}V${f(y1)}"/>`;

/** One slash for a separation, two for a divorce, upright because custody is
 * not recorded, centred on x across the couple's line at y. */
export const slashes = (n: number, x: number, y: number, W: number, fresh = false): string =>
  slashLines(n, x, y, W, fresh).join("");

/** The same slashes one by one, so a fresh one can be drawn over the rest. */
function slashLines(n: number, x: number, y: number, W: number, fresh = false): string[] {
  return Array.from({ length: n }, (_, i) => {
    const sx = x - (n - 1) * 0.05 * W + i * 0.1 * W;
    const pop = fresh && i === n - 1 ? " now pop" : "";
    return `<line class="slash${pop}" x1="${f(sx)}" y1="${f(y + 0.15 * W)}" x2="${f(sx)}" y2="${f(y - 0.25 * W)}"/>`;
  });
}

/** The death X: corner to corner, or only its corners when an age sits inside. */
export function crossOut(x: number, y: number, e: number, age: boolean, cls: string): string {
  const w = 0.6 * e;
  const corner = (sx: number, sy: number) => seg([x + sx * e, y + sy * e], [x + sx * (e - w), y + sy * (e - w)]);
  return `<path class="${cls}" d="${
    age
      ? corner(-1, -1) + corner(1, -1) + corner(-1, 1) + corner(1, 1)
      : seg([x - e, y - e], [x + e, y + e]) + seg([x + e, y - e], [x - e, y + e])
  }"/>`;
}

/** Anxiety: the moves board's eight flickering spikes around the person.
 * Carried from an earlier snapshot they stand still and grey. */
function spikes(L: Layout, id: string, cls: Tone): string {
  const fig = { id: 0, name: L.P[id].name, x: L.x[id], y: L.y[id], r: dimsOf(L).half(L.P[id]) };
  const marks = anxious(fig, "solo");
  const still = marks.replace(/<animate(Transform)?\b[^>]*\/>/g, "").replace(/ opacity="0"/g, "");
  return `<g class="spikes ${cls}" data-mark="anx:${esc(id)}">${cls === Tone.Was ? still : marks}</g>`;
}

/** Ruled 2026-09-26: an event with no drawing of its own is a short word beside
 * the person, below where a cross sits. */
interface Spot {
  x: number;
  y: number;
  /** Which way the word runs from x: 1 rightward, -1 leftward, 0 centred. */
  sd: number;
  box: Box;
}

function event(m: Placed, w: Spot): string {
  return (
    `<text class="evw${m.cls === Tone.Was ? " was" : " pop"}" data-mark="word:${esc(`${m.who}:${m.word}`)}" ` +
    `x="${f(w.x)}" y="${f(w.y)}" text-anchor="${w.sd > 0 ? "start" : w.sd < 0 ? "end" : "middle"}">${esc(m.word!)}</text>`
  );
}

/** Where a step's word goes: beside its person on their marks' side, else on
 * the other side when their name is not there, else under them, the first that
 * crosses nothing already taken and stays in the picture. A word never moves
 * people apart (Patrick, 2026-10-03), so the last resort is its own side. */
function spot(L: Layout, m: Placed, taken: Box[], drawn: Segment[]): Spot {
  if (!m.word) throw new Error(`an event mark with no word, for ${m.who}`);
  const d = dimsOf(L);
  const id = m.who;
  const e = d.half(L.P[id]);
  const w = m.word.length * NAME * CH;
  const row = (m.row ?? 0) * LEAD;
  const beside = (sd: number, more = 0): Spot => {
    const x = L.x[id] + sd * (e + L.inset[id]);
    const y = L.y[id] + e * 0.55 + 6 + row + more;
    return { x, y, sd, box: { x0: sd > 0 ? x : x - w, x1: sd > 0 ? x + w : x, y0: y - ASCENT, y1: y + 4 } };
  };
  const centred = (y: number): Spot => ({ x: L.x[id], y, sd: 0, box: { x0: L.x[id] - w / 2, x1: L.x[id] + w / 2, y0: y - ASCENT, y1: y + 4 } });
  const under = (more: number) =>
    centred(L.y[id] + L.below[id] + (L.side[id] === Side.Under ? LEAD * lines(L.P[id], Infinity).length : 0) + row + more);
  // over the person, above their name when it is there
  const top = Math.min(L.y[id] - e - L.ring[id], ...L.names.filter((b) => b.x0 <= L.x[id] && L.x[id] <= b.x1 && b.y1 <= L.y[id]).map((b) => b.y0));
  const over = centred(top - 6 - row);
  const own = L.zone[id] || (L.side[id] === Side.Right ? -1 : 1);
  const named = L.side[id] === Side.Right ? 1 : L.side[id] === Side.Left ? -1 : 0;
  const sides = named === -own ? [own] : [own, -own];
  // beside, then a line lower beside, clear of a move along the row, then
  // under, over, and further under
  const tries = [...sides.map((sd) => beside(sd)), ...sides.map((sd) => beside(sd, LEAD)), under(0), over, under(LEAD)];
  const free = (t: Spot) =>
    t.box.x0 >= 0 &&
    t.box.x1 <= L.vw &&
    t.box.y0 >= 0 &&
    t.box.y1 <= L.h &&
    !taken.some((b) => t.box.x0 < b.x1 && b.x0 < t.box.x1 && t.box.y0 < b.y1 && b.y0 < t.box.y1) &&
    !drawn.some((sg) => crosses(sg, { x0: t.box.x0 - 2, x1: t.box.x1 + 2, y0: t.box.y0 - 2, y1: t.box.y1 + 2 }));
  return tries.find(free) ?? tries[0];
}

/** What a step's words must keep clear of: every name, every shape with the
 * spikes around it, every health cross, and every move drawn, the step's own and
 * those carried from before. */
function ground(L: Layout, s: Frame): { boxes: Box[]; lines: Segment[] } {
  const d = dimsOf(L);
  const shapes = Object.keys(L.P).map((id) => {
    const e = d.half(L.P[id]) + L.ring[id] + 2;
    return { x0: L.x[id] - e, x1: L.x[id] + e, y0: L.y[id] - e, y1: L.y[id] + e };
  });
  const crosses = s.marks
    .filter((m) => m.k === Mark.Up || m.k === Mark.Down)
    .map((m) => {
      const z = L.zone[m.who] || 1;
      const e = d.half(L.P[m.who]);
      const [a, b] = [L.x[m.who] + z * (e + d.GAP), L.x[m.who] + z * (e + d.ZONE)];
      return { x0: Math.min(a, b), x1: Math.max(a, b), y0: L.y[m.who] - 15, y1: L.y[m.who] + 4 };
    });
  const where = { P: L.P, x: L.x, y: L.y, d };
  const lines = [...s.moves.map((mv) => ends(where, mv)), ...s.kin.flatMap((k) => across(where, k))];
  return { boxes: [...L.names, ...shapes, ...crosses], lines };
}

const STILL = { symptom: null, anxiety: null, functioning: null };

/** A move from the moves board's own language, imported rather than copied.
 * Carried from an earlier snapshot it turns grey and stops moving. */
function kin(L: Layout, m: Kin): string {
  const d = dimsOf(L);
  // a field reaches as far as the nearest edge of the picture from either
  // person and no further: the moves board scales it by the stage's height
  const room = Math.min(
    ...[m.from, m.to].flatMap((id) => (id ? [L.x[id], L.vw - L.x[id], L.y[id], L.h - L.y[id]] : [])),
  );
  const stage = { w: DEMO.w, h: (Math.min(room, FIELD) * DEMO.h) / FIELD };
  const at = (id: string) => ({
    id: 0,
    name: L.P[id].name,
    x: L.x[id],
    y: L.y[id],
    r: d.half(L.P[id]),
    mirror: L.zone[id] < 0,
    gender: L.P[id].g === Sex.Female ? "female" : null,
    stage,
    mark: d.MARK,
    still: true,
  });
  const marks = moveMarks(m.kind, at(m.from), m.to ? at(m.to) : null, STILL).marks;
  const was = m.cls === Tone.Was;
  return (
    `<g class="mvk ${m.cls ?? Tone.Now}" data-mark="move:${esc(`${m.from}>${m.to ?? ""}:${m.kind}`)}">` +
    (was ? marks.replace(/<animate(Transform)?\b[^>]*\/>/g, "") : marks) +
    `</g>`
  );
}

interface Bar {
  a: string;
  b: string;
  x0: number;
  x1: number;
  y: number;
}

export function bar(L: Layout, b: { a: string; b: string }): Bar {
  const d = dimsOf(L);
  let A = b.a;
  let B = b.b;
  if (L.x[A] > L.x[B]) [A, B] = [B, A];
  const yb =
    Math.max(L.y[A] + d.half(L.P[A]), L.y[B] + d.half(L.P[B])) +
    d.DROP +
    (L.level[`${b.a}|${b.b}`] ?? 0) * 6;
  return { a: A, b: B, x0: L.x[A], x1: L.x[B], y: yb };
}

function childLines(L: Layout, k: { x0: number; x1: number; y: number }, kids: string[]): string {
  const d = dimsOf(L);
  return kids
    .map((id) => {
      const top: Point = [L.x[id], L.y[id] - d.half(L.P[id])];
      const end: Point =
        top[0] >= k.x0 && top[0] <= k.x1 ? [top[0], k.y] : [top[0] < k.x0 ? k.x0 : k.x1, k.y];
      return `<path class="kin" d="${seg(top, end)}"/>`;
    })
    .join("");
}

/** One snapshot on the case's fixed layout. */
export function draw(L: Layout, s: Frame): string {
  const d = dimsOf(L);
  const { E } = d;
  const P = L.P;
  const { boxes: taken, lines: drawn } = ground(L, s);
  const spots = new Map<Placed, Spot>();
  s.marks
    .filter((m) => m.k === Mark.Event)
    .forEach((m) => {
      const w = spot(L, m, taken, drawn);
      spots.set(m, w);
      taken.push(w.box);
    });
  const texts = [...L.names, ...[...spots.values()].map((w) => w.box)];
  let out = "";
  // what this snapshot adds is drawn over everything carried from before, and
  // every name, age and word over all of it, haloed so a ring cannot hide it
  let top = "";
  let said = "";
  const put = (markup: string, now: boolean) => (now ? (top += markup) : (out += markup));
  const lit = (cls?: Tone) => (cls ?? Tone.Now) === Tone.Now;
  s.bonds.forEach((b) => {
    const kids = L.kids.find((c) => c.of.includes(b.a) && c.of.includes(b.b));
    if (kids) out += childLines(L, bar(L, b), kids.kids);
  });
  L.kids
    .filter((c) => c.of.length === 1)
    .forEach((c) => {
      const p = c.of[0];
      const xs = [...c.kids.map((id) => L.x[id]), L.x[p]];
      const k = { x0: Math.min(...xs), x1: Math.max(...xs), y: L.y[p] + d.half(P[p]) + d.DROP };
      out +=
        `<path class="tie" d="M${f(L.x[p])} ${f(L.y[p] + d.half(P[p]))}V${f(k.y)}M${f(k.x0)} ${f(k.y)}H${f(k.x1)}"/>` +
        childLines(L, k, c.kids);
    });
  s.bonds.forEach((b) => {
    const k = bar(L, b);
    // ruled 2026-09-26: only a marriage makes the line solid, and only a marriage can be divorced
    if (b.st === Tie.Divorced && !b.married)
      throw new Error(`a divorce for a couple that never married: ${b.a} and ${b.b}`);
    put(tie(
      k.x0,
      L.y[k.a] + d.half(P[k.a]),
      k.x1,
      L.y[k.b] + d.half(P[k.b]),
      k.y,
      b.married,
      b.hot ? " now pop" : "",
      ` data-bond="${esc(`${b.a}|${b.b}`)}"`,
    ), b.hot);
    const n = b.st === Tie.Separated ? 1 : b.st === Tie.Divorced ? 2 : 0;
    if (!n) return;
    // the slashes sit in an open stretch of the line, never on a child's line,
    // nearest the middle of the widest one where they cross no name or word
    const kids = L.kids.find((c) => c.of.includes(b.a) && c.of.includes(b.b));
    const stops = [k.x0, ...(kids?.kids ?? []).map((id) => L.x[id]).filter((x) => x > k.x0 && x < k.x1), k.x1].sort((p, q) => p - q);
    const open = stops.slice(1).map((x, i) => [stops[i], x]).sort((p, q) => q[1] - q[0] - (p[1] - p[0]));
    // a slash is 0.4 of the width it is given
    const len = d.MARK / 0.4;
    const hw = (n - 1) * 0.05 * len + 3;
    const clear = (cx: number) =>
      !texts.some((t) => t.x0 < cx + hw && cx - hw < t.x1 && t.y0 < k.y + 0.15 * len && k.y - 0.25 * len < t.y1);
    const at = open
      .flatMap(([p, q]) => {
        const room = Math.max(0, Math.floor(((q - p) / 2 - hw) / 2));
        return Array.from({ length: room + 1 }, (_, i) => [(p + q) / 2 - 2 * i, (p + q) / 2 + 2 * i]).flat();
      })
      .find(clear);
    slashLines(n, at ?? (open[0][0] + open[0][1]) / 2, k.y, len, b.fresh).forEach((l, i) =>
      put(l, b.fresh && i === n - 1),
    );
  });

  Object.keys(P).forEach((id) => {
    const p = P[id];
    const x = L.x[id];
    const y = L.y[id];
    const e = d.half(p);
    const dead = p.died != null && p.died <= s.t + 1e-6;
    // someone not yet born keeps their place (R-0546) but has no age to show
    const age = p.born == null || p.born > s.t + 1e-6 ? null : yr((dead ? p.died! : s.t) - p.born + 1e-6);
    let g = `<g class="p" data-id="${esc(id)}">`;
    let t = `<g class="pt" data-id="${esc(id)}">`;
    if (p.you) g += outline(p, x, y, e, "you");
    g += outline(p, x, y, E, "shape");
    if (age != null) t += `<text class="age" x="${f(x)}" y="${f(y + 4.5)}">${age}</text>`;
    else if (p.g === Sex.Unknown) t += `<text class="age" x="${f(x)}" y="${f(y + 4.5)}">?</text>`;
    if (dead) {
      // a death X is in the emphasis colour on its date, plain ink after
      if (s.died.has(id)) top += crossOut(x, y, e, age != null, "xd now pop");
      else g += crossOut(x, y, e, age != null, "xd");
    }
    const l = lines(p, s.t);
    const sd = L.side[id];
    let lx: number;
    let anchor = "start";
    let y0: number;
    if (sd === Side.Above) {
      lx = x + 5;
      y0 = y - e - rise(L.ring[id]) - LEAD * (l.length - 1);
    } else if (sd === Side.Top) {
      lx = x;
      anchor = "middle";
      y0 = y - e - rise(L.ring[id]) - LEAD * (l.length - 1);
    } else if (sd === Side.Under) {
      lx = x;
      anchor = "middle";
      y0 = y + L.below[id];
    } else {
      lx = sd === Side.Right ? x + e + offset(d, L.ring[id]) : x - e - offset(d, L.ring[id]);
      anchor = sd === Side.Right ? "start" : "end";
      y0 = y - e + 9;
    }
    l.forEach((line, i) => {
      if (line)
        t += `<text class="${i ? "lbd" : "lbn"}" x="${f(lx)}" y="${f(y0 + i * LEAD)}" text-anchor="${anchor}">${esc(line)}</text>`;
    });
    out += g + "</g>";
    said += t + "</g>";
  });

  s.marks.forEach((m) => {
    if (m.k === Mark.Up || m.k === Mark.Down)
      put(cross(L, m.who, m.k === Mark.Up ? Shift.Up : Shift.Down, m.cls ?? Tone.Now), lit(m.cls));
    else if (m.k === Mark.Event) said += event(m, spots.get(m)!);
    else if (m.k === Mark.Emphasis)
      put(outline(P[m.who], L.x[m.who], L.y[m.who], E, m.cls === Tone.Was ? "hl was" : "hl now pop").replace(
        "/>",
        ` data-mark="hl:${esc(m.who)}"/>`,
      ), lit(m.cls));
    // functioning: down breaks the outline into pieces, up is one continuous green line
    else if (m.k === Mark.FnUp || m.k === Mark.FnDown)
      put(outline(P[m.who], L.x[m.who], L.y[m.who], E, `fn ${m.k === Mark.FnUp ? "up" : "down"} ${lit(m.cls) ? "now pop" : m.cls}`).replace(
        "/>",
        ` data-mark="${m.k}:${esc(m.who)}"/>`,
      ), lit(m.cls));
    else if (m.k === Mark.Anxiety) put(spikes(L, m.who, m.cls ?? Tone.Now), lit(m.cls));
  });
  s.kin.forEach((m) => put(kin(L, m), lit(m.cls)));
  s.moves.forEach((mv) => put(boardMove(L, mv), lit(mv.cls)));
  return `<svg class="ss" viewBox="0 0 ${f(L.vw)} ${L.h}" role="img" aria-label="${esc(s.label)}">${out}<g class="fore">${top}</g><g class="said">${said}</g></svg>`;
}
