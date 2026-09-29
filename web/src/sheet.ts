import { el } from "./dom";

/** How long the sheet takes to go down, matched to the sessions sheet's own
 * motion in the stylesheet. */
const LOWER_MS = 280;

/** A modal sheet up from the bottom, drawn and moved as the sessions sheet
 * is. While it is up the scrim takes every tap and the rest of the app is
 * inert, so nothing behind it can be reached until the sheet is answered. */
export class Sheet {
  private scrim = el("div", "fs-scrim");
  readonly panel = el("div", "fs-sheet cf-sheet");
  private hiding = 0;
  /** What this sheet made inert, and gives back when it goes down. */
  private stilled: HTMLElement[] = [];

  constructor(private readonly host: HTMLElement, className: string) {
    this.scrim.classList.add(className);
    this.panel.classList.add(className);
    this.panel.setAttribute("role", "dialog");
    this.panel.setAttribute("aria-modal", "true");
    this.scrim.hidden = this.panel.hidden = true;
    host.append(this.scrim, this.panel);
  }

  get up(): boolean {
    return this.panel.classList.contains("in");
  }

  /** Up with this in it, or, already up, this in its place without moving. */
  show(html: string): void {
    this.panel.innerHTML = html;
    if (this.up) return;
    window.clearTimeout(this.hiding);
    this.stilled = [...this.host.children].filter(
      (one): one is HTMLElement =>
        one instanceof HTMLElement && one !== this.scrim && one !== this.panel && !one.inert,
    );
    for (const one of this.stilled) one.inert = true;
    this.scrim.hidden = this.panel.hidden = false;
    void this.panel.offsetWidth;
    this.scrim.classList.add("in");
    this.panel.classList.add("in");
    this.panel.querySelector<HTMLElement>("button:not([disabled])")?.focus({ preventScroll: true });
  }

  lower(): void {
    this.scrim.classList.remove("in");
    this.panel.classList.remove("in");
    for (const one of this.stilled) one.inert = false;
    this.stilled = [];
    this.hiding = window.setTimeout(() => {
      this.scrim.hidden = this.panel.hidden = true;
    }, LOWER_MS);
  }
}
