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

export function say(text: string): void {
  const synth = window.speechSynthesis;
  if (!synth) return;
  synth.cancel();
  const words = spoken(text);
  if (!words) return;
  synth.speak(new SpeechSynthesisUtterance(words));
}

/** The reader's tap cuts the reply being spoken, and opens the voice for the
 * next one: iOS Safari drops every speak() until one is made inside a tap, and
 * the reply arrives long after the tap, so an empty one is made here. */
export function hush(): void {
  const synth = window.speechSynthesis;
  synth.cancel();
  synth.speak(new SpeechSynthesisUtterance(""));
}
