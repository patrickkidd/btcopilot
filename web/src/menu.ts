import { esc } from "./dom";
import { openEditor } from "./editor";
import type { Chapter, Timeline, TimelineEvent } from "./types";

/** The full timeline list behind the menu, with one line saying chat edits it
 * too (R-0069). */

const BANNER = "You can also edit just by chatting.";

export class Menu {
  private editing: number | null = null;
  private adding = false;

  constructor(
    private body: HTMLElement,
    private reload: () => Promise<Timeline>,
  ) {}

  add(): void {
    this.adding = true;
    this.editing = null;
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

  private render(): void {
    const rows = this.data.events.map((event) => this.row(event)).join("");
    this.body.innerHTML =
      `<p class="banner">${esc(BANNER)}</p>` +
      (rows || `<div class="none">Nothing on your timeline yet.</div>`);
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

  private editor(event: TimelineEvent | null): HTMLElement {
    return openEditor(event, this.data.people, () => {
      this.editing = null;
      this.adding = false;
      void this.reload().then((data) => this.show(data));
    });
  }

  private row(event: TimelineEvent): string {
    const chapter = this.chapterOf(event.id);
    const meta = [
      event.dateTime ?? "no date yet",
      event.person_name,
      chapter?.label,
    ]
      .filter(Boolean)
      .join(" · ");
    return (
      `<div class="row${this.editing === event.id ? " on" : ""}" data-event="${event.id}" ` +
      `role="button" tabindex="0"><div class="rmain">` +
      `<div class="r1">${esc(event.label)}</div>` +
      `<div class="r2">${esc(meta)}</div></div></div>`
    );
  }
}
