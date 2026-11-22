import { esc } from "./dom";
import { type Found, KeptRecording } from "./keptrecording";
import { Sheet } from "./sheet";

/** Recording a conversation in the app, for a person who does not know the
 * phone's own recorder (R-0955). What is recorded is kept as it comes, so a
 * recording that ends early still keeps everything up to that point. If the
 * pieces of sound stop coming for a while, that time is missing from the file
 * and the drawer says so. */

/** The kinds a browser may record, in the order taken: Safari and Chrome
 * record MP4, Firefox WebM. The bytes go as recorded. */
const KINDS = ["audio/mp4", "audio/webm"];

/** The first kind this browser records, or none, when the browser chooses. */
export const kindFor = (supported: (kind: string) => boolean): string => KINDS.find(supported) ?? "";

/** The file ending for what was recorded. */
export const endingFor = (kind: string) => (kind.includes("webm") ? "webm" : "m4a");

const two = (n: number) => String(n).padStart(2, "0");

/** "0:35", "12:40", "1:02:03". */
export function clock(seconds: number): string {
  const whole = Math.floor(seconds);
  const [h, m, s] = [Math.floor(whole / 3600), Math.floor(whole / 60) % 60, whole % 60];
  return h ? `${h}:${two(m)}:${two(s)}` : `${m}:${two(s)}`;
}

/** How long apart pieces of sound arrive; a gap well over it is time the
 * file does not hold. */
const PIECE_MS = 1000;
const GAP_MS = 2500;

/** The time missing from the file, from the gaps between its pieces. */
export const missedFrom = (arrivals: number[]): number =>
  arrivals.slice(1).reduce((missed, at, i) => {
    const gap = at - arrivals[i];
    return gap > GAP_MS ? missed + (gap - PIECE_MS) / 1000 : missed;
  }, 0);

/** The time the microphone heard nothing. */
export const missedLine = (seconds: number) => `Missed ${clock(seconds)} while this screen was hidden`;

/** Why a recording ended before Stop. */
export enum Ended {
  Lost = "lost",
  Broke = "broke",
  Reloaded = "reloaded",
}

export const ENDED: Record<Ended, string> = {
  [Ended.Lost]: "Stopped when the microphone was lost",
  [Ended.Broke]: "Stopped by an error",
  [Ended.Reloaded]: "Stopped when the page reloaded",
};

/** Where a recording is made: the diagram open and its name. */
export interface Place {
  diagram: number | null;
  name: string;
}

/** The recording's name: the day and time it started, on the person's clock. */
export const nameFor = (at: Date, kind: string) =>
  `Recording ${at.getFullYear()}-${two(at.getMonth() + 1)}-${two(at.getDate())} ` +
  `${two(at.getHours())}.${two(at.getMinutes())}.${endingFor(kind)}`;

const missedFor = (missed: number) => (missed >= 1 ? `<span class="rc-v rc-missed">${esc(missedLine(missed))}</span>` : "");

const sheetFor = (seconds: number, missed: number) =>
  `<div class="cf-t">Recording</div>` +
  `<div class="rc-time">${clock(seconds)}</div>` +
  `<div class="rc-vals">${missedFor(missed)}</div>` +
  `<p class="cf-p">Recording carries on if the phone locks.</p>` +
  `<div class="cf-btns"><button class="cf-go" type="button" data-act="stop">Stop</button></div>`;

/** Speech needs no more: about 29 MB an hour, where the iPhone's own rate
 * gave about 86 MB. */
export const BITS_PER_SECOND = 64_000;

export const optionsFor = (kind: string): MediaRecorderOptions => ({
  ...(kind ? { mimeType: kind } : {}),
  audioBitsPerSecond: BITS_PER_SECOND,
});

/** The line naming the diagram a kept recording was made in, when another is
 * open. */
export const elsewhereLine = (name: string) => `Recorded in the diagram ${name}`;

export const endedFor = (seconds: number, missed: number, why: Ended, elsewhere: string | null = null) =>
  `<div class="cf-t">Recording</div>` +
  `<div class="rc-vals"><span class="rc-v">Recorded ${clock(seconds)}</span>` +
  `<span class="rc-v">${esc(ENDED[why])}</span>${missedFor(missed)}` +
  `${elsewhere === null ? "" : `<span class="rc-v">${esc(elsewhereLine(elsewhere))}</span>`}</div>` +
  `<div class="cf-btns"><button class="cf-go" type="button" data-act="keep">Keep</button>` +
  `<button class="cf-no" type="button" data-act="discard">Discard</button></div>`;

/** A kept recording made whole again from its pieces, as Stop would have
 * made it. */
export const rebuilt = ({ about, pieces }: Found) =>
  new File(pieces, nameFor(new Date(about.started), about.kind), { type: about.kind });

export class Recorder {
  private sheet: Sheet;
  private chunks: Blob[] = [];
  private file: File | null = null;
  private started = 0;
  /** When each piece of sound arrived. */
  private arrivals: number[] = [];
  private ticking = 0;
  private answer: ((file: File | null) => void) | null = null;
  private media: MediaRecorder | null = null;
  private lock: WakeLockSentinel | null = null;
  private ended: Ended | null = null;

  constructor(
    host: HTMLElement,
    private readonly kept: KeptRecording,
  ) {
    this.sheet = new Sheet(host, "rc");
    this.sheet.panel.addEventListener("click", (e) => {
      const act = (e.target as Element).closest<HTMLElement>("[data-act]")?.dataset.act;
      if (act === "stop") this.stop();
      if (act === "keep") this.done(true);
      if (act === "discard") this.done(false);
    });
    document.addEventListener("visibilitychange", () => {
      if (this.media?.state === "recording" && document.visibilityState === "visible") void this.awake();
    });
  }

  /** The screen kept on; asked only once the microphone is granted, since
   * Safari refuses it while its microphone question shows, and again each
   * time the page comes back. A refusal leaves recording as it is. */
  private async awake(): Promise<void> {
    this.lock = (await navigator.wakeLock?.request("screen").catch(() => null)) ?? null;
  }

  /** The microphone asked for, then recording until Stop; answers with the
   * recording, or null when there is none or the person discards it. A
   * refused microphone is the browser's to say, and is thrown. */
  async record(place: Place): Promise<File | null> {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const kind = kindFor((one) => MediaRecorder.isTypeSupported(one));
    const media = new MediaRecorder(stream, optionsFor(kind));
    this.media = media;
    this.chunks = [];
    this.ended = null;
    this.arrivals = [];
    const start = new Date();
    this.started = start.getTime();
    this.kept.begin({ kind, started: this.started, seconds: 0, missed: 0, ...place });
    media.addEventListener("dataavailable", (e) => {
      if (!e.data.size) return;
      this.chunks.push(e.data);
      this.arrivals.push(Date.now());
      this.kept.add(e.data, this.seconds(), this.missed(), media.mimeType || kind);
    });
    media.addEventListener("error", () => this.stop(Ended.Broke));
    for (const track of stream.getTracks()) track.addEventListener("ended", () => this.stop(Ended.Lost));
    media.addEventListener("stop", () => {
      for (const track of stream.getTracks()) track.stop();
      void this.lock?.release();
      this.lock = null;
      window.clearInterval(this.ticking);
      const type = media.mimeType || kind;
      this.file = new File(this.chunks, nameFor(start, type), { type });
      if (this.ended) this.sheet.show(endedFor(this.seconds(), this.missed(), this.ended));
      else this.done(true);
    });
    this.arrivals.push(Date.now());
    media.start(PIECE_MS);
    await this.awake();
    this.sheet.show(sheetFor(0, 0));
    this.ticking = window.setInterval(() => this.tick(), 1000);
    return new Promise((answer) => (this.answer = answer));
  }

  /** Recording, or a drawer of its own up. */
  busy(): boolean {
    return !!this.media || this.sheet.up;
  }

  /** A recording kept from before the page reloaded, offered with Keep and
   * Discard; answers with it rebuilt, or null once discarded. `elsewhere`
   * names the diagram it was made in, when another is open. */
  offer(found: Found, elsewhere: string | null): Promise<File | null> {
    this.file = rebuilt(found);
    this.sheet.show(endedFor(found.about.seconds, found.about.missed, Ended.Reloaded, elsewhere));
    return new Promise((answer) => (this.answer = answer));
  }

  private missed(): number {
    return missedFrom(this.arrivals);
  }

  /** What the file holds: the time since Start less the time missed. */
  private seconds(): number {
    return (Date.now() - this.started) / 1000 - this.missed();
  }

  private tick(): void {
    const time = this.sheet.panel.querySelector(".rc-time");
    if (!time) return;
    time.textContent = clock(this.seconds());
    this.sheet.panel.querySelector(".rc-vals")!.innerHTML = missedFor(this.missed());
  }

  stop(why: Ended | null = null): void {
    if (this.media?.state !== "recording") return;
    this.ended = why;
    this.media.stop();
  }

  private done(keep: boolean): void {
    this.sheet.lower();
    this.media = null;
    if (!keep) this.kept.forget();
    const answer = this.answer;
    this.answer = null;
    answer?.(keep ? this.file : null);
  }
}
