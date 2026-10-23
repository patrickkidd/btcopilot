import { arrange, Sex, Tie, type Bond, type Brood, type Cast, type Layout, type Shape } from "./diagram";
import { DateCertainty } from "./certainty";
import { dateText } from "./spotlight";
import { aboutOf, Family, tieBefore, when } from "./snapshots";
import {
  CardLine,
  CaseReportCard,
  ClusterSource,
  EventKind,
  EvidenceKind,
  QuestionKind,
  type AskedQuestion,
  type Cluster,
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
 * layout refuses is thrown, never covered over. */

export enum Card {
  Main = "main",
  Family = "family",
  Brought = "brought",
  Couple = "couple",
  Sides = "sides",
  Guesses = "guesses",
  OwnPart = "own_part",
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
  Card.WorkOn,
  Card.Effort,
];

/** A period's name without the years the server ends an app period's name
 * with, "When Lily came, 2009\u20132011", for a screen that writes those
 * years beside it, so they are written once (R-0853). */
export const nameOnly = (c: { title: string; label?: string }) =>
  c.label && c.title.endsWith(`, ${c.label}`) ? c.title.slice(0, -c.label.length - 2) : c.title;

/** A period on a chip: its name, then the years the server stored for it,
 * "When Lily came \u00b7 2009\u20132011"; a period with no name of its own has its
 * years as its title, and they are written once (R-0853). */
export const periodName = (c: Pick<Cluster, "title" | "label">) => {
  const name = nameOnly(c);
  return name !== c.label ? `${name} \u00b7 ${c.label}` : c.label;
};

/** How the coach opens a card the diagram holds too little for, before what it still needs (R-0850). */
export const TOO_LITTLE = "Not enough in the diagram yet";
const LITTLE = new RegExp(`^${TOO_LITTLE}[:.]?\\s*(.*?)\\.?$`, "s");

/** The guess cards: with nothing on them they say so in the coach's bubble (R-0699). */
export const GUESS_CARDS = new Set([Card.Main, Card.Family, Card.Couple, Card.Sides, Card.Guesses, Card.OwnPart, Card.WorkOn]);

/** A dated event on a chip: its date, then its words. An undated event is never a chip. */
export interface Fact {
  id: number;
  face: string;
  /** The date is marked certain; an approximate or unknown one is drawn as the
   * picture draws it, hollow (R-0855). */
  sure: boolean;
}

/** One dated event's chip, the date as sure as the record is. */
const dated = (e: TimelineEvent, words: string): Fact => ({
  id: e.id,
  face: `${dateText(e.dateTime!, e.dateCertainty, e.datePrecision)} · ${words}`,
  sure: e.dateCertainty === DateCertainty.Certain,
});

/** A cluster on a chip: its years and its title. */
export interface ClusterRef {
  id: string;
  label: string;
}

export interface Who {
  id: number;
  name: string;
}

/** What holds for and against one cluster, in the coach's words. */
export interface Slot {
  for: string | null;
  against: string | null;
}

/** A coach's guess: its words before any marked line, the dated facts, the
 * people and the clusters it rests on, the person's message it quotes, and
 * its marked lines (R-0850). */
export interface Guess {
  text: string;
  facts: Fact[];
  people: Who[];
  /** The people its chips show: those the coach cited, and those of its events its words name. */
  shown: Who[];
  clusters: ClusterRef[];
  /** Whose words and when, as the message it rests on is labelled: "You said, 21 Sep". */
  said: string | null;
  slots: Record<string, Slot>;
  open: string | null;
  other: string | null;
  prognosis: string | null;
  aim: string | null;
}

/** A cluster on the coach's guess: its chip, whether it is the person's own
 * period, and what holds for and against it. */
export interface Held extends ClusterRef, Slot {
  mine: boolean;
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
  still: Still;
}

/** A card the coach writes as one statement: its words with the facts and
 * people it rests on, or what the diagram still needs when it holds too
 * little for one (R-0850). */
export interface Stated {
  guess: Guess | null;
  needs: string | null;
}

/** The coach's statement on one parent's own family, under that side's name,
 * or under none when the diagram names no parents (R-0866). */
export interface SideNote {
  label: string | null;
  note: Stated;
}

export interface CaseView {
  name: string;
  him: string;
  his: string;
  /** Whose case it is, by first name: the person it belongs to, never the
   * account that owns the diagram (FD-387); null while they have no name. */
  owner: string | null;
  /** Today, as a year with its fraction: the date the pictures stand at. */
  now: number;
  household: Still;
  main: Guess | null;
  /** The coach's lines on the households the person grew up in and lives in now (R-0866). */
  family: Stated;
  /** The coach's card on what brought the person (R-0850), or null when not asked yet. */
  brought: Guess | null;
  /** Whether the person has a pair-bond of their own (R-0866). */
  bonded: boolean;
  /** The coach's one statement on the person's own couple from its early years,
   * and what the diagram still needs when it holds too little for one (R-0850). */
  couple: Stated;
  /** The pictures of each parent's side, for the family picture. */
  sides: Side[];
  /** The coach's statement on each parent's side, told apart by the people it rests on (R-0866). */
  sideNotes: SideNote[];
  /** The coach's one pattern statement (R-0850). */
  guess: Guess | null;
  /** Every stored cluster in date order, worded as the hypothesis it is (R-0698, R-0841), with its for and against. */
  hypotheses: Held[];
  /** The coach's first open question on no card, asked in its bubble. */
  ask: string | null;
  ownPart: { guess: Guess | null; ask: string | null; answer: string | null };
  /** The aim in the person's words, or the event the coach rested it on. */
  work: { aim: Fact | null; said: string | null; guesses: Guess[] };
  effort: string;
}

/** The most guesses the card on what to work on holds (R-0709). */
const WORK_ON_MAX = 3;
/** The notes each parent's family holds, one a side (R-0866). */
const SIDE_NOTES = 2;

const MARKS = Object.values(CardLine).join("|");
/** "For c3: ..." or "Open: ...": a marked line of a card (R-0850). */
const MARKED = new RegExp(`^(${MARKS})(?: (\\S+))?:\\s*(.*)$`);

const SELF_DESCRIBING = new Set<string>([
  EventKind.Birth,
  EventKind.Adopted,
  EventKind.Married,
  EventKind.Separated,
  EventKind.Divorced,
  EventKind.Bonded,
  EventKind.Death,
]);

const byDate = (a: TimelineEvent, b: TimelineEvent) => a.dateTime!.localeCompare(b.dateTime!);

/** "his", "her" or "their", and "him", "her" or "them", by the record's gender. */
function pronouns(p: Person): { him: string; his: string } {
  if (p.gender === "female") return { him: "her", his: "her" };
  if (p.gender === "male") return { him: "him", his: "his" };
  return { him: "them", his: "their" };
}

/** What someone is to the person, as the cards say it: her word, his word,
 * a word for either and a word for the group (R-0850). */
type Kin = [string, string, string, string];
const PARENT: Kin = ["mother", "father", "parent", "parents"];
const GRANDPARENT: Kin = ["grandmother", "grandfather", "grandparent", "grandparents"];
const SIBLING: Kin = ["sister", "brother", "sibling", "siblings"];
const AUNT: Kin = ["aunt", "uncle", "", ""];
const PARTNER: Kin = ["wife", "husband", "partner", "spouse"];
const CHILD: Kin = ["daughter", "son", "child", "children"];

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

  /** What each of the person's close family is to them, in the words a card names them by. */
  private kinWords?: Map<number, string[]>;
  kin(id: number): string[] {
    if (this.kinWords) return this.kinWords.get(id) ?? [];
    const words = (this.kinWords = new Map<number, string[]>());
    const add = (ids: number[], [her, him, either, all]: Kin) =>
      ids.forEach((i) => {
        const g = this.people.get(i)?.gender;
        const own = g === "female" ? [her, `${her}s`] : g === "male" ? [him, `${him}s`] : [her, him];
        words.set(i, [...(words.get(i) ?? []), ...own, either, all].filter(Boolean));
      });
    const s = this.subject.id;
    const kids = (b: PairBond | undefined, but: number) => (b ? this.childrenOf(b).map((c) => c.id).filter((c) => c !== but) : []);
    const parents = this.parentsOf(s);
    const pair = parents ? this.pair(parents) : [];
    add(pair, PARENT);
    add([...new Set(pair.flatMap((p) => this.bondsOf(p).flatMap((b) => kids(b, s))))], SIBLING);
    pair.forEach((p) => {
      const up = this.parentsOf(p);
      add(up ? this.pair(up) : [], GRANDPARENT);
      add(kids(up, p), AUNT);
    });
    this.bondsOf(s).forEach((b) => {
      const other = this.other(b, s);
      add(other == null ? [] : [other], PARTNER);
      add(kids(b, s), CHILD);
    });
    return words.get(id) ?? [];
  }

  /** A chip's words: the date as sure as the record is, then the event's own
   * label; a self-describing event about someone else says whose it is. */
  fact(e: TimelineEvent): Fact | null {
    if (!e.dateTime) return null;
    const about = aboutOf(e);
    const whose = SELF_DESCRIBING.has(e.kind ?? "") && about !== this.subject.id && e.person_name ? `${e.person_name} · ` : "";
    return dated(e, `${whose}${e.label}`);
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

  /** Each parent's own family, one picture a side: the parent's parents and
   * their children, and the parent's partners joined to the parent, the other
   * parent among them, so no one is drawn twice (R-0733). A partner's own
   * parents are on no side's picture. */
  sides(): (Side & { parent: Person })[] {
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
        return { parent, label: `${His} ${role}'s side`, still: this.still([...kin, ...partners], parent.id) };
      });
  }

  /** The people of one parent's own family: the parent, everyone above them,
   * and everyone descended from those above but the parent's own children. */
  lineage(id: number): Set<number> {
    const above = (p: number): number[] => {
      const b = this.parentsOf(p);
      return b ? this.pair(b).flatMap((a) => [a, ...above(a)]) : [];
    };
    const below = (p: number): number[] => this.bondsOf(p).flatMap((b) => this.childrenOf(b).flatMap((c) => [c.id, ...below(c.id)]));
    const side = new Set<number>(above(id).flatMap((a) => [a, ...below(a)]));
    below(id).forEach((d) => side.delete(d));
    return side.add(id);
  }

  /** A card's one statement, or what the diagram still needs for it. */
  stated(q: AskedQuestion | null): Stated {
    const little = q && LITTLE.exec(q.text.trim());
    return { guess: q && !little ? this.guess(q) : null, needs: little ? little[1] : null };
  }

  /** The coach's notes on each parent's family put under the side whose
   * people they rest on, never by a word in their text; the newest note on a
   * side wins, and a note whose people point to neither side, or to both,
   * takes a side left open in the order the coach writes them, the mother's
   * first (R-0866). */
  sideNotes(notes: AskedQuestion[]): SideNote[] {
    const sides = this.sides();
    if (!sides.length) return notes.map((q) => ({ label: null, note: this.stated(q) }));
    const lines = sides.map((s) => this.lineage(s.parent.id));
    const placed = new Map<number, AskedQuestion>();
    const loose: AskedQuestion[] = [];
    for (const q of [...notes].reverse()) {
      const named = new Set(this.guess(q).people.map((p) => p.id));
      const counts = lines.map((line) => [...named].filter((id) => line.has(id)).length);
      const most = Math.max(...counts);
      const at = most > 0 && counts.filter((n) => n === most).length === 1 ? counts.indexOf(most) : -1;
      if (at < 0) loose.unshift(q);
      else if (!placed.has(at)) placed.set(at, q);
    }
    const later = (i: number) => (sides[i].parent.gender === "female" ? 0 : 1);
    const mothersFirst = sides.map((_, i) => i).sort((a, b) => later(a) - later(b));
    for (const q of loose) {
      const open = mothersFirst.find((i) => !placed.has(i));
      if (open !== undefined) placed.set(open, q);
    }
    return sides.map((s, i) => ({ label: s.label, note: this.stated(placed.get(i) ?? null) }));
  }

  /** A guess as the case report shows it: the stored words whole, the dated
   * events it rests on as chips, and everyone it names but the person. */
  guess(q: AskedQuestion): Guess {
    const lines = q.text.split("\n");
    const body: string[] = [];
    const g = { slots: {} as Record<string, Slot>, open: null as string | null, other: null as string | null, prognosis: null as string | null, aim: null as string | null };
    for (const line of lines) {
      const m = MARKED.exec(line);
      if (!m) {
        body.push(line);
        continue;
      }
      const [, mark, id, words] = m;
      if (mark === CardLine.For || mark === CardLine.Against) {
        const slot = (g.slots[id] ??= { for: null, against: null });
        slot[mark === CardLine.For ? "for" : "against"] = words;
      } else if (mark === CardLine.Open) g.open = words;
      else if (mark === CardLine.OtherWay) g.other = words;
      else if (mark === CardLine.Prognosis) g.prognosis = words;
      else g.aim = words;
    }
    const clusters = q.evidence
      .filter((one) => one.kind === EvidenceKind.Cluster)
      .map((one) => this.tl.clusters.find((c) => c.id === String(one.id)))
      .filter((c): c is NonNullable<typeof c> => !!c)
      .map((c) => ({ id: c.id, label: periodName(c) }));
    const events = q.evidence
      .filter((one) => one.kind === EvidenceKind.Event)
      .map((one) => this.event(Number(one.id)))
      .filter((e): e is TimelineEvent => !!e);
    const someone = (id: number | null): id is number => id != null && id !== this.subject.id && this.people.has(id);
    const cited = q.evidence.filter((one) => one.kind === EvidenceKind.Person).map((one) => Number(one.id)).filter(someone);
    const around = events.flatMap((e) => [e.person, e.spouse, e.child, ...e.relationshipTargets, ...e.relationshipTriangles]).filter(someone);
    const text = body.join("\n").trim();
    const who = (ids: number[]) => [...new Set(ids)].map((id) => ({ id, name: this.name(id) }));
    return {
      text,
      facts: this.facts(events),
      people: who([...cited, ...around]),
      shown: who([...cited, ...around.filter((id) => names(text, [this.name(id)], "u") || names(text, this.kin(id), "iu"))]),
      clusters,
      said: q.evidence.find((one) => one.kind === EvidenceKind.Statement)?.label || null,
      ...g,
    };
  }
}

/** Whether the words name someone by any of these, each as a whole word. */
function names(text: string, words: string[], flags: string): boolean {
  const any = words.filter(Boolean).map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  return any.length > 0 && new RegExp(`(?<![\\p{L}\\p{N}])(?:${any.join("|")})(?![\\p{L}\\p{N}])`, flags).test(text);
}

const open = (q: AskedQuestion) => q.open;
const isGuess = (q: AskedQuestion) => q.kind === QuestionKind.Impression;
const onCard = (card: CaseReportCard | null) => (q: AskedQuestion) => q.case_report_card === card;

/** The card's newest guess or question: the coach's newest replaces the one
 * before (R-0709), so a stale second is never shown. */
const newest = (all: AskedQuestion[]) => all[all.length - 1] ?? null;

/** The person the case belongs to, by first name, for the header; null while
 * the diagram holds only the chat app's placeholder. */
export function subjectName(tl: Timeline): string | null {
  const name = tl.people.find((p) => p.primary)?.name;
  return name && name !== "User" ? name : null;
}

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
  const brought = guessOn(CaseReportCard.WhatBrought);
  const coach = guessOn(CaseReportCard.CoachGuess);
  const pattern = coach && r.guess(coach);
  const workOn = guesses.filter(onCard(CaseReportCard.WorkOn)).slice(-WORK_ON_MAX);
  const work = workOn.map((q) => r.guess(q));
  // what the person said they are working on: the first guess's first evidence (the coach's prompt)
  const said = workOn[0]?.evidence[0];
  const aimed = said?.kind === EvidenceKind.Event ? r.event(Number(said.id)) : undefined;
  const aim = [...work].reverse().find((g) => g.aim)?.aim ?? null;
  const answered = newest(questions.filter((q) => onCard(CaseReportCard.OwnPart)(q) && q.answer?.text));
  const { him, his } = pronouns(s);
  return {
    name: s.name,
    him,
    his,
    owner,
    now: r.now,
    household: r.still(r.household(), s.id),
    main: main && r.guess(main),
    family: r.stated(guessOn(CaseReportCard.Family)),
    brought: brought && r.guess(brought),
    bonded: r.bondsOf(s.id).length > 0,
    couple: r.stated(guessOn(CaseReportCard.Couple)),
    sides: r.sides().map(({ label, still }) => ({ label, still })),
    sideNotes: r.sideNotes(guesses.filter(onCard(CaseReportCard.Sides)).slice(-SIDE_NOTES)),
    // only what the coach chose for this card, never every guess it holds (Patrick, 2026-10-04)
    guess: pattern,
    hypotheses: [...tl.clusters]
      .sort((a, b) => a.start.localeCompare(b.start))
      .map((c) => {
        const mine = c.source === ClusterSource.User;
        const slot = pattern?.slots[c.id];
        const named = periodName(c);
        return { id: c.id, label: mine ? `Your suggestion: ${named}` : `Hypothesis: ${named}`, mine, for: slot?.for ?? null, against: slot?.against ?? null };
      }),
    ask: pattern?.open ?? questions.find((q) => open(q) && onCard(null)(q))?.text ?? null,
    ownPart: { guess: own && r.guess(own), ask: answered ? null : askOn(CaseReportCard.OwnPart), answer: answered?.answer?.text ?? null },
    work: { aim: !aim && aimed ? r.fact(aimed) : null, said: aim, guesses: work },
    effort: chats.length
      ? `${s.name} has talked with the coach in ${chats.length === 1 ? "one session" : `${chats.length} sessions`}.`
      : "",
  };
}
