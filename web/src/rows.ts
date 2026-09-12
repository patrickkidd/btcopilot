import { esc } from "./dom";
import type { Cluster, Person, TimelineEvent } from "./types";

/** The rows the record is read as, in the drawer and on the coding screen:
 * one line for what it is, one for when and who. One renderer, so the two
 * lists cannot drift apart. */

const UNPLACED = "unplaced";
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

export function when(event: TimelineEvent): string {
  if (!event.dateTime) return "no date yet";
  const [year, month] = event.dateTime.split("-");
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
  const meta = [when(event), event.person_name, codes(event, names)]
    .filter(Boolean)
    .join(" \u00b7 ");
  return (
    `<div class="row${on ? " on" : ""}" data-event="${event.id}" ` +
    `role="button" tabindex="0">` +
    `<div class="r1">${esc(event.label)}</div>` +
    `<div class="r2">${esc(meta)}</div></div>`
  );
}

export function personRow(person: Person, on = false): string {
  const meta = [
    person.birth ? `born ${person.birth.slice(0, 4)}` : "no birth on the record",
    person.gender,
    person.primary ? "you" : "",
  ]
    .filter(Boolean)
    .join(" \u00b7 ");
  return (
    `<div class="row${on ? " on" : ""}" data-person="${person.id}" ` +
    `role="button" tabindex="0">` +
    `<div class="r1">${esc(fullName(person))}</div>` +
    `<div class="r2">${esc(meta)}</div></div>`
  );
}

/** The header over a stretch of rows: the cluster they belong to and how many
 * events it holds. The word is "event" everywhere (R-0289). */
export function eventDivider(cluster: Cluster | undefined): string {
  const count = cluster
    ? `${cluster.count} event${cluster.count === 1 ? "" : "s"}`
    : "";
  return (
    `<div class="div"><span>${esc(cluster ? cluster.label : UNPLACED)}</span>` +
    `<span class="dcount">${esc(count)}</span></div>`
  );
}
