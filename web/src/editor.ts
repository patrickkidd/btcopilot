import { esc, el } from "./dom";
import * as api from "./api";
import type { Person, TimelineEvent } from "./types";

/** The event editor, markup unchanged from the page this replaces: it is behind
 * the menu, off the main journey, and is not being redesigned (R-0069). */

export enum EventKind {
  Shift = "shift",
  Birth = "birth",
  Adopted = "adopted",
  Bonded = "bonded",
  Married = "married",
  Separated = "separated",
  Divorced = "divorced",
  Moved = "moved",
  Death = "death",
}

export enum Direction {
  Up = "up",
  Down = "down",
  Same = "same",
}

export enum Certainty {
  Unknown = "unknown",
  Approximate = "approximate",
  Certain = "certain",
}

export enum Relationship {
  Fusion = "fusion",
  Conflict = "conflict",
  Distance = "distance",
  Overfunctioning = "overfunctioning",
  Underfunctioning = "underfunctioning",
  Projection = "projection",
  DefinedSelf = "defined-self",
  Toward = "toward",
  Away = "away",
  Inside = "inside",
  Outside = "outside",
  Cutoff = "cutoff",
}

const PAIR_KINDS = [
  EventKind.Bonded,
  EventKind.Married,
  EventKind.Separated,
  EventKind.Divorced,
] as string[];
const CHILD_KINDS = [EventKind.Birth, EventKind.Adopted] as string[];
const SHIFT_VARIABLES = ["symptom", "anxiety", "functioning"] as const;

const TARGET_LABELS: Partial<Record<Relationship, string>> = {
  [Relationship.Conflict]: "Other(s)",
  [Relationship.Distance]: "Other(s)",
  [Relationship.Overfunctioning]: "Underfunctioner(s)",
  [Relationship.Underfunctioning]: "Overfunctioner(s)",
  [Relationship.Projection]: "Focused",
  [Relationship.Inside]: "Inside(s)",
  [Relationship.Outside]: "Inside(s) 1",
  [Relationship.Toward]: "To",
  [Relationship.Away]: "From",
  [Relationship.DefinedSelf]: "In relation to",
};

interface Option {
  value: string | number;
  label: string;
}

const targetLabel = (r: string) =>
  TARGET_LABELS[r as Relationship] ?? "Person 2";

const triangleLabel = (r: string) =>
  r === Relationship.Inside
    ? "Outside(s)"
    : r === Relationship.Outside
      ? "Inside(s) 2"
      : "";

function chips(
  name: string,
  options: Option[],
  current: unknown,
  multiple = false,
): string {
  const chosen = Array.isArray(current) ? current.map(String) : [String(current)];
  return (
    `<div class="segs" data-name="${name}" data-multiple="${multiple ? "1" : ""}">` +
    options
      .map(
        (o) =>
          `<button type="button" class="seg${chosen.includes(String(o.value)) ? " on" : ""}" ` +
          `data-value="${esc(String(o.value))}">${esc(o.label)}</button>`,
      )
      .join("") +
    `</div>`
  );
}

const plain = (values: string[]): Option[] =>
  values.map((value) => ({ value, label: value }));

function field(
  label: string,
  name: string,
  value: string | null | undefined,
  type?: string,
): string {
  const body =
    type === "text"
      ? `<textarea class="f" data-name="${name}" rows="1">${esc(value ?? "")}</textarea>`
      : `<input class="f" data-name="${name}" type="${type ?? "text"}" value="${esc(value ?? "")}">`;
  return `<div class="lab">${esc(label)}</div>${body}`;
}

export function openEditor(
  event: TimelineEvent | null,
  people: Person[],
  done: () => void,
): HTMLElement {
  const kind = event?.kind ?? EventKind.Shift;
  const relationship = event?.relationship ?? "";
  const persons = (withNone: boolean): Option[] => {
    const list = people.map((p) => ({ value: p.id, label: p.name }));
    return withNone ? [{ value: "", label: "nobody" }, ...list] : list;
  };

  const editor = el(
    "div",
    "editor",
    `<div class="sec">What</div>` +
      chips("kind", plain(Object.values(EventKind)), kind) +
      `<div class="sec">Who</div><div class="lab">Person</div>` +
      chips("person", persons(true), event?.person ?? "") +
      `<div data-block="pair"${PAIR_KINDS.includes(kind) ? "" : " hidden"}>` +
      `<div class="lab">With</div>` +
      chips("spouse", persons(true), event?.spouse ?? "") +
      `</div><div data-block="child"${CHILD_KINDS.includes(kind) ? "" : " hidden"}>` +
      `<div class="lab">Child</div>` +
      chips("child", persons(true), event?.child ?? "") +
      `</div><div class="sec">Words</div>` +
      field("Summary", "description", event?.description, "text") +
      field("Details", "notes", event?.notes, "text") +
      field("Where", "location", event?.location) +
      `<div class="sec">When</div>` +
      field("When", "dateTime", event?.dateTime, "date") +
      field("Ended (optional)", "endDateTime", event?.endDateTime, "date") +
      `<div class="lab">Certainty</div>` +
      chips(
        "dateCertainty",
        plain(Object.values(Certainty)),
        event?.dateCertainty ?? Certainty.Certain,
      ) +
      `<div data-block="shift"${kind === EventKind.Shift ? "" : " hidden"}>` +
      `<div class="sec">Shifts</div>` +
      SHIFT_VARIABLES.map(
        (variable) =>
          `<div class="lab">&Delta; ${variable}</div>` +
          chips(
            variable,
            [...Object.values(Direction), ""].map((value) => ({
              value,
              label: value || "none",
            })),
            event?.[variable] ?? "",
          ),
      ).join("") +
      `<div class="lab">&Delta; relationship</div>` +
      chips(
        "relationship",
        [{ value: "", label: "none" }, ...plain(Object.values(Relationship))],
        relationship,
      ) +
      `<div data-block="targets"${relationship ? "" : " hidden"}>` +
      `<div class="lab" data-label="targets">${esc(targetLabel(relationship))}</div>` +
      chips("relationshipTargets", persons(false), event?.relationshipTargets ?? [], true) +
      `</div><div data-block="triangles"${
        relationship === Relationship.Inside || relationship === Relationship.Outside
          ? ""
          : " hidden"
      }>` +
      `<div class="lab" data-label="triangles">${esc(triangleLabel(relationship))}</div>` +
      chips(
        "relationshipTriangles",
        persons(false),
        event?.relationshipTriangles ?? [],
        true,
      ) +
      `</div></div><div class="acts"><button class="save" type="button">Save</button>` +
      (event ? `<button class="del" type="button">Delete</button>` : "") +
      `</div>`,
  );

  editor.querySelectorAll("textarea").forEach((area) => {
    const grow = () => {
      area.style.height = "auto";
      area.style.height = `${area.scrollHeight}px`;
    };
    area.addEventListener("input", grow);
    grow();
  });

  editor.querySelectorAll<HTMLElement>(".segs").forEach((group) => {
    group.addEventListener("click", (clicked) => {
      const button = (clicked.target as Element).closest<HTMLElement>(".seg");
      if (!button) return;
      if (group.dataset.multiple) button.classList.toggle("on");
      else
        group
          .querySelectorAll(".seg")
          .forEach((other) => other.classList.toggle("on", other === button));
      const value = button.dataset.value ?? "";
      if (group.dataset.name === "kind") {
        block(editor, "pair").hidden = !PAIR_KINDS.includes(value);
        block(editor, "child").hidden = !CHILD_KINDS.includes(value);
        block(editor, "shift").hidden = value !== EventKind.Shift;
      }
      if (group.dataset.name === "relationship") {
        block(editor, "targets").hidden = !value;
        label(editor, "targets").textContent = targetLabel(value);
        const triangle =
          value === Relationship.Inside || value === Relationship.Outside;
        block(editor, "triangles").hidden = !triangle;
        label(editor, "triangles").textContent = triangleLabel(value);
      }
    });
  });

  editor
    .querySelector(".save")
    ?.addEventListener("click", () => void save(event, editor, done));
  editor.querySelector(".del")?.addEventListener("click", () => {
    if (event) void api.deleteEvent(event.id).then(done);
  });
  return editor;
}

const block = (editor: HTMLElement, name: string) =>
  editor.querySelector<HTMLElement>(`[data-block="${name}"]`) as HTMLElement;

const label = (editor: HTMLElement, name: string) =>
  editor.querySelector<HTMLElement>(`[data-label="${name}"]`) as HTMLElement;

async function save(
  event: TimelineEvent | null,
  editor: HTMLElement,
  done: () => void,
): Promise<void> {
  const one = (name: string): string | null => {
    const on = editor.querySelector<HTMLElement>(`.segs[data-name="${name}"] .seg.on`);
    return on && on.dataset.value ? on.dataset.value : null;
  };
  const many = (name: string): number[] =>
    [
      ...editor.querySelectorAll<HTMLElement>(`.segs[data-name="${name}"] .seg.on`),
    ].map((button) => Number(button.dataset.value));
  const text = (name: string): string | null => {
    const node = editor.querySelector<HTMLInputElement>(`[data-name="${name}"]`);
    return node && node.value.trim() ? node.value.trim() : null;
  };
  const number = (name: string): number | null => {
    const value = one(name);
    return value === null ? null : Number(value);
  };
  await api.saveEvent(event ? event.id : null, {
    kind: one("kind"),
    person: number("person"),
    spouse: number("spouse"),
    child: number("child"),
    description: text("description"),
    notes: text("notes"),
    location: text("location"),
    dateTime: text("dateTime"),
    endDateTime: text("endDateTime"),
    dateCertainty: one("dateCertainty") ?? Certainty.Certain,
    symptom: one("symptom"),
    anxiety: one("anxiety"),
    functioning: one("functioning"),
    relationship: one("relationship"),
    relationshipTargets: many("relationshipTargets"),
    relationshipTriangles: many("relationshipTriangles"),
  });
  done();
}
