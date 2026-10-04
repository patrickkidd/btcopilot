import { el } from "./dom";
import type { Opened, Part, View } from "./store";

/** The case report: the open record laid out as the cards a presenter walks a
 * seminar through, drawn from the store like every other screen of the open
 * diagram (doc/UI_STANDARDS.md). Empty until its cards are built. */
export class CaseReport implements View {
  readonly screen = el("div", "screen");
  private readonly body = el("div", "fs-body");

  constructor() {
    this.screen.id = "case-screen";
    this.screen.hidden = true;
    this.screen.append(this.body);
  }

  reset(): void {
    this.body.replaceChildren();
  }

  draw(_opened: Opened, _parts: Part[]): void {}
}
