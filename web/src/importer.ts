import * as api from "./api";
import { closeX, el, esc } from "./dom";
import { OWN_FAMILY } from "./pro";
import { Sheet } from "./sheet";
import { Part, store } from "./store";
import { toast } from "./toast";
import type { Imported, Person } from "./types";

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
  Own = "own",
  NotOwn = "not-own",
  Yes = "yes",
  NotNow = "not-now",
}

/** From how many people on the list a name can be typed to find one. */
const FIND_FROM = 8;

/** What came in, on top of every step of the sheet; only the last step has
 * a cross, since the diagram must end with one primary person (R-0930). */
const head = ({ people, events, left_out }: Imported["imported"], closable = false): string =>
  `${closable ? closeX() : ""}<div class="cf-t">Your file is in: ${people} people and ${events} events.</div>` +
  (left_out > 0 ? `<p class="cf-p">${left_out} could not be brought in; the coach will ask about them.</p>` : "");

const buttons = (yes: [Answer, string], no: [Answer, string]): string =>
  `<div class="cf-btns">` +
  `<button class="cf-go" type="button" data-act="${yes[0]}">${yes[1]}</button>` +
  `<button class="cf-no" type="button" data-act="${no[0]}">${no[1]}</button>` +
  `</div>`;

/** First, as on a new diagram: whose family this is (R-0899). */
export const ownStep = (imported: Imported["imported"]): string =>
  head(imported) + `<p class="cf-p">${esc(OWN_FAMILY)}</p>` + buttons([Answer.Own, "Yes"], [Answer.NotOwn, "No"]);

const fullName = (person: Person) => [person.name, person.last_name].filter(Boolean).join(" ");

/** The people to pick from: the ones the file marks primary first, in its
 * order, then everyone else as the diagram lists them. */
export const chooseFrom = (people: Person[], primary: number[]): Person[] => [
  ...primary.map((id) => people.find((one) => one.id === id)!),
  ...people.filter((one) => !primary.includes(one.id)),
];

/** Who picks a person: the user saying which one they are, or saying who the
 * case is about. */
export enum Pick {
  Me = "me",
  About = "about",
}

const PICK_ASKS: Record<Pick, string> = {
  [Pick.Me]: "Which person are you?",
  [Pick.About]: "Who is this case about?",
};

/** Then the person: which one the user is, in their own family, or who the
 * case is about, in someone else's; the one person the file marks primary
 * comes picked, ready to go on with. Either way the diagram ends with one
 * primary person, which the Family view is drawn around (R-0930). */
export const pickStep = (imported: Imported["imported"], people: Person[], pick: Pick): string => {
  const ready = imported.primary.length === 1 ? people.find((one) => one.id === imported.primary[0]) : undefined;
  return (
  head(imported) +
  `<p class="cf-p">${PICK_ASKS[pick]}</p>` +
  (people.length >= FIND_FROM
    ? `<div class="sn-srch fdc-find"><input type="search" placeholder="Find a name" aria-label="Find a name"></div>`
    : "") +
  `<div class="sn-grp fdc-who">` +
  people
    .map(
      (one) =>
        `<button class="sn-row push${one === ready ? " cur" : ""}" type="button" data-${pick}="${one.id}" ` +
        `data-name="${esc(fullName(one).toLowerCase())}"><span class="sn-t">${esc(fullName(one))}</span></button>`,
    )
    .join("") +
  `</div>` +
  (ready
    ? `<div class="cf-btns"><button class="cf-go" type="button" data-${pick}="${ready.id}">Go on with ${esc(fullName(ready))}</button></div>`
    : "")
  );
};

/** Last: whether the coach should add the codes the file has none of. */
export const codesStep = (imported: Imported["imported"]): string =>
  head(imported, true) +
  `<p class="cf-p">Should the coach go through the events and add codes where the file has none?</p>` +
  buttons([Answer.Yes, "Yes"], [Answer.NotNow, "Not now"]);

/** The new diagram, or the server's own sentence for a file it refuses. */
export async function bring(file: File): Promise<Imported | string> {
  try {
    return await api.importDiagram(file, stem(file.name));
  } catch (error) {
    return api.refusedWith(error, CANNOT_BRING);
  }
}

/** The Diagrams page's way to make a new diagram from a desktop Family
 * Diagram file, for everyone, beside the new diagram row: its row picks the .fd
 * folder, the link under it a .zip of it for a phone, and a folder dropped on
 * the page on a computer is taken too. The new diagram opens, and the person
 * is asked once whether the coach should add codes (R-0899). */
export class Importer {
  private sheet: Sheet;
  /** One file at a time: a pick while one is out is not taken. */
  private sending = false;
  /** The diagram the sheet is about, while it is up. */
  private made: Imported | null = null;
  /** Whether the step showing may be put away unanswered. */
  private closable = false;

  constructor(
    host: HTMLElement,
    private opened: (made: Imported) => Promise<void>,
    private say: (statement: string) => void,
  ) {
    this.sheet = new Sheet(host, "fdc");
    host.addEventListener("click", (e) => {
      const target = e.target as Element;
      const picked = target.closest<HTMLElement>(`.fs-sheet.fdc :is([data-${Pick.Me}], [data-${Pick.About}])`);
      if (picked) return void this.choose(picked.dataset.me ? Pick.Me : Pick.About, Number(picked.dataset.me ?? picked.dataset.about));
      const act = target.closest<HTMLElement>(".fs-sheet.fdc [data-act]")?.dataset.act as Answer | undefined;
      if (act || target.closest(".fs-sheet.fdc .cardx, .fs-scrim.fdc")) this.answer(act);
    });
    host.addEventListener("input", (e) => {
      const field = (e.target as Element).closest<HTMLInputElement>(".fs-sheet.fdc .fdc-find input");
      if (!field) return;
      const query = field.value.trim().toLowerCase();
      for (const row of host.querySelectorAll<HTMLElement>(".fs-sheet.fdc .fdc-who [data-name]"))
        row.hidden = !!query && !row.dataset.name!.includes(query);
    });
  }

  /** An answer, or a cross or a tap beside the sheet, which only the codes
   * question takes, as Not now. */
  answer(act?: Answer): void {
    if (!act && !this.closable) return;
    const imported = this.made!.imported;
    const people = () => chooseFrom(store.current().record.people, imported.primary);
    if (act === Answer.Own) return this.sheet.show(pickStep(imported, people(), Pick.Me));
    if (act === Answer.NotOwn) return this.sheet.show(pickStep(imported, people(), Pick.About));
    this.sheet.lower();
    this.made = null;
    this.closable = false;
    if (act === Answer.Yes) this.say(ADD_CODES);
  }

  /** The person picked: who the user is, so the coach speaks to them as that
   * person from here on, which also makes them the primary person; or who the
   * case is about, made the primary person. The record is read again so the
   * Family view is drawn around them. */
  async choose(pick: Pick, personId: number): Promise<void> {
    const made = this.made!;
    try {
      if (pick === Pick.Me) store.update({ diagram: await api.setPerson(made.id, personId) });
      else await api.savePerson(personId, { primary: true }, made.id);
    } catch (error) {
      return toast(api.refusedWith(error, "Could not save who this diagram is about."), true);
    }
    await store.refresh(Part.Record);
    this.closable = true;
    this.sheet.show(codesStep(made.imported));
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
    this.made = made;
    this.sheet.show(ownStep(made.imported));
  }

  row(page: HTMLElement): HTMLElement {
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
