import { eventDetail, personDetail, type DetailHooks } from "./detail";
import { closeX, el, flash, slideOver } from "./dom";
import { openEditor, openPersonEditor } from "./editor";
import { Feature, tap } from "./track";
import { eventDivider, eventRow, fullName, personRow, sections } from "./rows";
import type { Questions } from "./questions";
import { emptyTimeline, ItemKind, type Cluster, type Person, type Timeline, type TimelineEvent } from "./types";

/** The full timeline list behind the menu: full screen, searched, and divided
 * by cluster with a sticky header, so you always know which cluster you are in
 * (owner rulings 2026-09-03). Chat edits it too (R-0069).
 *
 * Two ways into the same record: what happened, and who it happened to. The
 * people list is the same rows and the same editor, on the fields the record
 * keeps about a person. */

export enum Tab {
  Events = "events",
  People = "people",
  Questions = "questions",
}

/** Who is ordered by when they were born, and people the record has no birth
 * for come after everyone it does. */
function byBirth(a: Person, b: Person): number {
  if (a.birth && b.birth) return a.birth < b.birth ? -1 : a.birth > b.birth ? 1 : 0;
  if (a.birth) return -1;
  if (b.birth) return 1;
  return byName(a, b);
}

const byName = (a: Person, b: Person) => a.name.localeCompare(b.name);

const ADD = "add-sheet";

/** The form for something new, one for the whole app: it comes up over the
 * lists the way they came up over the chat, full screen, with what it makes
 * and the app's close button at its top. Made on the first add. */
function addSheet(): HTMLElement {
  const found = document.getElementById(ADD);
  if (found) return found;
  const sheet = el(
    "div",
    "slideover",
    `<div class="ovbar"><span class="ovt"></span>${closeX()}</div><div class="scroller"></div>`,
  );
  sheet.id = ADD;
  sheet.hidden = true;
  document.querySelector(".app")!.append(sheet);
  return sheet;
}

/** Whether the form for something new is up. */
export const adding = (): boolean =>
  document.getElementById(ADD)?.classList.contains("in") ?? false;

/** The form for something new goes back down, if one ever came up. */
export function shut(): void {
  const sheet = document.getElementById(ADD);
  if (sheet) slideOver(sheet, false);
}

export class Menu {
  private editing: number | null = null;
  /** Where the list was scrolled when a card opened over it, to go back to. */
  private listTop = 0;
  private query = "";
  private tab = Tab.Events;
  /** The people list is ordered by birth until the reader asks for names. */
  private byName = false;
  /** The questions the coach asked, on the one drawer that has that tab. */
  questions: Questions | null = null;

  constructor(
    private body: HTMLElement,
    private reload: () => Promise<Timeline>,
    /** The record being edited: the diagram open, or on the coding screen the
     * record its own coding is of. */
    private diagramId: () => number | undefined,
    /** Where a tapped row opens the read-only detail card instead of the form:
     * the chat app's own drawer. The coding screen passes none, and keeps the
     * forms, since coders change the record they code by hand. */
    private detail?: Pick<DetailHooks, "talk" | "cluster" | "said">,
  ) {}

  add(): void {
    this.editing = null;
    this.render();
    const people = this.tab === Tab.People;
    const sheet = addSheet();
    sheet.querySelector(".ovt")!.textContent = people ? "New person" : "New event";
    sheet.querySelector<HTMLElement>(".cardx")!.onclick = () => {
      shut();
      this.onMove?.();
    };
    const body = sheet.querySelector<HTMLElement>(".scroller")!;
    body.replaceChildren(people ? this.personEditor(null) : this.editor(null));
    body.scrollTop = 0;
    slideOver(sheet, true);
    this.onMove?.();
  }

  /** The thing whose editor is open, if one is. */
  edited(): number | null {
    return this.editing;
  }

  /** The open card or form closes, and the list is back where it was. */
  fold(): void {
    this.editing = null;
    this.render();
    this.body.scrollTop = this.listTop;
    this.onMove?.();
  }

  /** The card of what is open, as its own page in place of the list, when
   * this drawer has cards. */
  private page(): HTMLElement | null {
    if (!this.detail || this.editing === null) return null;
    if (this.tab === Tab.Events) {
      const event = this.data.events.find((e) => e.id === this.editing);
      return event ? this.view(event) : null;
    }
    const person = this.data.people.find((p) => p.id === this.editing);
    return person ? this.personView(person) : null;
  }

  /** Which of the two lists is on screen. */
  showing(): Tab {
    return this.tab;
  }

  open(tab: Tab): void {
    this.tab = tab;
    this.editing = null;
    this.body.scrollTop = 0;
    this.render();
  }

  /** Go to one thing's editor, on whichever list it lives on. This is how a
   * person reaches the events about them and how an event reaches the people
   * in it: the drawer stays open and the tab under it changes. */
  goTo(tab: Tab, id: number): void {
    shut();
    this.tab = tab;
    this.editing = id;
    this.query = "";
    this.onTab?.(tab);
    this.render();
    const row = this.body.querySelector<HTMLElement>(
      tab === Tab.People ? `.row[data-person="${id}"]` : `.row[data-event="${id}"]`,
    );
    if (row) flash(row);
    this.onMove?.();
  }

  /** Told when the drawer changes tab under its own steam, so the header and
   * the buttons above the list say the same thing it does. */
  onTab?: (tab: Tab) => void;

  /** Told when an editor opens or closes, so the address says so. */
  onMove?: () => void;

  search(query: string): void {
    this.query = query;
    this.editing = null;
    this.render();
  }

  show(data: Timeline): void {
    this.data = data;
    this.render();
  }

  private data: Timeline = emptyTimeline();

  private clusterOf(id: number): Cluster | undefined {
    return this.data.clusters.find((c) => c.event_ids.includes(id));
  }

  private names(): Map<number, string> {
    return new Map(this.data.people.map((p: Person) => [p.id, p.name]));
  }

  private matches(event: TimelineEvent, names: Map<number, string>): boolean {
    const words = this.query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (!words.length) return true;
    const targets = [
      ...event.relationshipTargets,
      ...event.relationshipTriangles,
    ].map((id) => names.get(id) ?? "");
    const hay = [event.label, event.person_name, ...targets]
      .join(" ")
      .toLowerCase();
    return words.every((word) => hay.includes(word));
  }

  private render(): void {
    const page = this.tab === Tab.Questions ? null : this.page();
    this.body.parentElement?.classList.toggle("carded", page !== null);
    if (page) {
      this.body.replaceChildren(page);
      this.body.scrollTop = 0;
      return;
    }
    if (this.tab === Tab.People) {
      this.renderPeople();
      return;
    }
    if (this.tab === Tab.Questions) {
      if (!this.questions) throw new Error("This drawer has no questions tab");
      this.questions.show(this.data.asked_questions);
      return;
    }
    const names = this.names();
    const shown = this.data.events.filter((event) => this.matches(event, names));
    let html = "";
    for (const { group, events } of sections(shown, (id) => this.clusterOf(id))) {
      html += eventDivider(group);
      for (const event of events) html += eventRow(event, names, this.data, this.editing === event.id);
    }
    if (!shown.length)
      html = `<div class="none">${
        this.data.events.length
          ? "Nothing matches that search."
          : "Nothing on your timeline yet."
      }</div>`;
    const top = this.body.scrollTop;
    this.body.innerHTML = html;
    this.body.scrollTop = top;
    this.body.querySelectorAll<HTMLElement>(".row").forEach((row) => {
      row.addEventListener("click", () => {
        const id = Number(row.dataset.event);
        this.listTop = this.body.scrollTop;
        if (this.editing !== id)
          tap(Feature.EventOpen, { kind: ItemKind.Event, id: String(id) });
        this.editing = this.editing === id ? null : id;
        this.render();
        this.onMove?.();
      });
    });
    if (this.editing !== null) {
      const event = this.data.events.find((e) => e.id === this.editing);
      const row = this.body.querySelector(`.row[data-event="${this.editing}"]`);
      if (event && row) row.after(this.editor(event));
    }
  }

  private renderPeople(): void {
    const words = this.query.trim().toLowerCase();
    const shown = this.data.people
      .filter((person) => fullName(person).toLowerCase().includes(words))
      .sort(this.byName ? byName : byBirth);
    let html = `<div class="div"><span>${
      this.byName ? "by name" : "by birth"
    }</span><span class="dcount" data-order="1" role="button" tabindex="0">${
      this.byName ? "order by birth" : "order by name"
    }</span></div>`;
    for (const person of shown)
      html += personRow(person, this.editing === person.id);
    if (!shown.length)
      html = `<div class="none">${
        this.data.people.length ? "Nobody matches that search." : "Nobody on your record yet."
      }</div>`;
    const top = this.body.scrollTop;
    this.body.innerHTML = html;
    this.body.scrollTop = top;
    this.body.querySelector('[data-order]')?.addEventListener("click", () => {
      tap(Feature.PeopleOrder);
      this.byName = !this.byName;
      this.render();
    });
    this.body.querySelectorAll<HTMLElement>(".row").forEach((row) => {
      row.addEventListener("click", () => {
        const id = Number(row.dataset.person);
        this.listTop = this.body.scrollTop;
        if (this.editing !== id)
          tap(Feature.PersonOpen, { kind: ItemKind.Person, id: String(id) });
        this.editing = this.editing === id ? null : id;
        this.render();
        this.onMove?.();
      });
    });
    if (this.editing !== null) {
      const person = this.data.people.find((p) => p.id === this.editing);
      const row = this.body.querySelector(`.row[data-person="${this.editing}"]`);
      if (person && row) row.after(this.personEditor(person));
    }
  }

  /** A save or a delete: the form for something new goes down, and the list
   * reads the record again. */
  private done(): void {
    this.editing = null;
    shut();
    this.onMove?.();
    void this.reload().then((data) => this.show(data));
  }

  /** PARKED, not dead, as the event form is (Patrick, 2026-10-01: "We need to
   * do the same thing with people that we did with events. hide + comment the
   * people editor form"). In the chat app a tapped person row opens the
   * read-only person card, and a person is changed by talking to the coach
   * about them; this form is reached there only to add someone. To bring
   * editing back, let page() return null for people: the row then opens this
   * form under it, as it still does on the coding screen. */
  private personEditor(person: Person | null): HTMLElement {
    return openPersonEditor(person, {
      done: () => this.done(),
      goToEvent: (eventId: number) => this.goTo(Tab.Events, eventId),
      diagramId: this.diagramId(),
      family: this.data,
    });
  }

  private hooks(): DetailHooks {
    return {
      ...this.detail!,
      person: (id) => this.goTo(Tab.People, id),
      event: (id) => this.goTo(Tab.Events, id),
      back: () => this.fold(),
    };
  }

  private view(event: TimelineEvent): HTMLElement {
    return eventDetail(event, this.data.people, this.clusterOf(event.id), this.hooks());
  }

  private personView(person: Person): HTMLElement {
    return personDetail(person, this.data, this.hooks());
  }

  /** PARKED, not dead (Patrick, 2026-10-01: "hide and adequately comment out
   * the event edit form for now and see how it goes with the chat"). In the
   * chat app a tapped event row opens the read-only detail view, and the event
   * is changed by talking to the coach about it; this form is reached there
   * only to add a new event. To bring editing back, let page() return null
   * for events: the row then opens this form under it, as it still does on
   * the coding screen. */
  private editor(event: TimelineEvent | null): HTMLElement {
    return openEditor(
      event,
      this.data.people,
      () => this.done(),
      (personId) => this.goTo(Tab.People, personId),
      this.diagramId(),
    );
  }
}
