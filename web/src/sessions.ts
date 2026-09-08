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
/** Swipe a row this far to the left to reveal Rename and Delete. */
const SWIPE_PX = 72;

export interface SessionsHandlers {
  /** Open a session: the chat swaps to its statements. */
  onPick(session: Session): void;
  /** The app moved to another family. */
  onDiagram(diagram: Diagram, how: { switched: boolean }): void;
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

export const summaryOf = (session: Session) =>
  session.summary?.trim() ||
  (session.message_count === 0 ? "just started" : "in progress");

/** One family and the sessions on it. A personal account has one of these; a
 * professional has one per client diagram. */
interface Family {
  diagram: Diagram;
  sessions: Session[];
}

export class Sessions {
  private families: Family[] = [];
  private current: number | null = null;
  private filter = "";
  /** The families the reader has opened past their three most recent. */
  private expanded = new Set<number>();
  private open = false;
  /** The row whose Rename and Delete are showing, if any. */
  private swiped: HTMLElement | null = null;
  /** True between the swipe revealing the actions and the click it ends with. */
  private opening = false;
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

  /** The record the sheet lists, re-read whenever the chat has moved on. The
   * family the app is on comes first; the rest follow by recency. */
  async load(currentId: number | null): Promise<void> {
    this.current = currentId;
    const diagrams = await api.diagrams();
    const lists = await Promise.all(
      diagrams.map((diagram) => api.sessionIndex(diagram.id)),
    );
    const fresh = diagrams
      .map((diagram, i) => ({ diagram, sessions: lists[i] }))
      .sort((a, b) => Number(b.diagram.current) - Number(a.diagram.current));
    // Newest first, except while the sheet is up: a list must not reorder under
    // the reader's thumb because a reply landed (ratified behaviour). New
    // sessions join at the end of their family until the sheet is closed.
    this.families = this.open ? fresh.map((f) => this.held(f)) : fresh;
    this.handlers.onList(this.families.flatMap((f) => f.sessions));
    if (this.open) this.render();
  }

  /** One family's sessions in the order they are already on screen, updated in
   * place, with anything new appended. */
  private held(family: Family): Family {
    const was = this.families.find((f) => f.diagram.id === family.diagram.id);
    if (!was) return family;
    const byId = new Map(family.sessions.map((s) => [s.id, s]));
    const kept = was.sessions.flatMap((s) => {
      const now = byId.get(s.id);
      byId.delete(s.id);
      return now ? [now] : [];
    });
    return { diagram: family.diagram, sessions: [...kept, ...byId.values()] };
  }

  /** The family the app is on, which is the one a new session belongs to. */
  private home(): Family | undefined {
    return this.families.find((f) => f.diagram.current) ?? this.families[0];
  }

  private find(id: number): Session | undefined {
    for (const family of this.families) {
      const found = family.sessions.find((s) => s.id === id);
      if (found) return found;
    }
    return undefined;
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
    this.swipeForActions();
    this.drags();
  }

  private onBodyClick(e: Event): void {
    const target = e.target as Element;
    const action = target.closest<HTMLElement>(".fs-act");
    if (action) {
      e.stopPropagation();
      const row = action.closest<HTMLElement>(".row")!;
      if (action.classList.contains("ren")) {
        this.closeActions();
        this.rename(row);
      } else void this.remove(row);
      return;
    }
    // The gesture that revealed the actions ends in a click of its own, which
    // must not immediately put them away again.
    if (this.opening) {
      this.opening = false;
      return;
    }
    // a tap anywhere else puts an open row's actions away rather than firing
    if (this.swiped) {
      this.closeActions();
      return;
    }
    const plus = target.closest<HTMLElement>(".fs-plus");
    if (plus) {
      e.stopPropagation();
      void this.start(Number(plus.dataset.family));
      return;
    }
    const more = target.closest<HTMLElement>(".fs-more");
    if (more) {
      this.expanded.add(Number(more.dataset.family));
      this.render();
      return;
    }
    const head = target.closest<HTMLElement>(".fs-fhead");
    if (head) {
      const id = Number(head.parentElement?.dataset.family);
      if (this.expanded.has(id)) this.expanded.delete(id);
      else this.expanded.add(id);
      this.render();
      return;
    }
    const row = target.closest<HTMLElement>(".row");
    if (!row || row.querySelector("input.rename")) return;
    this.pick(row);
  }

  /** Swipe a row left to reveal Rename and Delete, the ratified gesture beside
   * the long press. The sheet scrolls vertically, so only a drag that is more
   * across than down is a swipe. */
  private swipeForActions(): void {
    let from: { x: number; y: number; row: HTMLElement } | null = null;
    this.body.addEventListener("pointerdown", (e) => {
      const row = (e.target as Element).closest<HTMLElement>(".row");
      if (!row || (e.target as Element).closest(".fs-act")) return;
      from = { x: e.clientX, y: e.clientY, row };
    });
    this.body.addEventListener("pointermove", (e) => {
      if (!from) return;
      const dx = e.clientX - from.x;
      if (Math.abs(dx) <= Math.abs(e.clientY - from.y)) return;
      if (dx <= -SWIPE_PX) {
        this.openActions(from.row);
        from = null;
      } else if (dx >= SWIPE_PX && this.swiped === from.row) {
        this.closeActions();
        from = null;
      }
    });
    for (const kind of ["pointerup", "pointercancel"])
      this.body.addEventListener(kind, () => {
        from = null;
      });
  }

  private openActions(row: HTMLElement): void {
    if (this.swiped === row) return;
    this.closeActions();
    row.insertAdjacentHTML(
      "beforeend",
      `<div class="fs-acts">` +
        `<button class="fs-act ren" type="button">Rename</button>` +
        `<button class="fs-act del" type="button">Delete</button></div>`,
    );
    row.classList.add("swiped");
    this.swiped = row;
    this.opening = true;
  }

  private closeActions(): void {
    if (!this.swiped) return;
    this.swiped.classList.remove("swiped");
    this.swiped.querySelector(".fs-acts")?.remove();
    this.swiped = null;
  }

  private async remove(row: HTMLElement): Promise<void> {
    const session = this.find(Number(row.dataset.id));
    if (!session) return;
    await api.deleteSession(session.id);
    if (this.current === session.id) this.current = null;
    await this.load(this.current);
    this.render();
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
    this.closeActions();
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

  /** What one family shows right now: the matching sessions, collapsed to the
   * three most recent unless it is expanded or a search is running. A search
   * matching the family's own name keeps all of its sessions. */
  private shown(family: Family): { rows: Session[]; more: number } {
    const query = this.filter.trim().toLowerCase();
    const byName = !!query && family.diagram.name.toLowerCase().includes(query);
    const matches =
      query && !byName
        ? family.sessions.filter((s) =>
            `${sessionTitle(s)} ${summaryOf(s)}`.toLowerCase().includes(query),
          )
        : family.sessions;
    if (query || this.expanded.has(family.diagram.id) || matches.length <= COLLAPSED)
      return { rows: matches, more: 0 };
    const rows = matches.filter((s, i) => i < COLLAPSED || s.id === this.current);
    return { rows, more: matches.length - rows.length };
  }

  private render(): void {
    const home = this.home();
    this.newButton.textContent = `New session with ${home?.diagram.name ?? "your family"}`;
    const now = new Date();
    const searching = !!this.filter.trim();

    let html = "";
    let total = 0;
    for (const family of this.families) {
      const { rows, more } = this.shown(family);
      total += family.sessions.length;
      if (searching && !rows.length) continue;
      const id = family.diagram.id;
      html += `<section class="fs-sec" data-family="${id}">${this.headHtml(family)}`;
      // the clock only earns its place when a day holds more than one session
      const counts = new Map<number, number>();
      for (const s of family.sessions) {
        const key = dayKey(new Date(s.last_activity));
        counts.set(key, (counts.get(key) ?? 0) + 1);
      }
      let group = "";
      for (const session of rows) {
        const when = new Date(session.last_activity);
        const label = searching ? "" : groupLabel(when, now);
        if (label && label !== group) {
          group = label;
          html += `<div class="ghead">${esc(label)}</div>`;
        }
        html += this.rowHtml(
          session,
          whenText(when, now, counts.get(dayKey(when)) ?? 1),
        );
      }
      if (more) html += `<div class="fs-more" data-family="${id}">${more} more…</div>`;
      html += "</section>";
    }

    if (!html)
      html = `<div class="fs-hint">${
        searching ? "No sessions match" : "Past conversations collect here"
      }</div>`;
    else if (!searching && total <= 1)
      html += `<div class="fs-hint">Past conversations collect here</div>`;

    this.swiped = null;
    const top = this.body.scrollTop;
    this.body.innerHTML = html;
    this.body.scrollTop = top;
  }

  private headHtml(family: Family): string {
    const name = family.diagram.name;
    const last = family.sessions[0];
    return (
      `<div class="fs-fhead${family.diagram.current ? " cur" : ""}">` +
      this.thumb(family) +
      `<div class="fs-fmain">` +
      `<div class="fs-fname">${esc(name)}</div>` +
      `<div class="fs-flast">last: ${esc(last ? summaryOf(last) : "nothing yet")}</div>` +
      `</div>` +
      `<button class="fs-plus" type="button" data-family="${family.diagram.id}" ` +
      `aria-label="New session with ${esc(name)}">+</button>` +
      `</div>`
    );
  }

  /** The family's wire, small: one mark per session so the header carries the
   * same picture the app draws large. */
  private thumb(family: Family): string {
    const w = 60;
    const h = 14;
    const times = family.sessions.map((s) => new Date(s.last_activity).getTime());
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
      `<div class="r1 rtitle">${title}` +
      (session.title_set_by_user ? `<span class="pencil">&#9998;</span>` : "") +
      `</div>` +
      `<div class="r2">${esc(summaryOf(session))}</div>` +
      `</div>` +
      `<div class="r2 rwhen">${esc(when)}</div>` +
      `</div>`
    );
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
   * empty sessions say nothing the first one does not. A new session can only
   * start on the family the app is on, because that is the diagram the coach
   * writes to. */
  private async start(familyId?: number): Promise<void> {
    let home = this.home();
    // The "+" on another family moves the app there first: the coach writes to
    // the diagram the app is on, so there is nowhere else to put the session.
    if (familyId !== undefined && home && familyId !== home.diagram.id) {
      const moved = this.families.find((f) => f.diagram.id === familyId);
      if (!moved) return;
      await api.selectDiagram(familyId);
      this.handlers.onDiagram(moved.diagram, { switched: true });
      await this.load(null);
      home = this.home();
    }
    const current = this.current === null ? undefined : this.find(this.current);
    if (current && current.message_count === 0) {
      this.lower();
      toast("Still empty — say something first");
      $("composer").focus({ preventScroll: true });
      return;
    }
    const session = await api.newSession();
    if (home) home.sessions = [session, ...home.sessions];
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
      for (const family of this.families)
        family.sessions = family.sessions.map((s) =>
          s.id === saved.id ? saved : s,
        );
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
