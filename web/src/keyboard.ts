/** What Return does in the message box (Patrick, 2026-09-29). With a real
 * keyboard, Return sends and Shift- or Alt-Return starts a new line. On a
 * touch screen, Return always starts a new line and only the send button
 * sends. A touch screen is told by its pointer, never by the browser's name. */

export enum Return {
  Send = "send",
  Newline = "newline",
}

const KEYBOARD = "(hover: hover) and (pointer: fine)";

export const touch = (): boolean => !window.matchMedia(KEYBOARD).matches;

/** Nothing for a key that is not Return, or a Return that finishes a word
 * being composed in another script. */
export function returnKey(
  key: Pick<KeyboardEvent, "key" | "shiftKey" | "altKey" | "isComposing">,
  onTouch: boolean,
): Return | null {
  if (key.key !== "Enter" || key.isComposing) return null;
  return onTouch || key.shiftKey || key.altKey ? Return.Newline : Return.Send;
}
