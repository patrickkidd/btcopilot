import { esc } from "./dom";
import { Direction, openEditor, openPersonEditor } from "./editor";
import { emptyTimeline, type Cluster, type Person, type Timeline, type TimelineEvent } from "./types";

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

/** What the record calls someone, both names when it holds both. */
const fullName = (person: Person) =>
  [person.name, person.last_name].filter(Boolean).join(" ");

const UNPLACED = "unplaced";
const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

const ARROW: Record<string, string> = {
  [Direction.Up]: "↑",
  [Direction.Down]: "↓",
  [Direction.Same]: "=",
};

const SHIFTS: [keyof TimelineEvent, string][] = [
  ["symptom", "S"],
  ["anxiety", "A"],
  ["functioning", "F"],
];

function when(event: TimelineEvent): string {
  if (!event.dateTime) return "no date yet";
  const [year, month] = event.dateTime.split("-");
  return month ? `${MONTHS[Number(month) - 1]} ${year}` : year;
}

/** The row's second line must not overflow the phone, so the shifts and the
 * move are abbreviated: `S↑ A↑ F= R conflict→mom` (owner ruling 2026-09-03). */
function codes(event: TimelineEvent, names: Map<number, string>): string {
  const out: string[] = [];
  for (const [field, letter] of SHIFTS) {
    const value = event[field] as string | null;
    if (value) out.push(letter + (ARROW[value] ?? ` ${value}`));
  }
  if (event.relationship) {
    const named = (ids: number[]) =>
      ids.map((id) => names.get(id) ?? "?").join(",");
    const targets = event.relationshipTargets.length
      ? `→${named(event.relationshipTargets)}`
      : "";
    const triangles = event.relationshipTriangles.length
      ? ` △${named(event.relationshipTriangles)}`
      : "";
    out.push(`R ${event.relationship}${targets}${triangles}`);
  }
  return out.join("  ");
}

export class Menu {
  private editing: number | null = null;
  private adding = false;
  private query = "";
  private tab = Tab.Events;
  /** The people list is ordered by birth until the reader asks for names. */
  private byName = false;

  constructor(
    private body: HTMLElement,
    private reload: () => Promise<Timeline>,
  ) {}

  add(): void {
    this.adding = true;
    this.editing = null;
    this.body.scrollTop = 0;
    this.render();
  }

  /** Which of the two lists is on screen. */
  showing(): Tab {
    return this.tab;
  }

  open(tab: Tab): void {
    this.tab = tab;
    this.editing = null;
    this.adding = false;
    this.body.scrollTop = 0;
    this.render();
  }

  search(query: string): void {
    this.query = query;
    this.editing = null;
    this.adding = false;
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
    if (this.tab === Tab.People) {
      this.renderPeople();
      return;
    }
    const names = this.names();
    const shown = this.data.events.filter((event) => this.matches(event, names));
    let html = "";
    let last: string | null | undefined;
    for (const event of shown) {
      const cluster = this.clusterOf(event.id);
      const key = cluster ? cluster.id : null;
      if (key !== last) {
        last = key;
        html += this.divider(cluster);
      }
      html += this.row(event, names);
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
        this.editing = this.editing === id ? null : id;
        this.adding = false;
        this.render();
      });
    });
    if (this.adding) this.body.prepend(this.editor(null));
    else if (this.editing !== null) {
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
    for (const person of shown) html += this.personRow(person);
    if (!shown.length)
      html = `<div class="none">${
        this.data.people.length ? "Nobody matches that search." : "Nobody on your record yet."
      }</div>`;
    const top = this.body.scrollTop;
    this.body.innerHTML = html;
    this.body.scrollTop = top;
    this.body.querySelector('[data-order]')?.addEventListener("click", () => {
      this.byName = !this.byName;
      this.render();
    });
    this.body.querySelectorAll<HTMLElement>(".row").forEach((row) => {
      row.addEventListener("click", () => {
        const id = Number(row.dataset.person);
        this.editing = this.editing === id ? null : id;
        this.adding = false;
        this.render();
      });
    });
    if (this.adding) this.body.prepend(this.personEditor(null));
    else if (this.editing !== null) {
      const person = this.data.people.find((p) => p.id === this.editing);
      const row = this.body.querySelector(`.row[data-person="${this.editing}"]`);
      if (person && row) row.after(this.personEditor(person));
    }
  }

  private personRow(person: Person): string {
    const meta = [
      person.birth ? `born ${person.birth.slice(0, 4)}` : "no birth on the record",
      person.gender,
      person.primary ? "you" : "",
    ]
      .filter(Boolean)
      .join(" · ");
    return (
      `<div class="row${this.editing === person.id ? " on" : ""}" data-person="${person.id}" ` +
      `role="button" tabindex="0">` +
      `<div class="r1">${esc(fullName(person))}</div>` +
      `<div class="r2">${esc(meta)}</div></div>`
    );
  }

  private personEditor(person: Person | null): HTMLElement {
    return openPersonEditor(person, () => {
      this.editing = null;
      this.adding = false;
      void this.reload().then((data) => this.show(data));
    });
  }

  private divider(cluster: Cluster | undefined): string {
    const count = cluster
      ? `${cluster.count} moment${cluster.count === 1 ? "" : "s"}`
      : "";
    return (
      `<div class="div"><span>${esc(cluster ? cluster.label : UNPLACED)}</span>` +
      `<span class="dcount">${esc(count)}</span></div>`
    );
  }

  private editor(event: TimelineEvent | null): HTMLElement {
    return openEditor(event, this.data.people, () => {
      this.editing = null;
      this.adding = false;
      void this.reload().then((data) => this.show(data));
    });
  }

  private row(event: TimelineEvent, names: Map<number, string>): string {
    const meta = [when(event), event.person_name, codes(event, names)]
      .filter(Boolean)
      .join(" · ");
    return (
      `<div class="row${this.editing === event.id ? " on" : ""}" data-event="${event.id}" ` +
      `role="button" tabindex="0">` +
      `<div class="r1">${esc(event.label)}</div>` +
      `<div class="r2">${esc(meta)}</div></div>`
    );
  }
}
