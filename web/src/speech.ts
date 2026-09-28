/** Speak replies (R-0099): the coach's words read aloud by the phone's own
 * voice, nothing sent anywhere. Off unless the preference is on; a new reply
 * or a new message from the reader cuts the one being spoken. */

import { tokenize } from "./chips";

/** The words as a reader would hear them: a chip becomes its label. */
export function spoken(text: string): string {
  return tokenize(text)
    .map((p) => ("chip" in p ? p.chip.label : p.text))
    .join("")
    .replace(/\s+/g, " ")
    .trim();
}

/** Called once when the reading under way stops, however it stops: its end,
 * another reading, or the reader's tap. A cancelled reading's own end event
 * can arrive after the next one has begun, so the end is not trusted alone. */
let ended: (() => void) | null = null;

function stopped(): void {
  const done = ended;
  ended = null;
  done?.();
}

export function say(text: string, done: (() => void) | null = null): void {
  const synth = window.speechSynthesis;
  if (!synth) return;
  synth.cancel();
  stopped();
  const words = spoken(text);
  if (!words) return done?.();
  const reading = new SpeechSynthesisUtterance(words);
  ended = done;
  reading.onend = reading.onerror = () => {
    if (ended === done) stopped();
  };
  synth.speak(reading);
}

/** The reader's tap cuts the reply being spoken, and opens the voice for the
 * next one: iOS Safari drops every speak() until one is made inside a tap, and
 * the reply arrives long after the tap, so an empty one is made here. */
export function hush(): void {
  const synth = window.speechSynthesis;
  synth.cancel();
  stopped();
  synth.speak(new SpeechSynthesisUtterance(""));
}
