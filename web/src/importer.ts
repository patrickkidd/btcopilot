import * as api from "./api";
import { closeX, el } from "./dom";
import { PRO } from "./pro";
import { Sheet } from "./sheet";
import { toast } from "./toast";
import type { Imported } from "./types";

/** A desktop Family Diagram file is a folder, and the diagram.pickle in it is
 * all the app needs: that one file is sent, under the folder's name (R-0899). */
export const PICKLE = "diagram.pickle";
/** The most the server takes. */
export const MAX_BYTES = 20 * 1024 * 1024;
export const NO_DIAGRAM = "That folder is not a Family Diagram file.";
export const TOO_BIG = "That file is over 20 MB, more than the app takes.";
export const CANNOT_BRING = "Could not bring in the file.";

/** The diagram's name: the .fd folder's or the zip's, without the ending. */
export const stem = (name: string) => name.replace(/\.zip$/i, "").replace(/\.fd$/i, "");

/** The folder's diagram.pickle under the folder's name; null when the folder
 * holds none. */
export const fromFolder = (folder: string, files: File[]): File | null => {
  const pickle = files.find((one) => one.name === PICKLE);
  return pickle ? new File([pickle], folder) : null;
};

/** What a picker gave: a picked folder's own diagram.pickle under the folder's
 * name, or, from a browser that let one file be picked instead, that file as
 * it is. */
export const fromPicked = (files: File[]): File | null => {
  const folder = files[0]?.webkitRelativePath.split("/")[0];
  if (!folder) return files[0] ?? null;
  return fromFolder(
    folder,
    files.filter((one) => one.webkitRelativePath === `${folder}/${PICKLE}`),
  );
};

/** Every file directly in a dropped folder; a folder is read in batches until
 * one comes back empty. */
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

/** What was dropped: a folder's diagram.pickle, or a file as it is. The drop's
 * items are read at once, since they are gone once the event is over. */
export function fromDrop(data: DataTransfer): Promise<File | null> {
  const entry = data.items[0]?.webkitGetAsEntry();
  if (entry?.isDirectory)
    return inside(entry as FileSystemDirectoryEntry).then((files) => fromFolder(entry.name, files));
  return Promise.resolve(data.files[0] ?? null);
}

/** Why a file is not sent at all, or null when it may be. */
export const refusal = (file: File | null): string | null =>
  !file ? NO_DIAGRAM : file.size > MAX_BYTES ? TOO_BIG : null;

/** What the coach is sent when the person says yes to codes for the events
 * the file left without (R-0899). */
export const ADD_CODES = "Go through the events in this diagram and add codes where the file left them blank.";

export enum Answer {
  Yes = "yes",
  NotNow = "not-now",
}

/** Asked once, as the new diagram opens: what came in, and whether the coach
 * should add the codes the file has none of. */
export const arrived = ({ people, events, left_out }: Imported["imported"]): string =>
  `${closeX()}<div class="cf-t">Your file is in: ${people} people and ${events} events.</div>` +
  (left_out > 0 ? `<p class="cf-p">${left_out} could not be brought in; the coach will ask about them.</p>` : "") +
  `<p class="cf-p">Should the coach go through the events and add codes where the file has none?</p>` +
  `<div class="cf-btns">` +
  `<button class="cf-go" type="button" data-act="${Answer.Yes}">Yes</button>` +
  `<button class="cf-no" type="button" data-act="${Answer.NotNow}">Not now</button>` +
  `</div>`;

/** The new diagram, or the server's own sentence for a file it refuses. */
export async function bring(file: File): Promise<Imported | string> {
  try {
    return await api.importDiagram(file, stem(file.name));
  } catch (error) {
    return api.refusedWith(error, CANNOT_BRING);
  }
}

/** The Diagrams page's way to make a new diagram from a desktop Family
 * Diagram file, under the same licence as a new case: its row picks the .fd
 * folder, the link under it a .zip of it for a phone, and a folder dropped on
 * the page on a computer is taken too. The new diagram opens, and the person
 * is asked once whether the coach should add codes (R-0899). */
export class Importer {
  private sheet: Sheet;
  /** One file at a time: a pick while one is out is not taken. */
  private sending = false;

  constructor(
    host: HTMLElement,
    private opened: (made: Imported) => Promise<void>,
    private say: (statement: string) => void,
  ) {
    this.sheet = new Sheet(host, "fdc");
    host.addEventListener("click", (e) => {
      const target = e.target as Element;
      const act = target.closest<HTMLElement>(".fs-sheet.fdc [data-act]")?.dataset.act as Answer | undefined;
      if (act || target.closest(".fs-sheet.fdc .cardx, .fs-scrim.fdc")) this.answer(act);
    });
  }

  answer(act?: Answer): void {
    this.sheet.lower();
    if (act === Answer.Yes) this.say(ADD_CODES);
  }

  private pick(file: File | null): void {
    if (this.sending) return;
    const refused = refusal(file);
    if (refused) return toast(refused, true);
    void this.send(file!);
  }

  async send(file: File): Promise<void> {
    if (this.sending) return;
    this.sending = true;
    const made = await bring(file).finally(() => (this.sending = false));
    if (typeof made === "string") return toast(made, true);
    await this.opened(made);
    this.sheet.show(arrived(made.imported));
  }

  row(page: HTMLElement): HTMLElement | null {
    if (!PRO) return null;
    const row = el("div", "sn-row push");
    const sub = el("div", "sn-s");
    const zip = el("button", "sn-alt", "or a .zip of it");
    zip.type = "button";
    sub.append(zip);
    const main = el("div", "sn-m");
    main.append(el("div", "sn-t", "Import a Family Diagram file"), sub);
    const folder = picker();
    const zipped = picker(".zip,application/zip");
    folder.setAttribute("aria-label", "Pick a Family Diagram file");
    zipped.setAttribute("aria-label", "Pick a .zip of a Family Diagram file");
    row.append(main, el("div", "sn-chev", "\u203a"), folder, zipped);

    row.addEventListener("click", (e) => {
      if (this.sending || (e.target as Element).closest("input")) return;
      const input = (e.target as Element).closest(".sn-alt") ? zipped : folder;
      input.value = "";
      input.click();
    });
    for (const input of [folder, zipped])
      input.addEventListener("change", () => {
        const files = [...(input.files ?? [])];
        if (files.length) this.pick(fromPicked(files));
      });

    const files = (e: DragEvent) => !!e.dataTransfer?.types.includes("Files");
    page.addEventListener("dragover", (e) => {
      if (!files(e)) return;
      e.preventDefault();
      page.classList.add("dropping");
    });
    page.addEventListener("dragleave", (e) => {
      if (!page.contains(e.relatedTarget as Node | null)) page.classList.remove("dropping");
    });
    page.addEventListener("drop", (e) => {
      if (!files(e)) return;
      e.preventDefault();
      page.classList.remove("dropping");
      void fromDrop(e.dataTransfer!).then((file) => this.pick(file));
    });
    return row;
  }
}

function picker(accept?: string): HTMLInputElement {
  const input = document.createElement("input");
  input.type = "file";
  input.hidden = true;
  if (accept) input.accept = accept;
  else input.webkitdirectory = true;
  return input;
}
