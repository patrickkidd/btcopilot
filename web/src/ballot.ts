import * as api from "./api";
import { Feature, tap } from "./track";
import { asWritten, drawn, tokenize } from "./chips";
import { esc, el, stepBtn, type Title } from "./dom";
import {
  HAND_EDITS,
  openBondEditor,
  openEditor,
  openPersonEditor,
  Relationship,
  type Family,
} from "./editor";
import { DateCertainty, DatePrecision } from "./certainty";
import { when as rowsWhen } from "./rows";
import { dateText } from "./spotlight";
import {
  fieldsOf,
  isStructure,
  structureName,
  versionWords,
} from "./structure";
import {
  ItemKind,
  ItemStatus,
  VoteChoice,
  type BallotItem,
  type CodingRecord,
  type PairBond,
  type Person,
  type Opinion,
  type TimelineEvent,
  type TranscriptLine,
  type Vote,
} from "./types";

/** The vote before the meeting: one disputed event per screen, the opinions shown
 * without names so nobody defers to the most senior person in the room
 * (R-0252, R-0257). Nothing the coach thinks is in here at all (R-0254). No
 * rule decides anything before the meeting; the tallies only inform it
 * (R-0274). */

export interface BallotHandlers {
  onTitle(title: string | Title): void;
  /** The last item is voted on: back to the one task card. */
  onDone(): void;
  /** Open the conversation at the line this item came from (R-0278). */
  onTranscript(statementId: number): void;
  /** Another pairing is on screen. */
  onMoved(): void;
}

/** The fields an opinion can differ from the others by, in the order they read. */
export const TELLING = [
  "dateTime",
  "person_name",
  "kind",
  "title",
  "description",
  "symptom",
  "anxiety",
  "functioning",
  "relationship",
] as const;

const WORDS: Record<string, (value: string) => string> = {
  dateTime: (value) => when(value),
  kind: (value) => KIND_WORDS[value] ?? value,
  symptom: (value) => `symptom ${value}`,
  anxiety: (value) => `anxiety ${value}`,
  functioning: (value) => `functioning ${value}`,
  relationship: (value) => `relationship: ${value.replaceAll("-", " ")}`,
};

/** One value of an item said the way a coder reads it, never the stored slug
 * or date (R-0869). */
export function worded(field: string, value: string): string {
  return WORDS[field] ? WORDS[field](value) : value;
}

/** A line the server already joined from an item's values, each value worded
 * by what it is. A variable comes named, "symptom: up", since "up" alone says
 * nothing; any other value is told by its look. */
export function wordedLine(said: string): string {
  return said
    .split(" · ")
    .map((value) => {
      const named = /^(symptom|anxiety|functioning): (.+)$/.exec(value);
      if (named) return worded(named[1], named[2]);
      if (/^\d{4}(-\d{2}){0,2}$/.test(value)) return worded("dateTime", value);
      if (Object.hasOwn(KIND_WORDS, value)) return worded("kind", value);
      if (RELATIONSHIPS.has(value)) return worded("relationship", value);
      return value;
    })
    .join(" · ");
}

const RELATIONSHIPS = new Set<string>(Object.values(Relationship));

/** One dot per event, as the picture draws a line of them. */
export const LINE = { width: 400, height: 66, y: 34, edge: 16 };

/** The agreement timeline, which the ballot and the meeting both stand under:
 * one dot per event of the cut in order, teal where the vote agreed, amber
 * where it did not with a small count beside it, and the event in front of the
 * room enlarged in green (R-0277, R-0278). */
export function drawTimeline(
  events: BallotItem[],
  current: number | null,
): string {
  const step = (LINE.width - LINE.edge * 2) / Math.max(events.length, 1);
  const dots = events
    .map((one, index) => {
      const x = LINE.edge + step * (index + 0.5);
      if (one.id === current)
        return `<circle class="d-on" cx="${x}" cy="${LINE.y}" r="7.5" data-item="${one.id}"/>`;
      if (one.status === ItemStatus.Agreed)
        return `<circle class="d-ok" cx="${x}" cy="${LINE.y}" r="4.5" data-item="${one.id}"/>`;
      // The small number says how many different opinions there are, so it is
      // only there when there is more than one to tell apart.
      const opinions = group(one).length;
      return (
        `<circle class="d-no" cx="${x}" cy="${LINE.y}" r="5.5" data-item="${one.id}"/>` +
        (opinions > 1
          ? `<text class="d-n" x="${x + 8}" y="${LINE.y - 12}">${opinions}</text>`
          : "")
      );
    })
    .join("");
  return (
    `<div class="ss tl"><svg viewBox="0 0 ${LINE.width} ${LINE.height}" ` +
    `height="${LINE.height}">` +
    `<line class="wire2" x1="${LINE.edge}" y1="${LINE.y}" ` +
    `x2="${LINE.width - LINE.edge}" y2="${LINE.y}"/>${dots}</svg></div>`
  );
}

/** What a coder votes on: a disputed event that at least one person wrote. An
 * item only the coach wrote carries no opinion here, and is the meeting's to take
 * up rather than the room's to vote on (R-0254); the server refuses a vote on
 * one, so it never reaches the ballot. */
export const onBallot = (one: BallotItem) =>
  (one.item_kind === ItemKind.Event || isStructure(one.item_kind)) &&
  one.status === ItemStatus.Disputed &&
  one.opinions.length > 0;

/** Which coding's version is lit on a card: while the vote is open it is the
 * one this coder chose, and once the cut is ratified it is the one the meeting
 * kept, on every later reading of it (R-0339). */
export function litCoding(
  item: BallotItem,
  vote: Vote | undefined,
  ratified: boolean,
): number | null {
  if (ratified) return item.kept_coding_id ?? null;
  if (vote?.choice !== VoteChoice.Opinion) return null;
  return (vote.value?.coding_id as number | undefined) ?? null;
}

/** The order the ballot walks: the conversation's, by the line whose passage
 * each pairing shows; on one line the people, then the couples, then the
 * events (R-0326); then the earliest date any coder gave, never one coder's
 * (R-0965). */
export function ballotOrder(items: BallotItem[]): BallotItem[] {
  return walkOrder(items).filter(onBallot);
}

const KINDS = [ItemKind.Person, ItemKind.PairBond, ItemKind.Event];

const earliest = (values: (string | number)[], none: string | number) =>
  values.length ? values.reduce((a, b) => (a < b ? a : b)) : none;

/** The line a pairing's passage shows: the statement most of its entries
 * were written from, the earliest on a tie. */
function shownLine(item: BallotItem): TranscriptLine | null {
  const counts = new Map<number, { line: TranscriptLine; n: number }>();
  for (const { line } of item.opinions) {
    if (!line) continue;
    const seen = counts.get(line.statement_id) ?? { line, n: 0 };
    seen.n += 1;
    counts.set(line.statement_id, seen);
  }
  const most = [...counts.values()].sort(
    (a, b) => b.n - a.n || a.line.statement_id - b.line.statement_id,
  )[0];
  return most?.line ?? item.line ?? null;
}

const saidAt = (item: BallotItem): number =>
  shownLine(item)?.statement_id ?? Number.MAX_SAFE_INTEGER;

const datedAt = (item: BallotItem): string =>
  earliest(
    item.opinions
      .map((one) => text(one.item.dateTime))
      .filter((day) => day && !STAND_IN.test(day)),
    "\uffff",
  ) as string;

export const walkOrder = (items: BallotItem[]): BallotItem[] =>
  [...items].sort(
    (a, b) =>
      saidAt(a) - saidAt(b) ||
      KINDS.indexOf(a.item_kind) - KINDS.indexOf(b.item_kind) ||
      datedAt(a).localeCompare(datedAt(b)),
  );

/** Every event of a cut in the order they happened, which is the order both
 * screens walk them in. */
export function eventsOf(items: BallotItem[]): BallotItem[] {
  const day = (item: BallotItem) => String(item.opinions[0]?.item.dateTime ?? "");
  return items
    .filter((one) => one.item_kind === ItemKind.Event)
    .sort((a, b) => day(a).localeCompare(day(b)));
}

export const when = (value: unknown): string => {
  if (typeof value !== "string" || !value) return "no date yet";
  if (/^\d{4}$/.test(value)) return value;
  const day = new Date(`${value}T00:00:00`);
  if (Number.isNaN(day.getTime())) return value;
  return day.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
};

/** An event kind said the way a first-time reader would say it, for an item
 * whose writer left the description empty (R-0318). */
const KIND_WORDS: Record<string, string> = {
  shift: "a shift",
  birth: "a birth",
  adopted: "an adoption",
  bonded: "a new bond",
  married: "a marriage",
  separated: "a separation",
  divorced: "a divorce",
  noted: "something noted",
  death: "a death",
};

/** What happened, never a placeholder: a noted event or a shift by its title
 * (R-0681), another kind by its description, and with neither the kind is said
 * in words (R-0318). */
export function what(item: BallotItem): string {
  const first = item.opinions[0];
  const kind = String(first?.item.kind ?? "");
  return String(first?.item.title ?? first?.item.description ?? "") || KIND_WORDS[kind] || kind;
}

/** Who a row is about and what happened, which is what every row of the meeting
 * is named by (R-0318). */
export function names(item: BallotItem): string {
  const said = what(item);
  const who = item.opinions[0]?.person_name ?? "";
  return who && said ? `${who} · ${said}` : who || said;
}

/** What one opinion says, in the record's own words, for the fields given. */
export function words(opinion: Opinion, fields: readonly string[]): string {
  const said = fields
    .map((field) => {
      const value =
        field === "person_name" ? opinion.person_name : opinion.item[field];
      if (value === null || value === undefined || value === "") return "";
      const text = String(value);
      if (field === "person_name") return `→ ${text}`;
      return worded(field, text);
    })
    .filter(Boolean);
  return said.join(" · ");
}

/** What an opinion says when the coders differ by nothing the words can show —
 * one of them simply left the item out. The date, the person and the words are
 * already above the opinions, so only the variables are left to say. */
const REST = [
  "symptom",
  "anxiety",
  "functioning",
  "relationship",
] as const;

/** The fields the coders read differently, which is what an opinion is chosen by.
 * When they wrote the same thing and only differ by who left it out, the whole
 * opinion is shown instead. */
export function telling(
  opinions: Opinion[],
  kind: ItemKind = ItemKind.Event,
): readonly string[] {
  const all = isStructure(kind) ? fieldsOf(kind) : TELLING;
  const differs = all.filter((field) => {
    const seen = new Set(
      opinions.map((opinion) =>
        String(
          (field === "person_name" ? opinion.person_name : opinion.item[field]) ?? "",
        ),
      ),
    );
    return seen.size > 1;
  });
  if (differs.length) return differs;
  return isStructure(kind) ? all : REST;
}

/** Opinions worded the same way are one opinion with a count beside it: the ballot
 * is about the readings, not about how many people are in the room. */
export interface Grouped {
  label: string;
  coders: number;
  opinion: Opinion;
}

export function group(
  item: BallotItem,
  records?: Map<number, CodingRecord>,
): Grouped[] {
  const fields = telling(item.opinions, item.item_kind);
  const found = new Map<string, Grouped>();
  for (const opinion of item.opinions) {
    const label =
      (isStructure(item.item_kind)
        ? versionWords(records?.get(opinion.coding_id ?? -1), opinion.item, fields)
        : words(opinion, fields)) || "as written";
    const already = found.get(label);
    if (already) already.coders += 1;
    else found.set(label, { label, coders: 1, opinion });
  }
  return [...found.values()];
}

/** A line of the conversation quoted on the vote or in the meeting, who said
 * it and their words, the coach's markup drawn as the chat draws it rather
 * than as brackets (R-0072). */
const said = (line: TranscriptLine): string =>
  `<b>${esc(line.who)}:</b> &ldquo;${drawn(tokenize(line.text), asWritten)}&rdquo;`;

export const quote = (line: TranscriptLine): string => `<div class="quote">${said(line)}</div>`;

/** The line a pairing was written from, on top of its screen: two lines of it
 * until a tap shows all of it (R-0965). */
export const passage = (line: TranscriptLine, whole: boolean): string =>
  `<div class="quote${whole ? "" : " clip"}" id="bl-quote"><div class="qt">${said(line)}</div></div>`;

/** The transcript line one version was written from, under that version. A
 * version with no line was not written from anything said: the coach replayed
 * it, or somebody typed it into the editor (R-0278). */
export function versionLine(opinion: Opinion, openable: boolean): string {
  if (!opinion.line)
    return `<div class="quote"><i>no transcript line</i></div>`;
  const open = openable
    ? `<div><button class="chip" type="button" ` +
      `data-said="${opinion.line.statement_id}">open in transcript</button></div>`
    : "";
  return quote(opinion.line) + open;
}


/* ── The vote by pairing ──────────────────────────────────────────────────
 * One screen per thing said in the conversation: every coder's version of it
 * side by side, without names. A coder's version is the whole set of entries
 * they wrote for it, so a pairing of a move and a shift is voted on as one
 * (R-0961, R-0965). */

export interface PairValue {
  field: string;
  said: string;
}

/** Who each coder's person is: the people pairing it is in, keyed by coding
 * and person, so the people a version names are compared by who they are,
 * never by spelling or order (R-0967); and the one name each people pairing
 * is shown by on every card (R-0968). */
export interface Who {
  pairing: Map<string, number>;
  name: Map<number, string>;
}

const personKey = (coding: number, id: unknown) => `${coding}:${String(id)}`;

export function whoOf(items: BallotItem[]): Who {
  const people = items.filter((item) => item.item_kind === ItemKind.Person);
  return {
    pairing: new Map(
      people.flatMap((item) =>
        item.opinions.map((one) => [personKey(one.coding_id!, one.item_id), item.id] as const),
      ),
    ),
    name: new Map(people.map((item) => [item.id, mostGiven(item.opinions)] as const)),
  };
}

/** The name the most coders gave a person; on a tie, the first stored. A name
 * is only a coder's handle on who the person is, so it is never a difference
 * between opinions (R-0968). */
function mostGiven(opinions: Opinion[]): string {
  const coders = new Map<string, Set<number>>();
  for (const one of opinions) {
    const name = text(one.item.name);
    if (name) coders.set(name, (coders.get(name) ?? new Set()).add(one.coding_id!));
  }
  let best = "";
  for (const [name, by] of coders) if (by.size > (coders.get(best)?.size ?? 0)) best = name;
  return best;
}

/** A coder's person as every card names them: their pairing's name, or the
 * coder's own when they are in no pairing. */
const called = (who: Who, coding: number, id: unknown, own: string): string => {
  const pairing = who.pairing.get(personKey(coding, id));
  return (pairing === undefined ? "" : who.name.get(pairing)) || own;
};

/** One coder's entry, as the card draws it: fields by place, never a sentence
 * (R-0966). */
export interface PairEntry {
  coding_id: number;
  item_id: number | string;
  kind: string;
  date: string;
  end: string;
  prec: string;
  cert: string;
  who: string;
  toward: string;
  title: string;
  desc: string;
  values: PairValue[];
  /** What a place is compared by when it is not its words: the people
   * pairings of the people it names, or "" for a value not recorded. */
  keys: Record<string, string>;
  line: TranscriptLine | null;
}

export interface Pairing {
  item: BallotItem;
  line: TranscriptLine | null;
  /** One coder's entries per version, in no order a name could be read from. */
  versions: PairEntry[][];
}

const ARROWS: Record<string, string> = { up: "↑", down: "↓", same: "=" };
const SHIFTS = ["symptom", "anxiety", "functioning"] as const;

/** A year of 1900, year one, or the first of January 1970 is what a copy holds
 * when nobody said a date (R-0956). */
const STAND_IN = /^(1900-|0001-|1970-01-01)/;

/** The date as the coder wrote it, only as far as they said it: an estimate
 * or a date not sure at all as its year, as the timeline says it (R-0855); a
 * stand-in, which nobody said, as no date (R-0956). */
export function writtenDate(entry: PairEntry): string {
  if (!entry.date || STAND_IN.test(entry.date)) return rowsWhen(null);
  const from = GUESSED.has(entry.cert)
    ? dateText(entry.date, entry.cert)
    : rowsWhen(entry.date, entry.prec);
  const to = entry.end && rowsWhen(entry.end, DatePrecision.Year);
  return to && to !== from ? `${from} to ${to}` : from;
}

const GUESSED = new Set<string>([DateCertainty.Approximate, DateCertainty.Unknown]);

const text = (value: unknown) => (value === null || value === undefined ? "" : String(value));

/** The people a version names, as the pairings they are in, in one order; a
 * person in no pairing is known only by name. */
function someone(who: Who, coding: number, ids: unknown[], names: string[]): string {
  return ids
    .map((id, at) => {
      const pairing = who.pairing.get(personKey(coding, id));
      return pairing === undefined ? `=${names[at] ?? ""}` : `#${pairing}`;
    })
    .sort()
    .join("&");
}

function eventEntry(opinion: Opinion, who: Who): PairEntry {
  const event = opinion.item;
  const coding = opinion.coding_id!;
  const about = event.child ?? event.person;
  const toward = (event.relationshipTargets as unknown[] | undefined) ?? [];
  const values: PairValue[] = SHIFTS.filter((field) => event[field]).map((field) => ({
    field,
    said: `${field} ${ARROWS[text(event[field])] ?? text(event[field])}`,
  }));
  if (event.relationship)
    values.push({
      field: "relationship",
      said: `relationship · ${text(event.relationship).replaceAll("-", " ")}`,
    });
  return {
    coding_id: opinion.coding_id!,
    item_id: opinion.item_id!,
    kind: text(event.kind),
    date: text(event.dateTime),
    end: text(event.endDateTime),
    prec: text(event.datePrecision),
    cert: text(event.dateCertainty),
    who:
      about === null || about === undefined
        ? (opinion.person_name ?? "")
        : called(who, coding, about, opinion.person_name ?? ""),
    toward: toward
      .map((id, at) => called(who, coding, id, opinion.toward_names?.[at] ?? ""))
      .join(", "),
    title: text(event.title),
    desc: text(event.description),
    values,
    keys: {
      ...(about === null || about === undefined
        ? {}
        : { who: someone(who, coding, [about], [opinion.person_name ?? ""]) }),
      ...(toward.length ? { toward: someone(who, coding, toward, opinion.toward_names ?? []) } : {}),
    },
    line: opinion.line ?? null,
  };
}

/** A person or a couple on the same card: the kind, the name or the two names,
 * and what the copy says of them as values (R-0326, R-0965). */
const NAMED = ["name", "person_a", "person_b"];

function structureEntry(
  kind: ItemKind,
  opinion: Opinion,
  record: CodingRecord | undefined,
  who: Who,
): PairEntry {
  const coding = opinion.coding_id!;
  const own = record && {
    ...record,
    people: record.people.map((one) => ({ ...one, name: called(who, coding, one.id, one.name) })),
  };
  const item =
    kind === ItemKind.Person
      ? { ...opinion.item, name: called(who, coding, opinion.item.id, text(opinion.item.name)) }
      : opinion.item;
  const named = (id: unknown) => own?.people.find((one) => one.id === Number(id))?.name ?? "";
  const pair = (a: unknown, b: unknown) => someone(who, coding, [a, b], [named(a), named(b)]);
  const bond = own?.pair_bonds.find((one) => one.id === Number(item.parents));
  return {
    coding_id: opinion.coding_id!,
    item_id: opinion.item_id!,
    kind: kind === ItemKind.Person ? "person" : "couple",
    date: "",
    end: "",
    prec: "",
    cert: "",
    who: structureName(kind, item, own?.people ?? []),
    toward: "",
    title: "",
    desc: "",
    values: fieldsOf(kind)
      .filter((field) => !NAMED.includes(field))
      .map((field) => ({ field, said: versionWords(own, item, [field]) }))
      .filter((one) => one.said),
    keys:
      kind === ItemKind.Person
        ? {
            who: someone(who, coding, [item.id], [text(item.name)]),
            parents: bond ? pair(bond.person_a, bond.person_b) : "none",
          }
        : { who: pair(item.person_a, item.person_b) },
    line: opinion.line ?? null,
  };
}

/** A fixed shuffle per pairing, so it reads the same on every visit while no
 * position stands for a coder (R-0252). */
export function shuffled<T>(list: T[], seed: number): T[] {
  let state = (seed * 2654435761) % 2147483648;
  const next = () => {
    state = (state * 1103515245 + 12345) % 2147483648;
    return state / 2147483648;
  };
  const out = [...list];
  for (let at = out.length - 1; at > 0; at -= 1) {
    const other = Math.floor(next() * (at + 1));
    [out[at], out[other]] = [out[other], out[at]];
  }
  return out;
}

/** The line most of a pairing's entries were written from. */
/** The places a card can show under its first two lines, in the order they
 * read, and what an empty one says. */
const PLACES = [...SHIFTS, "relationship", "last_name", "gender", "parents", "married"];
const LINES = ["who", "toward"] as const;
const UNSAID: Record<string, string> = {
  who: "no person recorded",
  toward: "no one recorded",
  symptom: "no symptom recorded",
  anxiety: "no anxiety recorded",
  functioning: "no functioning recorded",
  relationship: "no relationship recorded",
  last_name: "no last name recorded",
  gender: "no gender recorded",
};

const holds = (entry: PairEntry, field: string) =>
  (LINES as readonly string[]).includes(field)
    ? Boolean(entry[field as (typeof LINES)[number]])
    : entry.values.some((one) => one.field === field);

/** An entry lacking a place another entry of its kind in the pairing holds is
 * given it, said as not recorded, so the cards of one kind line up (R-0967); a
 * kind is never given a place it cannot hold, so a noted event beside a shift
 * differs by its kind alone. */
function samePlaces(entries: PairEntry[]): PairEntry[] {
  return entries.map((entry) => {
    const kin = entries.filter((one) => one.kind === entry.kind);
    const shown = (fields: readonly string[]) =>
      fields.filter((field) => kin.some((one) => holds(one, field)));
    const places = shown(PLACES);
    const lines = shown(LINES) as (typeof LINES)[number][];
    const out = { ...entry, keys: { ...entry.keys } };
    for (const field of lines.filter((one) => !holds(entry, one))) {
      out[field] = UNSAID[field];
      out.keys[field] = "";
    }
    out.values = places.map((field) => {
      const found = entry.values.find((one) => one.field === field);
      if (found) return found;
      out.keys[field] = "";
      return { field, said: UNSAID[field] };
    });
    return out;
  });
}

/** A row of the ballot as a pairing: its entries grouped by coder. A coder's
 * several entries are that coder's distinct things, so each keeps the names
 * that coder gave (R-0970). */
export function toPairing(
  item: BallotItem,
  records: Map<number, CodingRecord>,
  who: Who = whoOf([item]),
): Pairing {
  const count = new Map<number, number>();
  for (const { coding_id } of item.opinions) count.set(coding_id!, (count.get(coding_id!) ?? 0) + 1);
  const own: Who = { pairing: who.pairing, name: new Map() };
  const built = item.opinions.map((opinion) => {
    const by = count.get(opinion.coding_id!)! > 1 ? own : who;
    return isStructure(item.item_kind)
      ? structureEntry(item.item_kind, opinion, records.get(opinion.coding_id ?? -1), by)
      : eventEntry(opinion, by);
  });
  const byCoder = new Map<number, PairEntry[]>();
  for (const entry of samePlaces(built))
    byCoder.set(entry.coding_id, [...(byCoder.get(entry.coding_id) ?? []), entry]);
  const versions = shuffled(
    [...byCoder.keys()].sort((a, b) => a - b).map((id) => byCoder.get(id)!),
    item.id,
  );
  return { item, versions, line: shownLine(item) };
}

export function fieldValue(entry: PairEntry, field: string): string {
  if (field === "kind") return entry.kind;
  if (field === "who") return entry.who;
  if (field === "toward") return entry.toward;
  if (field === "date") return writtenDate(entry);
  return entry.values.find((one) => one.field === field)?.said ?? "";
}

/** What a place is compared by: who the people are, never their spelling or
 * order; a value nobody recorded equals every other value nobody recorded. */
const keyOf = (entry: PairEntry, field: string) => entry.keys[field] ?? fieldValue(entry, field);

const placesOf = (entry: PairEntry) => [
  "kind",
  "who",
  "toward",
  "date",
  ...entry.values.map((one) => one.field),
];

/** Two entries say the same thing when every place holds the same value; the
 * words the coders used may differ. */
const sameness = (entry: PairEntry) =>
  placesOf(entry)
    .map((field) => `${field}\u0000${keyOf(entry, field)}`)
    .join("|");

/** One opinion: the entries its card draws, and for each of them every
 * coder's entry that says the same, which a tap on it selects together. */
export interface PairOpinion {
  entries: PairEntry[];
  twins: PairEntry[][];
  codings: number[];
}

/** Versions that read the same are one opinion, on the vote and on Patrick's
 * look over the pairings alike (R-0965, R-0967). */
export function pairOpinions(pairing: Pairing): PairOpinion[] {
  const found = new Map<string, PairOpinion>();
  for (const entries of pairing.versions) {
    const key = entries.map(sameness).sort().join("‖");
    const already = found.get(key);
    if (!already) {
      found.set(key, {
        entries,
        twins: entries.map((entry) => [entry]),
        codings: [entries[0].coding_id],
      });
      continue;
    }
    already.codings.push(entries[0].coding_id);
    const left = [...entries];
    already.entries.forEach((entry, at) => {
      const twin = left.findIndex((one) => sameness(one) === sameness(entry));
      already.twins[at].push(...left.splice(twin, 1));
    });
  }
  return [...found.values()];
}

/** The places the opinions disagree on: the accent goes on such a place in
 * every card, and never on a place all opinions agree on; an opinion's own
 * entries are never compared with each other (R-0965, R-0967). */
export function pairDiffers(opinions: PairOpinion[]): Set<string> {
  const held = (one: PairOpinion, field: string) =>
    [...new Set(one.entries.map((entry) => keyOf(entry, field)))].sort().join("\u0000");
  const places = new Set(opinions.flatMap((one) => one.entries.flatMap(placesOf)));
  return new Set(
    [...places].filter((field) => new Set(opinions.map((one) => held(one, field))).size > 1),
  );
}

const shade = (differs: boolean) => (differs ? "pv-diff" : "pv-same");

/** No field names; the kind and the date on the first line, who and toward
 * on the second, the values as the app's own chips on the third (R-0966). A
 * row inside a box of several leaves an undated kind to the box's line
 * (R-0970). */
function entryRows(entry: PairEntry, differs: Set<string>, row = false): string {
  const lit = (field: string) => shade(differs.has(field));
  const part = (field: string) =>
    `<span class="${entry.keys[field] === "" ? "chip " : ""}${lit(field)}">` +
    `${esc(fieldValue(entry, field))}</span>`;
  const values = entry.values
    .map((one) => `<span class="chip ${lit(one.field)}">${esc(one.said)}</span>`)
    .join("");
  const dated = !["person", "couple"].includes(entry.kind);
  return (
    (row && !dated
      ? ""
      : `<div class="pv-l1"><span class="pv-tag ${lit("kind")}">` +
        `${esc(entry.kind)}</span>${dated ? part("date") : ""}</div>`) +
    `<div class="pv-l2">${part("who")}` +
    (entry.toward ? ` <span class="pv-arrow">→</span> ${part("toward")}` : "") +
    `</div>` +
    (values ? `<div class="pv-l3">${values}</div>` : "")
  );
}

/** What the coder wrote in their own words, read under the fields. */
const ownWords = (entry: PairEntry, whole: boolean) => {
  const said = [entry.title, entry.desc !== entry.title ? entry.desc : ""].filter(Boolean);
  return said.length
    ? `<div class="pv-words${whole ? "" : " clip"}">${esc(said.join(" · "))}</div>`
    : "";
};

export const entryKey = (entry: { coding_id: number; item_id: number | string }) =>
  `${entry.coding_id}:${entry.item_id}`;

/** Every coder's entry an opinion stands for. */
export const opinionKeys = (one: PairOpinion) => one.twins.flat().map(entryKey);

const boxed = (one: PairOpinion, chosen: Set<string>) =>
  opinionKeys(one).every((key) => chosen.has(key));

/** What a box holding one coder's several entries calls them (R-0970). */
const MANY: Record<string, [string, string]> = {
  person: ["person", "people"],
  couple: ["couple", "couples"],
};

export const many = (one: PairOpinion) => one.entries.length > 1;

function manyLine(one: PairOpinion): string {
  const [tag, noun] = MANY[one.entries[0].kind] ?? ["event", "events"];
  return (
    `<div class="pv-l1 pv-many"><span class="pv-tag pv-same">${tag}</span>` +
    `<span>wrote ${one.entries.length} separate ${noun}</span></div>`
  );
}

/** The opinions of a pairing, each one box under a small "opinion N" label,
 * a coder's several entries rows inside it (R-0970). `lit` is the opinion
 * picked; `chosen` the entries selected for a split, which light a box when
 * they hold all of it. No count of the coders behind an opinion is shown
 * (R-0252, R-0272). */
export function opinionCards(
  opinions: PairOpinion[],
  lit: number | null,
  whole: boolean,
  chosen: Set<string> = new Set(),
): string {
  const differs = pairDiffers(opinions);
  return (
    `<div class="pv-ops">` +
    opinions
      .map(
        (one, index) =>
          `<div class="pv-label">opinion ${index + 1}</div>` +
          `<div class="opinion tap pv${many(one) ? " many" : ""}` +
          `${lit === index || boxed(one, chosen) ? " on" : ""}" data-opinion="${index}">` +
          (many(one) ? manyLine(one) : "") +
          one.entries
            .map((entry) => `<div class="pv-entry">${entryRows(entry, differs, many(one))}</div>`)
            .join("") +
          one.entries.map((entry) => ownWords(entry, whole)).join("") +
          `</div>`,
      )
      .join("") +
    `</div>`
  );
}

/** An opinion a voter wrote with change…, drawn as the coders' cards are, its
 * people named as the people pairings name them (R-0965, R-0966). */
export function ownCard(
  pairing: Pairing,
  value: Record<string, unknown>,
  records: Map<number, CodingRecord>,
  who: Who,
  whole: boolean,
): string {
  const { item } = pairing;
  const coding = item.opinions[0]?.coding_id ?? -1;
  const named = (id: unknown) => item.people.find((one) => one.id === Number(id))?.name ?? "";
  const about = value.child ?? value.person;
  const opinion: Opinion = {
    coding_id: coding,
    item_id: "yours",
    person_name: about === null || about === undefined ? null : named(about),
    toward_names: ((value.relationshipTargets as unknown[] | undefined) ?? []).map(named),
    item: value,
  };
  const built = isStructure(item.item_kind)
    ? structureEntry(item.item_kind, opinion, records.get(coding), who)
    : eventEntry(opinion, who);
  const entry = samePlaces([...pairing.versions.flat(), built]).at(-1)!;
  const differs = pairDiffers([
    ...pairOpinions(pairing),
    { entries: [entry], twins: [[entry]], codings: [coding] },
  ]);
  return (
    `<div class="pv-label">your opinion</div>` +
    `<div class="opinion pv on"><div class="pv-entry">${entryRows(entry, differs)}</div>` +
    `${ownWords(entry, whole)}</div>`
  );
}

/** "N coders left this event out", today's wording, only when one did. */
export function leftOut(item: BallotItem): string {
  return item.not_coded
    ? `<div class="note">${item.not_coded} coder${item.not_coded === 1 ? "" : "s"} left this ` +
        `${isStructure(item.item_kind) ? "out" : "event out"}</div>`
    : "";
}

/** One dot per pairing, in rows of 33, no numbers (R-0965). */
export const DOTS = { width: 400, edge: 16, row: 24, top: 14, perRow: 33 };

export function drawPairs(
  ids: number[],
  current: number,
  done: (id: number) => boolean,
): { svg: string; height: number } {
  const rows = Math.max(Math.ceil(ids.length / DOTS.perRow), 1);
  const height = DOTS.top * 2 + DOTS.row * (rows - 1);
  const step = (DOTS.width - DOTS.edge * 2) / DOTS.perRow;
  const dots = ids
    .map((id, index) => {
      const x = DOTS.edge + step * ((index % DOTS.perRow) + 0.5);
      const y = DOTS.top + DOTS.row * Math.floor(index / DOTS.perRow);
      const [cls, r] = id === current ? ["d-on", 6.5] : done(id) ? ["d-ok", 4] : ["d-no", 4];
      return `<circle class="${cls}" cx="${x.toFixed(1)}" cy="${y}" r="${r}" data-item="${id}"/>`;
    })
    .join("");
  return {
    height,
    svg:
      `<div class="ss tl"><svg viewBox="0 0 ${DOTS.width} ${height}" height="${height}">` +
      `${dots}</svg></div>`,
  };
}

/** What the strip says a screen is on: a person or a couple by the name, an
 * event by the date its first shown opinion gives, or nothing when no opinion
 * gives one (R-0326). */
export const nowWords = (pairing: Pairing): string => {
  const entries = pairOpinions(pairing).flatMap((one) => one.entries);
  if (isStructure(pairing.item.item_kind)) return entries[0]?.who ?? "";
  const dated = entries.find((one) => one.date && !STAND_IN.test(one.date));
  return dated ? writtenDate(dated) : "";
};

/** The screen both the vote and Patrick's look over the pairings draw on: the
 * strip of dots over the card, and the bar pinned at the foot. */
export interface PairScreen {
  view: HTMLElement;
  caption: HTMLElement;
  body: HTMLElement;
  bar: HTMLElement;
  overlay: HTMLElement;
}

export function drawStrip(
  screen: PairScreen,
  ids: number[],
  current: Pairing,
  done: (id: number) => boolean,
  open: string,
): void {
  const { svg, height } = drawPairs(ids, current.item.id, done);
  const now = nowWords(current);
  screen.view.innerHTML = svg;
  screen.view.style.height = `${height}px`;
  screen.caption.classList.add("pv-wrap");
  screen.caption.innerHTML =
    `<span class="cta">tap a dot to jump</span>` +
    `<button class="tok g" type="button">now${now ? ` · ${esc(now)}` : ""}</button>` +
    `<button class="tok" type="button">${esc(open)}</button>`;
}

/** The sheet that slides up over a pairing screen. */
export class PairSheet {
  private scrim = el("div", "fs-scrim");
  readonly sheet = el("div", "fs-sheet bl-sheet");
  private hiding = 0;

  constructor(overlay: HTMLElement) {
    overlay.append(this.scrim, this.sheet);
    this.scrim.hidden = true;
    this.sheet.hidden = true;
    this.scrim.addEventListener("click", () => this.close());
  }

  show(content: HTMLElement | string): void {
    this.sheet.innerHTML = `<div class="fs-handle"><div class="fs-grab"></div></div>`;
    const scroller = el("div", "fs-body");
    if (typeof content === "string") scroller.innerHTML = content;
    else scroller.append(content);
    this.sheet.append(scroller);
    window.clearTimeout(this.hiding);
    this.scrim.hidden = false;
    this.sheet.hidden = false;
    void this.sheet.offsetWidth;
    this.scrim.classList.add("in");
    this.sheet.classList.add("in");
  }

  close(): void {
    this.scrim.classList.remove("in");
    this.sheet.classList.remove("in");
    this.hiding = window.setTimeout(() => {
      this.scrim.hidden = true;
      this.sheet.hidden = true;
    }, 280);
  }
}

/** The people "change…" offers: one per people pairing, by its most given
 * name, so a person two copies or two entries hold is listed once; a person
 * in no pairing by their own name (R-0968). */
export function choosable(item: BallotItem, who: Who): Person[] {
  const coding = item.opinions[0]?.coding_id ?? -1;
  const seen = new Set<number>();
  return item.people.flatMap((one) => {
    const pairing = who.pairing.get(personKey(coding, one.id));
    if (pairing === undefined) return [{ id: one.id, name: one.name } as Person];
    if (seen.has(pairing)) return [];
    seen.add(pairing);
    return [{ id: one.id, name: who.name.get(pairing) || one.name } as Person];
  });
}

export class Ballot {
  private session = "";
  /** A ratified cut is read rather than voted on, and lights the version the
   * meeting kept (R-0339). */
  private ratified = false;
  private pairings: Pairing[] = [];
  private records = new Map<number, CodingRecord>();
  private who: Who = whoOf([]);
  private mine = new Map<number, Vote>();
  private at = 0;
  /** Pairings whose passage, or whose coders' own words, are shown whole. */
  private whole = new Set<number>();
  private full = new Set<number>();
  private sheet: PairSheet;
  /** The look over the pairings draws on the same screen, so only the one
   * open answers its taps. */
  private live = false;

  constructor(
    private screen: PairScreen,
    private handlers: BallotHandlers,
  ) {
    this.sheet = new PairSheet(screen.overlay);
    screen.body.addEventListener("click", (clicked) => this.onTap(clicked));
    screen.bar.addEventListener("click", (clicked) => this.onTap(clicked));
    screen.body.addEventListener("change", (changed) => {
      if (this.live && (changed.target as Element).id === "bl-say")
        void this.say((changed.target as HTMLInputElement).value);
    });
    screen.view.addEventListener("click", (clicked) => this.onDot(clicked));
  }

  /** The pairing on screen, so stepping out to the transcript and back comes
   * back to it. */
  onItem(): number | null {
    return this.pairing()?.item.id ?? null;
  }

  /** Open the ballot of one cut on the first pairing this coder has not voted
   * on, or on `itemId` when coming back to one (R-0257). */
  async open(cutId: number, itemId: number | null = null): Promise<void> {
    const [cut, items, votes, records] = await Promise.all([
      api.cut(cutId),
      api.items(cutId),
      api.votes(cutId),
      api.records(cutId),
    ]);
    this.live = true;
    this.session = cut.session;
    this.ratified = cut.ratified_at !== null;
    this.records = new Map(records.map((one) => [one.coding_id, one]));
    this.who = whoOf(items);
    this.pairings = ballotOrder(items).map((one) => toPairing(one, this.records, this.who));
    this.mine = new Map(votes.map((vote) => [vote.review_item_id, vote]));
    const back = this.pairings.findIndex((one) => one.item.id === itemId);
    this.at = back >= 0 ? back : Math.max(this.unvoted(0), 0);
    this.render();
  }

  private unvoted(from: number): number {
    const count = this.pairings.length;
    for (let step = 0; step < count; step += 1) {
      const index = (from + step) % count;
      if (!this.mine.has(this.pairings[index].item.id)) return index;
    }
    return -1;
  }

  private pairing(): Pairing | null {
    return this.pairings[this.at] ?? null;
  }

  private render(): void {
    const pairing = this.pairing();
    if (!pairing) {
      this.screen.body.innerHTML = `<div class="none">Nothing left to vote on.</div>`;
      this.screen.view.innerHTML = "";
      this.screen.caption.innerHTML = "";
      this.screen.bar.innerHTML = "";
      return;
    }
    this.handlers.onTitle({
      name: this.session,
      tail: `ballot · ${this.at + 1} of ${this.pairings.length}`,
    });
    const left = this.pairings.filter((one) => !this.mine.has(one.item.id)).length;
    drawStrip(
      this.screen,
      this.pairings.map((one) => one.item.id),
      pairing,
      (id) => this.mine.has(id),
      `${left} open`,
    );
    this.screen.body.innerHTML = this.card(pairing);
    this.screen.bar.innerHTML = this.controls(pairing);
  }

  private card(pairing: Pairing): string {
    const { item } = pairing;
    const vote = this.mine.get(item.id);
    const opinions = pairOpinions(pairing);
    const coding = litCoding(item, vote, this.ratified);
    const lit = opinions.findIndex((one) => one.codings.includes(coding ?? -1));
    const own =
      vote?.choice === VoteChoice.Change && vote.value
        ? ownCard(pairing, vote.value, this.records, this.who, this.full.has(item.id))
        : "";
    return (
      `<div class="bl-card pv-card">` +
      (pairing.line
        ? passage(pairing.line, this.whole.has(item.id)) +
          `<div><button class="chip" id="bl-line" type="button">open in transcript</button></div>`
        : "") +
      opinionCards(opinions, lit >= 0 ? lit : null, this.full.has(item.id)) +
      own +
      leftOut(item) +
      `</div>` +
      `<label class="saylab" for="bl-say">Say why you voted as you did ` +
      `(optional — you may skip it)</label>` +
      `<input class="say" id="bl-say" type="text" placeholder="say why (optional)" ` +
      `value="${esc(vote?.reason ?? "")}">`
    );
  }

  /** The controls stay at the foot of the screen while the pairing scrolls. */
  private controls(pairing: Pairing): string {
    const dropped = this.mine.get(pairing.item.id)?.choice === VoteChoice.Drop ? " on" : "";
    return (
      stepBtn("‹ Back", `id="bl-prev"`, this.at === 0) +
      `<button class="btn" id="bl-change" type="button">change&hellip;</button>` +
      `<button class="btn${dropped}" id="bl-drop" type="button">drop</button>` +
      stepBtn(this.last() ? "Done" : "Next ›", `id="bl-next"`, false)
    );
  }

  /** The last screen of the ballot: nothing is left unvoted after this one. */
  private last(): boolean {
    const id = this.pairing()?.item.id;
    return this.pairings.every((one) => one.item.id === id || this.mine.has(one.item.id));
  }

  private onTap(clicked: Event): void {
    const target = clicked.target as Element;
    const pairing = this.pairing();
    if (!pairing || !this.live) return;
    const { item } = pairing;
    const opinion = target.closest<HTMLElement>(".opinion[data-opinion]");
    if (target.closest(".pv-words.clip")) {
      this.full.add(item.id);
      this.render();
    } else if (opinion) {
      const picked = pairOpinions(pairing)[Number(opinion.dataset.opinion)];
      void this.vote(VoteChoice.Opinion, { coding_id: picked.codings[0] });
    } else if (target.closest("#bl-drop")) void this.vote(VoteChoice.Drop, null);
    else if (target.closest("#bl-change")) this.change(item);
    else if (target.closest("#bl-quote.clip")) {
      this.whole.add(item.id);
      this.render();
    } else if (target.closest("#bl-line") && pairing.line)
      this.handlers.onTranscript(pairing.line.statement_id);
    else if (target.closest("#bl-prev") && this.at > 0) this.step(this.at - 1);
    else if (target.closest("#bl-next")) this.next();
  }

  private step(at: number): void {
    this.at = at;
    this.render();
    this.handlers.onMoved();
  }

  private onDot(clicked: Event): void {
    const dot = (clicked.target as Element).closest<HTMLElement>("[data-item]");
    if (!dot || !this.live) return;
    this.step(this.pairings.findIndex((one) => one.item.id === Number(dot.dataset.item)));
  }

  private reason(): string | null {
    const said = this.screen.body.querySelector<HTMLInputElement>("#bl-say");
    return said?.value.trim() || null;
  }

  /** A second tap on the opinion already picked, or on drop when dropped,
   * takes the vote back and the pairing is open again (R-0965). */
  private async vote(
    choice: VoteChoice,
    value: Record<string, unknown> | null,
  ): Promise<void> {
    const pairing = this.pairing()!;
    const { item } = pairing;
    if (this.ratified) return;
    tap(Feature.BallotVote);
    const had = this.mine.get(item.id);
    const again =
      had?.choice === choice &&
      (choice === VoteChoice.Drop ||
        (choice === VoteChoice.Opinion &&
          pairOpinions(pairing).some(
            (one) =>
              one.codings.includes(Number(had.value?.coding_id)) &&
              one.codings.includes(Number(value?.coding_id)),
          )));
    if (again) {
      await api.unvote(item.id);
      this.mine.delete(item.id);
    } else this.mine.set(item.id, await api.castVote(item.id, choice, value, this.reason()));
    this.render();
  }

  /** Why you voted as you did, said after the vote itself. */
  private async say(reason: string): Promise<void> {
    const item = this.pairing()?.item;
    const vote = item ? this.mine.get(item.id) : null;
    if (!item || !vote) return;
    this.mine.set(item.id, await api.castVote(item.id, vote.choice, vote.value, reason || null));
  }

  /** The next pairing still open, from here on and then from the top; when
   * every one has a vote the ballot is finished. */
  private next(): void {
    const found = this.unvoted(this.at + 1);
    if (found < 0) {
      this.handlers.onDone();
      return;
    }
    this.step(found);
  }

  /** The family one version was written on, which the editor of a person or a
   * bond needs to offer the couples and the partners it can name. */
  private family(item: BallotItem): Family {
    const record = this.records.get(item.opinions[0]?.coding_id ?? -1);
    return {
      people: (record?.people ?? []) as Person[],
      pair_bonds: record?.pair_bonds ?? [],
      events: record?.events ?? [],
    };
  }

  private bondEditor(item: BallotItem, bond: PairBond): HTMLElement {
    const family = this.family(item);
    const self = family.people.find((one) => one.id === bond.person_a) ?? family.people[0];
    return openBondEditor(bond, self, family, {
      done: () => this.sheet.close(),
      onSave: (body) => void this.own({ ...bond, ...body }),
    });
  }

  /** "change…" opens the app's own editor over the ballot, prefilled, so you can
   * write an opinion nobody wrote (R-0257, R-0326). */
  private change(item: BallotItem): void {
    tap(Feature.BallotChange);
    const vote = this.mine.get(item.id);
    const from =
      vote?.choice === VoteChoice.Change ? vote.value : (item.opinions[0]?.item ?? {});
    const people = choosable(item, this.who);
    const editor =
      item.item_kind === ItemKind.Person
        ? openPersonEditor(from as unknown as Person, {
            done: () => this.sheet.close(),
            family: this.family(item),
            onSave: (body) => void this.own({ ...from, ...body }),
          })
        : item.item_kind === ItemKind.PairBond
          ? this.bondEditor(item, from as unknown as PairBond)
          : openEditor(
              from as unknown as TimelineEvent,
              people,
              () => this.sheet.close(),
              undefined,
              undefined,
              (body) => void this.own(body),
            );
    // The person form's parents and pair-bond pickers write to the diagram
    // itself, not to the vote, so they stay shut while hand edits are off.
    if (!HAND_EDITS)
      editor
        .querySelectorAll<HTMLButtonElement>(".parents, .bondrow")
        .forEach((one) => (one.disabled = true));
    editor.querySelector(".save")!.textContent = "save as my opinion";
    editor
      .querySelector(".acts")
      ?.before(
        el(
          "div",
          "hint",
          "The transcript line and the session it came from are kept with the " +
            "event; they are not edited here.",
        ),
      );
    editor.querySelector(".del")?.remove();
    editor.querySelector(".acts")?.append(el("button", "del", "cancel"));
    editor.querySelector(".acts .del")!.addEventListener("click", () => this.sheet.close());
    this.sheet.show(editor);
  }

  private async own(body: Record<string, unknown>): Promise<void> {
    await this.vote(VoteChoice.Change, body);
    this.sheet.close();
  }

  close(): void {
    this.live = false;
    this.sheet.close();
  }
}
