import type { Opened, Part, View } from "./store";

/** The case report: the open record laid out as the cards a presenter walks a
 * seminar through, drawn from the store like every other screen of the open
 * diagram (doc/UI_STANDARDS.md). Empty until its cards are built. */
export class CaseReport implements View {
  constructor(private readonly host: HTMLElement) {}

  reset(): void {
    this.host.replaceChildren();
  }

  draw(_opened: Opened, _parts: Part[]): void {}
}
