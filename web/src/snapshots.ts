import {
  arrange,
  draw,
  Mark,
  Sex,
  sexOf,
  Tie,
  Tone,
  type Arrow,
  type Bond,
  type Kin,
  type Brood,
  type Cast,
  type Layout,
  type Place,
  type Placed,
  type Shape,
} from "./diagram";
import { Move, Shift } from "./moves";
import { DateCertainty } from "./certainty";
import { dateText } from "./spotlight";
import { EventKind, type Case, type PairBond, type Person, type Timeline, type TimelineEvent } from "./types";

/** The coach tells one cluster in 3–6 snapshots (R-0563). A snapshot is one date: who was around the person,
 * how each was doing, what moved between them. This turns the coach's case and
 * the record into what each snapshot draws. */

/** One snapshot drawn, with its caption. */
export interface Shot {
  svg: string;
  date: string;
  gap: string | null;
  fact: string;
  guess: string | null;
  question: string | null;
  /** Who the snapshot is about, or the record's own person. */
  who: string;
  /** Who makes the step's move, if it has one, and everyone the move reaches. */
  mover: string | null;
  reach: string[];
  /** Both partners of a couple the step marries, separates or divorces. */
  couple: string[];
}

interface Step {
  t: number;
  date: string;
  marks: (Placed | Arrow | Pair | Kin)[];
}

interface Pair {
  k: Mark.Couple | Mark.Separated | Mark.Divorced;
  a: string;
  b: string;
}

export const COUPLE_KINDS = new Set<string>([EventKind.Married, EventKind.Bonded]);
export const ENDS: Record<string, Pair["k"]> = {
  [EventKind.Separated]: Mark.Separated,
  [EventKind.Divorced]: Mark.Divorced,
};
export const BIRTHS = new Set<string>([EventKind.Birth, EventKind.Adopted]);

/** Who an event is about: the child for a birth or an adoption, the person
 * for every other kind. */
export const aboutOf = (e: TimelineEvent): number | null => (BIRTHS.has(e.kind ?? "") ? e.child ?? e.person : e.person);

/** The one bond there ever is between two people (R-0326). */
export const bondOf = (bonds: PairBond[], a: number | null, b: number | null) =>
  bonds.find((pb) => (pb.person_a === a && pb.person_b === b) || (pb.person_a === b && pb.person_b === a));

const key = (id: number) => String(id);

/** A snapshot's date as sure as its events are: the month when certain, the
 * year when approximate, and no date when it is unknown. */
const caption = (e: TimelineEvent) =>
  e.dateCertainty === DateCertainty.Unknown ? "date unknown" : dateText(e.dateTime!, e.dateCertainty);

/** The whole family's date, the month in full when the record is sure of it. */
const spoken = (e: TimelineEvent) =>
  e.dateCertainty === DateCertainty.Unknown || e.dateCertainty === DateCertainty.Approximate
    ? caption(e)
    : new Date(e.dateTime!.slice(0, 10)).toLocaleString("en", { month: "long", year: "numeric", timeZone: "UTC" });

/** A date as a year with its fraction, so ages and gaps are arithmetic. */
export function when(iso: string): number {
  const [y, m = 1, d = 1] = iso.slice(0, 10).split("-").map(Number);
  return y + (m - 1) / 12 + (d - 1) / 365;
}

const NUM = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven"];
/** The gap since the last snapshot, in words. */
export function gapText(a: number, b: number): string {
  const n = Math.round((b - a) * 12);
  if (n >= 24) return `${Math.round(b - a)} years later`;
  if (n >= 12) return "a year later";
  if (n === 0) return "the same month";
  return n === 1 ? "one month later" : `${NUM[n]} months later`;
}

export class Family {
  readonly people = new Map<string, Person>();
  readonly events = new Map<number, TimelineEvent>();
  readonly you: string;

  constructor(readonly tl: Timeline) {
    tl.people.forEach((p) => this.people.set(key(p.id), p));
    tl.events.forEach((e) => this.events.set(e.id, e));
    const you = tl.people.find((p) => p.primary);
    if (!you) throw new Error("the record has no primary person to tell a case to");
    this.you = key(you.id);
  }

  event(id: number): TimelineEvent {
    const e = this.events.get(id);
    if (!e) throw new Error(`no event ${id} in the record`);
    if (!e.dateTime) throw new Error(`event ${id} has no date to stand in a snapshot`);
    return e;
  }

  bondOf(a: number | null, b: number | null): PairBond | undefined {
    return bondOf(this.tl.pair_bonds, a, b);
  }

  died(p: Person): number | null {
    const e = p.death_event == null ? undefined : this.events.get(p.death_event);
    return e?.dateTime ? when(e.dateTime) : null;
  }

  shape(id: string): Shape {
    const p = this.people.get(id);
    if (!p) throw new Error(`no person ${id} in the record`);
    return {
      name: p.last_name ? `${p.name} ${p.last_name}` : p.name,
      g: sexOf(p.gender),
      born: p.birth ? when(p.birth) : null,
      died: this.died(p),
      you: key(p.id) === this.you,
    };
  }

  /** Everyone an event names. */
  named(e: TimelineEvent): string[] {
    return [e.person, e.spouse, e.child, ...e.relationshipTargets, ...e.relationshipTriangles]
      .filter((id): id is number => id != null)
      .map(key);
  }
}

/** Moves with a still drawing of their own on the moves board, and those that
 * need no one on the far side. Inside and outside are position moves: words. */
const KIN = new Set<string>([
  Move.Distance,
  Move.Cutoff,
  Move.Conflict,
  Move.Fusion,
  Move.Projection,
  Move.Overfunctioning,
  Move.Underfunctioning,
  Move.DefinedSelf,
]);
const ALONE = new Set<string>([Move.Projection, Move.Overfunctioning, Move.Underfunctioning, Move.DefinedSelf]);
/** The few words a noted event or a shift is shown by, whole (R-0681); every
 * such event has them. */
function titleOf(e: TimelineEvent): string {
  if (!e.title) throw new Error(`event ${e.id} is a ${e.kind} event with no title`);
  return e.title;
}

/** What an event draws on its date: its own drawing when it has one, else the
 * person in the emphasis colour and its title beside them. An event about
 * nobody in particular is about the family: everyone alive then is emphasised,
 * and its title goes beside the reader. */
function marksOf(r: Family, e: TimelineEvent): Step["marks"] {
  const about = aboutOf(e);
  if (about == null)
    return [
      { k: Mark.Family, who: r.you },
      { k: Mark.Event, who: r.you, word: titleOf(e) },
    ];
  const who = key(about);
  const kind = e.kind ?? "";
  if (COUPLE_KINDS.has(kind) || ENDS[kind]) {
    const pb = r.bondOf(e.person, e.spouse);
    if (!pb) throw new Error(`event ${e.id} is about a couple the record does not hold`);
    const a = key(pb.person_a!);
    const b = key(pb.person_b!);
    return [{ k: ENDS[kind] ?? Mark.Couple, a, b }];
  }
  if (BIRTHS.has(kind)) return [{ k: Mark.Emphasis, who }];
  // the one who died is lit too, not only crossed out (Patrick, 2026-10-03)
  if (kind === EventKind.Death) return [{ k: Mark.Died, who }, { k: Mark.Emphasis, who }];
  const drawn: Step["marks"] = [];
  for (const [shift, [up, down]] of [
    [e.symptom, [Mark.Up, Mark.Down]],
    [e.functioning, [Mark.FnUp, Mark.FnDown]],
  ] as const) {
    if (shift === Shift.Up) drawn.push({ k: up, who });
    if (shift === Shift.Down) drawn.push({ k: down, who });
  }
  // an outline that breaks or holds says little on its own, so it carries its
  // event's words as an event with no drawing does (Patrick, 2026-10-03)
  if (e.functioning) drawn.push({ k: Mark.Event, who, word: titleOf(e) });
  if (e.anxiety === Shift.Up) drawn.push({ k: Mark.Anxiety, who });
  if (e.anxiety === Shift.Down) drawn.push({ k: Mark.AnxietyDown, who });
  const move = e.relationship ?? "";
  // inside and outside move the three people for the step, all three lit (R-0728)
  if ((move === Move.Inside || move === Move.Outside) && e.relationshipTargets.length) {
    const [to, third = null] = [key(e.relationshipTargets[0]), e.relationshipTriangles.length ? key(e.relationshipTriangles[0]) : null];
    const place: Place = { k: Mark.Place, kind: move, who, to, third };
    drawn.push(place, ...[who, to, third].flatMap((id) => (id ? [{ k: Mark.Emphasis, who: id }] : [])));
  } else if (move === Move.Toward || move === Move.Away)
    e.relationshipTargets.forEach((t) =>
      drawn.push({ k: move === Move.Away ? Mark.Away : Mark.Toward, from: who, to: key(t) }),
    );
  else if (KIN.has(move)) {
    const to = e.relationshipTargets.map(key);
    if (to.length) to.forEach((t) => drawn.push({ k: Mark.Move, kind: move as Move, from: who, to: t }));
    else if (ALONE.has(move)) drawn.push({ k: Mark.Move, kind: move as Move, from: who, to: null });
    // the parent's agitation is drawn inside their shape, and the one who
    // holds still turns green on the board, so the shape itself is lit too, as
    // the person an event is about is (Patrick, 2026-10-03)
    if (move === Move.Projection || move === Move.DefinedSelf) drawn.push({ k: Mark.Emphasis, who });
  }
  if (drawn.length) return drawn;
  return [
    { k: Mark.Event, who, word: titleOf(e) },
    { k: Mark.Emphasis, who },
  ];
}

/** Everyone a mark is drawn on or between. */
const peopleOf = (m: Step["marks"][number]): string[] => {
  if (isArrow(m) || isKin(m)) return m.to ? [m.from, m.to] : [m.from];
  if (isPair(m)) return [m.a, m.b];
  if (m.k === Mark.Place) return [m.who, (m as Place).to, ...((m as Place).third ? [(m as Place).third!] : [])];
  return [m.who];
};

/** The people `seeds` and only those that join them into one family (R-0781):
 * each joined to the rest by the fewest parent, partner and child links, and
 * a child's other parent beside the one drawn, so the couple's line holds the
 * child. Someone the family links do not reach stands alone, seeds first. */
export function joined(r: Family, seeds: string[]): string[] {
  const bonds = r.tl.pair_bonds;
  const of = (pb: PairBond) => [pb.person_a, pb.person_b].filter((p): p is number => p != null).map(key);
  const parents = (id: string) => {
    const pb = bonds.find((b) => b.id === r.people.get(id)?.parents);
    return pb ? of(pb) : [];
  };
  const near = (id: string) => [
    ...parents(id),
    ...bonds.filter((pb) => of(pb).includes(id)).flatMap((pb) => [...of(pb), ...r.tl.people.filter((o) => o.parents === pb.id).map((o) => key(o.id))]),
  ];
  const tree = new Set([seeds[0]]);
  seeds.slice(1).forEach((s) => {
    if (tree.has(s)) return;
    const prev = new Map<string, string | null>([[s, null]]);
    let hit: string | null = null;
    for (const queue = [s]; queue.length && !hit; ) {
      const u = queue.shift()!;
      for (const v of near(u)) {
        if (prev.has(v)) continue;
        prev.set(v, u);
        if (tree.has(v)) {
          hit = v;
          break;
        }
        queue.push(v);
      }
    }
    if (!hit) tree.add(s);
    for (let u: string | null = hit; u; u = prev.get(u)!) tree.add(u);
  });
  [...tree].forEach((id) => {
    const ps = parents(id);
    if (ps.some((p) => tree.has(p))) ps.forEach((p) => tree.add(p));
  });
  return [...seeds, ...[...tree].filter((id) => !seeds.includes(id))];
}

/** Three generations around `seeds` (R-0779): each one's parents, partners,
 * brothers and sisters, and children, seeds first; more only when the seeds
 * themselves span more, as a great-grandparent and a great-grandchild do. The
 * generation above the seeds is drawn while they span fewer than three, the
 * one below only while they all stand in one. */
export function circle(r: Family, seeds: string[]): string[] {
  const bonds = r.tl.pair_bonds;
  const of = (pb: PairBond) => [pb.person_a, pb.person_b].filter((p): p is number => p != null).map(key);
  const born = (id: string) => bonds.find((pb) => pb.id === r.people.get(id)?.parents);
  const kids = (pb: PairBond) => r.tl.people.filter((o) => o.parents === pb.id).map((o) => key(o.id));
  const out = new Set(seeds);
  seeds.forEach((id) => {
    const up = born(id);
    if (up) [...of(up), ...kids(up)].forEach((q) => out.add(q));
    bonds.filter((pb) => of(pb).includes(id)).forEach((pb) => [...of(pb), ...kids(pb)].forEach((q) => out.add(q)));
  });
  // each one's generation, counted through the whole record from the first seed
  const gen = new Map<string, number>([[seeds[0], 0]]);
  for (const queue = [seeds[0]]; queue.length; ) {
    const id = queue.shift()!;
    const g = gen.get(id)!;
    const up = born(id);
    const near: [string, number][] = [
      ...(up ? of(up).map((q): [string, number] => [q, g - 1]) : []),
      ...bonds.filter((pb) => of(pb).includes(id)).flatMap((pb) => [...of(pb).map((q): [string, number] => [q, g]), ...kids(pb).map((q): [string, number] => [q, g + 1])]),
    ];
    near.forEach(([q, at]) => {
      if (gen.has(q)) return;
      gen.set(q, at);
      queue.push(q);
    });
  }
  const at = seeds.filter((id) => gen.has(id)).map((id) => gen.get(id)!);
  const [lo, hi] = [Math.min(...at), Math.max(...at)];
  // three generations, or as many as the seeds themselves span
  const first = hi - lo >= 2 ? lo : lo - 1;
  const last = hi === lo ? hi + 1 : hi;
  return [...out].filter((id) => !gen.has(id) || (gen.get(id)! >= first && gen.get(id)! <= last));
}

const isArrow = (m: Step["marks"][number]): m is Arrow => m.k === Mark.Toward || m.k === Mark.Away;
const isKin = (m: Step["marks"][number]): m is Kin => m.k === Mark.Move;
const isPair = (m: Step["marks"][number]): m is Pair =>
  m.k === Mark.Couple || m.k === Mark.Separated || m.k === Mark.Divorced;
const isPlaced = (m: Step["marks"][number]): m is Placed => !isArrow(m) && !isPair(m) && !isKin(m);

/** A told case, laid out once and drawn per snapshot. */
export class Told {
  readonly steps: Step[];
  readonly cast: Cast;
  readonly layout: Layout;
  /** The events the case is about: its cluster's, or the ones it was given. */
  readonly eventIds: number[];
  private readonly start = new Map<string, Tie>();

  constructor(
    readonly tl: Timeline,
    readonly told: Case,
    /** The whole family stepped through dates (R-0742): the years line spans
     * every dated event in the record. */
    readonly whole = false,
    /** Only these people are drawn, the first of them standing for the reader,
     * and only the marks among them (R-0779). */
    keep: string[] | null = null,
  ) {
    const r = new Family(tl);
    const kept = keep && new Set(keep);
    this.steps = told.snapshots.map((s) => {
      const events = s.event_ids.map((id) => r.event(id));
      const first = events[0];
      const marks = events.flatMap((e) => marksOf(r, e));
      return {
        t: when(first.dateTime!),
        date: whole ? spoken(first) : caption(first),
        marks: kept ? marks.filter((m) => peopleOf(m).every((id) => kept.has(id))) : marks,
      };
    });
    // everyone the case's events name is drawn, the ones no snapshot shows too
    if (whole) this.eventIds = tl.events.filter((e) => e.dateTime).map((e) => e.id);
    else if (told.cluster_id === null) this.eventIds = told.snapshots.flatMap((s) => s.event_ids);
    else {
      const cluster = tl.clusters.find((c) => c.id === told.cluster_id);
      if (!cluster) throw new Error(`no cluster ${told.cluster_id} on the line`);
      this.eventIds = cluster.event_ids;
    }
    this.cast = castOf(r, this.steps, this.eventIds.map((id) => r.event(id)), whole, keep);
    this.cast.bonds.forEach((b) => this.start.set(`${b.a}|${b.b}`, b.st));
    this.layout = arrange(this.cast);
  }

  /** Who a snapshot puts in the emphasis colour: the people its events are
   * about, and for an event about the whole family, everyone alive then. */
  private emphasised(s: Step): string[] {
    const placed = s.marks.filter(isPlaced);
    const family = placed.some((m) => m.k === Mark.Family)
      ? Object.entries(this.cast.people)
          .filter(([, p]) => (p.born == null || p.born <= s.t) && (p.died == null || p.died > s.t))
          .map(([who]) => who)
      : [];
    return [...new Set([...placed.filter((m) => m.k === Mark.Emphasis).map((m) => m.who), ...family])];
  }

  /** Who an event is about, when they are drawn, else the record's own person. */
  private about(id: number): string {
    const e = this.tl.events.find((e) => e.id === id)!;
    const who = aboutOf(e);
    return who != null && key(who) in this.cast.people ? key(who) : this.cast.index;
  }

  /** The whole family's step `i`: the people its events involve and those
   * that join them (R-0781), or `focus`'s three generations when given
   * (R-0779); only that step and the ones before it, so its marks are new and
   * the earlier ones carried. */
  around(i: number, focus: string[] | null = null): Told {
    const r = new Family(this.tl);
    const seeds = [...new Set(this.steps[i].marks.flatMap(peopleOf))].filter((id) => r.people.has(id));
    const told = { ...this.told, snapshots: this.told.snapshots.slice(0, i + 1) };
    return new Told(this.tl, told, true, focus ? circle(r, focus) : joined(r, seeds.length ? seeds : [r.you]));
  }

  get length(): number {
    return this.steps.length;
  }

  /** Snapshot `i` drawn: the new marks in the emphasis colour, everything from
   * earlier snapshots carried in grey, so nothing drawn ever vanishes on a tap. */
  shot(i: number): Shot {
    const now = this.steps[i];
    const before = this.steps.slice(0, i);
    const tie = new Map(this.start);
    const trouble = new Map<string, Mark>();
    before.forEach((s) =>
      s.marks.forEach((m) => {
        if (m.k === Mark.Separated || m.k === Mark.Divorced) tie.set(pairKey(this.cast, m as Pair), m.k === Mark.Separated ? Tie.Separated : Tie.Divorced);
        if (m.k === Mark.Up || m.k === Mark.Down) trouble.set((m as Placed).who, m.k);
      }),
    );
    const pairs = now.marks.filter(isPair);
    const bonds = this.layout.bonds.map((b) => {
      const k = `${b.a}|${b.b}`;
      const hit = pairs.filter((m) => pairKey(this.cast, m) === k);
      const fresh = hit.find((m) => m.k !== Mark.Couple);
      return {
        a: b.a,
        b: b.b,
        st: fresh ? (fresh.k === Mark.Separated ? Tie.Separated : Tie.Divorced) : tie.get(k)!,
        fresh: !!fresh,
        hot: hit.some((m) => m.k === Mark.Couple),
        married: b.married,
      };
    });
    const placed = now.marks.filter(isPlaced);
    const marks: Placed[] = [];
    Object.keys(this.cast.people).forEach((id) => {
      const cur = placed.find((m) => (m.k === Mark.Up || m.k === Mark.Down) && m.who === id);
      const was = trouble.get(id);
      if (cur) marks.push({ ...cur, cls: Tone.Now });
      else if (was) marks.push({ k: was, who: id, cls: Tone.Was });
    });
    const lit = this.emphasised(now);
    // the whole family carries no one lit from an earlier date: a lifetime of
    // births would outline everyone
    const litBefore = new Set(this.whole ? [] : before.flatMap((s) => this.emphasised(s)));
    lit.forEach((who) => marks.push({ k: Mark.Emphasis, who, cls: Tone.Now }));
    litBefore.forEach((who) => lit.includes(who) || marks.push({ k: Mark.Emphasis, who, cls: Tone.Was }));
    // anxiety going down ends what was carried of it going up, until it goes up again (R-0729)
    const calmed = (who: string, from: number) =>
      [...this.steps.slice(from + 1, i + 1)].some((s) => s.marks.some((m) => m.k === Mark.AnxietyDown && (m as Placed).who === who));
    before.forEach((s, at) =>
      s.marks
        .filter(isPlaced)
        .filter((m) => m.k === Mark.FnUp || m.k === Mark.FnDown || (m.k === Mark.Anxiety && !calmed(m.who, at)))
        .forEach((m) => marks.push({ ...m, cls: Tone.Was })),
    );
    placed
      .filter((m) => m.k === Mark.FnUp || m.k === Mark.FnDown || m.k === Mark.Anxiety || m.k === Mark.AnxietyDown)
      .forEach((m) => marks.push({ ...m, cls: Tone.Now }));
    // an event's words show on its own step only, the one mark that does not
    // carry (R-0682, an exception to R-0552)
    const rows = new Map<string, number>();
    placed.forEach((m) => {
      if (m.k !== Mark.Event) return;
      const row = rows.get(m.who) ?? 0;
      rows.set(m.who, row + 1);
      marks.push({ ...m, cls: Tone.Now, row });
    });
    const moves = [
      ...before.flatMap((s) => s.marks.filter(isArrow)).map((m) => ({ ...m, cls: Tone.Was })),
      ...now.marks.filter(isArrow).map((m) => ({ ...m, cls: Tone.Now })),
    ];
    const kin = [
      ...before.flatMap((s) => s.marks.filter(isKin)).map((m) => ({ ...m, cls: Tone.Was })),
      ...now.marks.filter(isKin).map((m) => ({ ...m, cls: Tone.Now })),
    ];
    const snap = this.told.snapshots[i];
    const svg = draw(this.layout, {
      t: now.t,
      bonds,
      marks,
      died: new Set(placed.filter((m) => m.k === Mark.Died).map((m) => m.who)),
      moves,
      kin,
      label: `${now.date}: ${snap.fact}`,
      place: placeOf(now),
    });
    return {
      svg,
      who: lit[0] ?? this.about(snap.event_ids[0]),
      mover: [...now.marks.filter(isArrow), ...now.marks.filter(isKin)][0]?.from ?? null,
      // a move away runs off the far side of its mover, not toward the other
      reach: [...now.marks.filter(isArrow), ...now.marks.filter(isKin)].flatMap((m) => (m.to && m.k !== Mark.Away ? [m.to] : [])),
      couple: [...new Set(pairs.flatMap((m) => [m.a, m.b]))],
      date: now.date,
      gap: i > 0 ? gapText(this.steps[i - 1].t, now.t) : null,
      fact: snap.fact,
      guess: snap.guess,
      question: i === this.steps.length - 1 && this.told.question ? this.told.question : null,
    };
  }
}

/** The step's inside or outside, if it has one. */
const placeOf = (s: Step) => (s.marks.find((m) => m.k === Mark.Place) as Place | undefined) ?? null;

function pairKey(cast: Cast, m: Pair): string {
  const b = cast.bonds.find((b) => (b.a === m.a && b.b === m.b) || (b.a === m.b && b.b === m.a));
  if (!b) throw new Error(`no couple ${m.a} and ${m.b} in the cast`);
  return `${b.a}|${b.b}`;
}

/** The cast: you, everyone the case's events name, both partners of any couple
 * whose line changes, and the parents needed to connect them, following descent
 * through as many generations as it takes. Nobody else. */
export function castOf(r: Family, steps: Step[], events: TimelineEvent[], everyone = false, keep: string[] | null = null): Cast {
  const cast = new Set<string>(keep ?? (everyone ? r.people.keys() : [r.you]));
  if (!keep) {
    events.forEach((e) => r.named(e).forEach((id) => cast.add(id)));
    steps.forEach((s) => s.marks.forEach((m) => peopleOf(m).forEach((id) => cast.add(id))));
  }
  const ofBond = new Map(r.tl.pair_bonds.map((pb) => [pb.id, pb]));
  const up = (id: string): string[] => {
    const pb = ofBond.get(r.people.get(id)?.parents ?? -1);
    return pb ? [pb.person_a, pb.person_b].filter((p): p is number => p != null).map(key) : [];
  };
  for (let grew = !everyone && !keep; grew; ) {
    grew = false;
    const add = (id: string) => {
      if (!cast.has(id)) {
        cast.add(id);
        grew = true;
      }
    };
    const climb = (id: string, path: string[]) => {
      const of = up(id);
      const next = [...path, ...of];
      of.forEach((p) => {
        if (cast.has(p)) next.forEach(add);
        // someone recorded as their own forebear ends the climb; the picture refuses them
        if (!path.includes(p)) climb(p, next);
      });
    };
    [...cast].forEach((id) => climb(id, []));
    r.tl.pair_bonds.forEach((pb) => {
      const kids = r.tl.people.filter((p) => p.parents === pb.id && cast.has(key(p.id)));
      if (kids.length > 1) [pb.person_a, pb.person_b].forEach((p) => p != null && add(key(p)));
    });
  }
  const until = steps[steps.length - 1].t;
  const people: Record<string, Shape> = {};
  cast.forEach((id) => (people[id] = r.shape(id)));
  const bonds: Bond[] = [];
  const kids: Brood[] = [];
  const firstT = steps[0].t;
  r.tl.pair_bonds.forEach((pb) => {
    const pair = [pb.person_a, pb.person_b].filter((p): p is number => p != null).map(key);
    const inCast = pair.filter((id) => cast.has(id));
    if (pair.length === 2 && inCast.length === 2) {
      const bond = { a: pair[0], b: pair[1], ...tieBefore(r, pb, firstT), from: bondFrom(r, pb) };
      bonds.push(bond);
    }
    const children = r.tl.people.filter((p) => p.parents === pb.id && cast.has(key(p.id))).map((p) => key(p.id));
    if (children.length && inCast.length === pair.length) kids.push({ of: pair, kids: sortedIn(r, children) });
  });
  // ruled 2026-09-26: a child with one recorded parent gets the unknown partner, the spec's "?" shape
  const drawnKids = kids.map((k) => {
    if (k.of.length !== 1) return k;
    const q = `unknown-${k.of[0]}`;
    people[q] = { name: "", g: Sex.Unknown, born: null };
    bonds.push({ a: k.of[0], b: q, st: Tie.Married, married: true });
    return { of: [k.of[0], q], kids: k.kids };
  });
  const marked = new Set<string>();
  const crossed = new Set<string>();
  const words: Record<string, number> = {};
  const moves: Arrow[] = [];
  const places: Place[] = [];
  const kin: Kin[] = [];
  const anxious = new Set<string>();
  steps.forEach((s) =>
    s.marks.forEach((m) => {
      if (isArrow(m)) moves.push(m);
      // inside and outside move people in the whole family too (R-0777)
      if (m.k === Mark.Place) places.push(m as Place);
      if (isKin(m)) kin.push(m);
      if (!isPlaced(m)) return;
      if (m.k === Mark.Anxiety || m.k === Mark.AnxietyDown) anxious.add(m.who);
      if (m.k === Mark.Up || m.k === Mark.Down) crossed.add(m.who);
      if (m.k === Mark.Up || m.k === Mark.Down || m.k === Mark.Event) marked.add(m.who);
      if (m.k === Mark.Event) words[m.who] = Math.max(words[m.who] ?? 0, m.word!.length);
    }),
  );
  // someone with no family tie stands on the row of whoever they move with
  const assoc: Record<string, string> = {};
  steps
    .flatMap((s) => s.marks)
    .filter((m): m is Arrow | Kin => isArrow(m) || isKin(m))
    .forEach((m) => {
      if (!m.to) return;
      assoc[m.to] ??= m.from;
      assoc[m.from] ??= m.to;
    });
  // and failing a move, of whoever their events name them with
  events.forEach((e) => {
    const [head, ...rest] = r.named(e);
    rest.forEach((o) => {
      if (o === head) return;
      assoc[o] ??= head;
      assoc[head] ??= o;
    });
  });
  return {
    people,
    bonds,
    kids: drawnKids,
    // the reader, or when they are not drawn, the first of the people kept
    index: keep && !cast.has(r.you) ? keep[0] : r.you,
    marked: [...marked],
    cross: [...crossed],
    words,
    moves,
    places,
    kin,
    anxious: [...anxious],
    assoc,
    until,
  };
}

/** The record's order, which is the order the people were added, when any
 * birth is missing; the layout sorts by birth when all are known. */
function sortedIn(r: Family, ids: string[]): string[] {
  const order = [...r.people.keys()];
  return ids.slice().sort((a, b) => order.indexOf(a) - order.indexOf(b));
}

/** The year of a couple's first dated marriage, start, separation or divorce. */
const bondFrom = (r: Family, pb: PairBond): number | undefined =>
  r.tl.events
    .filter((e) => e.dateTime && (COUPLE_KINDS.has(e.kind ?? "") || ENDS[e.kind ?? ""]) && r.bondOf(e.person, e.spouse) === pb)
    .map((e) => Number(e.dateTime!.slice(0, 4)))
    .sort((a, b) => a - b)[0];

/** How a couple stood before the case's first snapshot, and whether they
 * married. Only the bond's own mark makes the line solid; a marriage or divorce
 * event on a couple not marked married is a fault in the record, refused here
 * as the server refuses it, never drawn solid from the event. */
export function tieBefore(r: Family, pb: PairBond, t: number): { st: Tie; married: boolean } {
  const own = r.tl.events.filter(
    (e) =>
      (e.person === pb.person_a && e.spouse === pb.person_b) ||
      (e.person === pb.person_b && e.spouse === pb.person_a),
  );
  const married = pb.married;
  const fault = own.find((e) => !married && (e.kind === EventKind.Married || e.kind === EventKind.Divorced));
  if (fault) throw new Error(`record fault: event ${fault.id} is a ${fault.kind} for a couple not marked married`);
  const last = own
    .filter((e) => ENDS[e.kind ?? ""] && e.dateTime && when(e.dateTime) < t)
    .sort((a, b) => when(a.dateTime!) - when(b.dateTime!))
    .pop();
  if (last?.kind === EventKind.Divorced) return { st: Tie.Divorced, married };
  if (last?.kind === EventKind.Separated) return { st: Tie.Separated, married };
  return { st: married ? Tie.Married : Tie.Together, married };
}

/** A play-by-play nobody told (R-0570): the dated events among `ids`, one
 * picture per date in date order, each in the events' own recorded words, with
 * no point, guess or question. What the coach's show tool and a coding open. */
export function untold(tl: Timeline, ids: number[]): Case {
  const byDate = new Map<string, TimelineEvent[]>();
  tl.events
    .filter((e) => ids.includes(e.id) && e.dateTime)
    .sort((a, b) => a.dateTime!.localeCompare(b.dateTime!))
    .forEach((e) => {
      const date = e.dateTime!.slice(0, 10);
      byDate.set(date, [...(byDate.get(date) ?? []), e]);
    });
  return {
    cluster_id: null,
    point: "",
    snapshots: [...byDate].map(([date, events]) => ({
      date,
      event_ids: events.map((e) => e.id),
      fact: events.map((e) => e.description ?? e.sentence).filter(Boolean).join(" "),
      guess: null,
    })),
    question: "",
  };
}

/** The kinds that change who is in the family or how a couple stands. */
const TURNS = new Set<string>([...BIRTHS, ...COUPLE_KINDS, ...Object.keys(ENDS), EventKind.Death]);

/** What a couple's event says they did; a couple's start is said in common words. */
const COUPLED: Record<string, string> = {
  [EventKind.Married]: "married",
  [EventKind.Bonded]: "got together",
  [EventKind.Separated]: "separated",
  [EventKind.Divorced]: "divorced",
};

/** What happened, who first, the date left to the top line: "Rose was born",
 * "Ray and June married", a shift in the record's own words after the name. */
function happened(people: Map<number, Person>, e: TimelineEvent): string {
  const name = (id: number) => {
    const p = people.get(id);
    if (!p) throw new Error(`event ${e.id} names person ${id}, who is not in the record`);
    return p.name;
  };
  const kind = e.kind ?? "";
  if (BIRTHS.has(kind) && e.child != null) return `${name(e.child)} was ${kind === EventKind.Birth ? "born" : "adopted"}`;
  if (COUPLED[kind] && e.person != null && e.spouse != null) return `${name(e.person)} and ${name(e.spouse)} ${COUPLED[kind]}`;
  if (kind === EventKind.Death && e.person != null) return `${name(e.person)} died`;
  const words = e.description ?? e.title ?? e.label;
  if (e.person == null) return words;
  // the record's words go on lower case after the name, unless they start with a name
  const lead = words.split(" ")[0];
  const named = [...people.values()].some((p) => p.name === lead);
  return `${name(e.person)} ${named || /^.[A-Z]/.test(words) ? words : words[0].toLowerCase() + words.slice(1)}`;
}

/** Where the family opens: the first date holding more than births, since
 * the early births alone show little; -1 when every date is only births
 * (R-0742, R-0775). */
export const familyStart = (tl: Timeline, c: Case): number => {
  const kinds = new Map(tl.events.map((e) => [e.id, e.kind ?? ""]));
  return c.snapshots.findIndex((s) => s.event_ids.some((id) => !BIRTHS.has(kinds.get(id)!)));
};

/** The whole family stepped through dates (R-0742): one step per date that
 * has a birth, an adoption, a couple's start or end, a death or a relationship
 * shift, in date order, each said once with who did it. */
export function family(tl: Timeline): Case {
  const people = new Map(tl.people.map((p) => [p.id, p]));
  const byId = new Map(tl.events.map((e) => [e.id, e]));
  const told = untold(
    tl,
    tl.events.filter((e) => TURNS.has(e.kind ?? "") || e.relationship).map((e) => e.id),
  );
  return {
    ...told,
    snapshots: told.snapshots.map((s) => ({
      ...s,
      fact: [...new Set(s.event_ids.map((id) => happened(people, byId.get(id)!)))].join("; "),
    })),
  };
}

/** The events a triangle is about: those naming two or more of its people. */
export function among(tl: Timeline, persons: number[]): number[] {
  const r = new Family(tl);
  const three = new Set(persons.map(key));
  return tl.events.filter((e) => r.named(e).filter((id) => three.has(id)).length >= 2).map((e) => e.id);
}
