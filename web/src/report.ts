import * as api from "./api";
import { esc } from "./dom";
import { dragScroll } from "./drag";
import type { Faults } from "./faults";
import { Sheet } from "./sheet";
import { ReportKind, type Report } from "./types";

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

/** Something that broke, rather than words the coach heard. */
const broke = (report: Report) => report.error !== undefined;

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
  private at: Report | null = null;
  private waiting: Report[] = [];
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

  /** A turn, the page or the server broke with this error, after these words
   * of the person's; an error of the same key is raised once. */
  bug(error: string, text: string, turnId: string, key = error): void {
    if (!this.faults.first(key)) return;
    this.queue({ kind: ReportKind.Bug, turn_id: turnId, text, error, version: window.BOOTSTRAP.version });
  }

  /** The coach heard the person say this about the app. */
  offer(kind: ReportKind, words: string, turnId: string): void {
    if (this.once(`${turnId}:${words}`)) return;
    this.queue({ kind, turn_id: turnId, text: words });
  }

  private once(key: string): boolean {
    if (this.raised.has(key)) return true;
    this.raised.add(key);
    return false;
  }

  /** One sheet at a time: the rest wait their turn. */
  private queue(report: Report): void {
    if (this.at === null) this.raise(report);
    else this.waiting.push(report);
  }

  private raise(report: Report): void {
    this.at = report;
    if (broke(report) && this.always) return void this.send(report);
    this.ask(report);
    dragScroll(this.sheet.panel.querySelector<HTMLElement>(".rp-list")!);
  }

  private ask(report: Report): void {
    if (broke(report))
      this.sheet.show(
        `<div class="cf-t">Something went wrong</div>` +
          `<div class="rp-list">` +
          row("Your last message", report.text) +
          row("The error", report.error!) +
          row("The app version", report.version!) +
          `</div><div class="cf-btns">` +
          button(Act.Send, "Send the report", true) +
          button(Act.Always, "Always send") +
          button(Act.Not, "Don't send", false, true) +
          `<div class="rp-note">Disabled during the beta</div></div>`,
      );
    else
      this.sheet.show(
        `<div class="cf-t">${HEADING[report.kind]}</div>` +
          `<div class="rp-list"><div class="rp-v">${esc(report.text)}</div></div>` +
          `<div class="cf-btns">` +
          button(Act.Send, "Send the report", true) +
          (this.always ? "" : button(Act.Always, "Always send")) +
          button(Act.Not, "Not feedback") +
          `</div>`,
      );
  }

  private async answer(act: Act): Promise<void> {
    const report = this.at!;
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
    const report = this.waiting.shift();
    if (report === undefined) this.sheet.lower();
    else this.raise(report);
  }
}
