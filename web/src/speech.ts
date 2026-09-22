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

export function hush(): void {
  window.speechSynthesis?.cancel();
}
