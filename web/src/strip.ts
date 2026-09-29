import { closeX, el, esc, stepBtn } from "./dom";
import { markup } from "./markup";

/** What the strip says and what its two taps do. */
export interface Call {
  title: string;
  body: string | null;
  /** The way in, when there is somewhere to go. */
  open: { label: string; tap(): void } | null;
  dismiss(): void;
}

/** One call to the reader at a time, in a strip above the message box: never
 * in the thread and never over the page (R-0611). Notices, the bug-report card
 * and the auditor's task all come through this one. */
export class Strip {
  private box = el("div", "strip");
  private call: Call | null = null;

  constructor(above: HTMLElement) {
    this.box.hidden = true;
    this.box.setAttribute("role", "status");
    above.before(this.box);
    this.box.addEventListener("click", (e) => {
      const at = e.target as Element;
      if (at.closest("a")) return;
      const hit = at.closest("button");
      // the words fold and unfold in place and do not count the call opened
      if (!hit && at.closest(".strip-m")) this.box.classList.toggle("open");
      if (!hit || !this.call) return;
      const call = this.call;
      this.hide();
      if (hit.matches(".cardx")) call.dismiss();
      else call.open?.tap();
    });
  }

  show(call: Call): void {
    if (call.title !== this.call?.title || call.body !== this.call?.body)
      this.box.classList.remove("open");
    this.call = call;
    this.box.innerHTML =
      `<div class="strip-c"><div class="strip-m">` +
      `<div class="strip-t">${esc(call.title)}</div>` +
      (call.body ? `<div class="strip-s">${markup(call.body)}</div>` : "") +
      `</div>` +
      (call.open ? stepBtn(esc(call.open.label), "", false) : "") +
      closeX() +
      `</div>`;
    this.box.hidden = false;
  }

  hide(): void {
    this.call = null;
    this.box.hidden = true;
  }
}
