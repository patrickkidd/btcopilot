import { crossOut, Mark, outline, Sex, sexOf, slashes, tie } from "./diagram";
import { esc } from "./dom";
import { BIRTHS, bondOf, COUPLE_KINDS, ENDS } from "./snapshots";
import { DateCertainty, EventKind, type Cluster, type Person, type Timeline, type TimelineEvent } from "./types";

/** The rows the record is read as, in the drawer and on the coding screen:
 * one line for what it is, one for when and who. One renderer, so the two
 * lists cannot drift apart. */

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

const ARROW: Record<string, string> = {
  up: "\u2191",
  down: "\u2193",
  same: "=",
};

const SHIFTS: [keyof TimelineEvent, string][] = [
  ["symptom", "S"],
  ["anxiety", "A"],
  ["functioning", "F"],
];

export function when(dateTime: string | null): string {
  if (!dateTime) return "no date yet";
  const [year, month] = dateTime.split("-");
  return month ? `${MONTHS[Number(month) - 1]} ${year}` : year;
}

/** The row's second line must not overflow the phone, so the shifts and the
 * move are abbreviated: `S\u2191 A\u2191 F= R conflict\u2192mom` (owner ruling 2026-09-03). */
export function codes(event: TimelineEvent, names: Map<number, string>): string {
  const out: string[] = [];
  for (const [field, letter] of SHIFTS) {
    const value = event[field] as string | null;
    if (value) out.push(letter + (ARROW[value] ?? ` ${value}`));
  }
  if (event.relationship) {
    const named = (ids: number[]) =>
      ids.map((id) => names.get(id) ?? "?").join(",");
    const targets = event.relationshipTargets.length
      ? `\u2192${named(event.relationshipTargets)}`
      : "";
    const triangles = event.relationshipTriangles.length
      ? ` \u25b3${named(event.relationshipTriangles)}`
      : "";
    out.push(`R ${event.relationship}${targets}${triangles}`);
  }
  return out.join("  ");
}

/** What the record calls someone, both names when it holds both. */
export const fullName = (person: Person) =>
  [person.name, person.last_name].filter(Boolean).join(" ");

type Tree = Pick<Timeline, "people" | "pair_bonds">;

/** The kinds the family diagram draws a mark of its own for. */
const drawn = (kind: string) =>
  COUPLE_KINDS.has(kind) || kind in ENDS || BIRTHS.has(kind) || kind === EventKind.Death;

/** The event's kind as the family diagram draws it, at the size of a row
 * (R-0113): the couple's line with its slashes, or the person, crossed out at a
 * death. Empty for a kind the diagram has no mark for, so the words still line up. */
export function kindMark(event: TimelineEvent, tree: Tree): string {
  const kind = event.kind ?? "";
  const shape = (id: number | null) => ({
    name: "",
    g: sexOf(tree.people.find((p) => p.id === id)?.gender ?? null),
    born: null,
  });
  let out = "";
  if (COUPLE_KINDS.has(kind) || kind in ENDS) {
    const bond = bondOf(tree.pair_bonds, event.person, event.spouse);
    if (!bond) throw new Error(`event ${event.id} is about a couple the record does not hold`);
    let [a, b] = [shape(bond.person_a), shape(bond.person_b)];
    if (b.g === Sex.Male && a.g !== Sex.Male) [a, b] = [b, a];
    out =
      tie(6.5, 11, 21.5, 11, 20, bond.married) +
      outline(a, 6.5, 7, 4, "shape") +
      outline(b, 21.5, 7, 4, "shape") +
      slashes(ENDS[kind] === Mark.Divorced ? 2 : ENDS[kind] ? 1 : 0, 14, 20, 30);
  } else if (drawn(kind)) {
    const who = shape(BIRTHS.has(kind) ? event.child : event.person);
    out = outline(who, 14, 14, 7, "shape") + (kind === EventKind.Death ? crossOut(14, 14, 7, false, "xd") : "");
  }
  return `<svg class="kmark" viewBox="0 0 28 28" aria-hidden="true">${out}</svg>`;
}

/** The first line: the server's words for the event, with the kind that opens
 * them in the data colour when the diagram has a mark for it. A description that
 * already says the kind is the label whole, and stays as it is. */
function title(event: TimelineEvent): string {
  const said = event.label !== (event.description ?? "").trim();
  if (!drawn(event.kind ?? "") || !said) return esc(event.label);
  const [word] = event.label.split(" \u00b7 ");
  return `<span class="kw">${esc(word)}</span>${esc(event.label.slice(word.length))}`;
}

export function eventRow(
  event: TimelineEvent,
  names: Map<number, string>,
  tree: Tree,
  on = false,
): string {
  const meta = [when(event.dateTime), event.person_name, codes(event, names)]
    .filter(Boolean)
    .join(" \u00b7 ");
  return (
    `<div class="row side${on ? " on" : ""}" data-event="${event.id}" ` +
    `role="button" tabindex="0">` +
    kindMark(event, tree) +
    `<div class="rmain"><div class="r1">${title(event)}</div>` +
    `<div class="r2">${esc(meta)}</div></div></div>`
  );
}

/** The people list stays as it is: the name alone, no second line under it
 * (R-0326). */
export function personRow(person: Person, on = false): string {
  return (
    `<div class="row${on ? " on" : ""}" data-person="${person.id}" ` +
    `role="button" tabindex="0">` +
    `<div class="r1">${esc(fullName(person))}</div></div>`
  );
}

/** What the rows under a header share when no cluster holds them: a place on
 * the line and no cluster, or no date the record is sure of — none at all, or
 * only a guess — and so no place on the line yet. */
export enum Loose {
  Dated = "not in a cluster",
  Undated = "no sure date yet",
}

/** The stretch of rows an event is listed under. */
export const groupOf = (event: TimelineEvent, cluster: Cluster | undefined) =>
  cluster ??
  (event.dateTime && event.dateCertainty !== DateCertainty.Unknown ? Loose.Dated : Loose.Undated);

/** The events list in its stretches, in time order: a cluster once, under one
 * header where its first event falls, with every event it holds, even those
 * dated after a loose event inside its years; the events no cluster holds in
 * runs between them. */
export function sections(
  events: TimelineEvent[],
  clusterOf: (id: number) => Cluster | undefined,
): { group: Cluster | Loose; events: TimelineEvent[] }[] {
  const out: { group: Cluster | Loose; events: TimelineEvent[] }[] = [];
  for (const event of events) {
    const group = groupOf(event, clusterOf(event.id));
    const held =
      typeof group === "string"
        ? out.at(-1)?.group === group ? out.at(-1) : undefined
        : out.find((section) => section.group === group);
    if (held) held.events.push(event);
    else out.push({ group, events: [event] });
  }
  return out;
}

/** The header over a stretch of rows: the cluster they belong to and how many
 * events it holds, or why no cluster does. The word is "event" everywhere
 * (R-0289). */
export function eventDivider(group: Cluster | Loose): string {
  const loose = typeof group === "string";
  const count = loose ? "" : `${group.count} event${group.count === 1 ? "" : "s"}`;
  return (
    `<div class="div"><span>${esc(loose ? group : group.label)}</span>` +
    `<span class="dcount">${esc(count)}</span></div>`
  );
}
