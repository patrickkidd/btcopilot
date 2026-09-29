import * as api from "./api";
import { esc } from "./dom";
import { dragScroll } from "./drag";
import type { Fault, Faults } from "./faults";
import { Sheet } from "./sheet";
import { ReportKind, ReportSource, ReportStatus, type Report, type RequestFailure } from "./types";

/** What the person sends from the app (R-0056): a bug when a coach turn or
 * the page breaks, and feedback when the coach heard them say something about
 * the app. Each is a sheet over the thread, which it never touches. Sent, the
 * sheet turns into a card saying so, which goes on OK or after ten seconds.
 * During the beta a bug cannot be declined, only sent. */

/** How long the card saying the report was sent stays up. */
export const SENT_MS = 10_000;
/** The sitting the coach last offered to send the person's words in: one
 * offer a sitting, even across a reload. */
const OFFERED = "reports.offered";

enum Act {
  Send = "send",
  Always = "always",
  Not = "not",
  Ok = "ok",
}

/** What the sheet lists of a report: each thing sent, named. */
type List = [string, string][];

/** A report on its way up, with the list of what it sends. */
interface Raised {
  /** Null for a turn that failed, which the server already keeps. */
  report: Report | null;
  list: List;
  /** Something that broke, rather than words the coach heard. */
  broke: boolean;
}

const button = (act: Act, words: string, primary = false, off = false) =>
  `<button class="${primary ? "cf-go" : "cf-no"}" type="button" data-act="${act}"${off ? " disabled" : ""}>${words}</button>`;

const row = (label: string, value: string) =>
  value ? `<div class="rp-row"><div class="rp-l">${label}</div><div class="rp-v">${esc(value)}</div></div>` : "";

const HEADING = {
  [ReportKind.Bug]: "Send this as a bug report?",
  [ReportKind.Feedback]: "Send this as feedback?",
};

export class Reports {
  private sheet: Sheet;
  private at: Raised | null = null;
  private waiting: Raised[] = [];
  private closing = 0;
  /** A bug goes without asking once the person has chosen Always send. */
  always = false;

  constructor(
    host: HTMLElement,
    /** Always send, tapped: the person's settings say so from now on. */
    private readonly alwaysSend: () => Promise<void>,
    /** Which errors were raised already on this page. */
    private readonly faults: Faults,
    /** The person is writing: a bug waits until the message box is empty. */
    private readonly drafting: () => boolean,
  ) {
    this.sheet = new Sheet(host, "rp");
    this.sheet.panel.addEventListener("click", (e) => {
      const act = (e.target as Element).closest<HTMLElement>("[data-act]")?.dataset.act;
      if (act) void this.answer(act as Act);
    });
  }

  /** A turn failed with this error, raised once per error. The server kept
   * the failure under the turn when it happened, so sending it posts nothing
   * more: the report is that turn. */
  turn(error: string, turnId: string): void {
    this.broke(error, null, [
      ["The error", error],
      ["The reply that failed", turnId],
      ["The app version", window.BOOTSTRAP.version],
    ]);
  }

  /** The page broke, raised once per error: it names the screen and the
   * newest statement on it, never the person's words, and the turn being
   * drawn if one was. */
  page(fault: Fault, statementId: number | null, turnId?: string): void {
    const report = { ...this.caught(), turn_id: turnId, statement_id: statementId, error: fault.error, frames: fault.frames };
    this.broke(fault.signature, report, [
      ["The error", fault.error],
      ["Where it broke", fault.frames[0] ?? ""],
      ["The screen", report.address],
      ["The newest message", statementId === null ? "" : `Number ${statementId}, not its words`],
      ["The app version", report.release],
    ]);
  }

  /** The server broke on a request, raised once per endpoint. */
  request({ status, method, path, request_id }: RequestFailure): void {
    this.broke(`${method} ${path}`, { ...this.caught(), error: `${status} ${method} ${path}`, request_id }, [
      ["The request", `${method} ${path}`],
      ["The server's answer", String(status)],
      ["The request's id", request_id],
      ["The app version", window.BOOTSTRAP.version],
    ]);
  }

  /** The coach heard the person say this about the app, in the reply now
   * done; it is offered once a sitting. */
  offer(kind: ReportKind, words: string, turnId: string, statementId: number, sitting: number): void {
    if (Number(window.localStorage.getItem(OFFERED)) === sitting) return;
    window.localStorage.setItem(OFFERED, String(sitting));
    const report = { ...this.sent(kind), turn_id: turnId, statement_id: statementId, words };
    if (kind === ReportKind.Bug) report.source = ReportSource.Page;
    this.queue({ report, list: [["", words]], broke: false });
  }

  /** The message box is empty again: a bug that waited on it comes up. */
  resume(): void {
    if (this.at === null) this.flush();
  }

  /** What every report from this page carries. */
  private sent(kind: ReportKind): Report {
    return { kind, status: ReportStatus.Sent, release: window.BOOTSTRAP.version, address: location.pathname };
  }

  /** What a bug this page caught carries. */
  private caught(): Report {
    return { ...this.sent(ReportKind.Bug), source: ReportSource.Page };
  }

  private broke(key: string, report: Report | null, list: List): void {
    if (this.faults.first(key)) this.queue({ report, list, broke: true });
  }

  /** One sheet at a time: the rest wait their turn, and a bug waits while the
   * person is writing. A bug goes with no sheet and no card once the person
   * chose Always send. */
  private queue(raised: Raised): void {
    if (raised.broke && this.always) void this.quietly(raised.report);
    else if (this.at === null && !(raised.broke && this.drafting())) this.raise(raised);
    else this.waiting.push(raised);
  }

  private flush(): void {
    for (const raised of this.waiting.splice(0)) this.queue(raised);
  }

  private raise(raised: Raised): void {
    this.at = raised;
    this.ask(raised);
    dragScroll(this.sheet.panel.querySelector<HTMLElement>(".rp-list")!);
  }

  /** Sent with nothing on screen: one that could not be sent is only logged. */
  private async quietly(report: Report | null): Promise<void> {
    if (!report) return;
    try {
      await api.report(report);
    } catch (error) {
      console.warn(api.whatFailed(error, (words) => words));
    }
  }

  private ask({ report, list, broke }: Raised): void {
    if (broke)
      this.sheet.show(
        `<div class="cf-t">Something went wrong</div>` +
          `<div class="rp-list">${list.map(([label, value]) => row(label, value)).join("")}</div>` +
          `<div class="cf-btns">` +
          button(Act.Send, "Send the report", true) +
          button(Act.Always, "Always send") +
          button(Act.Not, "Don't send", false, true) +
          `<div class="rp-note">Disabled during the beta</div></div>`,
      );
    else
      this.sheet.show(
        `<div class="cf-t">${HEADING[report!.kind]}</div>` +
          `<div class="rp-list"><div class="rp-v">${esc(list[0][1])}</div></div>` +
          `<div class="cf-btns">` +
          button(Act.Send, "Send the report", true) +
          button(Act.Not, "Not feedback") +
          `</div>`,
      );
  }

  private async answer(act: Act): Promise<void> {
    const { report } = this.at!;
    if (act === Act.Ok) return this.next();
    if (act === Act.Not) {
      // turned down, the offer keeps only where it was, never the words
      void this.quietly({ ...report!, status: ReportStatus.Declined, words: undefined });
      return this.next();
    }
    for (const one of this.sheet.panel.querySelectorAll("button")) one.disabled = true;
    if (act === Act.Always) {
      this.always = true;
      await this.alwaysSend();
      await this.quietly(report);
      return this.next();
    }
    await this.send(report);
  }

  /** Sent, the sheet says so in place of what it asked. A report that could
   * not be sent says why, and is not tried again. */
  private async send(report: Report | null): Promise<void> {
    let said: string;
    try {
      if (report) await api.report(report);
      said = `<div class="cf-t">Your report was sent</div>`;
    } catch (error) {
      const why = api.whatFailed(error, (words) => words);
      said = `<div class="cf-t">Your report was not sent</div><p class="cf-p">${esc(why)}</p>`;
    }
    this.sheet.show(`${said}<div class="cf-btns">${button(Act.Ok, "OK", true)}</div>`);
    this.closing = window.setTimeout(() => this.next(), SENT_MS);
  }

  /** On to the next report waiting, or the sheet down. */
  private next(): void {
    window.clearTimeout(this.closing);
    this.at = null;
    this.flush();
    if (this.at === null) this.sheet.lower();
  }
}
