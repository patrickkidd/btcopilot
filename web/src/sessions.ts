import * as api from "./api";
import { $, el, esc } from "./dom";
import { dragScroll } from "./drag";
import { toast } from "./toast";
import { clockTime, dayKey, groupLabel, whenText } from "./when";
import type { Diagram, Session } from "./types";

/** The session door: the button beside the message box, and the searchable
 * bottom sheet it raises — the `family-sections` option the owner picked. Every
 * family's sessions in one scroll under sticky family headers, each family
 * collapsed to its three most recent. */

const COLLAPSED = 3;
const TITLE_CAP = 120;
/** Drag up from the input bar this far to open; drag the grabber down this far
 * to close. */
const OPEN_DRAG = 40;
const CLOSE_DRAG = 90;
const PRESS_MS = 500;

export interface SessionsHandlers {
  /** Open a session: the chat swaps to its statements. */
  onPick(session: Session): void;
  /** The sessions as last read, so a moment tracing back to the one that coded
   * it can name it. */
  onList(sessions: Session[]): void;
}

const untitled = (session: Session) => !session.title?.trim();

/** What a session is called on screen. A session the coach has not titled yet
 * is named by when it happened, so two of them can still be told apart. */
export const sessionTitle = (session: Session) =>
  untitled(session)
    ? `Untitled · ${clockTime(new Date(session.last_activity))}`
    : (session.title as string);

const summaryOf = (session: Session) =>
  session.summary?.trim() ||
  (session.message_count === 0 ? "just started" : "in progress");

export class Sessions {
  private list: Session[] = [];
  private family: Diagram | null = null;
  private current: number | null = null;
  private filter = "";
  private expanded = false;
  private open = false;
  private drag: { kind: "open" | "close"; y0: number; dy: number } | null = null;

  private scrim = el("div", "fs-scrim");
  private sheet = el(
    "div",
    "fs-sheet",
    `<div class="fs-handle"><div class="fs-grab"></div></div>
     <div class="fs-search">
       <input type="search" placeholder="Search sessions and families"
              aria-label="Search sessions and families">
     </div>
     <div class="fs-body"></div>
     <div class="fs-foot"><button class="fs-new" type="button"></button></div>`,
  );

  private body: HTMLElement;
  private search: HTMLInputElement;
  private newButton: HTMLButtonElement;

  constructor(
    private button: HTMLElement,
    private overlay: HTMLElement,
    private screen: HTMLElement,
    private inbar: HTMLElement,
    private handlers: SessionsHandlers,
  ) {
    this.scrim.hidden = true;
    this.sheet.hidden = true;
    this.overlay.append(this.scrim, this.sheet);
    this.body = this.sheet.querySelector<HTMLElement>(".fs-body")!;
    this.search = this.sheet.querySelector<HTMLInputElement>(".fs-search input")!;
    this.newButton = this.sheet.querySelector<HTMLButtonElement>(".fs-new")!;
    this.wire();
    dragScroll(this.body);
  }

  /** The record the sheet lists, re-read whenever the chat has moved on. */
  async load(currentId: number | null): Promise<void> {
    this.current = currentId;
    const [sessions, account] = await Promise.all([
      api.sessionIndex(),
      api.account(),
    ]);
    this.list = sessions;
    this.family =
      account.diagrams.find((d) => d.free) ?? account.diagrams[0] ?? null;
    this.handlers.onList(this.list);
    if (this.open) this.render();
  }

  private wire(): void {
    this.button.addEventListener("click", () => void this.raise(false));
    this.scrim.addEventListener("click", () => this.lower());
    this.search.addEventListener("input", () => {
      this.filter = this.search.value;
      this.render();
    });
    this.newButton.addEventListener("click", () => void this.start());
    this.body.addEventListener("click", (e) => this.onBodyClick(e));
    this.pressToRename();
    this.drags();
  }

  private onBodyClick(e: Event): void {
    const target = e.target as Element;
    if (target.closest(".fs-plus")) {
      e.stopPropagation();
      void this.start();
      return;
    }
    if (target.closest(".fs-more")) {
      this.expanded = true;
      this.render();
      return;
    }
    if (target.closest(".fs-fhead")) {
      this.expanded = !this.expanded;
      this.render();
      return;
    }
    const row = target.closest<HTMLElement>(".row");
    if (!row || row.querySelector("input.rename")) return;
    this.pick(row);
  }

  /** A long press on a row opens its title for editing in place. */
  private pressToRename(): void {
    let timer = 0;
    const cancel = () => window.clearTimeout(timer);
    this.body.addEventListener("pointerdown", (e) => {
      const row = (e.target as Element).closest<HTMLElement>(".row");
      if (!row) return;
      timer = window.setTimeout(() => this.rename(row), PRESS_MS);
    });
    for (const kind of ["pointerup", "pointercancel", "pointermove"])
      this.body.addEventListener(kind, cancel);
  }

  private drags(): void {
    const at = (e: PointerEvent) =>
      e.clientY - this.overlay.getBoundingClientRect().top;
    const handle = this.sheet.querySelector<HTMLElement>(".fs-handle")!;
    this.inbar.addEventListener(
      "pointerdown",
      (e) => {
        if (this.open) return;
        this.drag = { kind: "open", y0: at(e as PointerEvent), dy: 0 };
      },
      true,
    );
    handle.addEventListener("pointerdown", (e) => {
      this.drag = { kind: "close", y0: at(e as PointerEvent), dy: 0 };
      this.sheet.style.transition = "none";
    });
    this.overlay.addEventListener("pointermove", (e) => {
      if (!this.drag) return;
      this.drag.dy = at(e as PointerEvent) - this.drag.y0;
      if (this.drag.kind === "close")
        this.sheet.style.transform = `translateY(${Math.max(0, this.drag.dy)}px)`;
    });
    const settle = () => {
      const drag = this.drag;
      this.drag = null;
      if (!drag) return;
      if (drag.kind === "open") {
        if (drag.dy <= -OPEN_DRAG) void this.raise(true);
        return;
      }
      this.sheet.style.transition = "";
      if (drag.dy >= CLOSE_DRAG) this.lower();
      else this.sheet.style.transform = "";
    };
    this.overlay.addEventListener("pointerup", settle);
    this.overlay.addEventListener("pointercancel", settle);
  }

  private async raise(viaDrag: boolean): Promise<void> {
    if (this.open) return;
    this.open = true;
    await this.load(this.current);
    this.render();
    this.body.scrollTop = 0;
    this.scrim.hidden = false;
    this.sheet.hidden = false;
    void this.sheet.offsetWidth;
    this.scrim.classList.add("in");
    this.sheet.classList.add("in");
    this.screen.style.transformOrigin = "50% 0";
    this.screen.style.transform = "scale(.96)";
    if (!viaDrag) this.search.focus({ preventScroll: true });
  }

  private lower(): void {
    if (!this.open) return;
    this.open = false;
    this.drag = null;
    this.sheet.style.transition = "";
    this.sheet.style.transform = "";
    this.scrim.classList.remove("in");
    this.sheet.classList.remove("in");
    this.screen.style.transform = "";
    window.setTimeout(() => {
      if (this.open) return;
      this.scrim.hidden = true;
      this.sheet.hidden = true;
    }, 280);
  }

  /** What the sheet shows right now: the matching sessions, collapsed to the
   * three most recent unless the family is expanded or a search is running. */
  private shown(): { rows: Session[]; more: number } {
    const query = this.filter.trim().toLowerCase();
    const matches = query
      ? this.list.filter((s) =>
          `${sessionTitle(s)} ${summaryOf(s)} ${this.family?.name ?? ""}`
            .toLowerCase()
            .includes(query),
        )
      : this.list;
    if (query || this.expanded || matches.length <= COLLAPSED)
      return { rows: matches, more: 0 };
    const rows = matches.filter((s, i) => i < COLLAPSED || s.id === this.current);
    return { rows, more: matches.length - rows.length };
  }

  private render(): void {
    const name = this.family?.name ?? "your family";
    this.newButton.textContent = `New session with ${name}`;
    const { rows, more } = this.shown();
    const now = new Date();
    const counts = new Map<number, number>();
    for (const s of this.list) {
      const key = dayKey(new Date(s.last_activity));
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }

    if (!rows.length) {
      this.body.innerHTML = `<div class="fs-hint">${
        this.filter.trim() ? "No sessions match" : "Past conversations collect here"
      }</div>`;
      return;
    }

    let html = `<section class="fs-sec">${this.headHtml(name)}`;
    let group = "";
    for (const session of rows) {
      const when = new Date(session.last_activity);
      const label = this.filter.trim() ? "" : groupLabel(when, now);
      if (label && label !== group) {
        group = label;
        html += `<div class="ghead">${esc(label)}</div>`;
      }
      html += this.rowHtml(
        session,
        whenText(when, now, counts.get(dayKey(when)) ?? 1),
      );
    }
    if (more) html += `<div class="fs-more">${more} more…</div>`;
    html += "</section>";
    if (this.list.length <= 1 && !this.filter.trim())
      html += `<div class="fs-hint">Past conversations collect here</div>`;
    const top = this.body.scrollTop;
    this.body.innerHTML = html;
    this.body.scrollTop = top;
  }

  private headHtml(name: string): string {
    const last = this.list[0];
    return (
      `<div class="fs-fhead">` +
      this.thumb() +
      `<div class="fs-fmain">` +
      `<div class="fs-fname">${esc(name)}</div>` +
      `<div class="fs-flast">last: ${esc(last ? summaryOf(last) : "nothing yet")}</div>` +
      `</div>` +
      `<button class="fs-plus" type="button" aria-label="New session with ${esc(name)}">+</button>` +
      `</div>`
    );
  }

  /** The family's wire, small: one mark per session so the header carries the
   * same picture the app draws large. */
  private thumb(): string {
    const w = 60;
    const h = 14;
    const times = this.list.map((s) => new Date(s.last_activity).getTime());
    let svg =
      `<svg class="thumb" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" aria-hidden="true">` +
      `<line x1="1" y1="${h / 2}" x2="${w - 1}" y2="${h / 2}" stroke="var(--line)" stroke-width="1"/>`;
    if (times.length) {
      const min = Math.min(...times);
      const max = Math.max(...times);
      for (const t of times) {
        const x = times.length === 1 ? w / 2 : 1 + ((t - min) / (max - min || 1)) * (w - 2);
        svg += `<circle cx="${x.toFixed(1)}" cy="${h / 2}" r="2" fill="var(--data)"/>`;
      }
    }
    return svg + "</svg>";
  }

  private rowHtml(session: Session, when: string): string {
    const title = untitled(session)
      ? `<span class="untitled">${esc(sessionTitle(session))}</span>`
      : esc(session.title as string);
    // The app has one list row: the timeline list's `.row` with its `.r1`
    // title and `.r2` secondary line. A session row is that row with a date
    // column beside it, not a second row component.
    return (
      `<div class="row side${session.id === this.current ? " cur" : ""}" data-id="${session.id}">` +
      `<div class="rmain">` +
      `<div class="r1 rtitle">${title}</div>` +
      `<div class="r2">${esc(summaryOf(session))}</div>` +
      `</div>` +
      `<div class="r2 rwhen">${esc(when)}</div>` +
      `</div>`
    );
  }

  private find(id: number): Session | undefined {
    return this.list.find((s) => s.id === id);
  }

  private pick(row: HTMLElement): void {
    const session = this.find(Number(row.dataset.id));
    if (!session) return;
    row.classList.add("tint");
    this.lower();
    this.current = session.id;
    this.handlers.onPick(session);
  }

  /** A new session is refused while the one you are in has nothing in it: two
   * empty sessions say nothing the first one does not. */
  private async start(): Promise<void> {
    const current = this.current === null ? undefined : this.find(this.current);
    if (current && current.message_count === 0) {
      this.lower();
      toast("Still empty — say something first");
      $("composer").focus({ preventScroll: true });
      return;
    }
    const session = await api.newSession();
    this.list = [session, ...this.list];
    this.current = session.id;
    this.lower();
    this.handlers.onPick(session);
  }

  private rename(row: HTMLElement): void {
    const session = this.find(Number(row.dataset.id));
    const holder = row.querySelector<HTMLElement>(".rtitle");
    if (!session || !holder || holder.querySelector("input")) return;
    const field = document.createElement("input");
    field.className = "rename";
    field.value = sessionTitle(session);
    holder.replaceChildren(field);
    field.focus({ preventScroll: true });
    field.select();

    const save = async () => {
      const title = field.value.trim().slice(0, TITLE_CAP);
      if (!title) {
        this.render();
        toast("Kept the coach's title");
        return;
      }
      const saved = await api.renameSession(session.id, title);
      this.list = this.list.map((s) => (s.id === saved.id ? saved : s));
      this.render();
    };
    field.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        void save();
      } else if (e.key === "Escape") this.render();
    });
    field.addEventListener("blur", () => void save());
  }
}
