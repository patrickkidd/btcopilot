import { arrange, Sex, Tie, type Bond, type Brood, type Cast, type Layout, type Shape } from "./diagram";
import { dateText } from "./spotlight";
import { aboutOf, Family, tieBefore, when } from "./snapshots";
import {
  CaseReportCard,
  EventKind,
  EvidenceKind,
  QuestionKind,
  type AskedQuestion,
  type PairBond,
  type Person,
  SessionKind,
  type Session,
  type Timeline,
  type TimelineEvent,
} from "./types";

/** The case report read from the record the chat screen reads (R-0711): the
 * cards in the approved proposal's order, each card's words produced from the
 * record by rule (R-0716), the coach's guesses and questions by the card the
 * coach put them on (R-0709), and the family pictures laid out by the app's
 * own layout. Nothing here draws; casereport.ts does. A record fault the
 * layout or the couple rule refuses is thrown, never covered over. */

export enum Card {
  Main = "main",
  Family = "family",
  Brought = "brought",
  Couple = "couple",
  Sides = "sides",
  Guesses = "guesses",
  OwnPart = "own_part",
  Choice = "choice",
  WorkOn = "work_on",
  Effort = "effort",
}

/** The cards in order, each the strip's item at the same place (R-0702). */
export const ORDER: Card[] = [
  Card.Main,
  Card.Family,
  Card.Brought,
  Card.Couple,
  Card.Sides,
  Card.Guesses,
  Card.OwnPart,
  Card.Choice,
  Card.WorkOn,
  Card.Effort,
];

/** The guess cards: with nothing on them they say so in the coach's bubble (R-0699). */
export const GUESS_CARDS = new Set([Card.Main, Card.Guesses, Card.OwnPart, Card.Choice, Card.WorkOn]);

/** A dated event on a chip: its date, then its words. An undated event is never a chip. */
export interface Fact {
  id: number;
  face: string;
}

/** A cluster on a chip: its years and its title. */
export interface ClusterRef {
  id: string;
  label: string;
}

export interface Who {
  id: number;
  name: string;
}

/** A coach's guess: its stored words whole, the dated facts it rests on, and
 * the people it names. */
export interface Guess {
  text: string;
  facts: Fact[];
  people: Who[];
}

/** A family standing still at today's date, as the app lays it out, or the
 * layout's own words for why it cannot. */
export interface Still {
  layout: Layout | null;
  fault: string | null;
}

/** One parent's side: one picture of the parent among their brothers and
 * sisters under their own parents, their partners joined to them (R-0733). */
export interface Side {
  label: string;
  lead: string;
  still: Still;
}

/** One stage of a couple: its date and what opened it, and the pair's own
 * dated events until the next stage. */
export interface Stage {
  /** The event that opened it, on a chip in what-it-opened words. */
  head: Fact;
  facts: Fact[];
}

export interface StageRow {
  label: string;
  stages: Stage[];
}

export interface CaseView {
  name: string;
  him: string;
  his: string;
  /** Who presents: the owner's name, or null for an account with no name. */
  owner: string | null;
  /** Today, as a year with its fraction: the date the pictures stand at. */
  now: number;
  household: Still;
  main: Guess | null;
  brought: { lead: string; first: Fact | null; latest: Fact | null; clusters: ClusterRef[]; asked: string };
  /** Married now: the picture's solid line with no later separation or divorce, both partners alive (R-0694). */
  married: boolean;
  /** The couple since they met, stage by stage (R-0833, R-0834, R-0835), and
   * what the card still needs of the floor: the marriage date, each partner's
   * place among their brothers and sisters, the children in order. */
  couple: { lead: string; stages: Stage[]; needs: string };
  stages: StageRow[];
  sides: Side[];
  guesses: Guess[];
  /** The coach's first open question on no card, asked in its bubble. */
  ask: string | null;
  ownPart: { guess: Guess | null; ask: string | null; answer: string | null };
  choice: { guess: Guess | null; ask: string | null };
  work: { aim: Fact | null; guesses: Guess[] };
  effort: string;
}

/** The most guesses the card on what to work on, and the card of the coach's guess, hold (R-0709). */
const WORK_ON_MAX = 3;
const COACH_GUESS_MAX = 3;

const SELF_DESCRIBING = new Set<string>([
  EventKind.Birth,
  EventKind.Adopted,
  EventKind.Married,
  EventKind.Separated,
  EventKind.Divorced,
  EventKind.Bonded,
  EventKind.Death,
]);
const COUPLE = new Set<string>([EventKind.Married, EventKind.Bonded, EventKind.Separated, EventKind.Divorced]);
const BIRTHS = new Set<string>([EventKind.Birth, EventKind.Adopted]);
const WEDDINGS = new Set<string>([EventKind.Bonded, EventKind.Married]);
const OPENERS = new Set<string>([...COUPLE, ...BIRTHS, EventKind.Death]);

/** The stage heads both couple cards share: a couple's own event in
 * what-it-opened words, Bowen's stages (R-0835). */
const WHAT: Record<string, string> = {
  [EventKind.Bonded]: "got together",
  [EventKind.Married]: "married",
  [EventKind.Separated]: "separated",
  [EventKind.Divorced]: "divorced",
};

/** How near, in years, another relative's event must fall to one of the
 * couple's own to be on the couple card (R-0834). */
const NEAR_YEARS = 2;

const byDate = (a: TimelineEvent, b: TimelineEvent) => a.dateTime!.localeCompare(b.dateTime!);

/** A shift that marks how someone was doing: a symptom, anxiety or functioning mark. */
const marked = (e: TimelineEvent) => e.symptom != null || e.anxiety != null || e.functioning != null;

/** Everyone an event is aimed at or stands in a triangle with. */
const aimedAt = (e: TimelineEvent) => [...e.relationshipTargets, ...e.relationshipTriangles];

/** "a", "a and b", "a, b, and c". */
const listed = (bits: string[]) => (bits.length < 3 ? bits.join(" and ") : `${bits.slice(0, -1).join(", ")}, and ${bits[bits.length - 1]}`);

/** "his", "her" or "their", and "him", "her" or "them", by the record's gender. */
function pronouns(p: Person): { him: string; his: string } {
  if (p.gender === "female") return { him: "her", his: "her" };
  if (p.gender === "male") return { him: "him", his: "his" };
  return { him: "them", his: "their" };
}

class Reader {
  readonly family: Family;
  readonly people = new Map<number, Person>();
  readonly subject: Person;
  readonly now = when(new Date().toISOString());

  constructor(readonly tl: Timeline) {
    this.family = new Family(tl);
    tl.people.forEach((p) => this.people.set(p.id, p));
    this.subject = tl.people.find((p) => p.primary)!;
  }

  name = (id: number) => this.people.get(id)?.name ?? "";

  bond = (id: number | null) => (id == null ? undefined : this.tl.pair_bonds.find((b) => b.id === id));

  /** The pair bond someone was born into, unless it holds them themself. */
  parentsOf(id: number): PairBond | undefined {
    const b = this.bond(this.people.get(id)?.parents ?? null);
    return b && b.person_a !== id && b.person_b !== id ? b : undefined;
  }

  pair = (b: PairBond) => [b.person_a, b.person_b].filter((p): p is number => p != null);

  bondsOf = (id: number) => this.tl.pair_bonds.filter((b) => b.person_a === id || b.person_b === id);

  other = (b: PairBond, id: number) => (b.person_a === id ? b.person_b : b.person_a);

  childrenOf = (b: PairBond) => this.tl.people.filter((p) => p.parents === b.id);

  dead = (id: number) => this.family.died(this.people.get(id)!) !== null;

  event = (id: number) => this.tl.events.find((e) => e.id === id);

  /** A chip's words: the date as sure as the record is, then the event's own
   * label; a self-describing event about someone else says whose it is. */
  fact(e: TimelineEvent): Fact | null {
    if (!e.dateTime) return null;
    const about = aboutOf(e);
    const whose = SELF_DESCRIBING.has(e.kind ?? "") && about !== this.subject.id && e.person_name ? `${e.person_name} · ` : "";
    return { id: e.id, face: `${dateText(e.dateTime, e.dateCertainty)} · ${whose}${e.label}` };
  }

  facts = (events: TimelineEvent[]) => events.filter((e) => e.dateTime).sort(byDate).map((e) => this.fact(e)!);

  /** How a couple stands today: the picture's own rule (snapshots.ts). */
  tie = (b: PairBond) => tieBefore(this.family, b, this.now);

  /** The people a still picture draws, laid out as the app's cast rule shapes
   * one: each couple as it stands today, and a child with one recorded parent
   * given the unknown partner (ruled 2026-09-26), around the one it is drawn for. */
  still(ids: number[], index: number): Still {
    const keys = new Set(ids.map(String));
    const people: Record<string, Shape> = {};
    keys.forEach((k) => (people[k] = this.family.shape(k)));
    const bonds: Bond[] = [];
    const kids: Brood[] = [];
    this.tl.pair_bonds.forEach((pb) => {
      const pair = this.pair(pb).map(String);
      const present = pair.filter((k) => keys.has(k));
      if (pair.length === 2 && present.length === 2) bonds.push({ a: pair[0], b: pair[1], ...this.tie(pb) });
      const children = this.tl.people.filter((p) => p.parents === pb.id && keys.has(String(p.id))).map((p) => String(p.id));
      if (!children.length || present.length !== pair.length || !pair.length) return;
      if (pair.length === 2) kids.push({ of: pair, kids: children });
      else {
        const unknown = `unknown-${pair[0]}`;
        people[unknown] = { name: "", g: Sex.Unknown, born: null };
        bonds.push({ a: pair[0], b: unknown, st: Tie.Married, married: true });
        kids.push({ of: [pair[0], unknown], kids: children });
      }
    });
    const cast: Cast = {
      people,
      bonds,
      kids,
      index: String(index),
      marked: [],
      cross: [],
      words: {},
      moves: [],
      kin: [],
      places: [],
      anxious: [],
      assoc: {},
      until: this.now,
    };
    try {
      return { layout: arrange(cast), fault: null };
    } catch (e) {
      return { layout: null, fault: (e as Error).message };
    }
  }

  /** The person, their partners now, their children, their parents with the
   * parents' other partners, and every brother, sister, half-brother and
   * half-sister. */
  household(): number[] {
    const s = this.subject.id;
    const ids = new Set<number>([s]);
    this.bondsOf(s).forEach((b) => {
      const other = this.other(b, s);
      if (other != null && this.tie(b).st !== Tie.Separated && this.tie(b).st !== Tie.Divorced) ids.add(other);
      this.childrenOf(b).forEach((c) => ids.add(c.id));
    });
    const parents = this.parentsOf(s);
    (parents ? this.pair(parents) : []).forEach((f) => {
      ids.add(f);
      this.bondsOf(f).forEach((b) => {
        const other = this.other(b, f);
        if (other != null) ids.add(other);
        this.childrenOf(b).forEach((c) => ids.add(c.id));
      });
    });
    return [...ids];
  }

  births = (ids: number[]) => ids.map((id) => this.people.get(id)!);

  died(p: Person): string {
    const e = p.death_event == null ? undefined : this.event(p.death_event);
    return e?.dateTime ? dateText(e.dateTime, e.dateCertainty) : "";
  }

  /** What brought the person: the record's own events of theirs that carry a
   * symptom, counted, the first and the latest as chips, and the clusters
   * they fall in (Patrick, 2026-10-03: no strip of its own). */
  brought(sessions: Session[]): CaseView["brought"] {
    const s = this.subject;
    const flares = this.tl.events.filter((e) => e.person === s.id && e.symptom && e.dateTime).sort(byDate);
    const ids = new Set(flares.map((e) => e.id));
    const clusters = this.tl.clusters.filter((c) => c.event_ids.some((id) => ids.has(id)));
    // dates only inside chips: the lead counts, the chips date
    return {
      lead: flares.length ? `${s.name}'s symptoms appear in ${flares.length === 1 ? "one event" : `${flares.length} events`} in the diagram.` : "",
      first: flares.length ? this.fact(flares[0]) : null,
      latest: flares.length > 1 ? this.fact(flares[flares.length - 1]) : null,
      clusters: clusters.map((c) => ({ id: c.id, label: `${c.label} · ${c.title}` })),
      asked: sessions.length ? `Who asked for help: ${s.name}, in ${pronouns(s).his} own chat with the coach.` : "",
    };
  }

  /** The person's marriage now (R-0694): the bond the picture draws solid,
   * with no later separation or divorce, and both partners alive. */
  marriage(): PairBond | undefined {
    const s = this.subject.id;
    return this.bondsOf(s).find((b) => {
      const other = this.other(b, s);
      return other != null && this.tie(b).st === Tie.Married && !this.dead(s) && !this.dead(other);
    });
  }

  /** A couple's own event: between these two (the spouse unset or one of them). */
  between = (e: TimelineEvent, pair: number[]) =>
    COUPLE.has(e.kind ?? "") && e.person != null && pair.includes(e.person) && (e.spouse == null || pair.includes(e.spouse));

  /** A stage head: the date, then what it opened. */
  head = (e: TimelineEvent, what: string): Fact => ({ id: e.id, face: `${dateText(e.dateTime!, e.dateCertainty)} · ${what}` });

  /** A chip on the couple card: whoever it is about is named unless it is the
   * person, so a partner's, a child's or a relative's event says whose it is. */
  named(e: TimelineEvent): Fact {
    const about = aboutOf(e);
    const who = about != null && about !== this.subject.id ? this.name(about) || e.person_name : "";
    return { id: e.id, face: `${dateText(e.dateTime!, e.dateCertainty)} · ${who ? `${who} · ` : ""}${e.label}` };
  }

  /** The people either partner was born beside: their parents and their
   * brothers and sisters, so the other partner's are the in-laws. */
  kinOf(pair: number[]): Set<number> {
    return new Set(
      pair.flatMap((id) => {
        const pb = this.parentsOf(id);
        return pb ? [...this.pair(pb), ...this.childrenOf(pb).map((c) => c.id).filter((c) => c !== id)] : [];
      }),
    );
  }

  /** An earlier marriage of a partner, shown as Kerr places it, before they met
   * (R-0833): one stage opened by its first dated event, holding the children
   * born to it and how it ended, dated as they are. */
  earlier(ob: PairBond): Stage | null {
    const two = this.pair(ob);
    const kids = this.childrenOf(ob).map((c) => c.id);
    const events = this.tl.events
      .filter((e) => e.dateTime && (this.between(e, two) || (BIRTHS.has(e.kind ?? "") && e.child != null && kids.includes(e.child))))
      .sort(byDate);
    if (!events.length) return null;
    const [first, ...rest] = events;
    const names = two.map(this.name).join(" and ");
    const what = WHAT[first.kind ?? ""] ? `${names} ${WHAT[first.kind!]}` : `${this.name(first.child!)} born, to ${names}`;
    return { head: this.head(first, what), facts: rest.map((e) => this.named(e)) };
  }

  /** What the couple card still needs, the floor of a couple's history: when
   * they married, where each stands among their brothers and sisters, the
   * children in order (R-0835). Nothing when the record holds all three. */
  needs(pair: number[], own: TimelineEvent[], children: number[]): string {
    const [a, b] = pair.map((id) => this.people.get(id)!);
    const bits: string[] = [];
    if (!own.some((e) => e.kind === EventKind.Married)) bits.push(`when ${a.name} and ${b.name} married`);
    const placeless = pair.filter((id) => !this.parentsOf(id)).map((id) => this.people.get(id)!);
    if (placeless.length === 2) bits.push("where each of them stands among their brothers and sisters");
    else if (placeless.length === 1) bits.push(`where ${placeless[0].name} stands among ${pronouns(placeless[0]).his} brothers and sisters`);
    if (!children.length) bits.push("the children, in order");
    return bits.length ? `This card still needs ${listed(bits)}.` : "";
  }

  /** The couple since they met. The card begins at their Bonded event, the
   * courtship, else their first event, and holds everything from then on
   * (R-0833): every event of either partner, aimed at anyone or no one; their
   * children's births, a child's marked shifts and moves while at home, and a
   * grown child's marriage; a parent's or sibling's death or serious illness
   * always, and any other relative's event only when the record ties that
   * relative to a partner and it falls within two years of an event of the
   * couple's own (R-0834); where anyone lives is no filter, since the record
   * does not hold it. An earlier marriage of either partner stands before, as
   * Kerr places it. All of it under Bowen's stage heads in date order (R-0835). */
  couple(b: PairBond): CaseView["couple"] {
    const s = this.subject.id;
    const partner = this.other(b, s)!;
    const pair = [s, partner];
    const inPair = (id: number | null) => id != null && pair.includes(id);
    const children = this.childrenOf(b).map((c) => c.id);
    const lead = `${this.subject.name} and ${this.name(partner)} are married.`;
    const dated = this.tl.events.filter((e) => e.dateTime).sort(byDate);
    const own = dated.filter((e) => this.between(e, pair));
    const births = dated.filter((e) => BIRTHS.has(e.kind ?? "") && e.child != null && children.includes(e.child));
    // a grown child's own couple: the record's nearest fact for leaving home
    const weddings = dated.filter((e) => WEDDINGS.has(e.kind ?? "") && (children.includes(e.person!) || (e.spouse != null && children.includes(e.spouse))));
    const grown = (child: number) => children.includes(child) && weddings.find((e) => e.person === child || e.spouse === child)?.dateTime;
    const start = (own.find((e) => e.kind === EventKind.Bonded) ?? own[0] ?? births[0])?.dateTime ?? null;
    const needs = this.needs(pair, own, children);
    const before = pair.flatMap((id) => this.bondsOf(id).filter((ob) => ob.id !== b.id && this.other(ob, id) != null)).map((ob) => this.earlier(ob));
    const at = (st: Stage) => this.event(st.head.id)!.dateTime!;
    const sorted = (stages: Stage[]) => stages.sort((p, q) => at(p).localeCompare(at(q)));
    if (!start) return { lead, stages: sorted(before.filter((st): st is Stage => !!st)), needs };
    const since = (e: TimelineEvent) => e.dateTime! >= start;
    const kin = this.kinOf(pair);
    const theirs = dated.filter((e) => since(e) && inPair(e.person) && !COUPLE.has(e.kind ?? "") && !BIRTHS.has(e.kind ?? ""));
    const kids = dated.filter((e) => {
      const who = e.person;
      if (!since(e) || who == null || !children.includes(who) || WEDDINGS.has(e.kind ?? "")) return false;
      const left = grown(who);
      if (left && e.dateTime! >= left) return false;
      return (e.kind === EventKind.Shift && marked(e)) || (e.kind === EventKind.Noted && !!e.location) || e.kind === EventKind.Death;
    });
    // the couple's own events, which the two-year window is measured from (R-0834): got together,
    // married, separated or divorced, each child's birth, each child's marriage; never a partner's or
    // a child's own shifts and moves
    const couples = [...own, ...births, ...weddings];
    const taken = new Set([...couples, ...theirs, ...kids]);
    const near = (e: TimelineEvent) => couples.some((o) => Math.abs(when(o.dateTime!) - when(e.dateTime!)) <= NEAR_YEARS);
    const tied = (id: number) => this.tl.events.some((x) => (x.person === id && aimedAt(x).some(inPair)) || (inPair(x.person) && aimedAt(x).includes(id)));
    const others = dated.filter((e) => {
      const who = e.person;
      if (!since(e) || who == null || inPair(who) || children.includes(who) || taken.has(e)) return false;
      if (kin.has(who) && (e.kind === EventKind.Death || (e.kind === EventKind.Shift && e.symptom != null))) return true;
      return tied(who) && near(e);
    });
    const heads = [
      ...own.map((e) => ({ e, what: WHAT[e.kind!] })),
      ...births.map((e) => ({ e, what: `${this.name(e.child!)} born` })),
      ...weddings.map((e) => ({ e, what: `${this.name(children.includes(e.person!) ? e.person! : e.spouse!)} ${WHAT[e.kind!]}` })),
    ].sort((p, q) => byDate(p.e, q.e));
    const chips = [...theirs, ...kids, ...others].sort(byDate);
    const stages = heads.map(({ e, what }, i) => {
      const next = heads[i + 1]?.e.dateTime;
      const under = chips.filter((c) => (i === 0 || c.dateTime! >= e.dateTime!) && (!next || c.dateTime! < next));
      return { head: this.head(e, what), facts: under.map((c) => this.named(c)) };
    });
    return { lead, stages: sorted([...before.filter((st): st is Stage => !!st), ...stages]), needs };
  }

  /** A couple's stages, each opened by a date the record holds: got together,
   * married, a child born, separated, divorced, a death of either. */
  stagesOf(b: PairBond): Stage[] {
    const pair = this.pair(b);
    const children = new Set(this.childrenOf(b).map((c) => c.id));
    const openers = this.tl.events
      .filter((e) => e.dateTime)
      .flatMap((e): { e: TimelineEvent; what: string }[] => {
        if (WHAT[e.kind ?? ""] && pair.includes(e.person!) && e.spouse != null && pair.includes(e.spouse)) return [{ e, what: WHAT[e.kind!] }];
        if ((e.kind === EventKind.Birth || e.kind === EventKind.Adopted) && e.child != null && children.has(e.child))
          return [{ e, what: `${this.name(e.child)} born` }];
        if (e.kind === EventKind.Death && e.person != null && pair.includes(e.person)) return [{ e, what: `${this.name(e.person)} died` }];
        return [];
      })
      .sort((p, q) => byDate(p.e, q.e));
    const theirs = this.tl.events
      .filter((e) => e.dateTime && e.person != null && pair.includes(e.person) && !OPENERS.has(e.kind ?? ""))
      .sort(byDate);
    return openers.map(({ e, what }, i) => {
      const next = openers[i + 1]?.e.dateTime;
      const under = theirs.filter((t) => t.dateTime! >= e.dateTime! && (!next || t.dateTime! < next));
      return { head: { id: e.id, face: `${dateText(e.dateTime!, e.dateCertainty)} · ${what}` }, facts: under.map((t) => this.fact(t)!) };
    });
  }

  /** The person's parents and partners, stage by stage: the couple they were
   * born to first, then their own, in the order they began. */
  stages(): StageRow[] {
    const s = this.subject;
    const born = this.parentsOf(s.id);
    const rows: StageRow[] = [];
    if (born && this.pair(born).length === 2) {
      const [a, b] = this.pair(born).map(this.name);
      rows.push({ label: `${a} and ${b}, ${pronouns(s).his} parents`, stages: this.stagesOf(born) });
    }
    this.bondsOf(s.id)
      .filter((b) => this.other(b, s.id) != null)
      .map((b) => ({ label: `${s.name} and ${this.name(this.other(b, s.id)!)}`, stages: this.stagesOf(b) }))
      .sort((p, q) => (this.event(p.stages[0]?.head.id)?.dateTime ?? "").localeCompare(this.event(q.stages[0]?.head.id)?.dateTime ?? ""))
      .forEach((row) => rows.push(row));
    return rows.filter((row) => row.stages.length);
  }

  /** A parent in a few words, beside what the pictures under it draw: whether
   * they have died, and how much the record holds about the people on this
   * side. The dates are on the pictures and the chips, never in the words. */
  personLine(p: Person, side: number[]): string {
    const bits = this.died(p) ? ["who has died"] : [];
    const told = this.tl.events.filter((e) => e.dateTime && !OPENERS.has(e.kind ?? "") && e.person != null && side.includes(e.person));
    const held = told.length ? ` The diagram holds ${told.length === 1 ? "one event" : `${told.length} events`} about this side of the family.` : "";
    return bits.length || held ? `${p.name}${bits.length ? `, ${bits.join(", ")}` : ""}.${held}` : "";
  }

  /** Each parent's own family, one picture a side: the parent's parents and
   * their children, and the parent's partners joined to the parent, the other
   * parent among them, so no one is drawn twice (R-0733). A partner's own
   * parents are on no side's picture. */
  sides(): Side[] {
    const s = this.subject;
    const pb = this.parentsOf(s.id);
    if (!pb) return [];
    const { his } = pronouns(s);
    const His = his[0].toUpperCase() + his.slice(1);
    return this.pair(pb)
      .map((id) => this.people.get(id)!)
      .sort((a, b) => (a.gender === "male" ? 0 : 1) - (b.gender === "male" ? 0 : 1))
      .map((parent) => {
        const role = parent.gender === "female" ? "mother" : parent.gender === "male" ? "father" : "parent";
        const up = this.parentsOf(parent.id);
        const kin = new Set<number>([parent.id, ...(up ? [...this.pair(up), ...this.childrenOf(up).map((c) => c.id)] : [])]);
        const partners = this.bondsOf(parent.id)
          .map((b) => this.other(b, parent.id))
          .filter((id): id is number => id != null);
        return {
          label: `${His} ${role}'s side`,
          lead: this.personLine(parent, [...kin]),
          still: this.still([...kin, ...partners], parent.id),
        };
      });
  }

  /** A guess as the case report shows it: the stored words whole, the dated
   * events it rests on as chips, and everyone it names but the person. */
  guess(q: AskedQuestion): Guess {
    const events = q.evidence
      .filter((one) => one.kind === EvidenceKind.Event)
      .map((one) => this.event(Number(one.id)))
      .filter((e): e is TimelineEvent => !!e);
    const named = [
      ...q.evidence.filter((one) => one.kind === EvidenceKind.Person).map((one) => Number(one.id)),
      ...events.flatMap((e) => [e.person, e.spouse, e.child, ...e.relationshipTargets, ...e.relationshipTriangles]),
    ].filter((id): id is number => id != null && id !== this.subject.id && this.people.has(id));
    return {
      text: q.text,
      facts: this.facts(events),
      people: [...new Set(named)].map((id) => ({ id, name: this.name(id) })),
    };
  }
}

const open = (q: AskedQuestion) => q.open;
const isGuess = (q: AskedQuestion) => q.kind === QuestionKind.Impression;
const onCard = (card: CaseReportCard | null) => (q: AskedQuestion) => q.case_report_card === card;

/** The card's newest guess or question: the coach's newest replaces the one
 * before (R-0709), so a stale second is never shown. */
const newest = (all: AskedQuestion[]) => all[all.length - 1] ?? null;

export function caseView(tl: Timeline, sessions: Session[], owner: string | null): CaseView {
  const r = new Reader(tl);
  const s = r.subject;
  // a note or a recording is not the person talking with the coach
  const chats = sessions.filter((one) => one.kind === SessionKind.Chat);
  const asked = tl.asked_questions;
  const guesses = asked.filter((q) => open(q) && isGuess(q));
  const questions = asked.filter((q) => !isGuess(q));
  const guessOn = (card: CaseReportCard) => newest(guesses.filter(onCard(card)));
  const askOn = (card: CaseReportCard) => newest(questions.filter((q) => open(q) && onCard(card)(q)))?.text ?? null;
  const main = guessOn(CaseReportCard.MainGuess);
  const own = guessOn(CaseReportCard.OwnPart);
  const choice = guessOn(CaseReportCard.Choice);
  const workOn = guesses.filter(onCard(CaseReportCard.WorkOn)).slice(-WORK_ON_MAX);
  const work = workOn.map((q) => r.guess(q));
  // what the person said they are working on: the first guess's first evidence (the coach's prompt)
  const said = workOn[0]?.evidence[0];
  const aimed = said?.kind === EvidenceKind.Event ? r.event(Number(said.id)) : undefined;
  const answered = newest(questions.filter((q) => onCard(CaseReportCard.OwnPart)(q) && q.answer?.text));
  const wed = r.marriage();
  const { him, his } = pronouns(s);
  return {
    name: s.name,
    him,
    his,
    owner,
    now: r.now,
    household: r.still(r.household(), s.id),
    main: main && r.guess(main),
    brought: r.brought(chats),
    married: !!wed,
    couple: wed ? r.couple(wed) : { lead: "", stages: [], needs: "" },
    stages: wed ? [] : r.stages(),
    sides: r.sides(),
    // only what the coach chose for this card, never every guess it holds (Patrick, 2026-10-04)
    guesses: guesses.filter(onCard(CaseReportCard.CoachGuess)).slice(-COACH_GUESS_MAX).map((q) => r.guess(q)),
    ask: questions.find((q) => open(q) && onCard(null)(q))?.text ?? null,
    ownPart: { guess: own && r.guess(own), ask: answered ? null : askOn(CaseReportCard.OwnPart), answer: answered?.answer?.text ?? null },
    choice: { guess: choice && r.guess(choice), ask: askOn(CaseReportCard.Choice) },
    work: { aim: aimed ? r.fact(aimed) : null, guesses: work },
    effort: chats.length
      ? `${s.name} has talked with the coach in ${chats.length === 1 ? "one session" : `${chats.length} sessions`}.`
      : "",
  };
}
