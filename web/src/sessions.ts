import * as api from "./api";
import { Feature, tap } from "./track";
import { $, closeX, el, esc, flash, isAdmin } from "./dom";
import { dragScroll } from "./drag";
import { toast } from "./toast";
import { periodLabel, rowDate } from "./when";
import { matching, sessionTitle, type Family } from "./search";
import { Access, SessionKind, type Diagram, type Session } from "./types";
import { PRO } from "./pro";
import { Recording } from "./recording";
import { Swipe } from "./swipe";

/** The sheet beside the message box, and the button that raises it, for those
 * with work in it: a professional's notes and recordings, and for Patrick the
 * family's conversations, to rename or delete one. Nobody opens or starts a
 * conversation here; the family has one thread. Coding, the meeting and the
 * replies picked blind are reached from the account view, since none of them
 * hangs on the family the app is on. */

const TITLE_CAP = 120;
const DAY_HEADINGS = new Set(["Today", "Yesterday"]);
/** Drag up from the input bar this far to open; drag the grabber down this far
 * to close. */
const OPEN_DRAG = 40;
const CLOSE_DRAG = 90;
const PRESS_MS = 500;

/** When a session happened: a recording's own day, else when it was last
 * spoken in. */
export const sessionWhen = (session: Session): Date =>
  new Date(session.date ? `${session.date}T12:00:00` : session.last_activity);

export interface SessionsHandlers {
  /** A professional's new note or recording, which joins the thread. */
  onMade(session: Session): void;
  /** The drawer came up or went down, so the address says so. */
  onMoved(): void;
  /** A session tapped: the drawer goes down and the thread goes to where that
   * session starts. */
  onPick(sitting: number): void;
  /** The diagram the app is on, whose sessions the drawer lists. */
  diagram(): Diagram | null;
}


export class Sessions {
  private families: Family[] = [];
  private filter = "";
  /** On a search, each session where something said carries the words, and
   * the newest line that does, which stands under its title. */
  private lines = new Map<number, string>();
  private open = false;
  private drag: { kind: "open" | "close"; y0: number; dy: number } | null = null;
  /** Only Patrick sees the family's conversations listed. */
  private admin = isAdmin();
  /** Whether the sheet holds anything for this reader, and so has a door. */
  readonly door = this.admin || PRO;

  private scrim = el("div", "fs-scrim");
  private sheet = el(
    "div",
    "fs-sheet",
    `<div class="fs-handle"><div class="fs-grab"></div></div>${closeX()}
     <div class="fs-search">
       <input type="search" placeholder="Search sessions"
              aria-label="Search sessions">
     </div>
     <div class="fs-body"></div>
     <div class="fs-foot">
       <button class="fs-new fs-upload" type="button" hidden>Upload a recording</button>
       <button class="fs-new fs-note" type="button" hidden>+ new note</button></div>`,
  );

  private body: HTMLElement;
  /** Swipe a row left to reveal Rename and Delete, the ratified gesture beside
   * the long press. */
  private swipe: Swipe;
  private search: HTMLInputElement;
  private uploadButton: HTMLButtonElement;
  private noteButton: HTMLButtonElement;
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
    this.swipe = new Swipe(this.body, ".row", () => ({
      html:
        `<button class="fs-act ren" type="button">Rename</button>` +
        `<button class="fs-act del" type="button">Delete</button>`,
      wide: false,
    }));
    this.search = this.sheet.querySelector<HTMLInputElement>(".fs-search input")!;
    this.search.parentElement!.hidden = this.body.hidden = !this.admin;
    this.uploadButton = this.sheet.querySelector<HTMLButtonElement>(".fs-upload")!;
    this.noteButton = this.sheet.querySelector<HTMLButtonElement>(".fs-note")!;
    this.uploadButton.hidden = !PRO;
    this.noteButton.hidden = !PRO;
    this.recording = new Recording(this.overlay, (made) => this.handlers.onMade(made));
    this.wire();
    dragScroll(this.body);
  }

  /** The conversations of the family the app is on, read as the sheet rises. */
  private async load(): Promise<void> {
    const diagram = this.handlers.diagram();
    const fresh = diagram
      ? [{ diagram, sessions: await api.sessionIndex(diagram.id) }]
      : [];
    // Newest first, except while the sheet is up: a list must not reorder under
    // the reader's thumb because a reply landed (ratified behaviour). New
    // sessions join at the end of their family until the sheet is closed.
    this.families = this.open ? fresh.map((f) => this.held(f)) : fresh;
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
    this.button.addEventListener("click", () => {
      tap(Feature.OpenSessions);
      void this.raise(true);
    });
    this.scrim.addEventListener("click", () => this.lower());
    this.sheet.querySelector(".cardx")!.addEventListener("click", () => this.lower());
    this.search.addEventListener("input", () => void this.seek());
    // One sheet is up at a time: the upload sheet takes the sessions sheet's
    // place rather than standing on top of it.
    this.uploadButton.addEventListener("click", () => {
      tap(Feature.UploadOpen);
      this.lower();
      this.recording.pick();
    });
    this.noteButton.addEventListener("click", () => {
      tap(Feature.NoteNew);
      void this.note();
    });
    this.body.addEventListener("click", (e) => this.onBodyClick(e));
    this.pressToRename();
    this.drags();
  }

  private onBodyClick(e: Event): void {
    const target = e.target as Element;
    const action = target.closest<HTMLElement>(".fs-act");
    if (action) {
      e.stopPropagation();
      const row = action.closest<HTMLElement>(".row")!;
      if (action.classList.contains("ren")) {
        tap(Feature.SessionRename);
        this.swipe.close();
        this.rename(row);
      } else {
        tap(Feature.SessionDelete);
        void this.remove(row);
      }
      return;
    }
    // a tap anywhere else puts an open row's actions away rather than firing
    if (this.swipe.claims()) return;
    const row = target.closest<HTMLElement>(".row");
    if (!row || row.querySelector("input")) return;
    if (target.closest(".rmore")) return this.swipe.open(row, false);
    tap(Feature.SessionOpen);
    this.lower();
    this.handlers.onPick(Number(row.dataset.id));
  }

  private async remove(row: HTMLElement): Promise<void> {
    const session = this.find(Number(row.dataset.id));
    if (!session) return;
    await api.deleteSession(session.id);
    await this.load();
    this.render();
  }

  /** A long press on a row opens its title for editing in place. */
  private pressToRename(): void {
    let timer = 0;
    const cancel = () => window.clearTimeout(timer);
    this.body.addEventListener("pointerdown", (e) => {
      const row = (e.target as Element).closest<HTMLElement>(".row");
      if (!row || this.handlers.diagram()?.access === Access.AdminView) return;
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
        if (this.open || !this.door) return;
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
        if (drag.dy <= -OPEN_DRAG) void this.raise(false);
        return;
      }
      this.sheet.style.transition = "";
      if (drag.dy >= CLOSE_DRAG) this.lower();
      else this.sheet.style.transform = "";
    };
    this.overlay.addEventListener("pointerup", settle);
    this.overlay.addEventListener("pointercancel", settle);
  }

  /** Whether the drawer is up. */
  get up(): boolean {
    return this.open;
  }

  /** The drawer up from wherever the app is, and one session's row in it lit,
   * the way a message is lit in the thread (R-0055). */
  async show(id: number | null): Promise<void> {
    await this.raise(false);
    if (id === null) return;
    if (this.filter) {
      this.search.value = this.filter = "";
      this.render();
    }
    const row = this.body.querySelector<HTMLElement>(`.row[data-id="${id}"]`);
    if (row) flash(row);
    else toast("That session is not in the list");
  }

  /** Up on a tap of its door with the search ready to type in; a drag or an
   * address brings it up without the keyboard. */
  private async raise(focus: boolean): Promise<void> {
    if (this.open) return;
    this.open = true;
    if (this.admin) {
      await this.load();
      this.render();
    }
    this.body.scrollTop = 0;
    this.scrim.hidden = false;
    this.sheet.hidden = false;
    void this.sheet.offsetWidth;
    this.scrim.classList.add("in");
    this.sheet.classList.add("in");
    this.screen.style.transformOrigin = "50% 0";
    this.screen.style.transform = "scale(.96)";
    if (focus && this.admin) this.search.focus({ preventScroll: true });
    this.handlers.onMoved();
  }

  /** The sessions drawer and the upload panel it hands over to, both put away. */
  close(): void {
    this.lower();
    this.recording.lower();
  }

  private lower(): void {
    if (!this.open) return;
    this.open = false;
    this.handlers.onMoved();
    this.swipe.close();
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

  /** The words typed, looked for in what was said as well as in the titles.
   * The server reads what was said, with the coach's own search; an answer
   * for words since typed over is dropped. */
  private async seek(): Promise<void> {
    const words = this.search.value;
    const home = this.home();
    const found = home && words.trim() ? await api.sessionSearch(home.diagram.id, words) : [];
    if (words !== this.search.value) return;
    this.filter = words;
    this.lines = new Map(found.map((s) => [s.id, s.match!]));
    this.render();
  }

  private render(): void {
    const home = this.home();
    const now = new Date();
    const searching = !!this.filter.trim();
    const rows = home ? matching(home, this.filter, new Set(this.lines.keys())).rows : [];

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

    this.swipe.forget();
    const top = this.body.scrollTop;
    this.body.innerHTML = html;
    this.body.scrollTop = top;
  }

  /** A row the way a messages list draws one: the title with the day small
   * at its right, then two lines of what the client first said, or on a
   * search the line that carries the words. */
  private rowHtml(session: Session, now: Date, period: string): string {
    // inside Today and Yesterday the heading already says the day
    const day = DAY_HEADINGS.has(period) ? "" : rowDate(sessionWhen(session), now);
    const said = this.lines.get(session.id) ?? session.preview ?? (session.kind === SessionKind.Chat ? "Nothing said yet" : `A ${session.kind} with nothing in it yet`);
    return (
      `<div class="row" data-id="${session.id}">` +
      `<div class="rmain">` +
      `<div class="rhead"><div class="r1 rtitle">${esc(sessionTitle(session))}</div>` +
      `<div class="rday">${esc(day)}</div></div>` +
      `<div class="rsub">${esc(said)}</div>` +
      `</div>` +
      `<button class="rmore" type="button" aria-label="Rename or delete">&#8943;</button>` +
      `</div>`
    );
  }

  /** A professional's note is a session of its own (R-0281), on the family
   * the app is on. A second one is refused while the last is still empty: two
   * empty notes say nothing the first does not. */
  private async note(): Promise<void> {
    const [last] = await api.sessionIndex();
    this.lower();
    if (last?.kind === SessionKind.Note && last.message_count === 0) {
      toast("Still empty — say something first");
      $("composer").focus({ preventScroll: true });
      return;
    }
    this.handlers.onMade(await api.newSession(SessionKind.Note));
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
