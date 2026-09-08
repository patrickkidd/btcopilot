import { esc } from "./dom";
import { Direction, openEditor } from "./editor";
import type { Chapter, Person, Timeline, TimelineEvent } from "./types";

/** The full timeline list behind the menu: full screen, searched, and divided
 * by chapter with a sticky header, so you always know which cluster you are in
 * (owner rulings 2026-09-03). Chat edits it too (R-0069). */

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

  private data: Timeline = { people: [], events: [], chapters: [], questions: [], axis: null, shelf: [] };

  private chapterOf(id: number): Chapter | undefined {
    return this.data.chapters.find((c) => c.event_ids.includes(id));
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
    const names = this.names();
    const shown = this.data.events.filter((event) => this.matches(event, names));
    let html = "";
    let last: string | null | undefined;
    for (const event of shown) {
      const chapter = this.chapterOf(event.id);
      const key = chapter ? chapter.id : null;
      if (key !== last) {
        last = key;
        html += this.divider(chapter);
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

  private divider(chapter: Chapter | undefined): string {
    const count = chapter
      ? `${chapter.count} moment${chapter.count === 1 ? "" : "s"}`
      : "";
    return (
      `<div class="div"><span>${esc(chapter ? chapter.label : UNPLACED)}</span>` +
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
