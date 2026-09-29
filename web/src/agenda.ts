import * as api from "./api";
import { Feature, tap } from "./track";
import { esc } from "./dom";
import { toast } from "./toast";
import { dayText, rowDate } from "./when";
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
 * What is on the agenda, by the day of its meeting: one day is one meeting,
 * with its date once, its cuts under it and one way to run it. Then each
 * coder's state with a count of who is closed out, one control that nudges
 * the ones who are not done, and the one button that opens the vote — nothing
 * else opens it (R-0273). Under it the next meeting's agenda fills itself
 * from the flagged rules (R-0276, R-0308). An event the room left unresolved
 * stays unresolved and is never brought back to a later meeting (R-0312).
 *
 * Two more pages hang off it: every session on every family, to put one on
 * the agenda, and the page of one meeting, each cut on it with who has
 * submitted a coding of it and who has not.
 */

export interface AgendaHandlers {
  /** The list a session is put on the agenda from is drawn. */
  onPick(): void;
  /** Place the cut on one conversation: one already on the agenda, to move
   * its line, or one picked from every family's sessions, to put it on. */
  onPlace(discussionId: number): void;
  /** The page of one meeting is drawn, under this title. */
  onMeeting(title: string): void;
  /** The room on one cut of the meeting: decide the open items and ratify
   * (R-0250). */
  onRatify(cutId: number): void;
  /** What the meeting produced on a cut the room has ratified (R-0275). */
  onResult(cutId: number): void;
}

const CROSS = "&#10005;";
/** A coder who has submitted a coding of a cut, whether or not they voted. */
const SUBMITTED = [CoderState.Done, CoderState.Voted];

export class Agenda {
  private cuts: Cut[] = [];
  private ratified: Cut[] = [];
  private coders: CoderLine[] = [];
  private next: NextMeeting | null = null;
  /** The day of the meeting whose page was last drawn. */
  meeting: string | null = null;

  constructor(
    private body: HTMLElement,
    private picker: HTMLElement,
    private room: HTMLElement,
    private handlers: AgendaHandlers,
  ) {
    for (const one of [body, picker, room])
      one.addEventListener("click", (e) => void this.onClick(e));
    this.body.addEventListener("change", (e) => void this.onDate(e));
    this.picker.addEventListener("input", (e) => {
      const field = (e.target as Element).closest<HTMLInputElement>(".tb-words");
      if (field) void this.seek(field);
    });
  }

  async load(): Promise<void> {
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
    this.render();
  }

  /** The cuts on the agenda by the day of their meeting, soonest first and
   * those with no day yet last: one day is one meeting. */
  private meetings(): [string | null, Cut[]][] {
    const days = [...new Set(this.cuts.map((cut) => cut.meeting_date))].sort((a, b) =>
      a === null ? 1 : b === null ? -1 : a.localeCompare(b),
    );
    return days.map((day) => [day, this.cuts.filter((cut) => cut.meeting_date === day)]);
  }

  /** The day a cut newly put on the agenda joins: the next meeting's, or none
   * while no meeting has a day. */
  nextDate(): string | null {
    return this.meetings().find(([day]) => day !== null)?.[0] ?? null;
  }

  private waiting(): CoderLine[] {
    return this.coders.filter(
      (one) =>
        one.state === CoderState.NotStarted || one.state === CoderState.Coding,
    );
  }

  /** A new day for one meeting moves every cut of it. */
  private async onDate(e: Event): Promise<void> {
    const field = (e.target as Element).closest<HTMLInputElement>(".tb-date");
    if (!field?.value) return;
    const was = field.dataset.was || null;
    for (const cut of this.cuts.filter((one) => one.meeting_date === was))
      await api.setMeetingDate(cut.id, field.value);
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
      const drawn = this.pick();
      this.handlers.onPick();
      await drawn;
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
      this.handlers.onMeeting(await this.meet(meet.dataset.day || null));
      return;
    }
    const run = target.closest<HTMLElement>(".tb-run");
    if (run) {
      this.handlers.onRatify(Number(run.dataset.cut));
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
      `<div class="sn-hd">On the agenda</div>` +
      (this.cuts.length
        ? this.meetings()
            .map(([day, cuts]) => this.meetingRows(day, cuts))
            .join("")
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
      this.agendaBox();
  }

  /** One meeting: its day once, its cuts under it, and once the vote is open
   * on them, the one way to run it (R-0250, R-0273). */
  private meetingRows(day: string | null, cuts: Cut[]): string {
    const open = cuts.some((cut) => cut.vote_opened_at !== null);
    return (
      this.dateRow(day) +
      cuts.map((cut) => this.cutRow(cut)).join("") +
      (open
        ? `<button class="nudge go tb-meet" type="button" data-day="${esc(day ?? "")}">` +
          `run the meeting</button>`
        : "")
    );
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

  /** The page of one meeting: each cut on it with who has submitted a coding
   * of it and who has not. A cut somebody has submitted, with the vote open
   * on it, is the way into the room on it; what nobody has submitted says so
   * rather than opening onto nothing. Answers the page's title. */
  async meet(day: string | null): Promise<string> {
    this.meeting = day;
    const cuts = this.cuts.filter((cut) => cut.meeting_date === day);
    const coders = await Promise.all(cuts.map((cut) => api.coders(cut.id)));
    this.room.innerHTML = cuts.map((cut, at) => this.meetRow(cut, coders[at])).join("");
    return day ? `Meeting · ${this.dayWords(day)}` : "Meeting";
  }

  private meetRow(cut: Cut, coders: CoderLine[]): string {
    const done = coders.filter((one) => SUBMITTED.includes(one.state));
    const missing = coders.filter((one) => !SUBMITTED.includes(one.state));
    const names = (some: CoderLine[]) => some.map((one) => esc(one.name)).join(", ");
    const opens = done.length > 0 && cut.vote_opened_at !== null;
    return (
      `<div class="sn-grp">` +
      `<div class="sn-row${opens ? " push tb-run" : ""}" data-cut="${cut.id}">` +
      this.cutLines(cut) +
      (done.length ? `<div class="sn-s">Submitted: ${names(done)}</div>` : "") +
      (done.length && missing.length
        ? `<div class="sn-s">Not submitted: ${names(missing)}</div>`
        : "") +
      `</div>${opens ? `<span class="sn-chev">&rsaquo;</span>` : ""}</div></div>` +
      (done.length ? "" : `<div class="sn-hint">No coder has submitted yet</div>`)
    );
  }

  /** Every session on every family, newest first, to put one on the agenda;
   * the words typed keep those where something said carries them. */
  private async pick(): Promise<void> {
    this.picker.innerHTML =
      `<div class="sn-srch"><input class="tb-words" type="search" ` +
      `placeholder="Search what was said" aria-label="Search what was said"></div>` +
      `<div class="tb-found"></div>`;
    await this.seek(this.picker.querySelector<HTMLInputElement>(".tb-words")!);
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
    this.picker.querySelector(".tb-found")!.innerHTML = found.length
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

  /** A meeting's day in words. */
  private dayWords(day: string): string {
    return new Date(`${day}T00:00:00`).toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
  }

  /** Tapping the date row opens the phone's own date picker. */
  private dateRow(day: string | null): string {
    return (
      `<label class="sn-row push tb-when"><div class="sn-m">` +
      `<div class="sn-t">Meeting date</div>` +
      `<div class="sn-s">${esc(day ? this.dayWords(day) : "not set")}</div>` +
      `</div><span class="sn-chev">&rsaquo;</span>` +
      `<input class="tb-date" type="date" value="${esc(day ?? "")}"` +
      ` data-was="${esc(day ?? "")}" aria-label="Meeting date"></label>`
    );
  }

  private cutRow(cut: Cut): string {
    const off = cut.started
      ? ""
      : `<button class="pl-btn" type="button" data-cut="${cut.id}" ` +
        `aria-label="take off the agenda">${CROSS}</button>`;
    return (
      `<div class="sn-row tb-cut" data-discussion="${cut.discussion_id}">` +
      this.cutLines(cut) +
      `</div>${off}</div>`
    );
  }

  /** A cut's session and where it stops, in a row's words left open for more
   * lines under them. */
  private cutLines(cut: Cut): string {
    return (
      `<div class="sn-m"><div class="sn-t">${esc(cut.session)}</div>` +
      `<div class="sn-s">up to turn ${cut.end_order ?? 0} · ` +
      `${esc(cut.cut_day ?? "")}</div>`
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
