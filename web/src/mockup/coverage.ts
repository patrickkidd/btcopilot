import type { Ref } from "../case";
import { EventKind } from "../types";
import { known, type CEvent, type CPerson, type CQuestion, type QuestionsFile } from "./casefile";
import { dated, fullDate } from "./dates";
import { labelOf, nameOf, pkey, restsOf, type Model } from "./model";

/** What the record covers, read from the whole record (Patrick, 2026-10-02: it
 * is critical that nothing implies we know more than we do; the coordinator,
 * 2026-10-02: the coverage visuals measure the whole record, never a
 * selection). Three things are counted and never guessed: how much the record
 * holds of each person, which years hold a dated fact, and what each guess on
 * the page rests on. A guess has enough to stand on when it rests on two or
 * more dated facts and the record tells something that happened to every
 * person it names; otherwise the page says "not enough in the record". The one
 * gap drawn is the record's own structure: a parent whose own parents' couple
 * has one child in the record and whom the coach has not asked about brothers
 * and sisters. An open question bears on a guess only when the record attaches
 * it to one of the guess's own facts or people. No person is invented. */

/** How much the record holds of a person: something that happened to them
 * (an event of their own that is not a birth, a death or a couple's date),
 * only dates or a mention in someone else's event, or a name alone. */
export type Tier = "story" | "dates" | "name";

export interface PersonCover {
  id: string;
  /** The app's id for the same person. */
  key: string;
  name: string;
  sex: CPerson["sex"];
  tier: Tier;
  story: number;
  dated: number;
  named: number;
  /** The record's dates in a few words. */
  dates: string;
}

export interface YearCell {
  year: number;
  n: number;
  /** The dated facts of that year, each in the record's words. */
  labels: string[];
}

export interface Run {
  from: number;
  to: number;
}

/** The years from the record's first dated fact to its last date, a cell each. */
export interface Band {
  from: number;
  to: number;
  cells: YearCell[];
  birth: number | null;
  /** The longest run of years with nothing, within the person's life. */
  empty: Run | null;
  /** Every run of years with nothing, within the person's life. */
  runs: Run[];
  emptyYears: number;
  lifeYears: number;
}

export interface GridSide {
  key: string;
  label: string;
}

/** A dashed place in the family where the record holds nobody: a parent's
 * brothers and sisters, where the parent's own parents have one child in the
 * record and the coach has not asked. */
export interface Slot {
  id: string;
  who: string;
  rel: "parent" | "sibling";
  /** Two lines: whose, and which relation. */
  role: [string, string];
  /** The open question that asks about them, where the record holds one. */
  question: CQuestion | null;
  gen: number;
  side: string;
}

export interface GridCell {
  /** Null for a person the record links to no one in the family. */
  gen: number | null;
  side: string;
  person?: PersonCover;
  slot?: Slot;
}

export interface Grid {
  sides: GridSide[];
  gens: { gen: number | null; label: string }[];
  cells: GridCell[];
}

/** What a guess rests on and how far the record reaches around it. */
export interface GuessCover {
  ids: string[];
  /** The dated facts, oldest first. */
  events: CEvent[];
  dated: number;
  years: string | null;
  people: PersonCover[];
  enough: boolean;
  why: string | null;
  /** The open tracked questions the record attaches to one of these facts or people. */
  bears: CQuestion[];
  clusters: string[];
}

export interface PartCover {
  id: string;
  text: string;
  rests: Ref[];
  cover: GuessCover;
  /** The page's one wording rule left this line off (it says what caused
   * what): it is counted among the reading's lines and shown as left off, its
   * words and its evidence never shown (Patrick, 2026-10-02: a count of lines
   * resting on facts counts every line). */
  off: boolean;
}

/** How a lower level ties to the reading: the cluster of the line it shares a dated fact with. */
export interface Tie {
  level: number;
  cluster: string | null;
  part: string | null;
}

export interface Coverage {
  people: PersonCover[];
  byId: Map<string, PersonCover>;
  /** The same, by the app's id. */
  byKey: Map<string, PersonCover>;
  band: Band;
  grid: Grid;
  slots: Slot[];
  questions: CQuestion[];
  open: CQuestion[];
  impressions: number;
  parts: PartCover[];
  ownPart: GuessCover;
  workOn: GuessCover;
  effort: GuessCover | null;
  /** At least one line of the reading has enough to stand on; every line has. */
  chosen: boolean;
  all: boolean;
  ties: Tie[];
  counts: { people: number; story: number; open: number; emptyYears: number; lifeYears: number; birth: number | null };
}

type M = Model;

const COUPLE = new Set<string>([EventKind.Married, EventKind.Bonded, EventKind.Separated, EventKind.Divorced]);
const BIRTH_DEATH = new Set<string>([EventKind.Birth, EventKind.Death, EventKind.Adopted]);
const BOND_FIELDS = ["bonded", "married", "separated", "divorced"] as const;

const year = (d: string | null | undefined): number | null => {
  const x = dated(d);
  return x ? Number(x.iso.slice(0, 4)) : null;
};

function datesOf(p: CPerson): string {
  const bits: string[] = [];
  if (known(p.birth)) bits.push(`born ${fullDate(dated(p.birth)!)}`);
  if (known(p.death)) bits.push(`died ${fullDate(dated(p.death)!)}`);
  return bits.join("; ");
}

/** How much the record holds of each person. */
function coverPeople(m: M): PersonCover[] {
  return m.file.people.map((p) => {
    const own = m.file.events.filter((e) => m.dates.get(e.id) && e.person === p.id);
    const story = own.filter((e) => !COUPLE.has(e.kind) && !BIRTH_DEATH.has(e.kind)).length;
    const couple = m.file.events.filter((e) => m.dates.get(e.id) && COUPLE.has(e.kind) && e.others.includes(p.id)).length;
    const bondDates = [...m.bonds.values()].filter((b) => b.a === p.id || b.b === p.id).flatMap((b) => BOND_FIELDS.filter((f) => known(b[f]))).length;
    const dates = (known(p.birth) ? 1 : 0) + (known(p.death) ? 1 : 0) + own.length + couple + bondDates;
    const named = m.file.events.filter((e) => e.person !== p.id && !COUPLE.has(e.kind) && e.others.includes(p.id)).length;
    const tier: Tier = story ? "story" : dates || named ? "dates" : "name";
    return { id: p.id, key: pkey(p.id), name: p.name, sex: p.sex, tier, story, dated: dates, named, dates: datesOf(p) };
  });
}

/** Every dated fact of the record by year: the app's line holds each once
 * (the record's events, with a death or a couple's date the file holds as a
 * date alone added by the model). */
function band(m: M): Band {
  const facts = m.tl.events.filter((e) => e.dateTime);
  const to = Number(dated(m.page.recordEnd)!.iso.slice(0, 4));
  const years = facts.map((e) => Number(e.dateTime!.slice(0, 4)));
  const from = years.length ? Math.min(...years) : to;
  const cells: YearCell[] = [];
  for (let y = from; y <= to; y++) {
    const own = facts.filter((e) => Number(e.dateTime!.slice(0, 4)) === y);
    cells.push({ year: y, n: own.length, labels: own.map((e) => e.sentence.trim()) });
  }
  const birth = year(m.subject.birth);
  let empty: Run | null = null;
  const runs: Run[] = [];
  let emptyYears = 0;
  let lifeYears = 0;
  if (birth != null) {
    let run: Run | null = null;
    for (let y = Math.max(birth, from); y <= to; y++) {
      lifeYears++;
      if (cells[y - from].n) {
        run = null;
        continue;
      }
      emptyYears++;
      if (run) run.to = y;
      else {
        run = { from: y, to: y };
        runs.push(run);
      }
      if (!empty || run.to - run.from > empty.to - empty.from) empty = run;
    }
  }
  return { from, to, cells, birth, empty, runs, emptyYears, lifeYears };
}

const partnersOf = (m: M, id: string): string[] =>
  [...m.bonds.values()]
    .filter((b) => b.a === id || b.b === id)
    .map((b) => (b.a === id ? b.b : b.a))
    .filter((x): x is string => !!x);

const childrenOf = (m: M, id: string): string[] =>
  m.file.people
    .filter((p) => {
      const pb = m.parentsOf(p.id);
      return pb && (pb.a === id || pb.b === id);
    })
    .map((p) => p.id);

/** Each person's generation against the person the case is about: parents one
 * up, children one down, partners level; a person the record links to nobody
 * in the family has none. */
function generations(m: M): Map<string, number> {
  const gen = new Map<string, number>([[m.subject.id, 0]]);
  const queue = [m.subject.id];
  const put = (id: string, g: number) => {
    if (gen.has(id)) return;
    gen.set(id, g);
    queue.push(id);
  };
  while (queue.length) {
    const x = queue.shift()!;
    const g = gen.get(x)!;
    const pb = m.parentsOf(x);
    if (pb) [pb.a, pb.b].forEach((p) => p && put(p, g - 1));
    partnersOf(m, x).forEach((p) => put(p, g));
    childrenOf(m, x).forEach((c) => put(c, g + 1));
  }
  return gen;
}

/** Which side of the family each person stands on: the person's own (partners
 * and children), each parent's side as the page file names them, each
 * partner's own family, or none where the record links them to no one. A side is everyone
 * the record links, through parents, partners and children, to its first
 * person, stopping at the other sides' first people. */
function sides(m: M): { sides: GridSide[]; of: Map<string, string> } {
  const of = new Map<string, string>();
  const list: GridSide[] = [];
  const s = m.subject.id;
  const roots = m.page.sides.map((side) => side.pics[0]?.index).filter((x): x is string => !!x);
  const claimAll = (starts: string[], key: string) => {
    const queue: string[] = [];
    const claim = (id: string) => {
      if (of.has(id) || (roots.includes(id) && !starts.includes(id))) return;
      of.set(id, key);
      queue.push(id);
    };
    starts.forEach(claim);
    while (queue.length) {
      const x = queue.shift()!;
      const pb = m.parentsOf(x);
      if (pb) [pb.a, pb.b].forEach((p) => p && claim(p));
      partnersOf(m, x).forEach(claim);
      childrenOf(m, x).forEach(claim);
    }
  };
  [s, ...partnersOf(m, s), ...childrenOf(m, s)].forEach((id) => of.set(id, "own"));
  m.page.sides.forEach((side, i) => {
    const key = `side${i}`;
    // the person's own column stands between the first parent's side and the second's
    list.push({ key, label: side.label });
    if (i === 0) list.push({ key: "own", label: m.subject.name });
    if (roots[i]) claimAll([roots[i]], key);
  });
  if (!list.some((x) => x.key === "own")) list.push({ key: "own", label: m.subject.name });
  partnersOf(m, s).forEach((q) => {
    const pb = m.parentsOf(q);
    if (!pb) return;
    const folks = [pb.a, pb.b].filter((x): x is string => !!x && !of.has(x));
    if (!folks.length) return;
    const key = `partner:${q}`;
    list.push({ key, label: `${nameOf(m, q)}'s side` });
    claimAll(folks, key);
  });
  // a person the record links to no one in the family stands on no side: the
  // grid gives them one row across the sides, under "no family link"
  m.file.people.forEach((p) => !of.has(p.id) && of.set(p.id, "loose"));
  return { sides: list, of };
}

/** The rows of the grid: each generation against the person's own, named as a
 * generation since a row holds uncles, aunts, step-parents and in-laws too. */
const GEN_LABEL: Record<number, string> = {
  [-3]: "great-grandparents' generation",
  [-2]: "grandparents' generation",
  [-1]: "parents' generation",
  1: "next generation",
  2: "two generations down",
};

const SIBLINGS = /\b(brothers?|sisters?|siblings?)\b/i;

/** The dashed places: a parent's brothers and sisters where the parent's own
 * parents have one child in the record; with the open question that asks
 * about them, where the coach has asked, and none where no one has. */
function slotsOf(m: M, questions: CQuestion[], gen: Map<string, number>, of: Map<string, string>): Slot[] {
  const slots: Slot[] = [];
  const pb = m.parentsOf(m.subject.id);
  [pb?.a, pb?.b].forEach((parent) => {
    if (!parent) return;
    const theirs = m.parentsOf(parent);
    if (!theirs) return;
    const sibs = m.file.people.filter((p) => p.id !== parent && m.parentsOf(p.id)?.id === theirs.id);
    if (sibs.length) return;
    const asked = questions.find((q) => q.attached?.kind === "person" && q.attached.id === parent && SIBLINGS.test(q.text)) ?? null;
    if (asked?.state === "resolved") return;
    slots.push({
      id: `slot-${parent}-sibs`,
      who: parent,
      rel: "sibling",
      role: [`${nameOf(m, parent)}'s`, "brothers and sisters"],
      question: asked,
      gen: gen.get(parent) ?? 0,
      side: of.get(parent) ?? "loose",
    });
  });
  return slots;
}

function grid(m: M, people: PersonCover[], slots: Slot[], gen: Map<string, number>, side: { sides: GridSide[]; of: Map<string, string> }): Grid {
  const cells: GridCell[] = people.map((p) => ({ gen: gen.get(p.id) ?? null, side: side.of.get(p.id) ?? "loose", person: p }));
  slots.forEach((s) => cells.push({ gen: s.gen, side: s.side, slot: s }));
  const gs = [...new Set(cells.map((c) => c.gen).filter((g): g is number => g != null))].sort((a, b) => a - b);
  const his = m.page.pronoun.his;
  const gens: Grid["gens"] = gs.map((g) => ({ gen: g, label: GEN_LABEL[g] ?? (g === 0 ? `${his} generation` : `${Math.abs(g)} generations ${g < 0 ? "up" : "down"}`) }));
  if (cells.some((c) => c.gen == null)) gens.push({ gen: null, label: "no family link" });
  return { sides: side.sides, gens, cells };
}

const isEvent = (id: string) => /^e\d+$/.test(id);
const isPerson = (id: string) => /^p\d+$/.test(id);

/** What a guess rests on, and whether that is enough to stand on. */
function coverGuess(m: M, ids: string[], byId: Map<string, PersonCover>, open: CQuestion[]): GuessCover {
  const events = ids
    .filter(isEvent)
    .map((id) => m.file.events.find((e) => e.id === id))
    .filter((e): e is CEvent => !!e && !!m.dates.get(e.id))
    .sort((a, b) => m.dates.get(a.id)!.iso.localeCompare(m.dates.get(b.id)!.iso));
  const persons = [...new Set([...ids.filter(isPerson), ...events.map((e) => e.person)])];
  const people = persons.map((id) => byId.get(id)).filter((p): p is PersonCover => !!p);
  const ys = events.map((e) => year(e.date)!);
  const years = ys.length ? (ys[0] === ys[ys.length - 1] ? String(ys[0]) : `${ys[0]}–${ys[ys.length - 1]}`) : null;
  const thin = people.filter((p) => p.tier !== "story");
  const enough = events.length >= 2 && thin.length === 0;
  const why: string[] = [];
  if (events.length < 2) why.push(`${events.length} dated fact${events.length === 1 ? "" : "s"}`);
  if (thin.length) why.push(`${thin.length} of ${people.length} people with dates or a name only`);
  // an open question bears on the guess when the record attaches it to one of
  // the guess's own facts or people, by id; a shared name is no link
  const own = new Set([...ids, ...events.map((e) => e.id), ...persons]);
  const bears = open.filter((q) => (q.attached && own.has(q.attached.id)) || q.events.some((e) => own.has(e))).sort((a, b) => a.askedAt.localeCompare(b.askedAt));
  const keys = events.map((e) => Number(pkey(e.id)));
  const clusters = m.clusters.filter((cl) => cl.cluster.event_ids.some((id) => keys.includes(id))).map((cl) => cl.cluster.id);
  return { ids, events, dated: events.length, years, people, enough, why: enough ? null : why.join("; "), bears, clusters };
}

/** The reading's lines one by one, each with its own evidence. A line the
 * page's rule leaves out stays in the count, marked off, with no words and no
 * evidence of its own on the page. */
function parts(m: M, byId: Map<string, PersonCover>, open: CQuestion[]): PartCover[] {
  const l = m.file.levels["6_reading"];
  const list = l.parts?.length ? l.parts : [{ id: "reading", text: l.text, rests: l.rests }];
  return list.map((p) => {
    const text = m.words.plain(p.text).trim();
    if (!text) return { id: p.id, text: "", rests: [], cover: coverGuess(m, [], byId, open), off: true };
    return { id: p.id, text, rests: restsOf(m, p.rests), cover: coverGuess(m, p.rests ?? [], byId, open), off: false };
  });
}

export function coverage(m: M, qf: QuestionsFile | undefined): Coverage {
  const questions = qf?.questions ?? [];
  const open = questions.filter((q) => q.state === "asked");
  const people = coverPeople(m);
  const byId = new Map(people.map((p) => [p.id, p]));
  const byKey = new Map(people.map((p) => [p.key, p]));
  const gen = generations(m);
  const side = sides(m);
  const slots = slotsOf(m, questions, gen, side.of);
  const lines = parts(m, byId, open);
  const own = coverGuess(m, m.file.levels["7_ownPart"].rests ?? [], byId, open);
  const work = coverGuess(m, m.file.levels["9_workOn"].rests ?? [], byId, open);
  const effort = m.file.levels["10_effort"].layer === "hypothesis" ? coverGuess(m, m.file.levels["10_effort"].rests ?? [], byId, open) : null;
  const choice = m.file.levels["8_choice"].event ? coverGuess(m, [m.file.levels["8_choice"].event!], byId, open) : null;
  const tie = (level: number, g: GuessCover | null): Tie => {
    if (!g) return { level, cluster: null, part: null };
    for (const p of lines.filter((x) => !x.off)) {
      const shared = p.cover.clusters.find((c) => g.clusters.includes(c));
      if (shared) return { level, cluster: shared, part: p.id };
    }
    return { level, cluster: null, part: null };
  };
  const b = band(m);
  return {
    people,
    byId,
    byKey,
    band: b,
    grid: grid(m, people, slots, gen, side),
    slots,
    questions,
    open,
    impressions: qf?.impressions ?? 0,
    parts: lines,
    ownPart: own,
    workOn: work,
    effort,
    chosen: lines.some((p) => !p.off && p.cover.enough),
    all: lines.some((p) => !p.off) && lines.filter((p) => !p.off).every((p) => p.cover.enough),
    ties: [tie(7, own), tie(8, choice), tie(9, work)],
    counts: { people: people.length, story: people.filter((p) => p.tier === "story").length, open: open.length, emptyYears: b.emptyYears, lifeYears: b.lifeYears, birth: b.birth },
  };
}

/** One item on a dated strip: when, the date as the record writes it, and the app's id of the event. */
export interface StripItem {
  t: number;
  date: string;
  label: string;
  event: string;
}

export function stripItems(m: M, events: CEvent[]): StripItem[] {
  return events
    .filter((e) => m.dates.get(e.id))
    .map((e) => {
      const d = m.dates.get(e.id)!;
      const [y, mo] = d.iso.split("-").map(Number);
      return { t: y + (mo - 1) / 12, date: fullDate(d), label: labelOf(m, e), event: pkey(e.id) };
    })
    .sort((a, b) => a.t - b.t);
}
