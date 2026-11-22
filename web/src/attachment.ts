import * as api from "./api";
import { closeX, el, esc } from "./dom";
import { KeptRecording } from "./keptrecording";
import { clock, Recorder } from "./recorder";
import type { Saved } from "./recording";
import { Sheet } from "./sheet";
import { store } from "./store";
import { toast } from "./toast";
import type { Utterance } from "./types";

/** iOS greys out every file in the Files picker for "audio/*" alone; the
 * endings let it pick them. */
export const AUDIO = [
  ".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg", ".opus", ".wma", ".amr", ".aif", ".aiff", ".caf", ".qta", ".webm",
];

/** What the picker offers; the server says what it takes and refuses the rest
 * in its own words. A recording is one more kind of document (R-0954). */
export const KINDS =
  ".pdf,.jpg,.jpeg,.png,.heic,.heif,.txt,.text,.md,.markdown,application/pdf,image/jpeg,image/png,image/heic,image/heif,text/plain,text/markdown," +
  [...AUDIO, "audio/*"].join(",");

export const isAudio = (file: File) =>
  file.type.startsWith("audio/") || AUDIO.some((ending) => file.name.toLowerCase().endsWith(ending));

/** A text file the page can count before it is sent; a PDF or a photo is read
 * on the server and is not counted here. */
const counted = (file: File) => /\.(txt|md)$/i.test(file.name) || /^text\//.test(file.type);

/** How long between asking whether the transcript is ready. */
const POLL_MS = 3000;

/** The file a message carries: its name as a chip, dimmed while the server
 * reads it, and once read a tap shows what the coach was given. One its turn
 * could not take stays dimmed, no longer said to be reading (R-0830). The file
 * itself is never kept or shown again. */
export const fileChip = (name: string, text: string | null = null, untaken = false): string =>
  `<div class="file"><button class="chip file${text !== null ? "" : untaken ? " untaken" : " reading"}" type="button"` +
  `${text === null ? " disabled" : ""}>${esc(name)}</button></div>`;

/** What the coach read from a file, in the sheet a tap on its chip raises. A
 * recording's transcript reads the same way, each turn of talk under the
 * speaker's name as the server writes it. */
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

/** Where a recording in the box has got. */
export enum Stage {
  Uploading = "uploading",
  Transcribing = "transcribing",
  Failed = "failed",
  Silent = "silent",
  Naming = "naming",
  Named = "named",
}

/** A recording in the box, from the upload to its speakers named. */
export interface Clip {
  file: File;
  stage: Stage;
  /** How much of the upload has gone, from 0 to 1. */
  sent: number;
  /** When transcribing began, in milliseconds. */
  since: number;
  id: string;
  /** The diagram open when it was put in, which every call about it names. */
  diagram: number | null;
  seconds: number | null;
  /** The dollars transcribing it cost, once transcribed. */
  price: number | null;
  utterances: Utterance[];
  voices: api.Suggested[];
  saved: Saved | null;
}

export const clipOf = (file: File): Clip => ({
  file,
  stage: Stage.Uploading,
  sent: 0,
  since: 0,
  id: "",
  diagram: null,
  seconds: null,
  price: null,
  utterances: [],
  voices: [],
  saved: null,
});

/** A transcription the recording will not be sent with is deleted at the
 * service, without the person waiting for it; the clip forgets its id. */
export function forget(clip: Clip): void {
  if (!clip.id) return;
  void api.deleteTranscription(clip.diagram, clip.id);
  clip.id = "";
}

/** A transcription that ended in error is already deleted by the server, so
 * its id is dead: nothing deletes it again, and Try again uploads the file
 * for a new one. */
export function erred(clip: Clip): void {
  clip.id = "";
}

/** A recording being made, or one in the box still uploading or
 * transcribing, would be cut off by a reload (R-0955). */
export const holding = (recording: boolean, clip: Clip | null): boolean =>
  recording || clip?.stage === Stage.Uploading || clip?.stage === Stage.Transcribing;

/** What the recording's chip says beside its name, as values (R-0953). */
export function values(clip: Clip, now: number): string[] {
  if (clip.stage === Stage.Uploading) return [`Uploading ${Math.round(clip.sent * 100)}%`];
  if (clip.stage === Stage.Transcribing) return [`Transcribing ${clock((now - clip.since) / 1000)}`];
  if (clip.stage === Stage.Failed) return ["Could not transcribe"];
  if (clip.stage === Stage.Silent) return ["No speech found"];
  const length = clip.seconds === null ? [] : [`Length ${Math.max(1, Math.round(clip.seconds / 60))} min`];
  return [...length, `Speakers ${clip.voices.length}`];
}

/** The name a message's attachment goes by in the thread. */
export const nameOf = (attached: File | api.Heard) => (attached instanceof File ? attached.name : attached.title);

const act = (name: string, words: string) =>
  `<button class="att-act" type="button" data-act="${name}">${words}</button>`;

/** The recording's chip in the box: a tap once transcribed says who each
 * speaker is; a failed one is tried again or removed. */
export function clipChip(clip: Clip, now: number): string {
  const open = clip.stage === Stage.Naming || clip.stage === Stage.Named;
  return (
    `<button class="chip file" type="button" data-act="name"${open ? "" : " disabled"}>` +
    `${esc(clip.saved?.title ?? clip.file.name)}</button>` +
    `<span class="att-v">${esc(values(clip, now).join(" · "))}</span>` +
    (clip.stage === Stage.Failed
      ? act("again", "Try again") + act("remove", "Remove")
      : clip.stage === Stage.Silent
        ? act("remove", "Remove")
        : closeX())
  );
}

/** What the paperclip offers: recording in the app first, the fewest steps
 * for a person on their own (R-0958), then a file already made. */
export const MENU =
  `<div class="cf-t">Attach</div><div class="sn-grp ap-rows">` +
  `<button class="sn-row push" type="button" data-act="record"><span class="sn-t">Record a conversation</span></button>` +
  `<button class="sn-row push" type="button" data-act="file"><span class="sn-t">Choose a file</span></button>` +
  `</div>`;

/** The paperclip in the chat bar, a file dropped on the chat on a computer,
 * the picked file's chip in the box, and the sheet of what the coach read. A
 * recording picked, dropped or recorded is transcribed in the box and its
 * speakers named before it goes (R-0953, R-0954). */
export class Attachment {
  readonly picked = new Picked();
  private clip: Clip | null = null;
  /** Counts the recordings put in the box, so one removed stops answering. */
  private run = 0;
  private ticking = 0;
  private input = document.createElement("input");
  private slot = el("div", "attached");
  private sheet: Sheet;
  private menu: Sheet;
  private recorder: Recorder;
  /** The recording kept on the device, and its clip while it is in the box
   * and not yet taken by the server (R-0955). */
  private kept = new KeptRecording();
  private keptClip: Clip | null = null;
  private offering = false;
  private texts = new WeakMap<HTMLElement, string>();

  constructor(
    button: HTMLElement,
    field: HTMLElement,
    screen: HTMLElement,
    list: HTMLElement,
    private readonly naming: (file: File, voices: api.Suggested[]) => Promise<Saved | null>,
  ) {
    this.input.type = "file";
    this.input.accept = KINDS;
    this.input.hidden = true;
    this.input.setAttribute("aria-label", "Attach a file");
    button.after(this.input);
    this.menu = new Sheet(screen, "ap");
    this.recorder = new Recorder(screen, this.kept);
    button.addEventListener("click", () => this.menu.show(MENU));
    this.menu.panel.addEventListener("click", (e) => {
      const target = e.target as Element;
      const chosen = target.closest<HTMLElement>("[data-act]")?.dataset.act;
      if (chosen) this.menu.lower();
      if (chosen === "file") {
        this.input.value = "";
        this.input.click();
      }
      if (chosen === "record") void this.record();
    });
    screen.addEventListener("click", (e) => {
      if ((e.target as Element).closest(".fs-scrim.ap")) this.menu.lower();
    });
    this.input.addEventListener("change", () => this.input.files?.[0] && this.pick(this.input.files[0]));
    this.slot.hidden = true;
    field.prepend(this.slot);
    this.slot.addEventListener("click", (e) => {
      const target = e.target as Element;
      const chosen = target.closest<HTMLElement>("[data-act]")?.dataset.act;
      if (target.closest(".cardx") || chosen === "remove") this.clear(true);
      else if (chosen === "again" && this.clip) void this.transcribe(this.clip);
      else if (chosen === "name" && this.clip) void this.name(this.clip, this.run);
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
      if (e.key !== "Escape") return;
      if (this.sheet.up) this.sheet.lower();
      if (this.menu.up) this.menu.lower();
    });
    list.addEventListener("click", (e) => {
      const chip = (e.target as Element).closest<HTMLElement>(".bub .chip.file");
      const text = chip && this.texts.get(chip);
      if (text != null) this.sheet.show(readSheet(chip!.textContent!, text));
    });
  }

  pick(file: File, kept = false): void {
    this.clear();
    if (isAudio(file)) {
      this.clip = clipOf(file);
      if (kept) this.keptClip = this.clip;
      this.slot.hidden = false;
      void this.transcribe(this.clip);
      return;
    }
    this.picked.pick(file);
    this.slot.innerHTML = `<span class="chip file">${esc(file.name)}</span>${closeX()}`;
    this.slot.hidden = false;
  }

  /** A recording kept from before the page reloaded, not in the box, is
   * offered with Keep and Discard; Keep puts it in the box as Stop does.
   * True when one was kept. */
  async offer(): Promise<boolean> {
    if (this.offering || this.keptClip || this.recorder.busy()) return false;
    this.offering = true;
    try {
      const found = await this.kept.find();
      if (!found || this.keptClip || this.recorder.busy()) return false;
      const elsewhere = found.about.diagram === store.id() ? null : found.about.name;
      const file = await this.recorder.offer(found, elsewhere);
      if (file) this.pick(file, true);
      return !!file;
    } finally {
      this.offering = false;
    }
  }

  private async record(): Promise<void> {
    // only one recording is kept: an older one is offered before a new one starts
    if (await this.offer()) return;
    if (this.offering) return;
    this.keptClip = null;
    let file;
    try {
      file = await this.recorder.record({ diagram: store.id(), name: store.current().diagram?.name ?? "" });
    } catch (refused) {
      if (!(refused instanceof DOMException)) throw refused;
      console.warn(refused.message);
      toast("Recording needs the microphone");
      return;
    }
    if (file) this.pick(file, true);
  }

  private draw(): void {
    if (this.clip) this.slot.innerHTML = clipChip(this.clip, Date.now());
  }

  private async transcribe(clip: Clip): Promise<void> {
    const run = ++this.run;
    const live = () => run === this.run;
    forget(clip);
    const diagram = (clip.diagram = store.id());
    Object.assign(clip, { stage: Stage.Uploading, sent: 0 });
    this.draw();
    try {
      clip.id = await api.startTranscription(diagram, clip.file, (sent) => {
        clip.sent = sent;
        if (live()) this.draw();
      });
      // taken out of the box while it was still uploading
      if (!live()) return forget(clip);
      if (clip === this.keptClip) {
        this.kept.forget();
        this.keptClip = null;
      }
      Object.assign(clip, { stage: Stage.Transcribing, since: Date.now() });
      this.draw();
      this.ticking = window.setInterval(() => this.draw(), 1000);
      let answer;
      for (;;) {
        answer = await api.transcription(diagram, clip.id);
        if (!live()) return;
        if (answer.status === "completed") break;
        if (answer.status === "error") {
          const id = clip.id;
          erred(clip);
          throw new api.Failed(200, `GET /transcriptions/${id}`, answer.error ?? "");
        }
        await new Promise((wait) => window.setTimeout(wait, POLL_MS));
        if (!live()) return;
      }
      clip.seconds = answer.audio_seconds;
      clip.price = answer.price;
      clip.utterances = answer.utterances ?? [];
      if (!clip.utterances.length) {
        window.clearInterval(this.ticking);
        clip.stage = Stage.Silent;
        return this.draw();
      }
      // the clock runs on under Transcribing until the speakers are known
      clip.voices = await api.recordingVoices(diagram, clip.utterances);
      if (!live()) return;
      window.clearInterval(this.ticking);
      clip.stage = Stage.Naming;
      this.draw();
      await this.name(clip, run);
    } catch (error) {
      if (!(error instanceof api.Failed)) throw error;
      window.clearInterval(this.ticking);
      if (!live()) return;
      console.warn(error.message);
      clip.stage = Stage.Failed;
      this.draw();
    }
  }

  /** Who each speaker is, said in the sheet that opens by itself once the
   * transcript is in; going down without Save leaves the chip to tap again. */
  private async name(clip: Clip, run: number): Promise<void> {
    const saved = await this.naming(clip.file, clip.voices);
    if (run !== this.run || !saved) return;
    clip.saved = saved;
    clip.stage = Stage.Named;
    this.draw();
  }

  /** The box emptied without sending: a recording's copy at the transcription
   * service is deleted, without waiting for it. Removed by the person, the
   * copy kept on the device goes too; emptied for another diagram, it stays
   * and is offered again. */
  clear(removed = false): void {
    if (this.clip) forget(this.clip);
    if (removed && this.keptClip) this.kept.forget();
    this.empty();
  }

  private empty(): void {
    this.run += 1;
    window.clearInterval(this.ticking);
    this.clip = null;
    this.keptClip = null;
    this.picked.take();
    this.slot.hidden = true;
    this.slot.innerHTML = "";
  }

  /** A new release waits while this is true. */
  holding(): boolean {
    return holding(this.recorder.busy(), this.clip);
  }

  /** Whether the box holds something to send with the message. */
  has(): boolean {
    return !!this.picked.file || !!this.clip;
  }

  /** What transcribing the recording in the box cost; null when the box
   * holds no recording. */
  transcribed(): number | null {
    return this.clip ? this.clip.price! : null;
  }

  /** A recording still on its way to being named holds the message back. */
  waiting(): boolean {
    return !!this.clip && this.clip.stage !== Stage.Named;
  }

  /** The words the page can count before sending: a text file's, or a
   * recording's transcript, priced the same way (R-0954). */
  async text(): Promise<string> {
    if (this.clip) return this.clip.utterances.map((one) => one.text).join("\n");
    const file = this.picked.file;
    return file && counted(file) ? file.text() : "";
  }

  /** What the message goes with; the box is left without it. */
  take(): File | api.Heard | null {
    const clip = this.clip;
    const file = this.picked.file;
    this.empty();
    if (!clip) return file;
    return { transcription: clip.id, ...clip.saved! };
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
