import * as api from "./api";
import { Part, store } from "./store";
import { closeX, el, esc } from "./dom";
import { dragScroll } from "./drag";
import { Sheet } from "./sheet";
import { toast } from "./toast";
import type { Person } from "./types";

/** Who each speaker of a recording put into the chat is, said in the drawer
 * that opens once the transcript is in, before the message goes (R-0951,
 * R-0953). */

/** Who a voice is: a person in the diagram, a person to add to it on Save,
 * the clinician, or someone the diagram leaves out. */
export enum Who {
  Person = "person",
  New = "new",
  Clinician = "clinician",
  Outside = "outside",
}

export type Choice =
  | { who: Who.Person; id: number }
  | { who: Who.New; name: string; last: string }
  | { who: Who.Clinician }
  | { who: Who.Outside; name: string };

/** What the pick-list's rows and buttons do, besides picking a person. */
enum Act {
  New = "new",
  Clinician = "clinician",
  Outside = "outside",
  Add = "add",
  Back = "back",
  Clear = "clear",
}

const CLINICIAN = "The clinician";

export const fullName = (person: { name: string; last_name: string | null }) =>
  [person.name, person.last_name].filter(Boolean).join(" ");

export const guessed = (suggestion: api.Suggestion): Choice =>
  suggestion.person_id === null ? { who: Who.Clinician } : { who: Who.Person, id: suggestion.person_id };

export const shown = (choice: Choice, people: Person[]): string => {
  if (choice.who === Who.Clinician) return CLINICIAN;
  if (choice.who === Who.Person) return fullName(people.find((one) => one.id === choice.id)!);
  if (choice.who === Who.New) return fullName({ name: choice.name, last_name: choice.last });
  return choice.name;
};

export const ready = (labels: string[], chosen: Map<string, Choice>) =>
  labels.every((label) => chosen.has(label));

/** Who each speaker of a recording sent with a message is. Any mix is
 * taken, the clinician or not (R-0952); a new person goes in with the id made
 * for them on Save. */
export const namedFor = (chosen: Map<string, Choice>, made: Map<string, number>): Record<string, api.Named> =>
  Object.fromEntries(
    [...chosen].map(([label, choice]): [string, api.Named] => {
      if (choice.who === Who.Clinician) return [label, { clinician: true }];
      if (choice.who === Who.Outside) return [label, { name: choice.name }];
      return [label, { person_id: choice.who === Who.Person ? choice.id : made.get(label)! }];
    }),
  );

/** What a recording in the chat is kept as once its speakers are named. */
export interface Saved {
  voices: Record<string, api.Named>;
  title: string;
  date: string;
}

const year = (person: Person) => person.birth?.slice(0, 4) ?? "";

/** The day a file was made, as the date field takes it. */
export const dayOf = (file: File) => new Date(file.lastModified).toISOString().slice(0, 10);

const row = (attrs: string, title: string, side = "", cur = false) =>
  `<button class="sn-row push${cur ? " cur" : ""}" type="button" ${attrs}>` +
  `<span class="sn-t">${esc(title)}</span>${side ? `<span class="sn-s">${esc(side)}</span>` : ""}</button>`;

const field = (name: string, label: string) =>
  `<div class="sn-srch rv-in"><input type="text" data-f="${name}" placeholder="${label}" aria-label="${label}"></div>`;

export class Recording {
  private scrim = el("div", "fs-scrim");
  private sheet = el(
    "div",
    "fs-sheet",
    `<div class="fs-handle"><div class="fs-grab"></div></div>${closeX()}
     <div class="fs-search"><input type="search" readonly aria-label="the recording"></div>
     <div class="fs-body"></div>
     <div class="fs-foot"><button class="fs-new" type="button">Save</button></div>`,
  );
  private body: HTMLElement;
  private head: HTMLInputElement;
  private make: HTMLButtonElement;
  private list: Sheet;

  private voices: api.Suggested[] = [];
  /** Set while the sheet names the speakers of a recording in the chat;
   * answered with what Save keeps, or null once the sheet goes down without. */
  private saved: ((answer: Saved | null) => void) | null = null;
  private chosen = new Map<string, Choice>();
  /** The voices still showing the app's suggestion, untouched. */
  private suggested = new Set<string>();
  /** The voice the pick-list is choosing for. */
  private picking = "";
  private title = "";
  private date = "";

  constructor(overlay: HTMLElement) {
    this.scrim.hidden = true;
    this.sheet.hidden = true;
    this.sheet.id = "recording-sheet";
    this.scrim.id = "recording-scrim";
    overlay.append(this.scrim, this.sheet);
    this.list = new Sheet(overlay, "rv");
    this.body = this.sheet.querySelector<HTMLElement>(".fs-body")!;
    this.head = this.sheet.querySelector<HTMLInputElement>(".fs-search input")!;
    this.make = this.sheet.querySelector<HTMLButtonElement>(".fs-new")!;
    this.scrim.addEventListener("click", () => this.lower());
    this.sheet.querySelector(".cardx")!.addEventListener("click", () => this.lower());
    this.sheet
      .querySelector(".fs-handle")!
      .addEventListener("click", () => this.lower());
    this.make.addEventListener("click", () => void this.save());
    this.body.addEventListener("click", (e) => {
      const chip = (e.target as Element).closest<HTMLElement>("[data-voice]");
      if (chip) this.offer(chip.dataset.voice!);
    });
    overlay.addEventListener("click", (e) => {
      const target = e.target as Element;
      if (target.closest(".fs-scrim.rv, .fs-sheet.rv .cardx")) return this.list.lower();
      const picked = target.closest<HTMLElement>(".fs-sheet.rv [data-person], .fs-sheet.rv [data-act]");
      if (picked) this.answer(picked);
    });
    this.list.panel.addEventListener("input", (e) => {
      const typed = e.target as HTMLInputElement;
      if (typed.type === "search") {
        const query = typed.value.trim().toLowerCase();
        for (const one of this.list.panel.querySelectorAll<HTMLElement>("[data-name]"))
          one.hidden = !!query && !one.dataset.name!.includes(query);
      } else {
        this.list.panel.querySelector<HTMLButtonElement>(`[data-act="${Act.Add}"]`)!.disabled =
          !this.typed("name");
      }
    });
    dragScroll(this.body);
  }

  private suggest(): void {
    for (const voice of this.voices) {
      if (!voice.suggestion) continue;
      this.chosen.set(voice.label, guessed(voice.suggestion));
      this.suggested.add(voice.label);
    }
  }

  /** A recording put into the chat, transcribed: who each speaker is, and the
   * date and title it is kept under (R-0951, R-0953). */
  name(file: File, voices: api.Suggested[]): Promise<Saved | null> {
    this.saved?.(null);
    this.title = file.name;
    this.date = dayOf(file);
    this.chosen.clear();
    this.suggested.clear();
    this.voices = voices;
    this.suggest();
    const answer = new Promise<Saved | null>((done) => (this.saved = done));
    this.head.value = "Who is each speaker";
    this.render();
    this.raise();
    return answer;
  }

  private async save(): Promise<void> {
    if (!this.title.trim()) {
      toast("Give the recording a title");
      return;
    }
    const voices = namedFor(this.chosen, await this.made());
    const answer = this.saved!;
    this.saved = null;
    this.lower();
    answer({ voices, title: this.title.trim(), date: this.date });
  }

  /** The new people the speakers named, added to the diagram, by speaker. */
  private async made(): Promise<Map<string, number>> {
    const made = new Map<string, number>();
    for (const [label, choice] of this.chosen)
      if (choice.who === Who.New)
        made.set(label, (await api.savePerson(null, { name: choice.name, last_name: choice.last || null }, store.id()!)).id);
    if (made.size) await store.refresh(Part.Record);
    return made;
  }

  private people(): Person[] {
    return store.current().record.people;
  }

  /** One speaker: the label and first words outside, who they are inside,
   * and the words a suggestion rests on when they are not those first words. */
  private block(voice: api.Suggested): string {
    const choice = this.chosen.get(voice.label);
    const guess = this.suggested.has(voice.label) ? voice.suggestion : null;
    const quoted = guess && !(guess.speaker === voice.label && guess.because === voice.said) ? guess : null;
    return (
      `<div class="rv-voice" data-for="${esc(voice.label)}">` +
      `<div class="rv-said"><span class="rv-lab">Speaker ${esc(voice.label)}</span> ` +
      `&ldquo;${esc(voice.said)}&rdquo;</div>` +
      `<div class="rv-box"><div class="rv-field">` +
      `<button class="rv-pick${choice ? "" : " rv-none"}" type="button" data-voice="${esc(voice.label)}">` +
      `${esc(choice ? shown(choice, this.people()) : "Choose who this is")}</button>` +
      (guess ? `<span class="rv-sugg">suggested</span>` : "") +
      `</div>` +
      (quoted
        ? `<div class="rv-because">Speaker ${esc(quoted.speaker)} said: ` +
          `<q>${esc(quoted.because)}</q></div>`
        : "") +
      `</div></div>`
    );
  }

  private render(): void {
    this.body.innerHTML =
      this.voices.map((voice) => this.block(voice)).join("") +
      `<div class="ghead">Recording</div>` +
      `<div class="row side"><div class="rmain"><div class="r1 rtitle">Date</div></div>` +
      `<input class="rwhen said" type="date" data-name="date" aria-label="Date" ` +
      `value="${esc(this.date)}"></div>` +
      `<div class="row side"><div class="rmain"><div class="r1 rtitle">Title</div></div>` +
      `<input class="rwhen said" type="text" data-name="title" aria-label="Title" ` +
      `value="${esc(this.title)}"></div>`;
    for (const input of this.body.querySelectorAll<HTMLInputElement>("input"))
      input.addEventListener("input", () => {
        if (input.dataset.name === "date") this.date = input.value;
        else this.title = input.value;
      });
    this.settle();
  }

  /** The one speaker that changed, drawn again where it stands. */
  private redraw(label: string): void {
    const voice = this.voices.find((one) => one.label === label)!;
    this.body.querySelector(`[data-for="${CSS.escape(label)}"]`)!.outerHTML = this.block(voice);
    this.settle();
  }

  private settle(): void {
    this.make.disabled = !ready(this.voices.map((voice) => voice.label), this.chosen);
  }

  /** The pick-list for one speaker: the suggestion first, then the diagram's
   * people as it lists them, then the three choices that are not one of them. */
  private offer(label: string): void {
    this.picking = label;
    const voice = this.voices.find((one) => one.label === label)!;
    const choice = this.chosen.get(label);
    const guess = voice.suggestion ? guessed(voice.suggestion) : null;
    const isCur = (test: Choice) => JSON.stringify(test) === JSON.stringify(choice);
    const person = (one: Person, side = year(one)) =>
      row(
        `data-person="${one.id}" data-name="${esc(fullName(one).toLowerCase())}"`,
        fullName(one),
        side,
        isCur({ who: Who.Person, id: one.id }),
      );
    const clinician = row(`data-act="${Act.Clinician}"`, CLINICIAN, "", choice?.who === Who.Clinician);
    const people = this.people();
    const first =
      guess?.who === Who.Person
        ? person(people.find((one) => one.id === guess.id)!, "suggested")
        : guess
          ? row(`data-act="${Act.Clinician}"`, CLINICIAN, "suggested", choice?.who === Who.Clinician)
          : "";
    this.list.show(
      `${closeX()}<div class="cf-t">Who is Speaker ${esc(label)}</div>` +
        `<div class="sn-srch rv-find"><input type="search" placeholder="Find a name" aria-label="Find a name"></div>` +
        `<div class="sn-grp rv-who">` +
        first +
        people
          .filter((one) => !(guess?.who === Who.Person && guess.id === one.id))
          .map((one) => person(one))
          .join("") +
        row(`data-act="${Act.New}"`, "New person", "", choice?.who === Who.New) +
        (guess?.who === Who.Clinician ? "" : clinician) +
        row(`data-act="${Act.Outside}"`, "Someone not in the diagram", "", choice?.who === Who.Outside) +
        (choice ? row(`data-act="${Act.Clear}"`, "Clear this choice") : "") +
        `</div>`,
    );
    dragScroll(this.list.panel.querySelector<HTMLElement>(".rv-who")!);
  }

  private form(title: string, fields: string, hint = ""): void {
    this.list.show(
      `${closeX()}<div class="cf-t">${esc(title)}</div>` +
        (hint ? `<p class="cf-p">${esc(hint)}</p>` : "") +
        fields +
        `<div class="cf-btns"><button class="cf-go" type="button" data-act="${Act.Add}" disabled>Add</button>` +
        `<button class="cf-no" type="button" data-act="${Act.Back}">Back</button></div>`,
    );
    this.list.panel.querySelector<HTMLInputElement>("input")!.focus({ preventScroll: true });
  }

  private typed(name: string): string {
    return this.list.panel.querySelector<HTMLInputElement>(`[data-f="${name}"]`)?.value.trim() ?? "";
  }

  private answer(picked: HTMLElement): void {
    const label = this.picking;
    if (picked.dataset.person) return this.set(label, { who: Who.Person, id: Number(picked.dataset.person) });
    const act = picked.dataset.act as Act;
    if (act === Act.Clinician) return this.set(label, { who: Who.Clinician });
    if (act === Act.New)
      return this.form("New person", field("name", "First name") + field("last", "Last name"));
    if (act === Act.Outside)
      return this.form("Someone not in the diagram", field("name", "Name"), "Nobody is added to the diagram.");
    if (act === Act.Back) return this.offer(label);
    if (act === Act.Clear) {
      this.chosen.delete(label);
      this.suggested.delete(label);
      this.list.lower();
      return this.redraw(label);
    }
    const last = this.list.panel.querySelector(`[data-f="last"]`);
    this.set(
      label,
      last ? { who: Who.New, name: this.typed("name"), last: this.typed("last") } : { who: Who.Outside, name: this.typed("name") },
    );
  }

  private set(label: string, choice: Choice): void {
    this.chosen.set(label, choice);
    this.suggested.delete(label);
    this.list.lower();
    this.redraw(label);
  }

  private hiding: number | null = null;

  private raise(): void {
    if (this.hiding !== null) window.clearTimeout(this.hiding);
    this.hiding = null;
    this.scrim.hidden = false;
    this.sheet.hidden = false;
    void this.sheet.offsetWidth;
    this.scrim.classList.add("in");
    this.sheet.classList.add("in");
  }

  lower(): void {
    this.saved?.(null);
    this.saved = null;
    this.scrim.classList.remove("in");
    this.sheet.classList.remove("in");
    this.hiding = window.setTimeout(() => {
      this.hiding = null;
      this.scrim.hidden = true;
      this.sheet.hidden = true;
    }, 280);
  }
}
