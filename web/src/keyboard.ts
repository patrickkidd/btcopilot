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

/** Return in a message box, the chat's and the coding screen's alike: it
 * sends, or puts in a new line (R-0368). The break is a plain newline so the
 * box's words keep it. */
export function onReturn(box: HTMLElement, send: () => void): void {
  box.addEventListener("keydown", (key) => {
    const act = returnKey(key, touch());
    if (!act) return;
    key.preventDefault();
    if (act === Return.Send) return send();
    const selection = window.getSelection();
    if (!selection?.rangeCount) return;
    const range = selection.getRangeAt(0);
    range.deleteContents();
    const br = document.createTextNode("\n");
    range.insertNode(br);
    // A newline that ends the box draws no line of its own, so the next letters
    // would join the line above; a second one holds the line open, and the
    // send trims it.
    let next = br.nextSibling;
    while (next instanceof Text && next.data === "") next = next.nextSibling;
    if (!next) br.after(document.createTextNode("\n"));
    // No browser scrolls a box to a caret a script put there, so the new line
    // would open below the box's bottom edge once the box is full (FD-366). The
    // box is only measured, never written to: an element put into the focused
    // box can make iOS scroll the page to it, sliding the box off the keyboard.
    const style = getComputedStyle(box);
    const breaks = document.createRange();
    breaks.selectNode(br);
    const glyph = breaks.getBoundingClientRect();
    const line = parseFloat(style.lineHeight);
    // the glyph sits centred in its line; the new line is the one under it
    const below =
      glyph.bottom +
      (line - glyph.height) / 2 +
      line -
      box.getBoundingClientRect().bottom +
      parseFloat(style.paddingBottom);
    if (below > 0) box.scrollTop += Math.ceil(below);
    range.setStartAfter(br);
    range.collapse(true);
    selection.removeAllRanges();
    selection.addRange(range);
  });
}
