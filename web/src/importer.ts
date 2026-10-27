import * as api from "./api";
import { closeX, el, esc } from "./dom";
import { OWN_FAMILY } from "./pro";
import { Sheet } from "./sheet";
import { Part, store } from "./store";
import { clearToasts, toast } from "./toast";
import type { Imported, Person } from "./types";

/** A desktop Family Diagram file is a folder, and the diagram.pickle in it is
 * all the app needs: that one file is sent, under the folder's name (R-0899). */
export const PICKLE = "diagram.pickle";
/** The most the server takes. */
export const MAX_BYTES = 20 * 1024 * 1024;
export const NO_DIAGRAM = "That folder is not a Family Diagram file.";
/** What the row's own picker offers; the server tells a file by its bytes. */
export const FILE_KINDS = ".fd,.zip";
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

export const ZIP_FIRST = "Zip the .fd folder first, or pick the folder.";
export const UNREAD = "Could not read that folder.";
export const STILL_SENDING = "Still bringing in the last file.";

/** What was dropped: a folder's diagram.pickle, a file as it is, or why
 * neither can be sent. The drop's items are read before anything waits, since
 * they are gone once the event is over. A desktop file is a macOS package: a
 * browser may hand it over as a folder, as a file zipped on the way, or as a
 * file of no bytes the page cannot open, which `pick` turns away. */
export async function fromDrop(data: DataTransfer): Promise<File | string> {
  const entry = data.items[0]?.webkitGetAsEntry() ?? null;
  const file = data.files[0] ?? null;
  if (entry?.isDirectory) {
    try {
      return fromFolder(entry.name, await inside(entry as FileSystemDirectoryEntry)) ?? NO_DIAGRAM;
    } catch (error) {
      if (!(error instanceof DOMException)) throw error;
      console.warn(error);
      return UNREAD;
    }
  }
  return file ?? NO_DIAGRAM;
}

/** The name a drop is said under while it is read. */
export const dropName = (data: DataTransfer): string =>
  data.items[0]?.webkitGetAsEntry()?.name ?? data.files[0]?.name ?? "the file";

/** A .fd handed over as the package itself, which a page cannot open: no
 * bytes, or bytes the browser will not give. */
async function unopened(file: File): Promise<boolean> {
  if (!/\.fd$/i.test(file.name)) return false;
  if (!file.size) return true;
  try {
    await file.slice(0, 1).arrayBuffer();
    return false;
  } catch (error) {
    if (!(error instanceof DOMException)) throw error;
    return true;
  }
}

/** Why a file is not sent at all, or null when it may be. */
export const refusal = (file: File | null): string | null =>
  !file ? NO_DIAGRAM : file.size > MAX_BYTES ? TOO_BIG : null;

/** What the coach is sent when the person says yes to codes for the events
 * the file left without (R-0899). */
export const ADD_CODES =
  "Go through every event in this diagram that has no codes and add codes where the file gives you enough to go on. " +
  "Don't ask me anything first; leave anything missing blank. Keep the events' titles as they are unless the app refuses one. " +
  "Keep going until you have considered every one, then tell me how many you coded and how many you left uncoded.";

export enum Answer {
  Own = "own",
  NotOwn = "not-own",
  Yes = "yes",
  NotNow = "not-now",
}

/** From how many people on the list a name can be typed to find one. */
const FIND_FROM = 8;

/** The import's report, the coach's message the import wrote into the chat,
 * on top of every step of the sheet, so it is read before anything can be
 * sent: its first line, what came in, as the title, then a line for each
 * object skipped (R-0947). Only the last step has a cross, since the diagram
 * must end with one primary person (R-0930). */
const head = ({ note }: Imported["imported"], closable = false): string => {
  const [counts, ...skipped] = note.split("\n");
  return (
    `${closable ? closeX() : ""}<div class="cf-t">${esc(counts)}</div>` +
    skipped.map((line) => `<p class="cf-p">${esc(line)}</p>`).join("")
  );
};

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

const dollars = (amount: number) => `$${amount.toFixed(2)}`;

/** The most a yes is likely to cost. */
export const costLine = ({ high }: Imported["imported"]["coding_cost"]): string => `Up to about ${dollars(high)}`;

/** Last: whether the coach should add the codes the file has none of, and
 * what that is likely to cost; with no event left needing codes, only the
 * report and its cross. The high end is a price per such event, so it is zero
 * exactly when there are none. */
export const codesStep = (imported: Imported["imported"]): string =>
  head(imported, true) +
  (imported.coding_cost.high
    ? `<p class="cf-p">Should the coach go through the events and add codes where the file has none?</p>` +
      `<p class="cf-p fdc-cost">${costLine(imported.coding_cost)}</p>` +
      buttons([Answer.Yes, "Yes"], [Answer.NotNow, "Not now"])
    : "");

/** The new diagram, or the server's own sentence for a file it refuses. */
export async function bring(file: File): Promise<Imported | string> {
  try {
    return await api.importDiagram(file, stem(file.name));
  } catch (error) {
    return api.refusedWith(error, CANNOT_BRING);
  }
}

/** The Diagrams page's way to make a new diagram from a desktop Family
 * Diagram file, for everyone, beside the new diagram row: its row picks the
 * file or a .zip of it, the link under it the .fd folder, and a folder dropped on
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

  /** A file to send, or the sentence saying why there is none. An error
   * anywhere after is said, and still thrown for the console. */
  async pick(file: File | string | null): Promise<void> {
    if (this.sending) return toast(STILL_SENDING, true);
    const refused = typeof file === "string" ? file : refusal(file);
    if (refused) return toast(refused, true);
    if (await unopened(file as File)) return toast(ZIP_FIRST, true);
    await this.send(file as File).catch((error) => {
      toast(CANNOT_BRING, true);
      throw error;
    });
  }

  async send(file: File): Promise<void> {
    if (this.sending) return;
    this.sending = true;
    const made = await bring(file).finally(() => (this.sending = false));
    if (typeof made === "string") return toast(made, true);
    await this.opened(made);
    this.made = made;
    // nothing said about the file sits over the sheet's buttons
    clearToasts();
    this.sheet.show(ownStep(made.imported));
  }

  row(page: HTMLElement): HTMLElement {
    const row = el("div", "sn-row push");
    const sub = el("div", "sn-s");
    const alt = el("button", "sn-alt", "or pick the folder");
    alt.type = "button";
    sub.append(alt);
    const main = el("div", "sn-m");
    main.append(el("div", "sn-t", "Import a Family Diagram file"), sub);
    // a Mac's folder picker will not take a .fd package, so the row picks a
    // file, which the server reads by its bytes, and the link picks the folder
    const file = picker(FILE_KINDS);
    const folder = picker();
    file.setAttribute("aria-label", "Pick a Family Diagram file or a .zip of it");
    folder.setAttribute("aria-label", "Pick a Family Diagram folder");
    row.append(main, el("div", "sn-chev", "\u203a"), file, folder);

    row.addEventListener("click", (e) => {
      if (this.sending || (e.target as Element).closest("input")) return;
      const input = (e.target as Element).closest(".sn-alt") ? folder : file;
      input.value = "";
      input.click();
    });
    for (const input of [file, folder])
      input.addEventListener("change", () => {
        const files = [...(input.files ?? [])];
        if (files.length) void this.pick(fromPicked(files));
      });

    const files = (e: DragEvent) => !!e.dataTransfer?.types.includes("Files");
    // the drop is only the page's when both the entering and every move over
    // it were taken from the browser
    for (const kind of ["dragenter", "dragover"])
      page.addEventListener(kind, (e) => {
        if (!files(e as DragEvent)) return;
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
      // said before anything is read, so a drop that comes to nothing still shows it landed
      toast(`Reading ${dropName(e.dataTransfer!)}\u2026`);
      void fromDrop(e.dataTransfer!).then(
        (file) => this.pick(file),
        (error) => {
          toast(UNREAD, true);
          throw error;
        },
      );
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
