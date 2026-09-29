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
  report: Report;
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
  /** Offers already raised on this page, never raised again. */
  private raised = new Set<string>();
  private closing = 0;
  /** A bug goes without asking once the person has chosen Always send. */
  always = false;

  constructor(
    host: HTMLElement,
    /** Always send, tapped: the person's settings say so from now on. */
    private readonly alwaysSend: () => Promise<void>,
    /** Which errors were raised already on this page. */
    private readonly faults: Faults,
  ) {
    this.sheet = new Sheet(host, "rp");
    this.sheet.panel.addEventListener("click", (e) => {
      const act = (e.target as Element).closest<HTMLElement>("[data-act]")?.dataset.act;
      if (act) void this.answer(act as Act);
    });
  }

  /** A turn broke with this error; the same error is raised once. */
  bug(error: string, turnId: string): void {
    this.broke(error, { ...this.caught(), turn_id: turnId, error }, [
      ["The error", error],
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

  /** The coach heard the person say this about the app. */
  offer(kind: ReportKind, words: string, turnId: string): void {
    if (this.once(`${turnId}:${words}`)) return;
    const report = { ...this.sent(kind), turn_id: turnId, words };
    if (kind === ReportKind.Bug) report.source = ReportSource.Page;
    this.queue({ report, list: [["", words]], broke: false });
  }

  /** What every report from this page carries. */
  private sent(kind: ReportKind): Report {
    return { kind, status: ReportStatus.Sent, release: window.BOOTSTRAP.version, address: location.pathname };
  }

  /** What a bug this page caught carries. */
  private caught(): Report {
    return { ...this.sent(ReportKind.Bug), source: ReportSource.Page };
  }

  private broke(key: string, report: Report, list: List): void {
    if (this.faults.first(key)) this.queue({ report, list, broke: true });
  }

  private once(key: string): boolean {
    if (this.raised.has(key)) return true;
    this.raised.add(key);
    return false;
  }

  /** One sheet at a time: the rest wait their turn. */
  private queue(raised: Raised): void {
    if (this.at === null) this.raise(raised);
    else this.waiting.push(raised);
  }

  private raise(raised: Raised): void {
    this.at = raised;
    if (raised.broke && this.always) return void this.send(raised.report);
    this.ask(raised);
    dragScroll(this.sheet.panel.querySelector<HTMLElement>(".rp-list")!);
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
        `<div class="cf-t">${HEADING[report.kind]}</div>` +
          `<div class="rp-list"><div class="rp-v">${esc(list[0][1])}</div></div>` +
          `<div class="cf-btns">` +
          button(Act.Send, "Send the report", true) +
          (this.always ? "" : button(Act.Always, "Always send")) +
          button(Act.Not, "Not feedback") +
          `</div>`,
      );
  }

  private async answer(act: Act): Promise<void> {
    const { report } = this.at!;
    if (act === Act.Ok || act === Act.Not) return this.next();
    for (const one of this.sheet.panel.querySelectorAll("button")) one.disabled = true;
    if (act === Act.Always) {
      this.always = true;
      await this.alwaysSend();
    }
    await this.send(report);
  }

  /** Sent, the sheet says so in place of what it asked. A report that could
   * not be sent says why, and is not tried again. */
  private async send(report: Report): Promise<void> {
    let said: string;
    try {
      await api.report(report);
      said = `<div class="cf-t">Your report was sent</div>`;
    } catch (error) {
      const why = api.whatFailed(error, (words) => words);
      said = `<div class="cf-t">Your report was not sent</div><p class="cf-p">${esc(why)}</p>`;
    }
    this.sheet.show(`${said}<div class="cf-btns">${button(Act.Ok, "OK", true)}</div>`);
    this.closing = window.setTimeout(() => this.next(), SENT_MS);
  }

  /** The sheet down, or on to the next report waiting. */
  private next(): void {
    window.clearTimeout(this.closing);
    this.at = null;
    const raised = this.waiting.shift();
    if (raised === undefined) this.sheet.lower();
    else this.raise(raised);
  }
}
