import { esc, el } from "./dom";
import * as api from "./api";
import type { PairBond, Person, TimelineEvent } from "./types";

/** The event editor, markup unchanged from the page this replaces: it is behind
 * the menu, off the main journey, and is not being redesigned (R-0069). */

/** Notes are a place to write something you are not ready to put in the
 * record, so the coach leaves them alone unless it is asked (R-0281). */
const NOTES_HINT =
  "Notes stay with this and are not read back to you in the thread unless you ask for them.";

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

/** Who the second person is, and when there is one, exactly as `EventForm.qml`
 * decides it. The Pro app's Pregnancy kind has no counterpart in the record's
 * `EventKind`, so it is the one entry that does not carry over. */
const PAIR_KINDS = [
  EventKind.Bonded,
  EventKind.Married,
  EventKind.Separated,
  EventKind.Divorced,
  EventKind.Moved,
  EventKind.Birth,
  EventKind.Adopted,
] as string[];
const CHILD_KINDS = [EventKind.Birth, EventKind.Adopted] as string[];
const PARTNER_KINDS = [
  EventKind.Bonded,
  EventKind.Married,
  EventKind.Separated,
  EventKind.Divorced,
] as string[];

const personLabel = (kind: string, relationship: string): string => {
  if (CHILD_KINDS.includes(kind)) return "Parent 1";
  if (PARTNER_KINDS.includes(kind)) return "Partner 1";
  if (kind === EventKind.Shift && relationship === Relationship.Overfunctioning)
    return "Overfunctioner";
  if (kind === EventKind.Shift && relationship === Relationship.Underfunctioning)
    return "Underfunctioner";
  return "Person";
};

const spouseLabel = (kind: string): string =>
  CHILD_KINDS.includes(kind)
    ? "Parent 2"
    : kind === EventKind.Moved
      ? "Partner"
      : "Partner 2";
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

/** The groups where one person is chosen, so a tap on the one already chosen
 * changes nothing and is free to mean "take me to them". The groups that hold
 * several keep that tap, because it is how one of them is taken off again. */
const ONE_PERSON = ["person", "spouse", "child"];

export function openEditor(
  event: TimelineEvent | null,
  people: Person[],
  done: () => void,
  goToPerson?: (personId: number) => void,
  diagramId?: number,
  /** Where Save goes when the event is not being written to a record: the
   * ballot takes the words themselves and makes a take of them (R-0257). */
  onSave?: (body: Partial<TimelineEvent>) => void,
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
      `<div class="sec">Who</div>` +
      `<div class="lab" data-label="person">${esc(personLabel(kind, relationship))}</div>` +
      chips("person", persons(true), event?.person ?? "") +
      `<div data-block="pair"${PAIR_KINDS.includes(kind) ? "" : " hidden"}>` +
      `<div class="lab" data-label="spouse">${esc(spouseLabel(kind))}</div>` +
      chips("spouse", persons(true), event?.spouse ?? "") +
      `</div><div data-block="child"${CHILD_KINDS.includes(kind) ? "" : " hidden"}>` +
      `<div class="lab">Child</div>` +
      chips("child", persons(true), event?.child ?? "") +
      `</div><div class="sec">Words</div>` +
      field("Summary", "description", event?.description, "text") +
      field("Notes", "notes", event?.notes, "text") +
      `<div class="hint">${NOTES_HINT}</div>` +
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
    // A detached textarea measures zero, and the caller inserts this editor
    // after openEditor returns, so the first measure waits for the next frame.
    requestAnimationFrame(grow);
  });

  editor.querySelectorAll<HTMLElement>(".segs").forEach((group) => {
    group.addEventListener("click", (clicked) => {
      const button = (clicked.target as Element).closest<HTMLElement>(".seg");
      if (!button) return;
      // the person this event is already about: the tap goes to them
      if (
        goToPerson &&
        ONE_PERSON.includes(group.dataset.name ?? "") &&
        button.classList.contains("on") &&
        button.dataset.value
      ) {
        goToPerson(Number(button.dataset.value));
        return;
      }
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
        label(editor, "person").textContent = personLabel(value, chosen(editor, "relationship"));
        label(editor, "spouse").textContent = spouseLabel(value);
      }
      if (group.dataset.name === "relationship") {
        label(editor, "person").textContent = personLabel(chosen(editor, "kind"), value);
        block(editor, "targets").hidden = !value;
        label(editor, "targets").textContent = targetLabel(value);
        const triangle =
          value === Relationship.Inside || value === Relationship.Outside;
        block(editor, "triangles").hidden = !triangle;
        label(editor, "triangles").textContent = triangleLabel(value);
      }
    });
  });

  editor.querySelector(".save")?.addEventListener("click", () => {
    if (onSave) onSave(values(editor));
    else void save(event, editor, done, diagramId);
  });
  editor.querySelector(".del")?.addEventListener("click", () => {
    if (event) void api.deleteEvent(event.id, diagramId).then(done);
  });
  return editor;
}

const block = (editor: HTMLElement, name: string) =>
  editor.querySelector<HTMLElement>(`[data-block="${name}"]`) as HTMLElement;

const label = (editor: HTMLElement, name: string) =>
  editor.querySelector<HTMLElement>(`[data-label="${name}"]`) as HTMLElement;

/** The value a single-choice group is currently on, for the labels that read
 * kind and relationship together. */
const chosen = (editor: HTMLElement, name: string): string =>
  editor.querySelector<HTMLElement>(`.segs[data-name="${name}"] .seg.on`)?.dataset
    .value ?? "";

/** What the editor is saying now, in the record's own field names.
 *
 * A group the chosen kind does not use is not read: the editor keeps what was
 * picked there so switching back restores it, but a marriage must not be saved
 * carrying the relationship shift the event used to be. */
export function values(editor: HTMLElement): Partial<TimelineEvent> {
  const group = (name: string): HTMLElement | null => {
    const found = editor.querySelector<HTMLElement>(`.segs[data-name="${name}"]`);
    // any hidden block above it, because the relationship groups sit inside
    // the shift block
    return found?.closest("[data-block][hidden]") ? null : found;
  };
  const one = (name: string): string | null => {
    const on = group(name)?.querySelector<HTMLElement>(".seg.on");
    return on && on.dataset.value ? on.dataset.value : null;
  };
  const many = (name: string): number[] =>
    [...(group(name)?.querySelectorAll<HTMLElement>(".seg.on") ?? [])].map(
      (button) => Number(button.dataset.value),
    );
  const text = (name: string): string | null => {
    const node = editor.querySelector<HTMLInputElement>(`[data-name="${name}"]`);
    return node && node.value.trim() ? node.value.trim() : null;
  };
  const number = (name: string): number | null => {
    const value = one(name);
    return value === null ? null : Number(value);
  };
  return {
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
  };
}

async function save(
  event: TimelineEvent | null,
  editor: HTMLElement,
  done: () => void,
  diagramId?: number,
): Promise<void> {
  await api.saveEvent(event ? event.id : null, values(editor), diagramId);
  done();
}

/** What the record holds a person as: which symbol they are drawn with. Two of
 * these are pregnancies that did not end in a birth, which the picture has its
 * own symbols for, so this is a kind of person and never a sex. */
export enum PersonKind {
  Male = "male",
  Female = "female",
  Abortion = "abortion",
  Miscarriage = "miscarriage",
  Unknown = "unknown",
}

/** The record around one person: who else is in it, who is bonded to whom, and
 * the events that say when a bond started and ended. The person editor needs it
 * to offer the couples somebody can be born to (R-0326). */
export interface Family {
  people: Person[];
  pair_bonds: PairBond[];
  events: TimelineEvent[];
}

export interface PersonEditor {
  done: () => void;
  goToEvent?: (eventId: number) => void;
  diagramId?: number;
  family?: Family;
  /** Where Save goes when the person is not being written to a record: the
   * ballot takes the words themselves and makes an opinion of them (R-0257). */
  onSave?: (body: Partial<Person>) => void;
}

const ADD_PARENTS = "add";

/** Both names of a bond, which is how a couple is named everywhere. */
export const bothNames = (bond: PairBond, people: Person[]): string =>
  [bond.person_a, bond.person_b]
    .map((id) => people.find((p) => p.id === id)?.name ?? "someone")
    .join(" & ");

/** When a bond ended, which the record holds as an event about the two of
 * them rather than as a field on the bond. */
const endedIn = (bond: PairBond, events: TimelineEvent[]): string | null => {
  const found = events.find(
    (event) =>
      (event.kind === EventKind.Divorced || event.kind === EventKind.Separated) &&
      [event.person, event.spouse].includes(bond.person_a) &&
      [event.person, event.spouse].includes(bond.person_b),
  );
  return found?.dateTime ? found.dateTime.slice(0, 4) : null;
};

/** One row per other person this person has ever been bonded to — never one
 * "with", because the record keeps one bond ever between any two people and a
 * bond that ended is still one of them (R-0326). */
function bondRows(person: Person, family: Family): string {
  const mine = family.pair_bonds.filter(
    (bond) => bond.person_a === person.id || bond.person_b === person.id,
  );
  const rows = mine
    .map((bond) => {
      const other =
        bond.person_a === person.id ? bond.person_b : bond.person_a;
      const name = family.people.find((p) => p.id === other)?.name ?? "someone";
      const ended = endedIn(bond, family.events);
      const said = [bond.married ? "married" : "together", ended ? `ended ${ended}` : ""]
        .filter(Boolean)
        .join(" · ");
      return (
        `<button class="btn bondrow" type="button" data-bond="${bond.id}">` +
        `${esc(name)} · ${esc(said)}</button>`
      );
    })
    .join("");
  return (
    `<div class="lab">Bonds</div>` +
    (rows || `<div class="hint">Nobody on the record yet.</div>`) +
    `<button class="btn bondrow" type="button" data-bond="new">+ a bond</button>`
  );
}

/** The couples this person could have been born to: every bond in the record
 * except the ones they are themselves part of, because nobody is their own
 * parent (R-0326). */
function bornTo(person: Person | null, family: Family, canWrite: boolean): string {
  const options: Option[] = [{ value: "", label: "nobody on the record" }];
  for (const bond of family.pair_bonds) {
    if (person && (bond.person_a === person.id || bond.person_b === person.id))
      continue;
    options.push({ value: bond.id, label: bothNames(bond, family.people) });
  }
  // Only for somebody who has nobody: a person is born to one couple, so the
  // way to change that is to pick another, never to make a second one.
  if (person && canWrite && person.parents === null)
    options.push({ value: ADD_PARENTS, label: "+ add parents" });
  return `<div class="lab">Born to</div>` + chips("parents", options, person?.parents ?? "");
}

/** The person editor: the event editor's own markup, with the fields the record
 * keeps on a person. Being born and dying are events about them, so those are
 * offered as the events themselves rather than as fields here. */
export function openPersonEditor(
  person: Person | null,
  opts: PersonEditor,
): HTMLElement {
  const { done, goToEvent, diagramId, family, onSave } = opts;
  const life = [
    ["birth_event", "Their birth"],
    ["death_event", "Their death"],
  ] as const;
  const editor = el(
    "div",
    "editor",
    `<div class="sec">Who</div>` +
      field("Name", "name", person?.name) +
      field("Last name", "last_name", person?.last_name) +
      `<div class="lab">Kind</div>` +
      chips(
        "gender",
        plain(Object.values(PersonKind)),
        person?.gender ?? PersonKind.Unknown,
      ) +
      field("Notes", "notes", person?.notes, "text") +
      `<div class="hint">${NOTES_HINT}</div>` +
      (family
        ? `<div class="sec">Family</div>` +
          bornTo(person, family, !onSave) +
          // The bonds a person is in are the record's, not one version's: they
          // are corrected where the record is, never on a ballot card.
          (person && !onSave ? bondRows(person, family) : "")
        : "") +
      `<div class="sec">When</div>` +
      `<div class="hint">Add birth and death events by chatting with the coach.</div>` +
      life
        .map(([key, label]) =>
          person?.[key]
            ? `<button class="btn" type="button" data-event="${person[key]}">${label}</button>`
            : "",
        )
        .join("") +
      `<div class="acts"><button class="save" type="button">Save</button>` +
      (person ? `<button class="del" type="button">Delete</button>` : "") +
      `</div>`,
  );

  editor.querySelectorAll<HTMLElement>("[data-event]").forEach((button) => {
    button.addEventListener("click", () =>
      goToEvent?.(Number(button.dataset.event)),
    );
  });

  editor.querySelectorAll<HTMLElement>(".segs").forEach((group) => {
    group.addEventListener("click", (clicked) => {
      const button = (clicked.target as Element).closest<HTMLElement>(".seg");
      if (!button) return;
      // "add parents" is not a couple to pick: it makes one, generically named
      // where nobody named them, and the record hands it back (R-0325).
      if (button.dataset.value === ADD_PARENTS && person) {
        void api.addParents(person.id, diagramId).then(done);
        return;
      }
      group
        .querySelectorAll(".seg")
        .forEach((other) => other.classList.toggle("on", other === button));
    });
  });

  editor.querySelectorAll<HTMLElement>(".bondrow").forEach((row) => {
    row.addEventListener("click", () => {
      if (!person || !family) return;
      const bond =
        family.pair_bonds.find((one) => String(one.id) === row.dataset.bond) ?? null;
      row.after(openBondEditor(bond, person, family, { done, diagramId }));
      row.hidden = true;
    });
  });

  editor.querySelector(".save")?.addEventListener("click", () => {
    const body = personValues(editor);
    if (onSave) {
      onSave(body);
      return;
    }
    void api.savePerson(person ? person.id : null, body, diagramId).then(done);
  });
  editor.querySelector(".del")?.addEventListener("click", () => {
    if (person) void api.deletePerson(person.id, diagramId).then(done);
  });
  return editor;
}

/** What the person editor is saying now, in the record's own field names. */
export function personValues(editor: HTMLElement): Partial<Person> {
  const text = (name: string): string | null => {
    const node = editor.querySelector<HTMLInputElement>(`[data-name="${name}"]`);
    return node && node.value.trim() ? node.value.trim() : null;
  };
  const one = (name: string): string =>
    editor.querySelector<HTMLElement>(`.segs[data-name="${name}"] .seg.on`)?.dataset
      .value ?? "";
  const parents = one("parents");
  return {
    name: text("name"),
    last_name: text("last_name"),
    notes: text("notes"),
    gender: one("gender") || PersonKind.Unknown,
    ...(editor.querySelector('.segs[data-name="parents"]')
      ? { parents: parents ? Number(parents) : null }
      : {}),
  } as Partial<Person>;
}

/** One bond's own small editor, opened from the person it belongs to: who the
 * other person is, and whether they married. When it started and when it ended
 * are events about the two of them, so they are not fields here (R-0326). */
export function openBondEditor(
  bond: PairBond | null,
  person: Person,
  family: Family,
  opts: {
    done: () => void;
    diagramId?: number;
    /** Where Save goes when the bond is a version on a ballot rather than a
     * bond on a record. */
    onSave?: (body: Partial<PairBond>) => void;
  },
): HTMLElement {
  const other = bond
    ? bond.person_a === person.id
      ? bond.person_b
      : bond.person_a
    : null;
  const taken = new Set(
    family.pair_bonds
      .filter((one) => one.id !== bond?.id)
      .flatMap((one) =>
        one.person_a === person.id
          ? [one.person_b]
          : one.person_b === person.id
            ? [one.person_a]
            : [],
      ),
  );
  const partners: Option[] = family.people
    .filter((p) => p.id !== person.id && !taken.has(p.id))
    .map((p) => ({ value: p.id, label: p.name }));
  const editor = el(
    "div",
    "editor bond",
    `<div class="lab">Partner</div>` +
      chips("partner", partners, other ?? "") +
      `<div class="lab">Married</div>` +
      chips("married", [
        { value: "yes", label: "married" },
        { value: "", label: "together, not married" },
      ], bond?.married ? "yes" : "") +
      `<div class="hint">When it started and when it ended are events about ` +
      `the two of them; say those to the coach.</div>` +
      `<div class="acts"><button class="save" type="button">Save</button>` +
      (bond ? `<button class="del" type="button">Remove</button>` : "") +
      `</div>`,
  );

  editor.querySelectorAll<HTMLElement>(".segs").forEach((group) => {
    group.addEventListener("click", (clicked) => {
      const button = (clicked.target as Element).closest<HTMLElement>(".seg");
      if (!button) return;
      group
        .querySelectorAll(".seg")
        .forEach((one) => one.classList.toggle("on", one === button));
    });
  });

  editor.querySelector(".save")?.addEventListener("click", () => {
    const picked = editor.querySelector<HTMLElement>(
      '.segs[data-name="partner"] .seg.on',
    )?.dataset.value;
    const married = !!editor.querySelector(
      '.segs[data-name="married"] .seg.on[data-value="yes"]',
    );
    if (!picked) return;
    const body = { person_a: person.id, person_b: Number(picked), married };
    if (opts.onSave) {
      opts.onSave(body);
      return;
    }
    void api.savePairBond(bond ? bond.id : null, body, opts.diagramId).then(opts.done);
  });
  editor.querySelector(".del")?.addEventListener("click", () => {
    if (bond) void api.deletePairBond(bond.id, opts.diagramId).then(opts.done);
  });
  return editor;
}
