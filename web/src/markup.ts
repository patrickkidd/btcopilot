import { esc } from "./dom";

/** A link to a secure site or to a page of this one; anything else is words. */
const LINK = /\[([^\]\n]+)\]\((https:\/\/[^\s()]+|\/(?!\/)[^\s()]*)\)/g;

const inline = (text: string): string =>
  esc(text)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|\W)_(.+?)_(?!\w)/g, "$1<em>$2</em>")
    .replace(/\n/g, "<br>");

/** A notice's words as HTML: **bold**, _italics_, [words](link) opening in a
 * new tab, and line breaks. Everything else, HTML included, stays literal. */
export function markup(text: string): string {
  let html = "";
  let at = 0;
  LINK.lastIndex = 0;
  for (let m = LINK.exec(text); m !== null; m = LINK.exec(text)) {
    html +=
      inline(text.slice(at, m.index)) +
      `<a href="${esc(m[2])}" target="_blank" rel="noopener">${inline(m[1])}</a>`;
    at = m.index + m[0].length;
  }
  return html + inline(text.slice(at));
}
