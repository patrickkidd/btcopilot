import { esc } from "./dom";
import { pill } from "./chips";
import { ChipKind, type Chip, type Person, type Timeline, type TimelineEvent } from "./types";

/** The card a coach's question about two people carries: who each is, side by
 * side, what the record says of them in grey and what the two disagree on in
 * amber (Patrick's pick M1). The whole card is one chip: a tap drops it in the
 * message box as the reader's yes, and nothing joins until they send it. */

interface Fact {
  key: string;
  text: string;
}

/** A count of events is no fact about who someone is, so it never differs. */
const COUNT = "events";

const PARENT: Record<string, string> = { male: "father", female: "mother" };

const involves = (e: TimelineEvent, id: number) =>
  [e.person, e.spouse, e.child, ...e.relationshipTargets, ...e.relationshipTriangles].includes(id);

function facts(person: Person, t: Timeline): Fact[] {
  const bonds = t.pair_bonds
    .filter((b) => b.person_a === person.id || b.person_b === person.id)
    .map((b) => b.id);
  const child = t.people.find((p) => p.parents !== null && bonds.includes(p.parents));
  const death = t.events.find((e) => e.id === person.death_event)?.dateTime;
  const count = t.events.filter((e) => involves(e, person.id)).length;
  return [
    child ? { key: "role", text: `${child.name}'s ${PARENT[person.gender ?? ""] ?? "parent"}` } : null,
    person.birth ? { key: "born", text: `born ${person.birth.slice(0, 4)}` } : null,
    death ? { key: "died", text: `died ${death.slice(0, 4)}` } : null,
    { key: COUNT, text: count === 1 ? "1 event" : `${count} events` },
  ].filter((f): f is Fact => f !== null);
}

const name = (p: Person) => [p.name, p.last_name].filter(Boolean).join(" ");

function half(person: Person, mine: Fact[], theirs: Fact[]): string {
  const differs = (f: Fact) =>
    f.key !== COUNT && theirs.some((o) => o.key === f.key && o.text !== f.text);
  return (
    `<span class="half"><span class="nm">${esc(name(person))}</span>` +
    `<span class="facts">${mine
      .map((f) => `<span${differs(f) ? ' class="differ"' : ""}>${esc(f.text)}</span>`)
      .join(" · ")}</span></span>`
  );
}

export function card(chip: Chip, t: Timeline): string {
  const [keep, drop] = chip.target.split(",").map((id) => t.people.find((p) => String(p.id) === id.trim()));
  const label = chip.label;
  // joined since, or the record not here yet: the yes it asked for, as a pill
  if (!keep || !drop) return pill(chip, label);
  const [a, b] = [facts(keep, t), facts(drop, t)];
  return (
    `<button type="button" class="chip ${chip.tone} merge" data-kind="${ChipKind.Merge}" ` +
    `data-target="${esc(chip.target)}" data-full="${esc(label)}" title="${esc(label)}">` +
    half(keep, a, b) +
    half(drop, b, a) +
    `<span class="yes">${esc(label)}</span></button>`
  );
}
