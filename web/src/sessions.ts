import * as api from "./api";
import { $, el, esc, isAdmin } from "./dom";
import { dragScroll } from "./drag";
import { toast } from "./toast";
import { meetingTitle, periodLabel, rowDate } from "./when";
import { matching, sessionTitle, type Family } from "./search";
import { SessionKind, type Diagram, type Session } from "./types";
import { PRO } from "./pro";
import { Recording } from "./recording";

/** The session door: the button beside the message box, and the searchable
 * bottom sheet it raises. The sessions of the family the app is on, newest
 * first under a heading per day; the family itself is chosen on the account
 * page, never here. */

const TITLE_CAP = 120;
const DAY_HEADINGS = new Set(["Today", "Yesterday"]);
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
  /** The sessions as last read, so an event tracing back to the one that coded
   * it can name it. */
  onList(sessions: Session[]): void;
  /** The coder's one task, reached from the foot of the sheet (R-0265). */
  onTask(): void;
  /** Patrick putting a conversation on the agenda: it opens so he can place
   * the cut (R-0267). Admins only. */
  onAgenda(session: Session): void;
  /** The agenda itself, which is Patrick's whole administration (R-0259). */
  onAgendaScreen(): void;
}


export class Sessions {
  private families: Family[] = [];
  private current: number | null = null;
  private filter = "";
  private open = false;
  /** The row whose Rename and Delete are showing, if any. */
  private swiped: HTMLElement | null = null;
  /** True between the swipe revealing the actions and the click it ends with. */
  private opening = false;
  private drag: { kind: "open" | "close"; y0: number; dy: number } | null = null;
  /** Only Patrick puts a conversation on the agenda, so only he is offered it. */
  private admin = isAdmin();

  private scrim = el("div", "fs-scrim");
  private sheet = el(
    "div",
    "fs-sheet",
    `<div class="fs-handle"><div class="fs-grab"></div></div>
     <div class="fs-search">
       <input type="search" placeholder="Search sessions"
              aria-label="Search sessions">
     </div>
     <div class="fs-body"></div>
     <div class="fs-foot"><button class="fs-new" type="button"></button>
       <button class="fs-new fs-upload" type="button" hidden>Upload a recording</button>
       <button class="fs-new fs-note" type="button" hidden>+ new note</button>
       <button class="fs-task" type="button" hidden></button>
       <button class="fs-task fs-agenda" type="button" hidden>Next meeting</button></div>`,
  );

  private body: HTMLElement;
  private search: HTMLInputElement;
  private newButton: HTMLButtonElement;
  private uploadButton: HTMLButtonElement;
  private noteButton: HTMLButtonElement;
  private taskButton: HTMLButtonElement;
  private agendaButton: HTMLButtonElement;
  private recording: Recording;

  constructor(
    private button: HTMLElement,
    private overlay: HTMLElement,
    private screen: HTMLElement,
    private inbar: HTMLElement,
    private handlers: SessionsHandlers,
  ) {
    this.scrim.hidden = true;
    this.sheet.hidden = true;
    // the page holds several sheets of one class; this one is the sessions'
    this.sheet.id = "sessions-sheet";
    this.scrim.id = "sessions-scrim";
    this.overlay.append(this.scrim, this.sheet);
    this.body = this.sheet.querySelector<HTMLElement>(".fs-body")!;
    this.search = this.sheet.querySelector<HTMLInputElement>(".fs-search input")!;
    this.newButton = this.sheet.querySelector<HTMLButtonElement>(".fs-new")!;
    this.uploadButton = this.sheet.querySelector<HTMLButtonElement>(".fs-upload")!;
    this.noteButton = this.sheet.querySelector<HTMLButtonElement>(".fs-note")!;
    this.taskButton = this.sheet.querySelector<HTMLButtonElement>(".fs-task")!;
    this.agendaButton = this.sheet.querySelector<HTMLButtonElement>(".fs-agenda")!;
    this.agendaButton.hidden = !this.admin;
    if (this.admin) void this.nameAgenda();
    this.uploadButton.hidden = !PRO;
    this.noteButton.hidden = !PRO;
    this.recording = new Recording(this.overlay, (made) => {
      this.current = made.id;
      this.handlers.onPick(made);
    });
    this.wire();
    dragScroll(this.body);
  }

  /** Raise the sheet from somewhere other than its own button — which is how
   * the agenda puts another conversation on. */
  show(): void {
    void this.raise(false);
  }

  /** The way to the coding task, when the signed-in coder has one. */
  task(label: string | null): void {
    this.taskButton.hidden = label === null;
    this.taskButton.textContent = label ?? "";
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

  /** The way in to the agenda is named by the meeting it is for, the same words
   * the agenda screen's own title carries. */
  private async nameAgenda(): Promise<void> {
    const cuts = await api.onAgenda();
    this.agendaButton.textContent = meetingTitle(
      cuts.find((cut) => cut.meeting_date)?.meeting_date ?? null,
    );
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
    // One sheet is up at a time: the upload sheet takes the sessions sheet's
    // place rather than standing on top of it.
    this.uploadButton.addEventListener("click", () => {
      this.lower();
      this.recording.pick();
    });
    this.noteButton.addEventListener("click", () =>
      void this.start(SessionKind.Note),
    );
    this.taskButton.addEventListener("click", () => {
      this.lower();
      this.handlers.onTask();
    });
    this.agendaButton.addEventListener("click", () => {
      this.lower();
      this.handlers.onAgendaScreen();
    });
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
      if (action.classList.contains("tbl")) {
        this.closeActions();
        this.openAgenda(row);
      } else if (action.classList.contains("ren")) {
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
    const row = target.closest<HTMLElement>(".row");
    if (!row || row.querySelector("input.rename")) return;
    if (target.closest(".rmore")) {
      this.openActions(row);
      this.opening = false;
      return;
    }
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
      `<div class="fs-acts${this.admin ? " wide" : ""}">` +
        (this.admin
          ? `<button class="fs-act tbl" type="button">Put on the agenda</button>`
          : "") +
        `<button class="fs-act ren" type="button">Rename</button>` +
        `<button class="fs-act del" type="button">Delete</button></div>`,
    );
    row.classList.add("swiped");
    if (this.admin) row.classList.add("wide");
    this.swiped = row;
    this.opening = true;
  }

  private closeActions(): void {
    if (!this.swiped) return;
    this.swiped.classList.remove("swiped", "wide");
    this.swiped.querySelector(".fs-acts")?.remove();
    this.swiped = null;
  }

  /** Patrick's swipe action: the conversation opens so he can place the cut
   * everyone will code up to. */
  private openAgenda(row: HTMLElement): void {
    const session = this.find(Number(row.dataset.id));
    if (!session) return;
    this.lower();
    this.handlers.onAgenda(session);
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

  private render(): void {
    const home = this.home();
    this.newButton.textContent = `New session with ${home?.diagram.name ?? "your family"}`;
    const now = new Date();
    const searching = !!this.filter.trim();
    const rows = home ? matching(home, this.filter).rows : [];

    let html = "";
    let period = "";
    for (const session of rows) {
      const when = new Date(session.last_activity);
      const label = periodLabel(when, now);
      if (label !== period) {
        if (period) html += `</div>`;
        period = label;
        html += `<div class="ghead">${esc(label)}</div><div class="fs-group">`;
      }
      html += this.rowHtml(session, now, label);
    }
    if (period) html += `</div>`;

    if (!html)
      html = `<div class="fs-hint">${
        searching ? "No sessions match" : "Past conversations collect here"
      }</div>`;
    else if (!searching && rows.length <= 1)
      html += `<div class="fs-hint">Past conversations collect here</div>`;

    this.swiped = null;
    const top = this.body.scrollTop;
    this.body.innerHTML = html;
    this.body.scrollTop = top;
  }

  /** A row the way a notes or messages list draws one: the title, then one
   * grey line with the day and the first thing the client said. A recording
   * or a note says which it is in that line. */
  /** A row the way a messages list draws one: the title with the day small
   * at its right, then two lines of what the client first said. */
  private rowHtml(session: Session, now: Date, period: string): string {
    const when = new Date(session.date ? `${session.date}T12:00:00` : session.last_activity);
    // inside Today and Yesterday the heading already says the day
    const day = DAY_HEADINGS.has(period) ? "" : rowDate(when, now);
    const said = session.preview ?? (session.kind === SessionKind.Chat ? "Nothing said yet" : `A ${session.kind} with nothing in it yet`);
    return (
      `<div class="row${session.id === this.current ? " cur" : ""}" data-id="${session.id}">` +
      `<div class="rmain">` +
      `<div class="rhead"><div class="r1 rtitle">${esc(sessionTitle(session))}</div>` +
      `<div class="rday">${esc(day)}</div></div>` +
      `<div class="rsub">${esc(said)}</div>` +
      `</div>` +
      `<button class="rmore" type="button" aria-label="Rename or delete">&#8943;</button>` +
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
   * empty sessions say nothing the first one does not. It starts on the family
   * the app is on, because that is the diagram the coach writes to. */
  private async start(kind: SessionKind = SessionKind.Chat): Promise<void> {
    const home = this.home();
    const current = this.current === null ? undefined : this.find(this.current);
    // two empty sessions of one kind say nothing the first does not; a note
    // beside an empty session is a different thing and is allowed
    if (current && current.kind === kind && current.message_count === 0) {
      this.lower();
      toast("Still empty — say something first");
      $("composer").focus({ preventScroll: true });
      return;
    }
    const session = await api.newSession(kind);
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
