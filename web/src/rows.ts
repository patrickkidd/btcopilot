import { esc } from "./dom";
import { DateCertainty, type Cluster, type Person, type TimelineEvent } from "./types";

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

export function eventRow(
  event: TimelineEvent,
  names: Map<number, string>,
  on = false,
): string {
  const meta = [when(event.dateTime), event.person_name, codes(event, names)]
    .filter(Boolean)
    .join(" \u00b7 ");
  return (
    `<div class="row${on ? " on" : ""}" data-event="${event.id}" ` +
    `role="button" tabindex="0">` +
    `<div class="r1">${esc(event.label)}</div>` +
    `<div class="r2">${esc(meta)}</div></div>`
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
