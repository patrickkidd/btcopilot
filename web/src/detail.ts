import { el, esc } from "./dom";
import { when } from "./rows";
import { DateCertainty, type Cluster, type Person, type TimelineEvent } from "./types";

/** One event, read-only, opened by a tap on its row in the events list
 * (Patrick's pick D2, 2026-10-01): what kind, what happened, when and how sure,
 * who, where, its cluster, its notes. Nothing is changed here; the one action
 * at its foot carries the event into the chat, where it is changed by talking
 * (D3). */

export const TALK = "Tap to comment or change this event in chat";

const SURE: Record<string, string> = {
  [DateCertainty.Approximate]: "around then",
  [DateCertainty.Unknown]: "not sure of the date",
};

const SHIFTS: [keyof TimelineEvent, string][] = [
  ["symptom", "symptom"],
  ["anxiety", "anxiety"],
  ["functioning", "functioning"],
];

export interface DetailHooks {
  /** The event goes into the message box as a lit chip, and the chat comes up. */
  talk: (event: TimelineEvent) => void;
  cluster: (id: string) => void;
  person: (id: number) => void;
}

const row = (key: string, value: string) =>
  `<div class="r"><div class="k">${key}</div><div class="v">${value}</div></div>`;

function dates(event: TimelineEvent): string {
  if (!event.dateTime) return esc(when(null));
  const span = event.endDateTime ? `${when(event.dateTime)} – ${when(event.endDateTime)}` : when(event.dateTime);
  const sure = SURE[event.dateCertainty ?? ""];
  return esc(span) + (sure ? ` <span class="sub">· ${sure}</span>` : "");
}

function shift(event: TimelineEvent, name: (id: number) => string): string {
  const out = SHIFTS.flatMap(([field, word]) => (event[field] ? [`${word} ${event[field]}`] : []));
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

export function eventDetail(
  event: TimelineEvent,
  people: Person[],
  cluster: Cluster | undefined,
  hooks: DetailHooks,
): HTMLElement {
  const name = (id: number) => people.find((p) => p.id === id)?.name ?? "someone not in the record";
  const who = [...new Set([event.person, event.spouse, event.child].filter((id): id is number => id !== null))];
  const kind = event.kind ?? "";
  const changed = shift(event, name);
  const view = el(
    "div",
    "det",
    `<div class="head"><div class="kind">${esc(kind)}</div>` +
      `<div class="what">${esc(event.label)}</div></div>` +
      row("When", dates(event)) +
      (who.length
        ? row(
            "Who",
            who
              .map((id) => `<button type="button" class="who" data-person="${id}">${esc(name(id))}</button>`)
              .join(", "),
          )
        : "") +
      (changed ? row("Shift", changed) : "") +
      (event.location ? row("Where", esc(event.location)) : "") +
      (cluster
        ? row(
            "Cluster",
            `<button type="button" class="chip" data-cluster="${esc(cluster.id)}">${esc(cluster.label)}</button>`,
          )
        : "") +
      (event.notes ? row("Notes", esc(event.notes)) : "") +
      `<div class="foot"><button type="button" class="talk">${TALK}</button></div>`,
  );
  view.querySelector<HTMLElement>(".talk")!.onclick = () => hooks.talk(event);
  view.querySelector<HTMLElement>("[data-cluster]")?.addEventListener("click", () => hooks.cluster(cluster!.id));
  for (const button of view.querySelectorAll<HTMLElement>("[data-person]"))
    button.onclick = () => hooks.person(Number(button.dataset.person));
  return view;
}
