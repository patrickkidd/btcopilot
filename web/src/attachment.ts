import { closeX, el, esc } from "./dom";
import { Sheet } from "./sheet";
import { toast } from "./toast";

/** What the picker offers; the server says what it takes and refuses the rest
 * in its own words. */
export const KINDS =
  ".pdf,.jpg,.jpeg,.png,.heic,.heif,.txt,.text,.md,.markdown,.fd,.zip,.pickle,application/pdf,image/jpeg,image/png,image/heic,image/heif,text/plain,text/markdown,application/zip";

/** A desktop Family Diagram file is a folder, and the diagram.pickle in it is
 * all the app needs: that one file is sent, under the folder's name (R-0882). */
export const PICKLE = "diagram.pickle";
export const NO_DIAGRAM = "That folder is not a Family Diagram file.";

/** The folder's diagram.pickle as the file the message carries; null when the
 * folder holds none. */
export const fromFolder = (folder: string, files: File[]): File | null => {
  const pickle = files.find((one) => one.name === PICKLE);
  return pickle ? new File([pickle], folder) : null;
};

/** What a folder picker gave: the folder's own diagram.pickle under the
 * folder's name, or, from a browser that let one file be picked instead, that
 * file as it is. */
export const fromPicked = (files: File[]): File | null => {
  const folder = files[0]?.webkitRelativePath.split("/")[0];
  if (!folder) return files[0] ?? null;
  return fromFolder(
    folder,
    files.filter((one) => one.webkitRelativePath === `${folder}/${PICKLE}`),
  );
};

export enum Pick {
  File = "file",
  Folder = "folder",
}

/** What the paperclip asks: a file the coach reads, or a desktop Family
 * Diagram file, which is a folder (R-0882). */
export const CHOICE =
  `${closeX()}<div class="cf-t">What are you attaching?</div>` +
  `<div class="cf-btns">` +
  `<button class="cf-go" type="button" data-act="${Pick.File}">A photo, PDF or text file</button>` +
  `<button class="cf-no" type="button" data-act="${Pick.Folder}">A Family Diagram file</button>` +
  `</div>`;

/** Every file directly in a folder dropped on the chat; a folder is read in
 * batches until one comes back empty. */
async function inside(folder: FileSystemDirectoryEntry): Promise<File[]> {
  const reader = folder.createReader();
  const entries: FileSystemEntry[] = [];
  for (;;) {
    const batch = await new Promise<FileSystemEntry[]>((done, fail) => reader.readEntries(done, fail));
    if (!batch.length) break;
    entries.push(...batch);
  }
  return Promise.all(
    entries
      .filter((one): one is FileSystemFileEntry => one.isFile)
      .map((one) => new Promise<File>((done, fail) => one.file(done, fail))),
  );
}

/** The file a message carries: its name as a chip, dimmed while the server
 * reads it, and once read a tap shows what the coach was given. One its turn
 * could not take stays dimmed, no longer said to be reading (R-0830). The file
 * itself is never kept or shown again. */
export const fileChip = (name: string, text: string | null = null, untaken = false): string =>
  `<div class="file"><button class="chip file${text !== null ? "" : untaken ? " untaken" : " reading"}" type="button"` +
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
  private folderInput = document.createElement("input");
  private slot = el("div", "attached");
  private sheet: Sheet;
  private texts = new WeakMap<HTMLElement, string>();

  constructor(button: HTMLElement, field: HTMLElement, screen: HTMLElement, list: HTMLElement) {
    this.input.type = this.folderInput.type = "file";
    this.input.accept = KINDS;
    this.folderInput.webkitdirectory = true;
    this.input.hidden = this.folderInput.hidden = true;
    this.input.setAttribute("aria-label", "Attach a file");
    this.folderInput.setAttribute("aria-label", "Attach a Family Diagram file");
    button.after(this.input, this.folderInput);
    button.addEventListener("click", () => this.sheet.show(CHOICE));
    this.input.addEventListener("change", () => this.input.files?.[0] && this.pick(this.input.files[0]));
    this.folderInput.addEventListener("change", () => {
      const files = [...(this.folderInput.files ?? [])];
      if (!files.length) return;
      const file = fromPicked(files);
      if (file) this.pick(file);
      else toast(NO_DIAGRAM, true);
    });
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
      // read now: the drop's items are gone once the event is over
      const entry = e.dataTransfer!.items[0]?.webkitGetAsEntry();
      if (entry?.isDirectory) return void this.folder(entry as FileSystemDirectoryEntry);
      const file = e.dataTransfer!.files[0];
      if (file) this.pick(file);
    });
    this.sheet = new Sheet(screen, "fl");
    screen.addEventListener("click", (e) => {
      const target = e.target as Element;
      const act = target.closest<HTMLElement>(".fs-sheet.fl [data-act]")?.dataset.act;
      if (act || target.closest(".fs-sheet.fl .cardx, .fs-scrim.fl")) this.sheet.lower();
      if (!act) return;
      // opened in the tap itself, which a browser asks of a file picker
      const picker = act === Pick.Folder ? this.folderInput : this.input;
      picker.value = "";
      picker.click();
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

  private async folder(entry: FileSystemDirectoryEntry): Promise<void> {
    const file = fromFolder(entry.name, await inside(entry));
    if (file) this.pick(file);
    else toast(NO_DIAGRAM, true);
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
  show(bubble: HTMLElement, name: string, text: string | null = null, untaken = false): void {
    bubble.querySelector(":scope > .file")?.remove();
    bubble.insertAdjacentHTML("afterbegin", fileChip(name, text, untaken));
    if (text !== null) this.texts.set(bubble.querySelector<HTMLElement>(":scope > .file > .chip")!, text);
  }

  /** The chips still reading once a turn has failed: none is read any more. */
  untaken(thread: HTMLElement): void {
    for (const chip of thread.querySelectorAll(".bub > .file > .chip.reading"))
      chip.classList.replace("reading", "untaken");
  }
}
