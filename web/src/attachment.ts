import { closeX, el, esc } from "./dom";
import { Sheet } from "./sheet";

/** What the picker offers; the server says what it takes and refuses the rest
 * in its own words. */
export const KINDS =
  ".pdf,.jpg,.jpeg,.png,.heic,.heif,.txt,.text,.md,.markdown,application/pdf,image/jpeg,image/png,image/heic,image/heif,text/plain,text/markdown";

/** The file a message carries: its name as a chip, dimmed while the server
 * reads it, and once read a tap shows what the coach was given. The file
 * itself is never kept or shown again. */
export const fileChip = (name: string, text: string | null = null): string =>
  `<div class="file"><button class="chip file${text === null ? " reading" : ""}" type="button"` +
  `${text === null ? " disabled" : ""}>${esc(name)}</button></div>`;

/** What the coach read from a file, in the sheet a tap on its chip raises. */
export const readSheet = (name: string, text: string): string =>
  `${closeX()}<div class="cf-t">${esc(name)}</div><p class="cf-p">What the coach read</p>` +
  `<div class="fl-text">${esc(text)}</div>`;

/** One file per message: a second pick takes the first one's place. */
export class Picked {
  file: File | null = null;

  pick(file: File): void {
    this.file = file;
  }

  /** The file goes with the message, and the box is left without one. */
  take(): File | null {
    const file = this.file;
    this.file = null;
    return file;
  }
}

/** The paperclip in the chat bar, a file dropped on the chat on a computer,
 * the picked file's chip in the box, and the sheet of what the coach read. */
export class Attachment {
  readonly picked = new Picked();
  private input = document.createElement("input");
  private slot = el("div", "attached");
  private sheet: Sheet;
  private texts = new WeakMap<HTMLElement, string>();

  constructor(button: HTMLElement, field: HTMLElement, screen: HTMLElement, list: HTMLElement) {
    this.input.type = "file";
    this.input.accept = KINDS;
    this.input.hidden = true;
    this.input.setAttribute("aria-label", "Attach a file");
    button.after(this.input);
    button.addEventListener("click", () => {
      this.input.value = "";
      this.input.click();
    });
    this.input.addEventListener("change", () => this.input.files?.[0] && this.pick(this.input.files[0]));
    this.slot.hidden = true;
    field.prepend(this.slot);
    this.slot.addEventListener("click", (e) => {
      if ((e.target as Element).closest(".cardx")) this.clear();
    });
    const files = (e: DragEvent) => !!e.dataTransfer?.types.includes("Files");
    screen.addEventListener("dragover", (e) => {
      if (!files(e)) return;
      e.preventDefault();
      screen.classList.add("dropping");
    });
    screen.addEventListener("dragleave", (e) => {
      if (!screen.contains(e.relatedTarget as Node | null)) screen.classList.remove("dropping");
    });
    screen.addEventListener("drop", (e) => {
      if (!files(e)) return;
      e.preventDefault();
      screen.classList.remove("dropping");
      const file = e.dataTransfer!.files[0];
      if (file) this.pick(file);
    });
    this.sheet = new Sheet(screen, "fl");
    screen.addEventListener("click", (e) => {
      if ((e.target as Element).closest(".fs-sheet.fl .cardx, .fs-scrim.fl")) this.sheet.lower();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.sheet.up) this.sheet.lower();
    });
    list.addEventListener("click", (e) => {
      const chip = (e.target as Element).closest<HTMLElement>(".bub .chip.file");
      const text = chip && this.texts.get(chip);
      if (text != null) this.sheet.show(readSheet(chip!.textContent!, text));
    });
  }

  pick(file: File): void {
    this.picked.pick(file);
    this.slot.innerHTML = `<span class="chip file">${esc(file.name)}</span>${closeX()}`;
    this.slot.hidden = false;
  }

  clear(): void {
    this.picked.take();
    this.slot.hidden = true;
    this.slot.innerHTML = "";
  }

  /** The file the message goes with; the box is left without one. */
  take(): File | null {
    const file = this.picked.file;
    this.clear();
    return file;
  }

  /** A message's file chip, put on its bubble or filled in once read. */
  show(bubble: HTMLElement, name: string, text: string | null = null): void {
    bubble.querySelector(":scope > .file")?.remove();
    bubble.insertAdjacentHTML("afterbegin", fileChip(name, text));
    if (text !== null) this.texts.set(bubble.querySelector<HTMLElement>(":scope > .file > .chip")!, text);
  }
}
