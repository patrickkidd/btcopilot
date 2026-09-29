import * as api from "./api";
import { Feature, tap } from "./track";
import { esc, type Title } from "./dom";
import { toast } from "./toast";
import { dayText, meetingTitle, rowDate } from "./when";
import { sessionTitle } from "./search";
import { sessionWhen } from "./sessions";
import {
  CoderState,
  type NextMeeting,
  type CoderLine,
  type Cut,
  type Rule,
  type Session,
} from "./types";

/** The agenda: the whole of Patrick's administration (R-0259, R-0267).
 *
 * The meeting date, what is on the agenda, each coder's state with a count of
 * who is closed out, one control that nudges the ones who are not done, and
 * the one button that opens the vote — nothing else opens it (R-0273). Under
 * it the next meeting's agenda fills itself from the flagged rules (R-0276,
 * R-0308). An event the room left unresolved stays unresolved and is never
 * brought back to a later meeting (R-0312).
 */

export interface AgendaHandlers {
  /** Place the cut on one conversation: one already on the agenda, to move
   * its line, or one picked from every family's sessions, to put it on. */
  onPlace(discussionId: number): void;
  /** Run the meeting on what is on the agenda: decide the open items and
   * ratify (R-0250). */
  onMeeting(cutId: number): void;
  /** What the screen is called, which the title row shows. */
  onTitle(title: string | Title): void;
  /** What the meeting produced on a cut the room has ratified (R-0275). */
  onResult(cutId: number): void;
}

const CROSS = "&#10005;";
const PICK_TITLE = "Pick a session";

export class Agenda {
  private cuts: Cut[] = [];
  private ratified: Cut[] = [];
  private coders: CoderLine[] = [];
  private next: NextMeeting | null = null;
  /** Whether the screen is the list a session is put on the agenda from,
   * which the back button returns from to the agenda. */
  picking = false;

  constructor(
    private body: HTMLElement,
    private handlers: AgendaHandlers,
  ) {
    this.body.addEventListener("click", (e) => void this.onClick(e));
    this.body.addEventListener("change", (e) => void this.onDate(e));
    this.body.addEventListener("input", (e) => {
      const field = (e.target as Element).closest<HTMLInputElement>(".tb-words");
      if (field) void this.seek(field);
    });
  }

  async load(): Promise<void> {
    this.picking = false;
    const [cuts, coders, next, every] = await Promise.all([
      api.onAgenda(),
      api.coders(),
      api.agenda(),
      api.allCuts(),
    ]);
    this.cuts = cuts;
    this.coders = coders;
    this.next = next;
    this.ratified = every.filter((cut) => cut.ratified_at !== null);
    this.handlers.onTitle(this.title());
    this.render();
  }

  /** The meeting the agenda is for, which is the date on the cuts on it. */
  private meeting(): string | null {
    return this.cuts.find((cut) => cut.meeting_date)?.meeting_date ?? null;
  }

  /** The meeting's day in words, or nothing when no date is set yet. */
  private day(): string | null {
    const meeting = this.meeting();
    if (!meeting) return null;
    return new Date(`${meeting}T00:00:00`).toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
  }

  private title(): string {
    return meetingTitle(this.meeting());
  }

  private waiting(): CoderLine[] {
    return this.coders.filter(
      (one) =>
        one.state === CoderState.NotStarted || one.state === CoderState.Coding,
    );
  }

  private async onDate(e: Event): Promise<void> {
    const field = (e.target as Element).closest<HTMLInputElement>(".tb-date");
    if (!field?.value) return;
    for (const cut of this.cuts) await api.setMeetingDate(cut.id, field.value);
    await this.load();
  }

  private async onClick(e: Event): Promise<void> {
    const target = e.target as Element;
    const off = target.closest<HTMLElement>(".pl-btn");
    if (off) {
      tap(Feature.AgendaTakeOff);
      await this.take(Number(off.dataset.cut));
      return;
    }
    const cut = target.closest<HTMLElement>(".tb-cut");
    if (cut) {
      tap(Feature.AgendaOpenItem);
      this.handlers.onPlace(Number(cut.dataset.discussion));
      return;
    }
    if (target.closest(".tb-add")) {
      tap(Feature.AgendaAdd);
      await this.pick();
      return;
    }
    const picked = target.closest<HTMLElement>(".tb-pick");
    if (picked) {
      tap(Feature.SessionToAgenda);
      this.handlers.onPlace(Number(picked.dataset.discussion));
      return;
    }
    if (target.closest(".tb-nudge")) {
      tap(Feature.AgendaNudge);
      await this.nudge();
      return;
    }
    if (target.closest(".tb-vote")) {
      tap(Feature.AgendaOpenVote);
      await this.openVote();
      return;
    }
    const result = target.closest<HTMLElement>(".tb-result");
    if (result) {
      tap(Feature.AgendaResult);
      this.handlers.onResult(Number(result.dataset.cut));
      return;
    }
    const meet = target.closest<HTMLElement>(".tb-meet");
    if (meet) {
      tap(Feature.MeetingStart);
      this.handlers.onMeeting(Number(meet.dataset.cut));
      return;
    }
    const close = target.closest<HTMLElement>(".agx");
    if (close) {
      await api.flagRule(Number(close.dataset.rule), false);
      await this.load();
    }
  }

  /** Taking a conversation off the agenda is one tap, and only before anyone
   * has started coding it. */
  private async take(cutId: number): Promise<void> {
    try {
      await api.offAgenda(cutId);
    } catch (error) {
      toast(
        error instanceof api.Failed && error.status === 400
          ? "Someone has already started coding that one"
          : "That did not come off the agenda",
      );
      return;
    }
    await this.load();
  }

  private async nudge(): Promise<void> {
    const sent = await api.nudge();
    toast(
      sent.nudged.length
        ? `Nudged ${sent.nudged.length}`
        : "Nobody is waiting to be nudged",
    );
    await this.load();
  }

  private async openVote(): Promise<void> {
    for (const cut of this.cuts)
      if (cut.vote_opened_at === null) await api.openVote(cut.id);
    toast("The vote is open");
    await this.load();
  }

  private render(): void {
    const closed = this.coders.filter((one) => one.closed_out).length;
    const behind = this.waiting().length;
    // The button stands while anything on the agenda still needs the vote
    // opening on it; once every one of them is open it becomes a plain line.
    const open =
      this.cuts.length > 0 &&
      this.cuts.every((cut) => cut.vote_opened_at !== null);
    this.body.innerHTML =
      this.dateRow() +
      `<div class="sn-hd">On the agenda</div>` +
      (this.cuts.length
        ? this.cuts.map((cut) => this.cutRow(cut)).join("")
        : `<div class="none">Nothing is on the agenda yet.</div>`) +
      `<button class="nudge tb-add" type="button">Put a session on the agenda</button>` +
      this.results() +
      `<div class="sn-hd">Coders</div>` +
      this.coders.map((one) => this.coderRow(one)).join("") +
      `<div class="plnote">closed out: ${closed} of ${this.coders.length}` +
      this.nudged() +
      `</div>` +
      (behind
        ? `<button class="nudge tb-nudge" type="button">nudge the ${behind} ` +
          `who ${behind === 1 ? "is" : "are"} not done</button>`
        : "") +
      (open
        ? `<div class="plnote">The vote is open.</div>`
        : `<button class="nudge tb-vote" type="button">open the vote</button>`) +
      this.meetingButtons() +
      this.agendaBox();
  }

  /** A conversation the room has ratified keeps one way in to what the meeting
   * produced, so the result stays reachable after the cut leaves the agenda
   * (R-0275). */
  private results(): string {
    if (!this.ratified.length) return "";
    return (
      `<div class="sn-hd">Ratified</div>` +
      this.ratified
        .map(
          (cut) =>
            `<div class="sn-row"><div class="sn-m">` +
            `<div class="sn-t">${esc(cut.session)}</div>` +
            // Two cuts of one conversation read alike unless the line says
            // where each one stops and when the room ratified it.
            `<div class="sn-s">up to ${esc(cut.cut_day ?? "")} · ratified ` +
            `${cut.ratified_at ? dayText(cut.ratified_at) : ""}</div></div></div>` +
            `<button class="nudge go tb-result" type="button" data-cut="${cut.id}">` +
            `see the result</button>`,
        )
        .join("")
    );
  }

  /** Once the vote is open the meeting can be run on that cut: the room
   * decides what the ballot left and ratifies (R-0250, R-0273). */
  private meetingButtons(): string {
    return this.cuts
      .filter((cut) => cut.vote_opened_at !== null)
      .map(
        (cut) =>
          `<button class="nudge go tb-meet" type="button" data-cut="${cut.id}">` +
          `run the meeting</button>`,
      )
      .join("");
  }

  /** Every session on every family, newest first, to put one on the agenda;
   * the words typed keep those where something said carries them. */
  private async pick(): Promise<void> {
    this.picking = true;
    this.handlers.onTitle(PICK_TITLE);
    this.body.innerHTML =
      `<div class="sn-srch"><input class="tb-words" type="search" ` +
      `placeholder="Search what was said" aria-label="Search what was said"></div>` +
      `<div class="tb-found"></div>`;
    await this.seek(this.body.querySelector<HTMLInputElement>(".tb-words")!);
  }

  /** An answer for words since typed over, or for a list since left, is
   * dropped. */
  private async seek(field: HTMLInputElement): Promise<void> {
    const words = field.value;
    const found = await api.allSessions(words);
    if (words === field.value && field.isConnected) this.list(found, words);
  }

  private list(found: Session[], words: string): void {
    const now = new Date();
    this.body.querySelector(".tb-found")!.innerHTML = found.length
      ? found
          .map(
            (session) =>
              `<div class="sn-row push tb-pick" data-discussion="${session.id}">` +
              `<div class="sn-m"><div class="sn-t">${esc(sessionTitle(session))}</div>` +
              `<div class="sn-s">${esc(session.family ?? "")} · ` +
              `${rowDate(sessionWhen(session), now)} · ${session.message_count} ` +
              `statement${session.message_count === 1 ? "" : "s"}</div>` +
              (session.match ? `<div class="sn-s">${esc(session.match)}</div>` : "") +
              `</div></div>`,
          )
          .join("")
      : `<div class="none">${words.trim() ? "No session matches." : "No sessions yet."}</div>`;
  }

  private nudged(): string {
    const when = this.cuts.map((cut) => cut.nudged_at).filter(Boolean)[0];
    if (!when) return "";
    const day = new Date(when as string).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
    return ` · nudged ${day}`;
  }

  /** Tapping the date row opens the phone's own date picker. */
  private dateRow(): string {
    const meeting = this.meeting();
    return (
      `<label class="sn-row push tb-when"><div class="sn-m">` +
      `<div class="sn-t">Meeting date</div>` +
      `<div class="sn-s">${esc(this.day() ?? "not set")}</div>` +
      `</div><span class="sn-chev">&rsaquo;</span>` +
      `<input class="tb-date" type="date" value="${esc(meeting ?? "")}"` +
      ` aria-label="Meeting date"></label>`
    );
  }

  private cutRow(cut: Cut): string {
    const off = cut.started
      ? ""
      : `<button class="pl-btn" type="button" data-cut="${cut.id}" ` +
        `aria-label="take off the agenda">${CROSS}</button>`;
    return (
      `<div class="sn-row tb-cut" data-discussion="${cut.discussion_id}">` +
      `<div class="sn-m"><div class="sn-t">${esc(cut.session)}</div>` +
      `<div class="sn-s">up to turn ${cut.end_order ?? 0} · ` +
      `${esc(cut.cut_day ?? "")}</div></div>${off}</div>`
    );
  }

  private coderRow(one: CoderLine): string {
    return (
      `<div class="srow"><span class="s1">${esc(one.name)}</span>` +
      `<span class="s2">${esc(one.state)}</span></div>`
    );
  }

  private agendaBox(): string {
    const lines = this.agendaLines();
    if (!lines.length) return "";
    return (
      `<div class="agbox"><div class="aghd">Next meeting's agenda · ` +
      `${lines.length}</div>` +
      lines
        .map(
          (line) =>
            `<div class="agrow"><span class="agt">${esc(line.text)}</span>` +
            (line.rule_id === null
              ? ""
              : `<span class="agx" data-rule="${line.rule_id}">close</span>`) +
            `</div>`,
        )
        .join("") +
      `</div>`
    );
  }

  /** What put itself on the agenda, in the words of the thing it came from. */
  private agendaLines(): { text: string; rule_id: number | null }[] {
    const found = this.next;
    if (!found) return [];
    return found.flagged_rules.map((rule: Rule) => ({
      text: `flagged rule: ${rule.text}`,
      rule_id: rule.id,
    }));
  }
}
