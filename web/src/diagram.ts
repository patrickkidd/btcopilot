import { esc } from "./dom";
import { CROSS, cross as healthCross, draw as moveMarks, FIELD, FLANK, Move, Shift, SPIKES, spikes as anxious, WALL } from "./moves";

/** A small family diagram generated from a cast, to FAMILY_DIAGRAM_VISUAL_SPEC.md,
 * ported from the approved play-by-play reference (design/playbyplay-snapshots,
 * diagram.js). `layout` runs once per case; `draw` runs per snapshot on the same
 * positions, so between snapshots only marks, ages, bond status and the death X
 * change. */

export enum Sex {
  Male = "m",
  Female = "f",
  Unknown = "?",
  Miscarriage = "x",
  Abortion = "a",
}

const SEXES: Record<string, Sex> = {
  female: Sex.Female,
  male: Sex.Male,
  miscarriage: Sex.Miscarriage,
  abortion: Sex.Abortion,
};

export const sexOf = (gender: string | null): Sex => SEXES[gender ?? ""] ?? Sex.Unknown;

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
  /** The year of the couple's first dated event: before it their line is faded (R-0756). */
  from?: number;
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
  /** Anxiety going down: the spikes hold, then shorten back to the rim (R-0729). */
  AnxietyDown = "anxd",
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
  /** Inside or outside: the three people move to new places for the step (R-0728). */
  Place = "place",
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

/** Whose field a move rings: the one it reaches, and the one who holds their ground too. */
const fielded = (m: Kin): string[] =>
  !m.to ? [] : m.kind === Move.Distance || m.kind === Move.Cutoff ? [m.to] : m.kind === Move.DefinedSelf ? [m.to, m.from] : [];

export interface Placed {
  k: Mark;
  who: string;
  word?: string;
  cls?: Tone;
  row?: number;
}

/** Inside or outside: who moved, the one they were with, and the third. On
 * inside the mover comes in beside the one they were with and the third is
 * pushed out; on outside the mover walks out and the other two draw together
 * (R-0728). */
export interface Place extends Placed {
  k: Mark.Place;
  kind: Move.Inside | Move.Outside;
  to: string;
  third: string | null;
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
  /** A step's words find room under or over their person and never widen the
   * frame: the Family view's one frame over every date (R-0784). */
  wordsUnder?: boolean;
  /** The names the words around the picture may say beside it, so each
   * name drawn has room for the initial a namesake there gives it (R-0548). */
  others?: string[];
  moves: Arrow[];
  /** The steps' insides and outsides, each moving people from their places. */
  places: Place[];
  /** The moves drawn the moves board's way, and who shows anxiety, so names and
   * words stand clear of their marks. */
  kin: Kin[];
  anxious: string[];
  /** A person with no family tie stands on the row of the one they move with. */
  assoc: Record<string, string>;
  until: number;
  /** Parent links left out to break a parentage cycle; set by arrange. */
  cut?: Cut[];
}

/** A parent link that closes a parentage cycle: left out of the layout and
 * drawn in the error colour with a note (R-0751). */
export interface Cut {
  kid: string;
  parent: string;
  /** How many generations up the loop the kid meets themselves: 2 is their own grandparent. */
  up: number;
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
 * above centred, under, or under beside the line down to the children. */
export enum Side {
  Right = "r",
  Left = "l",
  Above = "a",
  Top = "t",
  Under = "u",
  Below = "b",
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
  /** Laid out by the fallback, generation by generation (ruled 2026-10-04). */
  loose: boolean;
  cut: Cut[];
  /** The note under the family naming each cut link, and its first line's baseline. */
  note: { y: number; lines: string[] } | null;
}

export interface DrawnBond {
  a: string;
  b: string;
  st: Tie;
  /** How many of the couple's slashes are this step's own. */
  fresh: number;
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
  /** The places this step moves people to, for its own step only (R-0728);
   * the next step has them home at once (R-0764). */
  place?: Place | null;
  /** What the people drawn are called on this step, when the words around
   * the picture name a namesake of theirs (R-0548). */
  names?: Record<string, string>;
}

/** The drawing is laid out in a box this wide; the page scales it to the phone. */
export const VIEW = 360;
/** Clearance kept between any two things in a row. */
const PAD = 10;
/** Ruled 2026-09-26: labels at least 13px. */
export const NAME = 13;
/** The one size people are drawn at in every view; a view scales the whole
 * drawing, never the people against their names and marks (R-0759). */
export const W = 44;
/** How far a couple's line drops below the lower of the two, in widths. */
export const DROP = 1 / 2.2;
/** How far the index person's outline reaches past their shape, in widths. */
export const RIM = 0.1;
/** Where an age sits below the centre of its shape. */
const AGE_DROP = 4.5;
/** Decided 2026-09-27: labels never under 13px, the family's margin never under 20px.
 * A picture scales whole (R-0759), so the labels' floor is the people's too. */
export const LEAST = { label: 13, margin: 20 };
/** The least a drawn family may be scaled by, in any frame: labels at 13px and
 * the family's margin, with the frame's own `padding`, at 20px. Below it the
 * frame scrolls (R-0759, R-0744). */
export const leastScale = (L: Layout, padding: number) =>
  Math.max(LEAST.label / NAME, (LEAST.margin - padding) / L.my);
/** The least a name is drawn at when a picture is scaled to fit its space;
 * under it the picture pans (R-0796). */
export const FIT = 6.5;
/** The scale a drawing takes as a whole in a space `w` wide and `h` tall, in
 * the Family view and the play-by-play alike: the smaller of the width's and
 * the height's, never past its own size, never with names under FIT px (R-0796). */
export const fitScale = (L: Layout, w: number, h: number) => Math.max(FIT / NAME, Math.min(1, w / L.vw, h / L.h));
export const CH = 0.6;
const LEAD = 15;
/** How far a label's box reaches above its line. */
const ASCENT = 18;

/** How far a name stands from its shape, clear of what the person's own marks reach. */
const offset = (d: Dims, ring: number) => Math.max(d.OFF, ring + 2);
/** How far above its shape a name above it ends, clear of the same. */
const rise = (ring: number) => Math.max(4, ring + 4);
/** People are always laid out this wide against their names and marks; a
 * family too wide for the phone is scaled whole, then scrolls (R-0759, R-0744). */
const STEPS = [W];

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
  CK: number;
  ZONE: number;

  constructor(w: number, compact = false) {
    this.W = w;
    this.E = w / 2;
    // the index outline: the Pro app adds a tenth of the width on each side
    this.RIM = w * RIM;
    this.DROP = w * DROP;
    this.SIB = (compact ? 2 : 3) * w;
    this.LOOSE = (compact ? 2 : 2.5) * w;
    this.COUPLE = this.SIB;
    this.OFF = 0.2 * w;
    // ruled 2026-09-26: a mark sits within an eighth of a width of its person
    this.GAP = w / 8;
    // a mark that stands on its own, a wall, is as tall as a person; a slash is two thirds of that
    this.MARK = w;
    // the health cross keeps the size against its person it had where people
    // were drawn 36 across, as every mark scales with the person (R-0759)
    this.CK = w / 36;
    // how far the cross and its arrow reach past the shape: two square cells
    this.ZONE = this.GAP + 2 * CROSS * this.CK;
  }

  half(p: Shape): number {
    return p.you ? this.E + this.RIM : this.E;
  }
}

export class Unplaceable extends Error {
  constructor(
    rule: string,
    readonly wide = false,
  ) {
    super(`cannot place: ${rule}`);
  }
}

/** What each of `names` is called in a picture and in the words around it:
 * ruled 2026-09-26, first names; a surname initial only for two people who
 * share a first name in one picture or one line of words, among `names` or
 * the `others` drawn beside that line, as a father and his grandfather both
 * called Robert (R-0548, as widened in the FD-371 review, 2026-10-05); never
 * for a namesake the record holds elsewhere. A stand-in is named by the
 * nearest named person and the relation, in the record's own words: "Jim
 * O'Malley's partner" is "Jim's partner", "Catherine's mother's partner" stays
 * whole (R-0766). */
export function called(names: Record<string, string>, others: string[] = []): Record<string, string> {
  const standIn = (n: string) => /'s /.test(n);
  const first = (n: string) => {
    const [whose, ...rest] = n.split(/'s /);
    return standIn(n) ? `${whose.split(" ")[0]}'s ${rest.join("'s ")}` : n.split(" ")[0];
  };
  const pool = [...Object.values(names), ...others].map(first);
  return Object.fromEntries(
    Object.entries(names).map(([id, n]) => {
      const parts = n.split(" ");
      const twin = parts.length > 1 && !standIn(n) && pool.filter((o) => o === first(n)).length > 1;
      return [id, twin ? `${first(n)} ${parts[parts.length - 1].charAt(0)}.` : first(n)];
    }),
  );
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
  w: W,
  inset: "auto",
  names: Names.Widen,
  steps: true,
  fit: true,
  compact: false,
};

/** Each person's parents and couples, read once from the cast. */
interface Ties {
  parents: Record<string, string[]>;
  kidsOf: Record<string, string[]>;
  bondsOf: Record<string, Bond[]>;
  other: (b: Bond, id: string) => string;
  tied: (id: string) => boolean;
}

function ties(cast: Cast): Ties {
  const parents: Record<string, string[]> = {};
  const kidsOf: Record<string, string[]> = {};
  const bondsOf: Record<string, Bond[]> = {};
  Object.keys(cast.people).forEach((id) => (bondsOf[id] = []));
  cast.bonds.forEach((b) => {
    bondsOf[b.a].push(b);
    bondsOf[b.b].push(b);
  });
  cast.kids.forEach((k) => {
    k.kids.forEach((id) => (parents[id] = k.of));
    k.of.forEach((p) => (kidsOf[p] ??= []).push(...k.kids));
  });
  return {
    parents,
    kidsOf,
    bondsOf,
    other: (b, id) => (b.a === id ? b.b : b.a),
    tied: (id) => bondsOf[id].length > 0 || !!parents[id] || !!kidsOf[id],
  };
}

/** The generation of each person and the order of each row, top to bottom. */
interface Plan {
  gen: Record<string, number>;
  rows: string[][];
  /** Families with no tie between them, each drawn to the right of the one before. */
  comps: string[][];
  /** Laid out by the fallback: rows may cross and settling may give up. */
  loose: boolean;
}

/** The layout the approved page uses: names beside or above, and under the
 * shapes only when nothing else fits; scaled down as the last resort. A family
 * the row rules cannot place is laid out generation by generation instead
 * (Patrick, 2026-10-04). Someone recorded as their own forebear is drawn
 * too, the link that closes the loop left out and shown as an error. */
export function arrange(given: Cast): Layout {
  const cast = uncycle(given);
  try {
    return strict(cast);
  } catch (e) {
    if (!(e instanceof Unplaceable)) throw e;
    return fallback(cast);
  }
}

function strict(cast: Cast): Layout {
  const L = layout(cast);
  if (L.vw <= VIEW) return L;
  try {
    return layout(cast, { names: Names.Under, compact: true, fit: false });
  } catch (e) {
    if (!(e instanceof Unplaceable)) throw e;
    return L;
  }
}

/** The cast with each parentage cycle broken at its closing link (R-0751). */
function uncycle(cast: Cast): Cast {
  const cut: Cut[] = [];
  let kids = cast.kids;
  for (let c = loop(kids, cast); c; c = loop(kids, cast)) {
    const { kid, parent } = c;
    cut.push(c);
    kids = kids
      .map((k) => (k.of.includes(parent) ? { ...k, kids: k.kids.filter((id) => id !== kid) } : k))
      .filter((k) => k.kids.length);
  }
  return cut.length ? { ...cast, kids, cut } : cast;
}

/** The first link the walk finds back to someone already on its path: the
 * kid is that person, the parent the one found last. */
function loop(kids: Brood[], cast: Cast): Cut | null {
  const { kidsOf } = ties({ ...cast, kids });
  const done = new Set<string>();
  const path: string[] = [];
  const walk = (id: string): Cut | null => {
    path.push(id);
    for (const k of kidsOf[id] ?? []) {
      if (path.includes(k)) return { kid: k, parent: id, up: path.length - path.indexOf(k) };
      const c = done.has(k) ? null : walk(k);
      if (c) return c;
    }
    path.pop();
    done.add(id);
    return null;
  };
  for (const id of Object.keys(cast.people)) {
    const c = done.has(id) ? null : walk(id);
    if (c) return c;
  }
  return null;
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
  const t = ties(cast);
  const { gen, anchor } = gens(cast, t);
  return place(cast, opts, t, { gen, rows: order(cast, t, gen, anchor), comps: [Object.keys(cast.people)], loose: false });
}

/** Ruled 2026-10-04: generation by generation on a larger picture that scrolls;
 * lines may cross where they must, and nobody is drawn twice. */
function fallback(cast: Cast): Layout {
  const t = ties(cast);
  const { gen, comps } = looseGens(cast, t);
  const rows = looseOrder(cast, t, gen, comps);
  return place(cast, { ...DEFAULTS, inset: true, steps: false }, t, { gen, rows, comps, loose: true });
}

function gens(cast: Cast, t: Ties): { gen: Record<string, number>; anchor: Record<string, string> } {
  const P = cast.people;
  const ids = Object.keys(P);
  const { tied } = t;
  const gen: Record<string, number> = {};
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
  const anchor: Record<string, string> = {};
  ids.forEach((id) => {
    // the reader stands on row 0 even with no family drawn beside them
    if (tied(id) || gen[id] != null) return;
    anchor[id] = cast.assoc[id] != null && gen[cast.assoc[id]] != null ? cast.assoc[id] : cast.index;
    gen[id] = gen[anchor[id]];
  });
  let lo = Infinity;
  ids.forEach((id) => {
    if (gen[id] == null) throw new Unplaceable(`a person not connected to the rest of the family (${P[id].name})`);
    lo = Math.min(lo, gen[id]);
  });
  cast.bonds.forEach((b) => {
    if (gen[b.a] !== gen[b.b]) throw new Unplaceable("a couple across generations");
  });
  ids.forEach((id) => (gen[id] -= lo));
  return { gen, anchor };
}

// men on the left, so a woman's partners go to her left
const manSide = (p: Shape) => (p.g === Sex.Female ? -1 : 1);

function order(cast: Cast, t: Ties, gen: Record<string, number>, loose: Record<string, string>): string[][] {
  const P = cast.people;
  const ids = Object.keys(P);
  const { parents, bondsOf, other, tied } = t;
  const rows: string[][] = [];
  const top = Math.max(...ids.map((id) => gen[id]));
  // ---- the order of each row, top to bottom ----
  const placed = new Set<string>();
  const at: Record<string, number> = {};
  
  // Kerr fig. 14: a couple where both partners' parents are in the record joins
  // the two families, the man's on the left, each spouse at the inner end of their sibship
  const join = cast.bonds.filter((b) => parents[b.a] && parents[b.b]);
  if (join.length > 1) throw new Unplaceable("two couples each joining two families");
  const inner: Record<string, number> = {};
  const wed = join[0];
  if (wed) {
    const left = P[wed.b].g === Sex.Male && P[wed.a].g !== Sex.Male ? wed.b : wed.a;
    inner[left] = 1;
    inner[other(wed, left)] = -1;
  }
  const isJoin = (p: string, q: string) => !!wed && inner[p] != null && inner[q] != null && p !== q;
  // each joining spouse's forebears in the record, and the side of each sibship they stand at
  const anc: Record<string, Set<string>> = {};
  const edge: Record<string, number> = {};
  Object.keys(inner).forEach((sp) => {
    anc[sp] = new Set();
    const up = (id: string) =>
      (parents[id] || []).forEach((q) => {
        if (anc[sp].has(q)) return;
        anc[sp].add(q);
        edge[q] = inner[sp];
        up(q);
      });
    up(sp);
  });
  const ofSpouse = (id: string) => Object.keys(anc).find((sp) => anc[sp].has(id));
  // spec 5: siblings oldest-left; with no dates, the record's order
  const sibOrder = (kids: string[]) => {
    const o = kids.every((id) => P[id].born != null)
      ? kids.slice().sort((a, b) => P[a].born! - P[b].born!)
      : kids.slice();
    const j = o.find((id) => inner[id] != null || edge[id] != null);
    if (j == null) return o;
    const rest = o.filter((id) => id !== j);
    return (inner[j] ?? edge[j]) === 1 ? [...rest, j] : [j, ...rest];
  };
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
    const partners = bondsOf[anchor]
      .map((b) => other(b, anchor))
      .filter((q) => !placed.has(q) && gen[q] === gen[anchor])
      .filter((q) => !isJoin(anchor, q));
    // two partners stand one each side; three or more stand in order on one
    // side, each couple's line under the ones before it (R-0783)
    partners.forEach((q, i) => {
      if (parents[q] && parents[anchor])
        throw new Unplaceable("a couple where both partners’ parents are in the record");
      put(q, split && partners.length === 2 && i === 1 ? -dir : dir);
    });
    while (queue.length) {
      const [p, s] = queue.shift()!;
      bondsOf[p].forEach((b) => {
        const q = other(b, p);
        if (placed.has(q) || gen[q] !== gen[p] || isJoin(p, q)) return;
        if (parents[q] && parents[p])
          throw new Unplaceable("a couple where both partners’ parents are in the record");
        put(q, s);
      });
    }
    seq.push(...sides[-1].reverse(), anchor, ...sides[1]);
  }
  for (let g = 0; g <= top; g++) {
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
          inner[s] != null
            ? lay(s, -inner[s], seq, false)
            : edge[s] != null
              ? lay(s, edge[s], seq, false)
              : lay(s, n > 1 && i === 0 ? -1 : n > 1 && i === n - 1 ? 1 : manSide(P[s]), seq, n === 1),
        );
      });
    const roots = ids.filter((id) => gen[id] === g && !placed.has(id) && tied(id));
    if (roots.length) {
      const pick = (rs: string[]) =>
        rs
          .slice()
          .sort(
            (a, b) =>
              bondsOf[b].length - bondsOf[a].length ||
              cast.bonds.indexOf(bondsOf[a][0]) - cast.bonds.indexOf(bondsOf[b][0]),
          )[0];
      const comps: { a: string; out: string[] }[] = [];
      for (let rest = roots; rest.length; rest = roots.filter((id) => !placed.has(id))) {
        const a = pick(rest);
        placed.add(a);
        const out: string[] = [];
        lay(a, comps.length || P[a].g !== Sex.Female ? 1 : -1, out, true);
        comps.push({ a, out });
      }
      if (comps.length === 1 && !seq.length) seq.push(...comps[0].out);
      else {
        const spOf = (out: string[]) => out.map(ofSpouse).find((s) => s);
        // each side laid so the joining spouse's forebears stand at its inner end
        const side = (a: string, sp: string, comp: string[]): string[] => {
          const tryDir = (dir: number) => {
            const out: string[] = [];
            comp.forEach((id) => placed.delete(id));
            placed.add(a);
            lay(a, dir, out, true);
            return out;
          };
          const ok = (out: string[]) => {
            const idx = out.map((id, i) => (anc[sp].has(id) ? i : -1)).filter((i) => i >= 0);
            const n = idx.length;
            return idx.every((i) => (inner[sp] === 1 ? i >= out.length - n : i < n));
          };
          const r = tryDir(1);
          return ok(r) ? r : tryDir(-1);
        };
        const parts = [
          ...(seq.length ? [{ sp: spOf(seq), out: seq.slice() }] : []),
          ...comps.map((c) => {
            const sp = spOf(c.out);
            return { sp, out: sp ? side(c.a, sp, c.out) : c.out };
          }),
        ];
        if (parts.length !== 2 || !parts[0].sp || !parts[1].sp || parts[0].sp === parts[1].sp)
          throw new Unplaceable(
            seq.length
              ? "a couple in a row beside another family, with nothing to say which side it goes on"
              : "two separate families side by side in one row",
          );
        parts.sort((p, q) => inner[q.sp!] - inner[p.sp!]);
        seq.splice(0, seq.length, ...parts[0].out, ...parts[1].out);
      }
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
    if (wed && gen[wed.a] === g && Math.abs(at[wed.a] - at[wed.b]) !== 1)
      throw new Unplaceable("a couple where both partners’ parents are in the record, with another family between them");
    rows.push(seq);
  }
  ids.forEach((id) => {
    if (!placed.has(id)) throw new Unplaceable(`a person the row rules do not reach (${P[id].name})`);
  });
  return rows;
}

/** Generations by the longest line of descent: a child a row below the lower
 * of its parents; partners on one row, so a partner whose own family reaches
 * back fewer generations stands on their partner's row with that family laid
 * out up from there; someone with no family tie on the row of the one they
 * move with. A family with no tie to the reader's is its own group, each
 * group's top row the picture's. */
function looseGens(cast: Cast, t: Ties): { gen: Record<string, number>; comps: string[][] } {
  const ids = Object.keys(cast.people);
  const { parents, kidsOf, other, tied } = t;
  const gen: Record<string, number> = {};
  ids.forEach((id) => (gen[id] = 0));
  const topo: string[] = [];
  const seen = new Set<string>();
  const visit = (id: string): void => {
    if (seen.has(id)) return;
    seen.add(id);
    (parents[id] ?? []).forEach(visit);
    topo.push(id);
  };
  ids.forEach(visit);
  const down = () =>
    topo.forEach((id) => {
      if (parents[id]) gen[id] = Math.max(gen[id], ...parents[id].map((p) => gen[p] + 1));
    });
  const below = (p: string, q: string): boolean => (kidsOf[p] ?? []).some((k) => k === q || below(k, q));
  const forebears = (id: string, out = new Set<string>()): Set<string> => {
    (parents[id] ?? []).forEach((q) => out.has(q) || forebears(q, out.add(q)));
    return out;
  };
  down();
  for (let pass = 0; pass < ids.length; pass++) {
    let moved = false;
    cast.bonds.forEach((b) =>
      [b.a, b.b].forEach((p) => {
        const q = other(b, p);
        if (gen[q] <= gen[p] || below(p, q)) return;
        // one who married in comes down to their partner's row, their forebears
        // with them, unless the two share a forebear and the line decides
        const up = forebears(p);
        const theirs = forebears(q);
        if (up.has(q) || [...up].some((a) => theirs.has(a))) return;
        const by = gen[q] - gen[p];
        [p, ...up].forEach((a) => (gen[a] += by));
        moved = true;
      }),
    );
    if (!moved) break;
    down();
  }
  const near = (id: string) => (cast.assoc[id] != null && tied(cast.assoc[id]) ? cast.assoc[id] : cast.index);
  ids.forEach((id) => {
    if (!tied(id)) gen[id] = gen[near(id)];
  });
  const root: Record<string, string> = {};
  const find = (id: string): string => (root[id] === id ? id : (root[id] = find(root[id])));
  ids.forEach((id) => (root[id] = id));
  const join = (a: string, b: string) => (root[find(a)] = find(b));
  cast.bonds.forEach((b) => join(b.a, b.b));
  cast.kids.forEach((k) => [...k.of, ...k.kids].forEach((id) => join(id, k.kids[0] ?? k.of[0])));
  ids.forEach((id) => tied(id) || join(id, near(id)));
  const groups = new Map<string, string[]>();
  [find(cast.index), ...ids.map(find)].forEach((r) => groups.has(r) || groups.set(r, []));
  ids.forEach((id) => groups.get(find(id))!.push(id));
  const comps = [...groups.values()];
  comps.forEach((c) => {
    const lo = Math.min(...c.map((id) => gen[id]));
    c.forEach((id) => (gen[id] -= lo));
  });
  // a group with no tie to the reader's, such as two friends who are a couple,
  // stands on the row of whoever in the family one of them is involved with,
  // never on the grandparents' row by default
  const home = comps.find((c) => c.includes(cast.index))!;
  comps.forEach((c) => {
    if (c === home) return;
    const m = c.find((id) => cast.assoc[id] != null && home.includes(cast.assoc[id]));
    if (m == null) return;
    const by = gen[cast.assoc[m]] - gen[m];
    c.forEach((id) => (gen[id] += by));
  });
  const lo = Math.min(...ids.map((id) => gen[id]));
  ids.forEach((id) => (gen[id] -= lo));
  return { gen, comps };
}

/** Siblings oldest-left; with no dates, the record's order (spec 5). */
const byAge = (P: Record<string, Shape>, kids: string[]) =>
  kids.every((id) => P[id].born != null) ? kids.slice().sort((a, b) => P[a].born! - P[b].born!) : kids.slice();

/** Each group's rows: the top row in the cast's order with partners together,
 * each lower row by where its parents stand, then four sweeps down and up that
 * move each person toward the mean place of their family in the next row. */
function looseOrder(cast: Cast, t: Ties, gen: Record<string, number>, comps: string[][]): string[][] {
  const P = cast.people;
  const { parents, kidsOf, bondsOf, other } = t;
  const n = Math.max(...Object.keys(P).map((id) => gen[id])) + 1;
  const rows: string[][] = Array.from({ length: n }, () => []);
  const partners = (id: string) => bondsOf[id].map((b) => other(b, id));
  comps.forEach((comp) => {
    const own = new Set(comp);
    const sub: string[][] = rows.map(() => []);
    const placed = new Set<string>();
    const put = (id: string): void => {
      if (placed.has(id)) return;
      placed.add(id);
      sub[gen[id]].push(id);
      partners(id)
        .filter((q) => gen[q] === gen[id] && !parents[q])
        .forEach(put);
    };
    for (let g = 0; g < n; g++) {
      const at = (id: string) => sub[gen[id]].indexOf(id);
      cast.kids
        .filter((k) => own.has(k.kids[0]) && gen[k.kids[0]] === g)
        .map((k) => ({ k, key: k.of.reduce((s, id) => s + at(id), 0) / k.of.length }))
        .sort((a, b) => a.key - b.key)
        .forEach(({ k }) => byAge(P, k.kids).forEach(put));
      comp.filter((id) => gen[id] === g).forEach(put);
    }
    const near = (id: string, r: number) =>
      [...(parents[id] ?? []), ...(kidsOf[id] ?? []), ...partners(id)].filter((q) => own.has(q) && gen[q] === r);
    const sweep = (g: number, r: number) => {
      const there = sub[r];
      const here = sub[g];
      const key: Record<string, number> = {};
      here.forEach((id, i) => {
        // a partner in the same row is left out, or each pass swaps the couple (R-0747)
        const v = near(id, r).map((q) => there.indexOf(q));
        key[id] = v.length ? v.reduce((s, a) => s + a, 0) / v.length : i;
      });
      sub[g] = here
        .map((id, i) => ({ id, i }))
        .sort((a, b) => key[a.id] - key[b.id] || a.i - b.i)
        .map((e) => e.id);
    };
    for (let s = 0; s < 4; s++) {
      for (let g = 1; g < n; g++) sweep(g, g - 1);
      for (let g = n - 2; g >= 0; g--) sweep(g, g + 1);
    }
    // the last word goes to the parents, so each child stands under their own
    for (let g = 1; g < n; g++) sweep(g, g - 1);
    cast.kids
      .filter((k) => own.has(k.kids[0]))
      .forEach((k) => {
        const row = sub[gen[k.kids[0]]];
        const slots = k.kids.map((id) => row.indexOf(id)).sort((a, b) => a - b);
        byAge(P, k.kids).forEach((id, i) => (row[slots[i]] = id));
      });
    comp.forEach((id) => {
      if (parents[id] || bondsOf[id].length !== 1) return;
      const q = partners(id)[0];
      const row = sub[gen[id]];
      if (gen[q] !== gen[id]) return;
      row.splice(row.indexOf(id), 1);
      const i = row.indexOf(q);
      row.splice(manSide(P[q]) < 0 ? i : i + 1, 0, id);
    });
    sub.forEach((row, g) => rows[g].push(...row));
  });
  return rows;
}

function place(cast: Cast, opts: Options, t: Ties, plan: Plan): Layout {
  const d = new Dims(opts.w, opts.compact);
  const { E } = d;
  const tight = opts.names === Names.Above;
  const under = opts.names === Names.Under;
  let P = cast.people;
  const ids = Object.keys(P);
  const { parents, bondsOf } = t;
  const { gen, rows } = plan;
  const half = (id: string) => d.half(P[id]);
  const names = called(Object.fromEntries(ids.map((id) => [id, P[id].name])), cast.others);
  P = Object.fromEntries(ids.map((id) => [id, { ...P[id], name: names[id] }]));
  const x: Record<string, number> = {};
  const y: Record<string, number> = {};
  const side: Record<string, Side> = {};
  const zone: Record<string, number> = {};
  const lw: Record<string, number> = {};
  const nl: Record<string, number> = {};
  const ROW = Math.max(3 * d.W, under ? 100 : 66);
  ids.forEach((id) => {
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
  // a flank arrow stands beside its person as a cross or a word does, on the side away from the name
  flanked.forEach((id) => marked.add(id));
  const ring: Record<string, number> = {};
  const inset: Record<string, number> = {};
  ids.forEach((id) => {
    ring[id] = spiked.has(id) ? SPIKES + 1 : 0;
    inset[id] = Math.max(d.GAP, ring[id] + 2, flanked.has(id) ? FLANK.at + FLANK.wing + 3 : 0);
  });
  const off = (id: string) => offset(d, ring[id]);
  const words = cast.words;
  // how far a person's longest event word reaches past the shape
  const ww = (id: string) => (words[id] && !cast.wordsUnder ? inset[id] + words[id] * NAME * CH : 0);
  // how far a person's marks reach past the shape: the cross and its arrow, or the word
  const zw = (id: string, reach: Reach) => Math.max(crossed.has(id) ? d.ZONE : 0, reach === Reach.All ? ww(id) : 0);


  // how far past a person's shape the given reach runs, on the marks' side
  const marks = (id: string, reach: Reach) =>
    reach === Reach.All || reach === Reach.Marks ? zw(id, reach) : reach === Reach.Words ? ww(id) : 0;
  function rightExt(id: string, reach = Reach.All): number {
    const e = half(id);
    let r = e;
    if (side[id] === Side.Under || side[id] === Side.Top) r = Math.max(r, lw[id] / 2);
    if (side[id] === Side.Right) r = Math.max(r, e + off(id) + lw[id]);
    if (side[id] === Side.Above || side[id] === Side.Below) r = Math.max(r, 5 + lw[id]);
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
  const group: Record<string, number> = {};
  plan.comps.forEach((c, i) => c.forEach((id) => (group[id] = i)));
  function gapFor(a: string, b: string): number {
    // a family with no tie to the person's stands clearly apart (R-0750)
    if (group[a] !== group[b]) return 2 * d.LOOSE;
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
  // the least distance between two neighbours in a row; a mark between them stays nearer its own
  const room = (a: string, b: string) =>
    Math.max(gapFor(a, b), between(a, b) + PAD + (zone[a] === 1 || zone[b] === -1 ? 2 * PAD : 0));
  // a move carries the rest of the row with it; centring a couple over their
  // children, or children under their parents, pushes each neighbour only as
  // far as keeps that distance (R-0749), so no one is carried off across the
  // empty width beside them; except in the fallback, whose bars would come apart
  const shift = (row: string[], from: string, by: number, least = false) => {
    const i = row.indexOf(from);
    x[from] += by;
    for (let j = i + 1; j < row.length; j++) {
      const need = least && !plan.loose ? x[row[j - 1]] + room(row[j - 1], row[j]) - x[row[j]] : by;
      if (need <= 0) break;
      x[row[j]] += need;
    }
  };
  // spec 8, collision step 1: widen the spacing until nothing in the row touches
  function widen(row: string[]): void {
    for (let i = 1; i < row.length; i++) {
      const need = room(row[i - 1], row[i]) - (x[row[i]] - x[row[i - 1]]);
      if (need > 0) shift(row, row[i], need);
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
  // in the fallback, a parents' bar that keeps the rows pushing each other apart
  // is let go: its children's lines may cross, the rest still settle
  let active = units;
  // ...or that keeps them drifting right past twice the rows packed side by side
  let most = Infinity;
  const width = () => Math.max(...ids.map((id) => x[id])) - Math.min(...ids.map((id) => x[id]));
  function settle(): void {
    const keep = { ...x };
    const hit = new Set<(typeof units)[number]>();
    const cap = Math.max(most, width());
    for (let it = 0; it < 200 && width() <= cap; it++) {
      let moved = false;
      hit.clear();
      for (const u of active) {
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
            shift(rowWith(lead), lead, to - b0, true);
            moved = true;
            hit.add(u);
          } else if (b0 - to > 0.5) {
            shift(rowWith(first), first, b0 - to, true);
            moved = true;
            hit.add(u);
          } else if (w - (b1 - b0) > 0.5) {
            shift(rowWith(last), last, w - (b1 - b0), true);
            moved = true;
            hit.add(u);
          }
          continue;
        }
        if (b0 - (k0 - inset) > 0.5) {
          shift(rowWith(first), first, b0 - (k0 - inset), true);
          moved = true;
          hit.add(u);
        } else if (k1 + inset - b1 > 0.5) {
          shift(rowWith(last), last, k1 + inset - b1);
          moved = true;
          hit.add(u);
        }
      }
      if (!moved) return;
    }
    if (!plan.loose) throw new Unplaceable("children under their parents’ bar: the rows keep pushing each other apart");
    Object.assign(x, keep);
    active = active.filter((u) => !hit.has(u));
    settle();
  }

  // each family with no tie to the one before starts to the right of it
  let base = 0;
  plan.comps.forEach((comp) => {
    const own = new Set(comp);
    let right = base;
    rows.forEach((all) => {
      const row = all.filter((id) => own.has(id));
      row.forEach((id, i) => (x[id] = i ? x[row[i - 1]] + gapFor(row[i - 1], id) : base));
      if (row.length) right = Math.max(right, x[row[row.length - 1]]);
    });
    base = right + 2 * d.LOOSE;
  });
  if (plan.loose) most = 2 * width();
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
    // a couple across two rows (the fallback's) stacks with the bars of both
    rows.forEach((_, g) => {
      const here: Record<string, number> = {};
      cast.bonds
        .filter((b) => gen[b.a] === g || gen[b.b] === g)
        .map((b) => ({ key: `${b.a}|${b.b}`, x0: Math.min(x[b.a], x[b.b]), x1: Math.max(x[b.a], x[b.b]) }))
        .sort((a, b) => a.x1 - a.x0 - (b.x1 - b.x0))
        .forEach((r, i, all) => {
          let l = 0;
          while (all.slice(0, i).some((o) => here[o.key] === l && o.x0 <= r.x1 && r.x0 <= o.x1)) l++;
          here[r.key] = l;
          level[r.key] = Math.max(level[r.key] ?? 0, l);
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
    } else if (sd === Side.Below) {
      x0 = x[id] + 5;
      base = y[id] + below[id];
    } else {
      x0 = x[id] - w / 2;
      base = y[id] + below[id];
    }
    return { x0: x0 - 2, x1: x0 + w + 2, y0: base - 12, y1: base + LEAD * (nl[id] - 1) + 4 };
  }
  // each child's line up to their parents' bar, straight or slanting to its end
  const descents = (outside: boolean): Segment[] =>
    cast.bonds.flatMap((b) => {
      const k = cast.kids.find((c) => c.of.length === 2 && c.of.includes(b.a) && c.of.includes(b.b));
      if (!k) return [];
      const [x0, x1] = [Math.min(x[b.a], x[b.b]), Math.max(x[b.a], x[b.b])];
      const yb = Math.max(y[b.a] + half(b.a), y[b.b] + half(b.b)) + d.DROP + (level[`${b.a}|${b.b}`] ?? 0) * 6;
      return k.kids
        .filter((id) => !outside || x[id] < x0 || x[id] > x1)
        .map((id): Segment => [[x[id], y[id] - half(id)], [Math.min(Math.max(x[id], x0), x1), yb]]);
    });
  /** How far apart two names stand, above and below, so each reads as its own. */
  const NAME_GAP = 6;
  const overlap = (a: Box, b: Box) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;
  const shape = (o: string): Box => ({ x0: x[o] - half(o), x1: x[o] + half(o), y0: y[o] - half(o), y1: y[o] + half(o) });
  const tried = (id: string) => [Side.Right, Side.Left, parents[id] ? Side.Above : Side.Top, Side.Under];
  /* no move, child's line, shape or other name lies on a name. A name a move
   * crosses takes the first side, right, left, above, under, that no move
   * crosses; any other takes, of those sides and under beside the line down
   * to the children, the one on the fewest lines and shapes, then the one
   * that widens the family least, then the one on the fewest names (which
   * may still move out of its way). The rows then widen and settle again. */
  const where = { P, x, y, d };
  for (let pass = 0; pass < 4; pass++) {
    const moves = [
      ...cast.moves.map((mv) => ends(where, mv)),
      ...cast.kin.flatMap((k) => across(where, k)),
      ...(plan.loose ? descents(true) : []),
    ];
    // a couple's line too: the drop from each partner and the bar between them
    const couples = cast.bonds.flatMap((b): Segment[] => {
      const yb = Math.max(y[b.a] + half(b.a), y[b.b] + half(b.b)) + d.DROP + (level[`${b.a}|${b.b}`] ?? 0) * 6;
      return [
        [[x[b.a], y[b.a] + half(b.a)], [x[b.a], yb]],
        [[x[b.b], y[b.b] + half(b.b)], [x[b.b], yb]],
        [[Math.min(x[b.a], x[b.b]), yb], [Math.max(x[b.a], x[b.b]), yb]],
      ];
    });
    const lines = [...moves, ...descents(false), ...couples];
    const [x0, x1] = [Math.min(...ids.map((o) => x[o] - leftExt(o))), Math.max(...ids.map((o) => x[o] + rightExt(o)))];
    // names as the pass found them: one moved this pass is not yet clear of its row
    const was = { ...side };
    const cost = (id: string, sd: Side, at = side): number[] => {
      const bx = nameBox(id, sd);
      const others = ids.filter((o) => o !== id);
      return [
        lines.filter((s) => crosses(s, bx)).length + others.filter((o) => overlap(bx, shape(o))).length,
        Math.max(0, x0 - bx.x0) + Math.max(0, bx.x1 - x1),
        // two names that only touch read as one, so a name keeps a gap from the next, beside it and above or below
        others.filter((o) => overlap({ x0: bx.x0 - NAME_GAP, x1: bx.x1 + NAME_GAP, y0: bx.y0 - NAME_GAP, y1: bx.y1 + NAME_GAP }, nameBox(o, at[o]))).length,
      ];
    };
    const less = (a: number[], b: number[]) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2];
    let moved = false;
    ids.forEach((id) => {
      const free = (sd: Side) => !moves.some((s) => crosses(s, nameBox(id, sd)));
      const now = cost(id, side[id], was);
      let pick: Side;
      if (!free(side[id])) pick = tried(id).find(free) ?? Side.Under;
      else if (now[0] || now[2])
        pick = [...tried(id), Side.Below]
          .filter(free)
          .map((sd) => ({ sd, c: cost(id, sd) }))
          .reduce((a, b) => (less(b.c, a.c) < 0 ? b : a)).sd;
      else return;
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
    const low = side[id] === Side.Under || side[id] === Side.Below;
    if (words[id]) fam(x[id], y[id] + below[id] + (low ? LEAD * nl[id] : 0) + 4);
    if (side[id] === Side.Above || side[id] === Side.Top) fam(x[id], y[id] - e - rise(ring[id]) - LEAD * (nl[id] - 1) - 14);
    else if (low) fam(x[id], y[id] + below[id] + LEAD * (nl[id] - 1) + 3);
    else {
      fam(x[id], y[id] - e - 5);
      fam(x[id], y[id] - e + LEAD * (nl[id] - 1) + 4);
    }
  });
  const L: Layout = {
    P, x, y, side, zone, bonds: cast.bonds, kids: cast.kids, gen, w: opts.w, level, below,
    names: [], h: 0, vw: VIEW, px: d.W, wide: 0, my: 0, ring, inset, loose: plan.loose,
    cut: cast.cut ?? [], note: null,
  };
  // a step's inside or outside stands people away from their places; the box
  // holds them and their words there too, so the frame scrolls to them (R-0728, R-0759)
  cast.places.forEach((m) =>
    Object.entries(placed(L, m)).forEach(([id, [ox, oy]]) => {
      const e = half(id);
      const nb = nameBox(id, side[id]);
      grow(x[id] + ox - leftExt(id), y[id] + oy - e);
      grow(x[id] + ox + rightExt(id), y[id] + oy + e);
      grow(nb.x0 + ox, nb.y0 + oy);
      grow(nb.x1 + ox, nb.y1 + oy);
      said.x0 = Math.min(said.x0, x[id] + ox - leftExt(id, Reach.Words), nb.x0 + ox);
      said.x1 = Math.max(said.x1, x[id] + ox + rightExt(id, Reach.Words), nb.x1 + ox);
    }),
  );
  cast.bonds.forEach((b) => fam(x[b.a], bar(L, b).y + 4));
  cast.moves.forEach((mv) => awayTip(L, mv).forEach(([ax, ay]) => grow(ax, ay)));
  // a field's rings run their whole reach inside the picture (R-0776, R-0796)
  cast.kin.forEach((m) =>
    fielded(m).forEach((id) => {
      // the ring's own line too
      grow(x[id] - FIELD - 2, y[id]);
      grow(x[id] + FIELD + 2, y[id]);
    }),
  );
  L.cut.forEach((c) => {
    const [a, q, b] = bend(where, c);
    fam((a[0] + 2 * q[0] + b[0]) / 4, (a[1] + 2 * q[1] + b[1]) / 4);
  });

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
  if (wide > VIEW && !tight && !under) return place(cast, { ...opts, names: Names.Above }, t, plan);
  L.wide = wide;
  let dx = L.vw / 2 - mid;
  if (wide > VIEW && opts.fit) {
    // scaled down to fit the phone, the margin kept at its size on the screen;
    // re-ruled 2026-10-04: the shapes keep the drawer's floor and the picture scrolls sideways,
    // its margin still the same size on the screen, never growing with the width.
    // A family wider than the phone is centred on its people, as every picture
    // is (R-0797): whatever reaches further out on one side is matched on the other
    const fits = Math.max(reach, span / (1 - (2 * MX) / VIEW));
    const least = LEAST.label / NAME;
    if (VIEW / fits >= least) {
      L.vw = fits;
      MX *= L.vw / VIEW;
      MY *= L.vw / VIEW;
    } else {
      MX /= least;
      MY /= least;
    }
    // every name keeps the family's margin from the frame's side too
    const nb = ids.map((id) => nameBox(id, side[id]));
    const half = Math.max(mid - Math.min(box.x0, said.x0 - MX, ...nb.map((b) => b.x0 - MX)), Math.max(box.x1, said.x1 + MX, ...nb.map((b) => b.x1 + MX)) - mid);
    const lo = mid - half;
    L.vw = 2 * half;
    L.px = d.W * Math.max(least, Math.min(1, VIEW / L.vw));
    dx = -lo;
  } else if (wide > VIEW)
    throw new Unplaceable(`the drawing is ${Math.round(wide)} wide, wider than the phone’s ${VIEW}`, true);
  const dy = Math.max(MY - core.y0, 2 - box.y0);
  ids.forEach((id) => {
    x[id] += dx;
    y[id] += dy;
  });
  L.names = ids.map((id) => nameBox(id, side[id]));
  L.h = Math.ceil(Math.max(core.y1 + dy + MY, box.y1 + dy + 2));
  L.my = MY;
  if (L.cut.length) {
    const said = L.cut.map((c) => `${P[c.kid].name} is recorded as their own ${c.up === 2 ? "grandparent" : "ancestor"}`);
    const lines = wrap(said, Math.floor((L.vw - 2 * MX) / (NAME * CH)));
    L.note = { y: L.h - MY + ASCENT, lines };
    L.h = Math.ceil(L.note.y + LEAD * (lines.length - 1) + MY);
  }
  return L;
}

export type Point = [number, number];
type Segment = [Point, Point];
interface Where {
  P: Record<string, Shape>;
  x: Record<string, number>;
  y: Record<string, number>;
  d: Dims;
}

const dimsOf = (L: Layout) => new Dims(L.w);

/** Where the frame's people and their names stand on any of its steps: each
 * name as long as its last step makes it, so it is the same box on every step
 * (R-0797). */
export function people(L: Layout): Box {
  const d = dimsOf(L);
  const shapes = Object.keys(L.P).map((id) => {
    const e = d.half(L.P[id]);
    return { x0: L.x[id] - e, x1: L.x[id] + e, y0: L.y[id] - e, y1: L.y[id] + e };
  });
  const all = [...shapes, ...L.names];
  return {
    x0: Math.min(...all.map((b) => b.x0)),
    x1: Math.max(...all.map((b) => b.x1)),
    y0: Math.min(...all.map((b) => b.y0)),
    y1: Math.max(...all.map((b) => b.y1)),
  };
}

function ray(o: Point, to: Point, dist: number): Point {
  const a = to[0] - o[0];
  const b = to[1] - o[1];
  const c = Math.hypot(a, b);
  const p = c > 0 ? dist / c : 0;
  return [o[0] + p * a, o[1] + p * b];
}
/** A cut link's curve, from the parent's side out past both shapes and back
 * to the kid's, so it lies on no line of the family: its ends and control point. */
function bend(L: Where, c: Cut): [Point, Point, Point] {
  const { P, x, y, d } = L;
  const s = x[c.kid] <= x[c.parent] ? -1 : 1;
  const a: Point = [x[c.parent] + s * d.half(P[c.parent]), y[c.parent]];
  const b: Point = [x[c.kid] + s * d.half(P[c.kid]), y[c.kid]];
  return [a, [(s < 0 ? Math.min(a[0], b[0]) : Math.max(a[0], b[0])) + 2 * s * d.W, (a[1] + b[1]) / 2], b];
}

/** A sentence broken at spaces into lines of at most `n` characters. */
const fill = (t: string, n: number) =>
  t.split(" ").reduce<string[]>((ls, w) => {
    const l = ls[ls.length - 1];
    if (l != null && l.length + 1 + w.length <= n) ls[ls.length - 1] = `${l} ${w}`;
    else ls.push(w);
    return ls;
  }, []);

/** Sentences in as few lines as fit `n` characters, the lines of each about even. */
function wrap(said: string[], n: number): string[] {
  return said.flatMap((t) => {
    const k = fill(t, n).length;
    let m = Math.ceil(t.length / k);
    while (fill(t, m).length > k) m++;
    return fill(t, m);
  });
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
  const mirror = L.zone[id] < 0;
  // drawn beside its own origin, then set a gap past the shape at the person's scale
  const fig = { id: 0, name: L.P[id].name, x: 0, y: 0, r: CROSS / 2 - 29, mirror };
  const x = L.x[id] + (mirror ? -1 : 1) * (d.half(L.P[id]) + d.GAP);
  return (
    `<g class="mk ${cls}${cls === Tone.Now ? " pop" : ""}" data-mark="cross:${esc(id)}" style="--ck:${d.CK.toFixed(4)}">` +
    `<g transform="translate(${f(x)} ${f(L.y[id])}) scale(${d.CK.toFixed(4)})">${healthCross(fig, dir)}</g>` +
    `</g>`
  );
}

export function outline(p: Shape, x: number, y: number, e: number, cls: string): string {
  if (p.g === Sex.Miscarriage || p.g === Sex.Abortion)
    return `<path class="${cls}" d="M${f(x)} ${f(y - e)}L${f(x + e)} ${f(y + e)}H${f(x - e)}Z"/>`;
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

/** How far a slash reaches below and above the couple's line, in person
 * widths: two thirds of a person in all, crossing the line a quarter of a
 * person from its foot (R-0758, R-0759). */
export const SLASH = { below: 0.25, above: 5 / 12 };
/** How far apart a divorce's two slashes stand, in person widths. */
const STEP = 0.25;
/** How far either side of x a run of n slashes reaches, for a person w wide. */
const slashSpan = (n: number, w: number) => ((n - 1) * STEP * w) / 2;
/** How many slashes a tie draws: one for a separation, two for a divorce. */
export const slashCount = (st: Tie) => (st === Tie.Separated ? 1 : st === Tie.Divorced ? 2 : 0);

/** One slash for a separation, two for a divorce, upright because custody is
 * not recorded, centred on x across the couple's line at y, for people w wide. */
export const slashes = (n: number, x: number, y: number, w: number, fresh = false): string =>
  slashLines(n, x, y, w, fresh ? 1 : 0).join("");

/** The same slashes one by one, the last `fresh` of them this step's own, so
 * they can be drawn over the rest. */
function slashLines(n: number, x: number, y: number, w: number, fresh = 0, carried = ""): string[] {
  return Array.from({ length: n }, (_, i) => {
    const sx = x - slashSpan(n, w) + i * STEP * w;
    const pop = i >= n - fresh ? " now pop" : carried;
    return `<line class="slash${pop}" x1="${f(sx)}" y1="${f(y + SLASH.below * w)}" x2="${f(sx)}" y2="${f(y - SLASH.above * w)}"/>`;
  });
}

/** A line from a child up to their parents' line, or between twins. */
export const kinLine = (p: Point, q: Point, cls = "") => `<path class="kin${cls}" d="${seg(p, q)}"/>`;

/** A person's age, or the question of their sex, inside their shape. */
export const ageText = (x: number, y: number, said: string, cls = "") =>
  `<text class="age${cls}" x="${f(x)}" y="${f(y + AGE_DROP)}">${esc(said)}</text>`;

/** One line of a person's name and dates: the name first, the dates under it. */
export const nameText = (x: number, y: number, line: string, anchor: string, first: boolean, cls = "") =>
  `<text class="${first ? "lbn" : "lbd"}${cls}" x="${f(x)}" y="${f(y)}" text-anchor="${anchor}">${esc(line)}</text>`;

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
function spikes(L: Layout, id: string, cls: Tone, down = false): string {
  const fig = { id: 0, name: L.P[id].name, x: L.x[id], y: L.y[id], r: dimsOf(L).half(L.P[id]), still: down };
  // going down the spikes are there at full strength from the first frame, as the projection's parent's are
  const marks = anxious(fig, down ? "out" : "solo");
  const still = marks.replace(/<animate(Transform)?\b[^>]*\/>/g, "").replace(/ opacity="0"/g, "");
  return `<g class="spikes ${cls}${down ? " down" : ""}" data-mark="${down ? "anxd" : "anx"}:${esc(id)}">${cls === Tone.Was ? still : marks}</g>`;
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
    centred(L.y[id] + L.below[id] + (L.side[id] === Side.Under || L.side[id] === Side.Below ? LEAD * lines(L.P[id], Infinity).length : 0) + row + more);
  // over the person, above their name when it is there
  const top = Math.min(L.y[id] - e - L.ring[id], ...L.names.filter((b) => b.x0 <= L.x[id] && L.x[id] <= b.x1 && b.y1 <= L.y[id]).map((b) => b.y0));
  const over = centred(top - 6 - row);
  const own = L.zone[id] || (L.side[id] === Side.Right ? -1 : 1);
  const named = L.side[id] === Side.Right ? 1 : L.side[id] === Side.Left ? -1 : 0;
  const sides = named === -own ? [own] : [own, -own];
  // beside, then a line lower beside, clear of a move along the row, then
  // under, over, and further under
  const tries = [...sides.map((sd) => beside(sd)), ...sides.map((sd) => beside(sd, LEAD)), under(0), over, under(LEAD)];
  const inPicture = (t: Spot) => t.box.x0 >= 0 && t.box.x1 <= L.vw && t.box.y0 >= 0 && t.box.y1 <= L.h;
  // how many of what is already drawn the word would lie on
  const covers = (t: Spot) =>
    taken.filter((b) => t.box.x0 < b.x1 && b.x0 < t.box.x1 && t.box.y0 < b.y1 && b.y0 < t.box.y1).length +
    drawn.filter((sg) => crosses(sg, { x0: t.box.x0 - 2, x1: t.box.x1 + 2, y0: t.box.y0 - 2, y1: t.box.y1 + 2 })).length;
  const free = (t: Spot) => inPicture(t) && !covers(t);
  // no free place: the lit word lies on top of the fewest things at its
  // usual distance from its person, beside, under or over (R-0734)
  const near = [...sides.map((sd) => beside(sd)), under(0), over].filter(inPicture);
  return tries.find(free) ?? near.sort((p, q) => covers(p) - covers(q))[0] ?? tries[0];
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
  // every field's rings reach the same distance, wherever its person stands;
  // the picture's edge cuts them rather than shrinking them (R-0776)
  const at = (id: string) => ({
    id: 0,
    name: L.P[id].name,
    x: L.x[id],
    y: L.y[id],
    r: d.half(L.P[id]),
    mirror: L.zone[id] < 0,
    gender: L.P[id].g === Sex.Female ? "female" : null,
    mark: d.MARK,
    still: true,
  });
  const marks = moveMarks(m.kind, at(m.from), m.to ? at(m.to) : null, STILL).marks;
  const was = m.cls === Tone.Was;
  return (
    `<g class="mvk ${m.cls ?? Tone.Now}" data-mark="move:${esc(`${m.from}>${m.to ?? ""}:${m.kind}`)}">` +
    // carried, a wall keeps the line from its person to it, at the rest the
    // loop ends on, so its strike never stands alone
    (was ? marks.replace(/<animate(Transform)?\b[^>]*\/>/g, "").replace(/(<line class="mv-trace"[^>]*?)opacity="0"/g, '$1opacity=".55"') : marks) +
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

function childLines(L: Layout, k: { x0: number; x1: number; y: number }, kids: string[], t: number): string {
  const d = dimsOf(L);
  return kids
    .map((id) => {
      const top: Point = [L.x[id], L.y[id] - d.half(L.P[id])];
      const end: Point =
        top[0] >= k.x0 && top[0] <= k.x1 ? [top[0], k.y] : [top[0] < k.x0 ? k.x0 : k.x1, k.y];
      return kinLine(top, end, unborn(L.P[id], t));
    })
    .join("");
}

/** Someone not yet born, or a couple not yet together, keeps their place faded (R-0756). */
const yet = (since: number | null | undefined, t: number) => (since != null && since > t + 1e-6 ? " yet" : "");
const unborn = (p: Shape, t: number) => yet(p.born, t);

type Offset = [number, number];

/** How far each person stands from their own place while a step's inside or
 * outside lasts, as the approved drawing places them: the two who end up
 * close overlap by half a shape, the third stands a shape's width further
 * out from them (R-0728). */
function placed(L: Layout, m: Place): Record<string, Offset> {
  const R = dimsOf(L).half(L.P[m.who]);
  const at = (id: string): Offset => [L.x[id], L.y[id]];
  const unit = (a: Offset, b: Offset): Offset => {
    const l = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    return [(b[0] - a[0]) / l, (b[1] - a[1]) / l];
  };
  const by = (u: Offset, k: number): Offset => [u[0] * k, u[1] * k];
  const gap = (a: Offset, b: Offset) => Math.hypot(b[0] - a[0], b[1] - a[1]);
  const mid = (a: Offset, b: Offset): Offset => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  const [CLOSE, OUT] = [1.5 * R, 2 * R];
  const [a, b] = [at(m.who), at(m.to)];
  const out: Record<string, Offset> = {};
  if (m.kind === Move.Inside) {
    out[m.who] = by(unit(a, b), Math.max(0, gap(a, b) - CLOSE));
    if (m.third) out[m.third] = by(unit(mid(a, b), at(m.third)), OUT);
  } else {
    if (m.third) {
      const c = at(m.third);
      out[m.who] = by(unit(mid(b, c), a), OUT);
      const half = Math.max(0, (gap(b, c) - CLOSE) / 2);
      out[m.to] = by(unit(b, c), half);
      out[m.third] = by(unit(c, b), half);
    } else out[m.who] = by(unit(b, a), OUT);
  }
  return out;
}

/** The step's slide from home to its places, the grow time eased, held, and
 * round again from home, jumping back rather than sliding (R-0763), in the
 * wall's five seconds (R-0679). */
const SLIDE = `dur="5s" repeatCount="indefinite" calcMode="spline" keyTimes="0;0.28;1" keySplines="0.42 0 0.58 1;0 0 1 1"`;

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
  // inside and outside: a moved person's shape, words and marks slide together
  // to their place for the step, and their family lines stay anchored where
  // they were, a straight stretch running on to them (R-0728)
  const moved = s.place ? placed(L, s.place) : {};
  const slid = (id: string, markup: string) => {
    const m = moved[id];
    if (!m) return markup;
    const xy = `${f(m[0])} ${f(m[1])}`;
    return (
      `<g class="slid" transform="translate(${xy})">` +
      `<animateTransform attributeName="transform" type="translate" values="0.0 0.0;${xy};${xy}" ${SLIDE}/>` +
      `${markup}</g>`
    );
  };
  const stretch = (id: string, ax: number, ay: number) => {
    const m = moved[id];
    if (!m) return "";
    const half = d.half(P[id]);
    // the point on the moved shape's rim nearest the anchor
    const rim = (o: Offset) => {
      const [cx, cy] = [L.x[id] + o[0], L.y[id] + o[1]];
      const l = Math.hypot(ax - cx, ay - cy) || 1;
      const [ux, uy] = [(ax - cx) / l, (ay - cy) / l];
      const e = P[id].g === Sex.Female ? half : half / Math.max(Math.abs(ux), Math.abs(uy));
      return [cx + ux * e, cy + uy * e];
    };
    const [a, b] = [rim([0, 0]), rim(m)];
    return (
      `<line class="tie stretch" data-stretch="${esc(id)}" x1="${f(ax)}" y1="${f(ay)}" x2="${f(b[0])}" y2="${f(b[1])}">` +
      `<animate attributeName="x2" values="${f(a[0])};${f(b[0])};${f(b[0])}" ${SLIDE}/>` +
      `<animate attributeName="y2" values="${f(a[1])};${f(b[1])};${f(b[1])}" ${SLIDE}/></line>`
    );
  };
  s.bonds.forEach((b) => [b.a, b.b].forEach((id) => (out += stretch(id, L.x[id], L.y[id] + d.half(P[id])))));
  L.kids.forEach((c) => c.kids.forEach((id) => (out += stretch(id, L.x[id], L.y[id] - d.half(P[id])))));
  s.bonds.forEach((b) => {
    const kids = L.kids.find((c) => c.of.includes(b.a) && c.of.includes(b.b));
    if (kids) out += childLines(L, bar(L, b), kids.kids, s.t);
  });
  L.kids
    .filter((c) => c.of.length === 1)
    .forEach((c) => {
      const p = c.of[0];
      const xs = [...c.kids.map((id) => L.x[id]), L.x[p]];
      const k = { x0: Math.min(...xs), x1: Math.max(...xs), y: L.y[p] + d.half(P[p]) + d.DROP };
      out +=
        `<path class="tie" d="M${f(L.x[p])} ${f(L.y[p] + d.half(P[p]))}V${f(k.y)}M${f(k.x0)} ${f(k.y)}H${f(k.x1)}"/>` +
        childLines(L, k, c.kids, s.t);
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
      (b.hot ? " now pop" : "") + yet(L.bonds.find((o) => o.a === b.a && o.b === b.b)?.from, s.t),
      ` data-bond="${esc(`${b.a}|${b.b}`)}"`,
    ), b.hot);
    const n = slashCount(b.st);
    if (!n) return;
    // the slashes sit in an open stretch of the line, never on a child's line,
    // nearest the middle of the widest one where they cross no name or word
    const kids = L.kids.find((c) => c.of.includes(b.a) && c.of.includes(b.b));
    const stops = [k.x0, ...(kids?.kids ?? []).map((id) => L.x[id]).filter((x) => x > k.x0 && x < k.x1), k.x1].sort((p, q) => p - q);
    const open = stops.slice(1).map((x, i) => [stops[i], x]).sort((p, q) => q[1] - q[0] - (p[1] - p[0]));
    const hw = slashSpan(n, d.MARK) + 3;
    const clear = (cx: number) =>
      !texts.some(
        (t) => t.x0 < cx + hw && cx - hw < t.x1 && t.y0 < k.y + SLASH.below * d.MARK && k.y - SLASH.above * d.MARK < t.y1,
      );
    const at = open
      .flatMap(([p, q]) => {
        const room = Math.max(0, Math.floor(((q - p) / 2 - hw) / 2));
        return Array.from({ length: room + 1 }, (_, i) => [(p + q) / 2 - 2 * i, (p + q) / 2 + 2 * i]).flat();
      })
      .find(clear);
    // a slash from an earlier date fades like every other carried mark (R-0793, R-0794)
    slashLines(n, at ?? (open[0][0] + open[0][1]) / 2, k.y, d.MARK, b.fresh, ` ${Tone.Was}`).forEach((l, i) =>
      put(l, i >= n - b.fresh),
    );
  });

  Object.keys(P).forEach((id) => {
    const p = P[id];
    const x = L.x[id];
    const y = L.y[id];
    const e = d.half(p);
    const dead = p.died != null && p.died <= s.t + 1e-6;
    // someone not yet born keeps their place (R-0546) but has no age to show
    const born = unborn(p, s.t);
    const age = p.born == null || born ? null : yr((dead ? p.died! : s.t) - p.born + 1e-6);
    let g = `<g class="p${born}" data-id="${esc(id)}">`;
    let t = `<g class="pt${born}" data-id="${esc(id)}">`;
    if (p.you) g += outline(p, x, y, e, "you");
    g += outline(p, x, y, E, "shape");
    if (age != null) t += ageText(x, y, String(age));
    else if (p.g === Sex.Unknown) t += ageText(x, y, "?");
    if (dead) {
      // a death X is in the emphasis colour on its date, plain ink after
      if (s.died.has(id)) top += crossOut(x, y, e, age != null, "xd now pop");
      else g += crossOut(x, y, e, age != null, "xd");
    }
    const l = lines(p, s.t);
    if (s.names?.[id]) l[0] = s.names[id];
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
    } else if (sd === Side.Below) {
      lx = x + 5;
      y0 = y + L.below[id];
    } else {
      lx = sd === Side.Right ? x + e + offset(d, L.ring[id]) : x - e - offset(d, L.ring[id]);
      anchor = sd === Side.Right ? "start" : "end";
      y0 = y - e + 9;
    }
    l.forEach((line, i) => {
      if (line) t += nameText(lx, y0 + i * LEAD, line, anchor, !i);
    });
    out += slid(id, g + "</g>");
    said += slid(id, t + "</g>");
  });

  const own = put;
  s.marks.forEach((m) => {
    const put = (markup: string, now: boolean) => own(slid(m.who, markup), now);
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
    // going down leaves nothing to carry: grey, it is not drawn (R-0729)
    else if (m.k === Mark.AnxietyDown && lit(m.cls)) put(spikes(L, m.who, Tone.Now, true), true);
  });
  s.kin.forEach((m) => put(kin(L, m), lit(m.cls)));
  s.moves.forEach((mv) => put(boardMove(L, mv), lit(mv.cls)));
  L.cut.forEach((c) => {
    const [a, q, b] = bend({ P, x: L.x, y: L.y, d }, c);
    out += `<path class="cut" data-cut="${esc(`${c.kid}|${c.parent}`)}" d="M${f(a[0])} ${f(a[1])}Q${f(q[0])} ${f(q[1])} ${f(b[0])} ${f(b[1])}"/>`;
  });
  if (L.note)
    said += L.note.lines
      .map((l, i) => `<text class="cutn" x="${f(L.vw / 2)}" y="${f(L.note!.y + i * LEAD)}" text-anchor="middle">${esc(l)}</text>`)
      .join("");
  return `<svg class="ss diagram" viewBox="0 0 ${f(L.vw)} ${L.h}" role="img" aria-label="${esc(s.label)}">${out}<g class="fore">${top}</g><g class="said">${said}</g></svg>`;
}
