import { el, esc } from "./dom";
import { fullName, when } from "./rows";
import {
  ChipKind,
  ChipTone,
  DateCertainty,
  type Chip,
  type Cluster,
  type Person,
  type Timeline,
  type TimelineEvent,
} from "./types";

/** One event or one person, read-only, opened by a tap on its row in the lists
 * (Patrick's pick D2, 2026-10-01, and the same for people the same day). What
 * the record holds is shown and nothing is changed here; the one action at the
 * foot carries the thing into the chat, where it is changed by talking (D3). */

export const TALK_EVENT = "Tap to comment or change this event in chat";
export const TALK_PERSON = "Tap to comment or change this person in chat";

const SURE: Record<string, string> = {
  [DateCertainty.Approximate]: "around then",
  [DateCertainty.Unknown]: "not sure of the date",
};

const SHIFTS: (keyof TimelineEvent)[] = ["symptom", "anxiety", "functioning"];

/** The kinds of person the record keeps that say something on their own;
 * unknown says nothing, so it is not shown. */
const UNSAID = "unknown";

export interface DetailHooks {
  /** The thing goes into the message box as a lit chip, and the chat comes up. */
  talk: (chip: Chip) => void;
  cluster: (id: string) => void;
  person: (id: number) => void;
  event: (id: number) => void;
}

const row = (key: string, value: string) =>
  `<div class="r"><div class="k">${key}</div><div class="v">${value}</div></div>`;

const link = (attr: string, id: number | string, words: string) =>
  `<button type="button" class="who" ${attr}="${esc(String(id))}">${esc(words)}</button>`;

const clusterChip = (cluster: Cluster) =>
  `<button type="button" class="chip" data-cluster="${esc(cluster.id)}">${esc(cluster.label)}</button>`;

function dates(event: TimelineEvent): string {
  if (!event.dateTime) return esc(when(null));
  const span = event.endDateTime ? `${when(event.dateTime)} – ${when(event.endDateTime)}` : when(event.dateTime);
  const sure = SURE[event.dateCertainty ?? ""];
  return esc(span) + (sure ? ` <span class="sub">· ${sure}</span>` : "");
}

function shift(event: TimelineEvent, name: (id: number) => string): string {
  const out = SHIFTS.flatMap((field) => (event[field] ? [`${field} ${event[field]}`] : []));
  if (event.relationship) {
    const targets = event.relationshipTargets.map(name);
    const triangles = event.relationshipTriangles.map(name);
    out.push(
      event.relationship +
        (targets.length ? ` with ${targets.join(", ")}` : "") +
        (triangles.length ? `, outside ${triangles.join(", ")}` : ""),
    );
  }
  return esc(out.join(" · "));
}

/** The card itself: a head with the kind over the name, one labelled line per
 * fact the record holds, the action at the foot; and every link in it wired. */
function card(kind: string, title: string, rows: string, talk: string, chip: Chip, hooks: DetailHooks): HTMLElement {
  const view = el(
    "div",
    "det",
    `<div class="head"><div class="kind">${esc(kind)}</div><div class="what">${esc(title)}</div></div>` +
      rows +
      `<div class="foot"><button type="button" class="talk">${talk}</button></div>`,
  );
  view.querySelector<HTMLElement>(".talk")!.onclick = () => hooks.talk(chip);
  for (const button of view.querySelectorAll<HTMLElement>("[data-cluster]"))
    button.onclick = () => hooks.cluster(button.dataset.cluster!);
  for (const button of view.querySelectorAll<HTMLElement>("[data-person]"))
    button.onclick = () => hooks.person(Number(button.dataset.person));
  for (const button of view.querySelectorAll<HTMLElement>("[data-event]"))
    button.onclick = () => hooks.event(Number(button.dataset.event));
  return view;
}

const chipFor = (kind: ChipKind, id: number, label: string): Chip => ({
  kind,
  target: String(id),
  label,
  tone: ChipTone.Data,
  bare: false,
});

const nameIn = (people: Person[]) => (id: number) =>
  people.find((p) => p.id === id)?.name ?? "someone not in the record";

export function eventDetail(
  event: TimelineEvent,
  people: Person[],
  cluster: Cluster | undefined,
  hooks: DetailHooks,
): HTMLElement {
  const name = nameIn(people);
  const who = [...new Set([event.person, event.spouse, event.child].filter((id): id is number => id !== null))];
  const changed = shift(event, name);
  return card(
    event.kind ?? "",
    event.label,
    row("When", dates(event)) +
      (who.length ? row("Who", who.map((id) => link("data-person", id, name(id))).join(", ")) : "") +
      (changed ? row("Shift", changed) : "") +
      (event.location ? row("Where", esc(event.location)) : "") +
      (cluster ? row("Cluster", clusterChip(cluster)) : "") +
      (event.notes ? row("Notes", esc(event.notes)) : ""),
    TALK_EVENT,
    chipFor(ChipKind.Event, event.id, event.label),
    hooks,
  );
}

/** Everyone a person is tied to in the record, and everything it says about
 * them: their birth and death, their parents, partners and children, the
 * events they are in and the clusters those sit in. */
export function personDetail(person: Person, record: Timeline, hooks: DetailHooks): HTMLElement {
  const name = nameIn(record.people);
  const id = person.id;
  const dated = (eventId: number | null) => {
    const event = record.events.find((e) => e.id === eventId);
    return event ? link("data-event", event.id, when(event.dateTime)) : "";
  };
  const people = (ids: number[]) => ids.map((other) => link("data-person", other, name(other))).join(", ");
  const bond = record.pair_bonds.find((b) => b.id === person.parents);
  const parents = bond ? [bond.person_a, bond.person_b].filter((p): p is number => p !== null) : [];
  const own = record.pair_bonds.filter((b) => b.person_a === id || b.person_b === id);
  const partners = own.flatMap((b) => {
    const other = b.person_a === id ? b.person_b : b.person_a;
    return other === null ? [] : [link("data-person", other, name(other)) + (b.married ? " <span class=\"sub\">· married</span>" : "")];
  });
  const children = record.people
    .filter((p) => own.some((b) => b.id === p.parents))
    .map((p) => p.id);
  const events = record.events.filter((e) =>
    [e.person, e.spouse, e.child, ...e.relationshipTargets, ...e.relationshipTriangles].includes(id),
  );
  const clusters = record.clusters.filter((c) => events.some((e) => c.event_ids.includes(e.id)));
  const kind = person.gender && person.gender !== UNSAID ? person.gender : "person";
  return card(
    kind,
    fullName(person),
    (person.birth_event !== null ? row("Born", dated(person.birth_event)) : "") +
      (person.death_event !== null ? row("Died", dated(person.death_event)) : "") +
      (parents.length ? row("Parents", people(parents)) : "") +
      (partners.length ? row("Partners", partners.join(", ")) : "") +
      (children.length ? row("Children", people(children)) : "") +
      (clusters.length ? row("Clusters", clusters.map(clusterChip).join(" ")) : "") +
      (events.length
        ? row("Events", events.map((e) => link("data-event", e.id, e.label)).join("<br>"))
        : "") +
      (person.notes ? row("Notes", esc(person.notes)) : ""),
    TALK_PERSON,
    chipFor(ChipKind.Person, id, fullName(person)),
    hooks,
  );
}
