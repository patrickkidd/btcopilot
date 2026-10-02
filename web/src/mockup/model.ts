import type { CaseView, ClusterView, Guess, Ref, Row, SideView, Still } from "../case";
import { arrange, Sex, Tie, type Bond, type Brood, type Cast, type Layout, type Shape } from "../diagram";
import { spanYears } from "../picture";
import { Family, tieBefore, Told, when } from "../snapshots";
import { DateCertainty } from "../certainty";
import { ChipKind, EventKind, type Case, type Cluster, type PairBond, type Person, type Timeline, type TimelineEvent } from "../types";
import { known, num, UNKNOWN, type CaseFile, type CaseInput, type CBond, type CEvent, type CLevel, type CPerson, type CCluster, type CStep, type PageFile } from "./casefile";
import { at, dated, endOf, fullDate, lastIso, type Dated } from "./dates";
import { Wording } from "./words";

/** One case file mapped onto the app's shapes: the record as a Timeline for
 * the app's line, the people as Casts for the app's family picture, each
 * cluster as a Case the app's drawer tells, and all of it read into the
 * CaseView the case page (casepage.ts) composes. Everything drawn is drawn by
 * the app's own code (diagram.ts, snapshots.ts, picture.ts, drawer.ts);
 * nothing here edits what it draws. Every word of a family comes from the
 * case file and the page file beside it. */

export interface Picture {
  cast: Cast;
  layout: Layout | null;
  /** Why the app's layout refused the picture, in its own words. */
  fault: string | null;
}

export interface ClusterModel {
  /** The cluster as the case file holds it. */
  src: CCluster;
  cluster: Cluster;
  /** The cluster as a told case for the app's drawer: one snapshot per step
   * the record dates, the step's line as the snapshot's fact. */
  told: Case;
  /** Steps the record does not date: the app's telling stands on dated
   * events only (R-0570), so these are said under the line instead. */
  undatedSteps: CStep[];
  events: CEvent[];
  /** Why the app cannot tell this cluster, in its own words; null when it can. */
  fault: string | null;
}

export interface SideModel {
  label: string;
  text: string;
  pics: { sub: string | null; pic: Picture; people: string[]; bond: string }[];
}

export interface Model {
  file: CaseFile;
  page: PageFile;
  words: Wording;
  /** The record's last date: the pictures' "now" for ages and for how each
   * couple stands, so a closed record is drawn as it stood when it closed. */
  now: number;
  subject: CPerson;
  people: Map<string, CPerson>;
  bonds: Map<string, CBond>;
  parentsOf: (id: string) => CBond | null;
  dates: Map<string, Dated | null>;
  tl: Timeline;
  family: Family;
  clusters: ClusterModel[];
  household: Picture;
  householdIds: string[];
  sides: SideModel[];
  /** Dated events no cluster claims, and the undated ones. */
  loose: CEvent[];
  undated: CEvent[];
  /** The case as the page reads it. */
  view: CaseView;
}

export const genderOf = (s: CPerson["sex"]): string | null => (s === "M" ? "male" : s === "F" ? "female" : null);

const COUPLE = new Set([EventKind.Married, EventKind.Bonded, EventKind.Separated, EventKind.Divorced]);

/** The app's casts key people by the record's numeric id ("4"); the files say "p4". */
export const pkey = (id: string): string => String(num(id));

/** When the record first dates the couple together: when they got together,
 * else the wedding. Null when it dates neither. */
const bondStart = (b: CBond): number | null => at(b.bonded) ?? at(b.married);

/** The record's dates on a couple, each as the event the app's line and the
 * app's own tie rule (snapshots.ts tieBefore) read. */
const BOND_DATES: [keyof CBond, EventKind][] = [
  ["bonded", EventKind.Bonded],
  ["married", EventKind.Married],
  ["separated", EventKind.Separated],
  ["divorced", EventKind.Divorced],
];

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** The day before an iso date. */
function dayBefore(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  const t = new Date(Date.UTC(y, m - 1, d - 1));
  return `${t.getUTCFullYear()}-${String(t.getUTCMonth() + 1).padStart(2, "0")}-${String(t.getUTCDate()).padStart(2, "0")}`;
}

/** Where each cluster ends on the line. A cluster's `to` is the last day of the
 * period the record names (a year is its 31 December); where that `to` is the
 * very period the next cluster starts in, the first ends the day before the
 * next begins, so no pill is pushed off the line. */
function clusterEnds(clusters: CCluster[]): string[] {
  return clusters.map((s, i) => {
    const end = lastIso(dated(s.to)!);
    const next = clusters[i + 1];
    return next && next.from === s.to ? dayBefore(dated(next.from)!.iso) : end;
  });
}

export function build(input: CaseInput): Model {
  const { file, page } = input;
  const words = new Wording(page);
  const plain = (t: string) => words.plain(t);
  const now = when(dated(page.recordEnd)!.iso);
  const people = new Map(file.people.map((p) => [p.id, p]));
  const bonds = new Map([...file.pairBonds, ...page.derived.bonds].map((b) => [b.id, b]));
  const subject = file.people.find((p) => p.isSubject);
  if (!subject) throw new Error(`case ${file.case} names no subject`);
  // a parents bond that holds the person themself is no parents bond
  const parentsOf = (id: string): CBond | null => {
    const key = page.derived.parents[id] ?? people.get(id)?.parents ?? null;
    const b = key ? (bonds.get(key) ?? null) : null;
    return b && b.a !== id && b.b !== id ? b : null;
  };
  const dates = new Map(file.events.map((e) => [e.id, dated(e.date)]));

  // ---- the record as the app's Timeline ----
  const events: TimelineEvent[] = file.events.map((e) => eventRow(e, dates.get(e.id) ?? null, people, plain));
  let extra = 900;
  // a death the record holds as a date on the person, with no event of its own,
  // is an event of the record: the app reads a death from its event
  file.people.forEach((p) => {
    const d = dated(p.death);
    if (!d || file.events.some((e) => e.kind === EventKind.Death && e.person === p.id)) return;
    events.push(eventRow({ id: `e${++extra}`, date: p.death, kind: EventKind.Death, person: p.id, others: [], text: "", layer: "fact", source: "" }, d, people, plain));
  });
  // the record's dates on a couple, likewise, where the file holds no event for them
  bonds.forEach((b) => {
    if (!b.a || !b.b) return;
    BOND_DATES.forEach(([field, kind]) => {
      const d = dated(b[field] as string | null | undefined);
      if (!d) return;
      const have = file.events.some(
        (e) => e.kind === kind && ((e.person === b.a && e.others[0] === b.b) || (e.person === b.b && e.others[0] === b.a)),
      );
      if (have) return;
      events.push(eventRow({ id: `e${++extra}`, date: b[field] as string, kind, person: b.a!, others: [b.b!], text: "", layer: "fact", source: "" }, d, people, plain));
    });
  });
  // the app's line reads its events in date order, the undated last
  events.sort((p, q) => (p.dateTime ?? "9999").localeCompare(q.dateTime ?? "9999"));
  const deathOf = (id: string) => events.find((e) => e.kind === EventKind.Death && e.person === num(id))?.id ?? null;
  const persons: Person[] = file.people.map((p) => ({
    id: num(p.id),
    name: p.name,
    last_name: null,
    gender: genderOf(p.sex),
    notes: null,
    primary: p.isSubject,
    birth: dated(p.birth)?.iso ?? null,
    birth_event: null,
    death_event: deathOf(p.id),
    parents: parentsOf(p.id) ? num(parentsOf(p.id)!.id) : null,
  }));
  const pairs: PairBond[] = [...bonds.values()].map((b) => ({
    id: num(b.id),
    person_a: b.a ? num(b.a) : null,
    person_b: b.b ? num(b.b) : null,
    married: known(b.married) || b.married === UNKNOWN,
  }));

  // ---- the clusters: which events each holds, and its steps ----
  // each step names the event it is the words of; a name the file does not hold is a fault in the file
  const stepEvents = file.clusters.map((s) =>
    s.steps.map((st) => {
      if (!st.event) return null;
      const e = file.events.find((x) => x.id === st.event);
      if (!e) throw new Error(`cluster ${s.id}: step names event ${st.event}, which the case file does not hold`);
      return e;
    }),
  );
  const claimed = new Map<string, string>();
  file.clusters.forEach((s, i) => stepEvents[i].forEach((e) => e && !claimed.has(e.id) && claimed.set(e.id, s.id)));
  // on the app's line a cluster ends on its last event, so no pill reaches past
  // the record's last dated event, where the line ends; a case file's `to` that
  // names a whole period (a year is its 31 December) would otherwise end past
  // the line when the record's last events are dated to that period alone
  const lastDated = events.filter((e) => e.dateTime).at(-1)?.dateTime ?? null;
  const ends = clusterEnds(file.clusters).map((end) => (lastDated && end > lastDated ? lastDated : end));
  // an event no step speaks for goes to the cluster whose years hold it, the
  // latest-starting one where clusters overlap
  const inYears = (i: number, t: number) => at(file.clusters[i].from)! <= t && t <= endOf(dated(ends[i])!);
  const holderOf = (t: number): string | undefined =>
    file.clusters
      .map((s, i) => ({ s, i }))
      .filter(({ i }) => inYears(i, t))
      .sort((p, q) => at(q.s.from)! - at(p.s.from)!)[0]?.s.id;
  file.events.forEach((e) => {
    const d = dates.get(e.id);
    if (!d || claimed.has(e.id)) return;
    const holder = holderOf(when(d.iso));
    if (holder) claimed.set(e.id, holder);
  });
  // the record's dates on a couple or a death, added above, likewise
  const added = new Map<number, string>();
  events
    .filter((e) => e.id > 900 && e.dateTime)
    .forEach((e) => {
      const holder = holderOf(when(e.dateTime!));
      if (holder) added.set(e.id, holder);
    });
  const tl: Timeline = { people: persons, pair_bonds: pairs, events, clusters: [], questions: [], asked_questions: [], axis: null, shelf: [], coded_in: {} };
  const family = new Family(tl);
  // a cluster's years are the record's own, as the file states them; the
  // claimed events say which dots the cluster holds
  const clusters: ClusterModel[] = file.clusters.map((src, i) => {
    const own = file.events.filter((e) => claimed.get(e.id) === src.id);
    const start = dated(src.from)!.iso;
    const end = ends[i];
    const ids = [...own.map((e) => num(e.id)), ...[...added].filter(([, s]) => s === src.id).map(([id]) => id)].sort(
      (p, q) => events.find((e) => e.id === p)!.dateTime!.localeCompare(events.find((e) => e.id === q)!.dateTime!),
    );
    const cluster: Cluster = {
      id: src.id,
      label: spanYears(start, end),
      title: src.title,
      summary: null,
      reason: null,
      cluster_ids: [],
      start,
      end,
      event_ids: ids,
      play_ids: ids,
      count: ids.length,
      digest: src.id,
    };
    // the app's telling stands on dated events (R-0570): one snapshot per step
    // the record dates, in the step's own line
    const told: Case = {
      cluster_id: src.id,
      point: "",
      snapshots: src.steps.flatMap((st, j) => {
        const e = stepEvents[i][j];
        const d = e ? dates.get(e.id) : null;
        return e && d ? [{ date: d.iso, event_ids: [num(e.id)], fact: plain(st.line), guess: null }] : [];
      }),
      question: "",
    };
    const undatedSteps = src.steps.filter((_, j) => !(stepEvents[i][j] && dates.get(stepEvents[i][j]!.id)));
    return { src, cluster, told, undatedSteps, events: own, fault: null };
  });
  tl.clusters = clusters.map((s) => s.cluster);
  // whether the app can tell each one, in its own words
  clusters.forEach((cl) => {
    if (!cl.told.snapshots.length) {
      cl.fault = "no step of this cluster has a date in the record";
      return;
    }
    try {
      new Told(tl, cl.told);
    } catch (e) {
      cl.fault = (e as Error).message;
    }
  });
  const loose = file.events.filter((e) => dates.get(e.id) && !claimed.has(e.id));
  const undated = file.events.filter((e) => !dates.get(e.id));

  // ---- the people on pictures ----
  const householdIds = household(subject, file, bonds, parentsOf);
  const cast = (ids: string[], index: string) => castFor(ids, index, family, tl, people, now);
  const sides: SideModel[] = page.sides.map((side) => ({
    label: side.label,
    text: plain(file.levels[side.text].text),
    pics: side.pics.map((p) => {
      const b = bonds.get(p.bond)!;
      const ids = [b.a, b.b].filter((x): x is string => !!x);
      file.people.forEach((q) => parentsOf(q.id)?.id === b.id && ids.push(q.id));
      return { sub: p.sub ?? null, pic: cast(ids, p.index), people: ids, bond: p.bond };
    }),
  }));

  const m: Omit<Model, "view"> = {
    file,
    page,
    words,
    now,
    subject,
    people,
    bonds,
    parentsOf,
    dates,
    tl,
    family,
    clusters,
    household: cast(householdIds, subject.id),
    householdIds,
    sides,
    loose,
    undated,
  };
  return { ...m, view: viewOf(m) };
}

/** The record's event as the app's line holds one. A death or a couple's date
 * the file holds as a date alone has the kind's own name for its label, as the
 * app labels a self-describing event. */
function eventRow(e: CEvent, d: Dated | null, people: Map<string, CPerson>, plain: (t: string) => string): TimelineEvent {
  const couple = COUPLE.has(e.kind as EventKind);
  const birth = e.kind === EventKind.Birth;
  const who = people.get(e.person)?.name ?? "";
  const text = plain(e.text);
  const label = text || cap(e.kind);
  const sentence = text
    ? `${who} ${text}`.trim()
    : couple
      ? `${who} and ${people.get(e.others[0])?.name ?? ""} ${e.kind}`
      : `${who} ${e.kind === EventKind.Death ? "died" : e.kind}`;
  return {
    id: num(e.id),
    label,
    sentence,
    person_name: who,
    person: num(e.person),
    dateTime: d?.iso ?? null,
    endDateTime: null,
    dateCertainty: d?.certainty ?? DateCertainty.Unknown,
    kind: e.kind,
    description: text || null,
    notes: null,
    location: null,
    symptom: e.symptom ?? null,
    anxiety: e.anxiety ?? null,
    functioning: e.functioning ?? null,
    relationship: e.relationship ?? null,
    relationshipTargets: couple || birth ? [] : e.others.map(num),
    relationshipTriangles: [],
    spouse: couple && e.others[0] ? num(e.others[0]) : null,
    child: birth ? num(e.person) : null,
  };
}

/** Who stands on the person's own picture: the person, their partners and
 * children, their parents with the parents' other partners, and every brother,
 * sister, half-brother and half-sister. One line of descent: the app's layout
 * refuses a couple whose both sets of parents are drawn, so a partner's family
 * is a picture of its own under level 4. */
function household(subject: CPerson, file: CaseFile, bonds: Map<string, CBond>, parentsOf: (id: string) => CBond | null): string[] {
  const ids = new Set<string>([subject.id]);
  const partnersOf = (id: string) =>
    [...bonds.values()]
      .filter((b) => b.a === id || b.b === id)
      .map((b) => (b.a === id ? b.b : b.a))
      .filter((x): x is string => !!x);
  partnersOf(subject.id).forEach((p) => ids.add(p));
  file.people.forEach((p) => {
    const pb = parentsOf(p.id);
    if (pb && (pb.a === subject.id || pb.b === subject.id)) ids.add(p.id);
  });
  const parents = parentsOf(subject.id);
  const folks = parents ? [parents.a, parents.b].filter((x): x is string => !!x) : [];
  folks.forEach((f) => {
    ids.add(f);
    partnersOf(f).forEach((p) => ids.add(p));
    file.people.forEach((p) => {
      const pb = parentsOf(p.id);
      if (pb && (pb.a === f || pb.b === f)) ids.add(p.id);
    });
  });
  return [...ids];
}

/** A cast of the given people, shaped as the app's own cast rule shapes one
 * (snapshots.ts castOf): each person as the record's Family shapes them, each
 * couple as the record's events stand them at the record's last date, and a
 * child with one recorded parent given the unknown partner (ruled 2026-09-26). */
function castFor(ids: string[], index: string, family: Family, tl: Timeline, people: Map<string, CPerson>, now: number): Picture {
  const keys = ids.map(pkey);
  const inCast = new Set(keys);
  const shapes: Record<string, Shape> = {};
  keys.forEach((k) => (shapes[k] = family.shape(k)));
  const drawn: Bond[] = [];
  const kids: Brood[] = [];
  tl.pair_bonds.forEach((pb) => {
    const pair = [pb.person_a, pb.person_b].filter((p): p is number => p != null).map(String);
    const present = pair.filter((x) => inCast.has(x));
    if (pair.length === 2 && present.length === 2) drawn.push({ a: pair[0], b: pair[1], ...tieBefore(family, pb, now) });
    const children = tl.people.filter((p) => p.parents === pb.id && inCast.has(String(p.id))).map((p) => String(p.id));
    if (!children.length || present.length !== pair.length) return;
    if (pair.length === 2) kids.push({ of: pair, kids: sortKids(children, people) });
    else {
      const q = `unknown-${pair[0]}`;
      shapes[q] = { name: "", g: Sex.Unknown, born: null };
      drawn.push({ a: pair[0], b: q, st: Tie.Married, married: true });
      kids.push({ of: [pair[0], q], kids: sortKids(children, people) });
    }
  });
  const cast: Cast = { people: shapes, bonds: drawn, kids, index: pkey(index), marked: [], cross: [], words: {}, moves: [], assoc: {}, until: now };
  try {
    return { cast, layout: arrange(cast), fault: null };
  } catch (e) {
    return { cast, layout: null, fault: (e as Error).message };
  }
}

/** The record's own order of brothers and sisters, else by birth. */
function sortKids(keys: string[], people: Map<string, CPerson>): string[] {
  const of = (k: string) => people.get(`p${k}`)!;
  return keys.slice().sort((a, b) => {
    const pa = of(a);
    const pb = of(b);
    if (pa.siblingOrder != null && pb.siblingOrder != null) return pa.siblingOrder - pb.siblingOrder;
    return (at(pa.birth) ?? 0) - (at(pb.birth) ?? 0);
  });
}

type M = Omit<Model, "view">;

export const nameOf = (m: M, id: string): string => m.people.get(id)?.name ?? id;

const byDate = (m: M) => (p: CEvent, q: CEvent) => m.dates.get(p.id)!.iso.localeCompare(m.dates.get(q.id)!.iso);

/** A move or a job in the record's words: a move is a Noted event [R-0364];
 * the record's own words name the rest. */
const MOVE_OR_JOB = /\b(moved?|moving|relocat\w*|jobs?|college|school|program|abroad)\b/i;

/** The record's own marks of how someone was doing on an event. */
const coded = (e: CEvent) => !!(e.symptom || e.anxiety || e.functioning);

export interface CoupleRecord {
  /** The couple's bond: the one standing at the record's last date. */
  bond: CBond | null;
  partners: string[];
  /** Whether the record dates when the couple first got together. */
  met: boolean;
  /** Dated events of the couple since the record first dates them together:
   * the couple's own, their children's births, moves and jobs, and the record's
   * marks of how each was doing at those events. */
  events: CEvent[];
  /** Whether any of them is a move or a job, and whether any carries a mark of how someone was doing. */
  movesOrJobs: boolean;
  howDoing: boolean;
  /** The person's earlier partners in the record, with the dates it holds. */
  earlier: string[];
}

/** Two dates fall in the same month, or the same year where the record holds
 * only the year of either. */
function sameTime(a: Dated, b: Dated): boolean {
  const n = a.grain === "year" || b.grain === "year" ? 4 : 7;
  return a.iso.slice(0, n) === b.iso.slice(0, n);
}

/** The record's dates on a bond in a few words: "got together 2005, separated Jul 2006". */
function bondDates(b: CBond): string {
  const said = BOND_DATES.flatMap(([field]) => {
    const d = dated(b[field] as string | null | undefined);
    return d ? [`${field === "bonded" ? "got together" : field} ${fullDate(d)}`] : [];
  });
  return said.join(", ");
}

/** Level 3: the couple since they met, from the record's dated events. The
 * couple is the person and the partner the record holds them with at its last
 * date (a bond with no separation or divorce in the record), else the latest;
 * earlier partners are said in a line. The big events are the couple's own,
 * their children's births, a move or a job of either, and a move between the
 * two; how each was doing is the record's own mark on an event of either partner
 * at the time of a big event. */
export function coupleRecord(m: M): CoupleRecord {
  const s = m.subject.id;
  const own = [...m.bonds.values()].filter((b) => (b.a === s || b.b === s) && b.a && b.b);
  const standing = own.filter((b) => !b.separated && !b.divorced);
  const latest = (bs: CBond[]) => bs.slice().sort((p, q) => (bondStart(q) ?? -Infinity) - (bondStart(p) ?? -Infinity))[0] ?? null;
  const bond = latest(standing.length ? standing : own);
  const partners = bond ? [bond.a === s ? bond.b! : bond.a!] : [];
  const earlier = own.filter((b) => b !== bond).map((b) => `${nameOf(m, b.a === s ? b.b! : b.a!)}${bondDates(b) ? `, ${bondDates(b)}` : ""}`);
  const pair = new Set([s, ...partners]);
  const together = m.file.events
    .filter((e) => m.dates.get(e.id) && COUPLE.has(e.kind as EventKind) && pair.has(e.person) && e.others[0] != null && pair.has(e.others[0]))
    .map((e) => when(m.dates.get(e.id)!.iso));
  const starts = [...(bond ? [bondStart(bond)] : []).filter((t): t is number => t != null), ...together];
  const start = starts.length ? Math.min(...starts) : null;
  const children = m.file.people.filter((p) => {
    const pb = m.parentsOf(p.id);
    return pb && [pb.a, pb.b].includes(s);
  });
  const since = m.file.events.filter((e) => {
    const d = m.dates.get(e.id);
    return d && (start == null || when(d.iso) >= start);
  });
  const moveOrJob = (e: CEvent) => pair.has(e.person) && (e.kind === EventKind.Noted || MOVE_OR_JOB.test(e.text));
  const big = since.filter((e) => {
    if (COUPLE.has(e.kind as EventKind)) return pair.has(e.person) && (e.others[0] == null || pair.has(e.others[0]));
    if (e.kind === EventKind.Birth) return children.some((c) => c.id === e.person);
    return moveOrJob(e) || (pair.has(e.person) && e.others.some((o) => pair.has(o) && o !== e.person));
  });
  const doing = since.filter((e) => pair.has(e.person) && coded(e) && !big.includes(e) && big.some((b) => sameTime(m.dates.get(b.id)!, m.dates.get(e.id)!)));
  const events = [...big, ...doing].sort(byDate(m));
  return { bond, partners, met: start != null, events, movesOrJobs: big.some(moveOrJob), howDoing: events.some(coded), earlier };
}

/** The record's last dated events, oldest first: where things stand now, in facts. */
export function latestEvents(m: M, n: number): CEvent[] {
  return m.file.events
    .filter((e) => m.dates.get(e.id))
    .sort(byDate(m))
    .slice(-n);
}

/** Whose birth dates the record holds. */
export function birthLine(m: M): string {
  const have = m.file.people.filter((p) => known(p.birth)).map((p) => p.name);
  if (!have.length) return "Birth dates: none in the record.";
  if (have.length === m.file.people.length) return "";
  return `Birth dates in the record: ${have.join(", ")}; not for the others.`;
}

/** Whether this picture draws the "?" shape for a parent the record does not hold. */
export function drawsUnknown(pic: Picture): boolean {
  return Object.keys(pic.cast.people).some((id) => id.startsWith("unknown-"));
}

/** The side of the family a person is drawn on, by index; null when no side picture holds them. */
export function sideOf(m: M, id: string): number | null {
  const i = m.sides.findIndex((s) => s.pics.some((p) => p.people.includes(id)));
  return i < 0 ? null : i;
}

/** The subject's place among brothers and sisters, from the record's links. */
export function siblingLine(m: M): string {
  const s = m.subject;
  const pb = m.parentsOf(s.id);
  const his = m.page.pronoun.his;
  if (!pb) return `${s.name}'s parents: not in the record.`;
  const names = [pb.a, pb.b].filter((x): x is string => !!x).map((id) => nameOf(m, id));
  const sibs = m.file.people.filter((p) => p.id !== s.id && m.parentsOf(p.id)?.id === pb.id);
  const halves = m.file.people.filter((p) => {
    const q = m.parentsOf(p.id);
    return p.id !== s.id && q && q.id !== pb.id && [q.a, q.b].some((x) => x && [pb.a, pb.b].includes(x));
  });
  const parts: string[] = [];
  // a record with no brother or sister in it is a gap, never "only child": a
  // case file may hold a few of the record's people
  if (!sibs.length) parts.push(`${s.name}'s place among brothers and sisters: not in the record.`);
  else {
    const ordered = sibs.every((p) => p.siblingOrder != null) && s.siblingOrder != null;
    const list = sibs.map((p) => `${p.name}${known(p.birth) ? ` (born ${fullDate(dated(p.birth)!)})` : ""}`).join(", ");
    parts.push(
      ordered
        ? `${s.name}, child ${s.siblingOrder} of ${sibs.length + 1} of ${names.join(" and ")}; the others: ${list}.`
        : `${s.name} has ${sibs.length === 1 ? "one sibling" : `${sibs.length} siblings`} in the record, ${list}; who is older is not in the record.`,
    );
  }
  halves.forEach((p) => {
    const q = m.parentsOf(p.id)!;
    const via = [q.a, q.b].find((x) => x && [pb.a, pb.b].includes(x))!;
    const sex = m.people.get(via)?.sex;
    parts.push(
      `Half-${p.sex === "F" ? "sister" : "brother"} ${p.name}${known(p.birth) ? `, born ${fullDate(dated(p.birth)!)}` : ""}, through ${his} ${sex === "F" ? "mother" : "father"}.`,
    );
  });
  return parts.join(" ");
}

/** The record's dates on a couple that it holds with no date at all: said
 * once, as a gap, since the picture cannot draw an undated change. */
export function undatedBondLines(m: M, bondIds: string[]): string[] {
  return bondIds.flatMap((id) => {
    const b = m.bonds.get(id);
    if (!b || !b.a || !b.b) return [];
    const what = BOND_DATES.filter(([field]) => b[field] === UNKNOWN).map(([field]) => field as string);
    if (!what.length) return [];
    const said = what.map((w) => (w === "bonded" ? "got together" : w)).join(" and later ");
    return [`${nameOf(m, b.a)} and ${nameOf(m, b.b)} ${said}; the date${what.length > 1 ? "s are" : " is"} not in the record.`];
  });
}

/** What a guess rests on: the people and events the case file names for it,
 * from the record's own evidence list. Chips, not prose. */
export function restsOf(m: M, ids: string[] | undefined): Ref[] {
  return (ids ?? []).flatMap((id): Ref[] => {
    if (/^p\d+$/.test(id)) {
      const p = m.people.get(id);
      return p ? [{ kind: ChipKind.Person, id: pkey(id), label: p.name }] : [];
    }
    const e = m.file.events.find((x) => x.id === id);
    if (!e) return [];
    const d = m.dates.get(e.id);
    return [{ kind: ChipKind.Event, id: pkey(id), label: `${d ? fullDate(d) : "no date"} · ${m.words.plain(e.text)}` }];
  });
}

/** A level's words as the page shows them, and what they rest on. A level that
 * quotes several sayings (the coach's impressions) is read saying by saying:
 * one the page's rule leaves out takes its own evidence with it, so the chips
 * are the shown guess's own. */
function guessOf(m: M, l: CLevel): Guess {
  const plain = (t: string) => m.words.plain(t);
  if (l.parts?.length) {
    const kept = l.parts.filter((p) => plain(p.text).trim());
    const rests = [...new Set(kept.flatMap((p) => p.rests ?? []))];
    return { text: kept.map((p) => plain(p.text).trim()).join(" "), rests: restsOf(m, rests), gaps: l.gaps ?? [] };
  }
  return { text: plain(l.text), rests: restsOf(m, l.rests), gaps: l.gaps ?? [] };
}

/** A person in a few words: the name and the dates the record holds. */
function say(p: CPerson): string {
  const bits: string[] = [];
  if (known(p.birth)) bits.push(`born ${fullDate(dated(p.birth)!)}`);
  if (known(p.death)) bits.push(`died ${fullDate(dated(p.death)!)}`);
  return `${p.name}${bits.length ? ` (${bits.join("; ")})` : ""}`;
}

/** The people the record holds and no picture here draws, each with the link
 * the record holds to someone drawn: a parent, a brother or sister, or none. */
function undrawn(m: M): string | null {
  const shown = [...new Set<string>([...m.householdIds, ...m.sides.flatMap((s) => s.pics.flatMap((p) => p.people))])];
  const rest = m.file.people.filter((p) => !shown.includes(p.id));
  if (!rest.length) return null;
  const done = new Set<string>();
  const said: string[] = [];
  const kin = (sex: CPerson["sex"], one: boolean) => (one ? (sex === "F" ? "sister" : sex === "M" ? "brother" : "sibling") : "siblings");
  shown.forEach((q) => {
    const pb = m.parentsOf(q);
    if (!pb) return;
    const folks = [pb.a, pb.b].filter((x): x is string => !!x && rest.some((p) => p.id === x) && !done.has(x));
    const sibs = rest.filter((p) => !done.has(p.id) && !folks.includes(p.id) && m.parentsOf(p.id)?.id === pb.id);
    if (!folks.length && !sibs.length) return;
    [...folks, ...sibs.map((p) => p.id)].forEach((id) => done.add(id));
    const her = m.people.get(q)?.sex === "F" ? "her" : m.people.get(q)?.sex === "M" ? "his" : "their";
    const parts: string[] = [];
    if (folks.length) parts.push(`${nameOf(m, q)}'s ${folks.length === 2 ? "parents" : "parent"} ${folks.map((id) => say(m.people.get(id)!)).join(" and ")}`);
    if (sibs.length) parts.push(`${folks.length ? her : `${nameOf(m, q)}'s`} ${kin(sibs[0].sex, sibs.length === 1)} ${sibs.map(say).join(", ")}`);
    said.push(parts.join(" and "));
  });
  rest.filter((p) => !done.has(p.id)).forEach((p) => said.push(`${say(p)}, the link to the family is not in the record`));
  return `Also in the record, not on a picture here: ${said.join("; ")}.`;
}

/** The bonds a picture draws both partners of. */
const bondsOn = (m: M, people: string[]) => [...m.bonds.values()].filter((b) => b.a && b.b && people.includes(b.a) && people.includes(b.b)).map((b) => b.id);

/** A parent's place among brothers and sisters, as far as the record holds it:
 * a record with one child of the couple in it is a gap, never "only child".
 * A death the record holds with no date is said once: the record's own event
 * of it, where there is one, is the gap line of the level (undatedLine). */
function kidsLine(m: M, pic: { people: string[] }, bondId: string): string {
  const b = m.bonds.get(bondId);
  if (!b) return "";
  const parents = [b.a, b.b].filter((x): x is string => !!x).map((id) => nameOf(m, id));
  const kids = pic.people.filter((id) => m.parentsOf(id)?.id === bondId);
  const undatedDeaths = pic.people
    .filter((id) => m.people.get(id)?.death === "unknown" && !m.undated.some((e) => e.kind === "death" && e.person === id))
    .map((id) => nameOf(m, id));
  const tail = undatedDeaths.length ? ` ${undatedDeaths.join(" and ")} died; the date is not in the record.` : "";
  if (!kids.length) return tail.trim();
  if (kids.length === 1) return `Brothers and sisters of ${nameOf(m, kids[0])}: not in the record.${tail}`;
  return `Children of ${parents.join(" and ")} in the record: ${kids.map((id) => nameOf(m, id)).join(", ")}.${tail}`;
}

/** An event the record holds with no date, as a gap line of the level it
 * belongs to; the person's own events on their own page need no name. */
const undatedLine = (m: M, e: CEvent) => `No date in the record: ${e.person === m.subject.id ? "" : `${nameOf(m, e.person)} `}${m.words.plain(e.text)}.`;

const still = (pic: Picture, label: string): Still => ({ layout: pic.layout, fault: pic.fault, label, unknownParent: drawsUnknown(pic) });

const row = (m: M, e: CEvent): Row => ({ date: fullDate(m.dates.get(e.id)!), text: m.words.plain(e.text) });

/** The case as the page reads it (case.ts CaseView), every string as the page shows it. */
export function viewOf(m: M): CaseView {
  const { file, page, subject } = m;
  const plain = (t: string) => m.words.plain(t);
  const levels = file.levels;
  // level 2: the trouble's course, dated
  const flares = file.events
    .filter((e) => e.person === subject.id && e.symptom && m.dates.get(e.id))
    .sort(byDate(m))
    .map((e) => row(m, e));
  // level 3: the couple
  const c = coupleRecord(m);
  const coupleGaps: string[] = [];
  if (!c.met) coupleGaps.push("When they met: not in the record.");
  if (c.bond && !known(c.bond.married)) coupleGaps.push("When they married: not in the record.");
  if (!c.events.length) coupleGaps.push("Dates for the couple: not in the record.");
  else if (!c.movesOrJobs) coupleGaps.push("Moves and jobs since they met: not in the record.");
  if (!c.howDoing) coupleGaps.push("How each was doing at each event: not in the record.");
  if (c.earlier.length) coupleGaps.push(`Earlier ${c.earlier.length === 1 ? "partner" : "partners"} in the record: ${c.earlier.join("; ")}.`);
  // level 4: each side
  const sides: SideView[] = m.sides.map((sm, i) => ({
    label: sm.label,
    text: sm.text,
    pics: sm.pics.map((p) => ({
      sub: p.sub,
      still: still(p.pic, sm.label),
      kids: kidsLine(m, p, p.bond),
      gaps: undatedBondLines(m, bondsOn(m, p.people)),
    })),
    // an undated event about someone on this side belongs to this side
    undated: m.undated.filter((e) => e.person !== subject.id && sideOf(m, e.person) === i).map((e) => undatedLine(m, e)),
  }));
  // level 5: the clusters, the pins, what the record does not hold
  const clusters: ClusterView[] = m.clusters.map((cl) => ({
    cluster: cl.cluster,
    title: cl.src.title,
    told: cl.told,
    fault: cl.fault,
    undated: cl.undatedSteps.map((st) => plain(st.line)),
  }));
  const byYear = new Map<string, number>();
  file.events.filter((e) => m.dates.get(e.id)?.grain === "year").forEach((e) => byYear.set(e.date!, (byYear.get(e.date!) ?? 0) + 1));
  const stacked = [...byYear].filter(([, n]) => n >= 4).map(([y, n]) => `${n} events in ${y} are dated to the year only, so they share one point on the line.`);
  const pins = page.pins.map((p) => ({
    to:
      p.to.kind === "cluster"
        ? (() => {
            const cl = clusters.find((s) => s.cluster.id === p.to.id)!;
            return { kind: ChipKind.Cluster as const, id: cl.cluster.id, label: `${cl.cluster.label} · ${cl.title}` };
          })()
        : { kind: ChipKind.Person as const, id: pkey(p.to.id), label: nameOf(m, p.to.id) },
    text: p.text,
  }));
  // level 8: the choice
  const ch = levels["8_choice"];
  const name = subject.name;
  const effort = levels["10_effort"];
  return {
    key: file.case,
    title: page.title,
    subject: { id: pkey(subject.id), name },
    self: file.presenter === "self",
    presenter: page.presenter,
    pro: page.pro,
    pronoun: page.pronoun,
    header: page.header,
    account: page.account,
    tl: m.tl,
    now: m.now,
    recordEnd: { closed: page.closed, date: fullDate(dated(page.recordEnd)!) },
    household: still(m.household, `${name}'s family`),
    siblings: siblingLine(m),
    householdGaps: undatedBondLines(m, bondsOn(m, m.householdIds)),
    undrawn: undrawn(m),
    asked: page.asked,
    whatBrought: plain(levels["2_whatBrought"].text),
    flares,
    ownUndated: m.undated.filter((e) => e.person === subject.id).map((e) => undatedLine(m, e)),
    couple: { text: plain(levels["3_couple"].text), rows: c.events.map((e) => row(m, e)), gaps: coupleGaps },
    sides,
    looseUndated: m.undated.filter((e) => e.person !== subject.id && sideOf(m, e.person) === null).map((e) => undatedLine(m, e)),
    clusters,
    stacked,
    pins,
    notHeld: [...file.unknowns, birthLine(m)].filter(Boolean),
    reading: guessOf(m, levels["6_reading"]),
    ownPart: guessOf(m, levels["7_ownPart"]),
    choice: {
      date: fullDate(dated(ch.date)!),
      event: ch.event ? pkey(ch.event) : null,
      step: plain(ch.step),
      part: ch.quote ? `What ${name} did, in ${page.pronoun.his} own words.` : page.noted ? `What ${name} did, ${page.noted}.` : `What ${name} did.`,
      facts: ch.facts.map(plain),
      question: ch.opening ? plain(ch.opening) : null,
    },
    workOn: guessOf(m, levels["9_workOn"]),
    effort: { text: plain(effort.text), guess: effort.layer === "hypothesis" ? guessOf(m, effort) : null, gaps: effort.gaps ?? [] },
    outcome: latestEvents(m, 4).map((e) => row(m, e)),
  };
}

export { fullDate };
