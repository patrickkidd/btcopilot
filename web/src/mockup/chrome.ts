import indexHtml from "../../index.html?raw";
import { esc } from "../dom";

/** The app's own chrome, taken from index.html as it stands: the title row,
 * the picture region (the path, the view, the row under it), the speak row,
 * the message box, the drawer's host and the list screen behind the row's list
 * glyph. Nothing is drawn here; the ids come off, since a gallery holds many
 * frames, and the title row says whose page it is. The message box is mounted
 * dead by the page (casepage.ts): nothing on a case page posts to the coach
 * (Patrick, 2026-10-01). */

function pick(re: RegExp): string {
  const m = indexHtml.match(re);
  if (!m) throw new Error(`index.html no longer holds ${re}`);
  return m[0].replace(/ id="([^"]*)"/g, (_, id: string) => (id === "pbp" ? " data-pbp" : ""));
}

/** The app's font links, as index.html loads them: the two preconnects and the one stylesheet. */
export const FONTS = pick(/<link rel="preconnect" href="https:\/\/fonts\.googleapis\.com">[\s\S]*?<link rel="stylesheet" href="https:\/\/fonts\.googleapis\.com\/css2[^>]*>/);

const TITLEROW = pick(/<div class="titlerow">[\s\S]*?<button class="avatar" id="account"[^>]*><\/button>\s*<\/div>/);
export const PIC = pick(/<div class="pic">\s*<div class="pin-label">[\s\S]*?<div class="caption" id="caption"><\/div>\s*<\/div>/);
export const SPEAKROW = pick(/<label class="speakrow" id="speakrow">[\s\S]*?<\/label>/);
/** The message box: the sessions glyph, the words and the send button. */
export const INBAR = pick(/<div class="inbar" id="inbar">[\s\S]*?<button class="send" id="send"[^>]*><span>&#8593;<\/span><\/button>\s*<\/div>/);
export const PBP = pick(/<div id="pbp" hidden><\/div>/);
/** The list screen: the events and the people, over the whole screen (R-0345). */
export const MENU = pick(/<div class="screen slideover" id="menu-screen" hidden>[\s\S]*?<div class="foot" id="menu-foot">[\s\S]*?<\/div>\s*<\/div>/);

const AVATAR = /(<button class="avatar" type="button" aria-label="Account and settings">)(<\/button>)/;
if (!AVATAR.test(TITLEROW)) throw new Error("index.html no longer holds the account button as the title row draws it");

/** The title row with the page's title, and the account's initial in the
 * account button, in its own element, as settings.ts marks it. */
export const titlerow = (title: string, initial: string): string =>
  TITLEROW.replace(">Your family<", `>${esc(title)}<`).replace(AVATAR, (_, open: string, close: string) => `${open}<span>${esc(initial)}</span>${close}`);
