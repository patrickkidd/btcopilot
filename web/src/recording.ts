import * as api from "./api";
import { el, esc } from "./dom";
import { dragScroll } from "./drag";
import { toast } from "./toast";
import { VoiceRole, type Session, type Utterance, type Voice } from "./types";

/** Putting a recorded session into the record. The audio goes straight from the
 * browser to the transcription service, the way the training app already sends
 * it, so it never passes through our own server. What comes back is split into
 * voices, and the reader says who each one is before anything is read into the
 * record (R-0243, R-0267). */

/** How long between asking the service whether the transcript is ready. */
const POLL_MS = 3000;
const SERVICE = "https://api.assemblyai.com/v2";

const ROLES = [
  { role: VoiceRole.Clinician, label: "the clinician" },
  { role: VoiceRole.Client, label: "the client" },
];

const today = () => new Date().toISOString().slice(0, 10);

/** The file name without its extension, which is what the session is called
 * until the reader types something else. */
const titleFrom = (name: string) => name.replace(/\.[^.]+$/, "");

async function transcribe(file: File, key: string): Promise<Utterance[]> {
  const put = await fetch(`${SERVICE}/upload`, {
    method: "POST",
    headers: { authorization: key },
    body: file,
  });
  if (!put.ok) throw new Error(await put.text());
  const asked = await fetch(`${SERVICE}/transcript`, {
    method: "POST",
    headers: { authorization: key, "Content-Type": "application/json" },
    body: JSON.stringify({
      audio_url: (await put.json()).upload_url,
      speaker_labels: true,
    }),
  });
  if (!asked.ok) throw new Error(await asked.text());
  const id = (await asked.json()).id;
  for (;;) {
    const answer = await fetch(`${SERVICE}/transcript/${id}`, {
      headers: { authorization: key },
    });
    const data = await answer.json();
    if (data.status === "completed") return data.utterances ?? [];
    if (data.status === "error") throw new Error(data.error);
    await new Promise((wait) => window.setTimeout(wait, POLL_MS));
  }
}

export class Recording {
  private scrim = el("div", "fs-scrim");
  private sheet = el(
    "div",
    "fs-sheet",
    `<div class="fs-handle"><div class="fs-grab"></div></div>
     <div class="fs-search"><input type="search" readonly aria-label="the recording"></div>
     <div class="fs-body"></div>
     <div class="fs-foot"><button class="fs-new" type="button">Create session</button></div>`,
  );
  private body: HTMLElement;
  private head: HTMLInputElement;
  private make: HTMLButtonElement;
  private file = document.createElement("input");

  private utterances: Utterance[] = [];
  private voices: Voice[] = [];
  private roles = new Map<string, VoiceRole>();
  private title = "";
  private date = today();

  constructor(
    overlay: HTMLElement,
    private onMade: (session: Session) => void,
  ) {
    this.scrim.hidden = true;
    this.sheet.hidden = true;
    overlay.append(this.scrim, this.sheet);
    this.body = this.sheet.querySelector<HTMLElement>(".fs-body")!;
    this.head = this.sheet.querySelector<HTMLInputElement>(".fs-search input")!;
    this.make = this.sheet.querySelector<HTMLButtonElement>(".fs-new")!;
    this.file.type = "file";
    this.file.accept = "audio/*";
    this.file.hidden = true;
    overlay.append(this.file);
    this.file.addEventListener("change", () => void this.take());
    this.scrim.addEventListener("click", () => this.lower());
    this.sheet
      .querySelector(".fs-handle")!
      .addEventListener("click", () => this.lower());
    this.make.addEventListener("click", () => void this.create());
    this.body.addEventListener("click", (e) => this.onBodyClick(e));
    dragScroll(this.body);
  }

  /** The sessions sheet's own button: the file picker, then everything else. */
  pick(): void {
    this.file.value = "";
    this.file.click();
  }

  private async take(): Promise<void> {
    const file = this.file.files?.[0];
    if (!file) return;
    this.title = titleFrom(file.name);
    this.date = today();
    this.roles.clear();
    this.utterances = [];
    this.voices = [];
    this.raise();
    this.head.value = `Reading ${file.name}…`;
    this.waiting("The recording is being transcribed. This takes a few minutes.");
    try {
      const key = await api.transcriptionKey();
      this.utterances = await transcribe(file, key);
      this.voices = await api.recordingVoices(this.utterances);
    } catch (wrong) {
      this.head.value = file.name;
      this.waiting(
        `That recording could not be transcribed: ${(wrong as Error).message}`,
      );
      return;
    }
    // The service names the voices in the order they first speak, and the
    // clinician is the one who opens a session.
    this.voices.forEach((voice, index) =>
      this.roles.set(voice.label, index === 0 ? VoiceRole.Clinician : VoiceRole.Client),
    );
    this.head.value = `Who is who · ${file.name}`;
    this.render();
  }

  private waiting(words: string): void {
    this.make.hidden = true;
    this.body.innerHTML = `<div class="fs-hint">${esc(words)}</div>`;
  }

  private render(): void {
    this.make.hidden = false;
    let html = "";
    for (const voice of this.voices) {
      const role = this.roles.get(voice.label)!;
      const said = ROLES.find((r) => r.role === role)!.label;
      html +=
        `<div class="row side" data-voice="${esc(voice.label)}">` +
        `<div class="rmain"><div class="r1 rtitle">Voice ${esc(voice.label)}</div>` +
        `<div class="r2">&ldquo;${esc(voice.said)}&rdquo;</div></div>` +
        `<div class="r2 rwhen said">${esc(said)} &rsaquo;</div></div>`;
    }
    html +=
      `<div class="ghead">Session</div>` +
      `<div class="row side"><div class="rmain"><div class="r1 rtitle">Date</div></div>` +
      `<input class="rwhen said" type="date" data-name="date" aria-label="Date" ` +
      `value="${esc(this.date)}"></div>` +
      `<div class="row side"><div class="rmain"><div class="r1 rtitle">Title</div></div>` +
      `<input class="rwhen said" type="text" data-name="title" aria-label="Title" ` +
      `value="${esc(this.title)}"></div>` +
      `<div class="fs-hint">The clinician's lines become the coach's side of the ` +
      `thread. Once created, a voice named wrongly has to be fixed by editing ` +
      `the events it produced.</div>`;
    this.body.innerHTML = html;
    for (const field of this.body.querySelectorAll<HTMLInputElement>("input"))
      field.addEventListener("input", () => {
        if (field.dataset.name === "date") this.date = field.value;
        else this.title = field.value;
      });
  }

  /** A voice is one of two things, so a tap on the row is the whole choice. */
  private onBodyClick(e: Event): void {
    const row = (e.target as Element).closest<HTMLElement>("[data-voice]");
    if (!row) return;
    const label = row.dataset.voice!;
    this.roles.set(
      label,
      this.roles.get(label) === VoiceRole.Clinician
        ? VoiceRole.Client
        : VoiceRole.Clinician,
    );
    this.render();
  }

  private async create(): Promise<void> {
    if (!this.title.trim()) {
      toast("Give the session a title");
      return;
    }
    const voices: Record<string, { type: string }> = {};
    for (const [label, role] of this.roles) voices[label] = { type: role };
    const made = await api.newRecording({
      utterances: this.utterances,
      voices,
      title: this.title.trim(),
      date: this.date || null,
    });
    this.lower();
    this.onMade(made);
  }

  private raise(): void {
    this.scrim.hidden = false;
    this.sheet.hidden = false;
    void this.sheet.offsetWidth;
    this.scrim.classList.add("in");
    this.sheet.classList.add("in");
  }

  private lower(): void {
    this.scrim.classList.remove("in");
    this.sheet.classList.remove("in");
    window.setTimeout(() => {
      this.scrim.hidden = true;
      this.sheet.hidden = true;
    }, 280);
  }
}
