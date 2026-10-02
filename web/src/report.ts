import * as api from "./api";
import { esc } from "./dom";
import { dragScroll } from "./drag";
import { Sheet } from "./sheet";
import { ReportKind, ReportStatus, type Report } from "./types";

/** What the person sends from the app (R-0056), each offered by the coach
 * from the conversation: a bug when the app or the coach behaved wrongly as
 * they experienced it, and feedback when they wish for or dislike something
 * in it. Each is a sheet over the thread, which it never touches. Sent, the
 * sheet turns into a card saying so, which goes on OK or after ten seconds.
 * An error in the code is never a sheet: the page's and the server's errors
 * go to Grafana. */

/** How long the card saying the report was sent stays up. */
export const SENT_MS = 10_000;
/** The words the coach offered to send in the person's latest sitting, sent
 * or declined, trimmed and case-folded: the same words are never offered
 * twice a sitting, even across a reload. */
const OFFERED = "reports.offered";
/** The beta: a bug is sent or always sent, never turned down, and its Don't
 * send is drawn disabled (R-0615). The server's switch, which also refuses a
 * bug turned down. */
const BETA = window.BOOTSTRAP.beta;

enum Act {
  Send = "send",
  Always = "always",
  Not = "not",
  Ok = "ok",
}

const button = (act: Act, words: string, primary = false, disabled = false) =>
  `<button class="${primary ? "cf-go" : "cf-no"}" type="button" data-act="${act}"` +
  `${disabled ? ' disabled aria-describedby="rp-why"' : ""}>${words}</button>`;

const HEADING = {
  [ReportKind.Bug]: "Send this as a bug report?",
  [ReportKind.Feedback]: "Send this as feedback?",
};

const DECLINE = {
  [ReportKind.Bug]: "Don't send",
  [ReportKind.Feedback]: "Not feedback",
};

export class Reports {
  private sheet: Sheet;
  private at: Report | null = null;
  private waiting: Report[] = [];
  private closing = 0;
  /** A bug goes without asking once the person has chosen Always send. */
  always = false;

  constructor(
    host: HTMLElement,
    /** Always send, tapped: the person's settings say so from now on. */
    private readonly alwaysSend: () => Promise<void>,
  ) {
    this.sheet = new Sheet(host, "rp");
    this.sheet.panel.addEventListener("click", (e) => {
      const act = (e.target as Element).closest<HTMLElement>("[data-act]")?.dataset.act;
      if (act) void this.answer(act as Act);
    });
  }

  /** The coach offered to send these words, in the reply now done; words
   * already offered in this sitting are not offered again. */
  offer(kind: ReportKind, words: string, turnId: string, statementId: number, sitting: number): void {
    const said = words.trim().toLowerCase();
    const kept = JSON.parse(window.localStorage.getItem(OFFERED) ?? "null") as { sitting: number; words: string[] } | null;
    const offered = kept?.sitting === sitting ? kept.words : [];
    if (offered.includes(said)) return;
    window.localStorage.setItem(OFFERED, JSON.stringify({ sitting, words: [...offered, said] }));
    this.queue({
      kind,
      status: ReportStatus.Sent,
      release: window.BOOTSTRAP.version,
      address: location.pathname,
      turn_id: turnId,
      statement_id: statementId,
      words,
    });
  }

  /** One sheet at a time: the rest wait their turn. A bug goes with no sheet
   * and no card once the person chose Always send. */
  private queue(report: Report): void {
    if (report.kind === ReportKind.Bug && this.always) void this.quietly(report);
    else if (this.at === null) this.raise(report);
    else this.waiting.push(report);
  }

  private raise(report: Report): void {
    this.at = report;
    const forced = BETA && report.kind === ReportKind.Bug;
    this.sheet.show(
      `<div class="cf-t">${HEADING[report.kind]}</div>` +
        `<div class="rp-list"><div class="rp-v">${esc(report.words!)}</div></div>` +
        `<div class="cf-btns">` +
        button(Act.Send, "Send the report", true) +
        (report.kind === ReportKind.Bug ? button(Act.Always, "Always send") : "") +
        button(Act.Not, DECLINE[report.kind], false, forced) +
        (forced ? `<p class="rp-why" id="rp-why">Disabled during the beta</p>` : "") +
        `</div>`,
    );
    dragScroll(this.sheet.panel.querySelector<HTMLElement>(".rp-list")!);
  }

  /** Sent with nothing on screen: one that could not be sent is only logged. */
  private async quietly(report: Report): Promise<void> {
    try {
      await api.report(report);
    } catch (error) {
      console.warn(api.whatFailed(error, (words) => words));
    }
  }

  private async answer(act: Act): Promise<void> {
    const report = this.at!;
    if (act === Act.Ok) return this.next();
    if (act === Act.Not) {
      // turned down, the offer keeps only where it was, never the words
      void this.quietly({ ...report, status: ReportStatus.Declined, words: undefined });
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

  /** On to the next report waiting, or the sheet down. */
  private next(): void {
    window.clearTimeout(this.closing);
    this.at = null;
    for (const report of this.waiting.splice(0)) this.queue(report);
    if (this.at === null) this.sheet.lower();
  }
}
