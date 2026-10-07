import { el } from "./dom";

/** One line the app says about what it just did, then takes back. */
const SHOWN_MS = 1500;
const FADE_MS = 220;

let host: HTMLElement | null = null;

/** Long enough to read: a toast that must be read, such as the server's reason
 * for refusing something, stays this long for each of its letters. */
const LETTER_MS = 60;

export function toast(text: string, read = false): void {
  if (!host) {
    host = el("div", "toasts");
    document.querySelector(".app")?.append(host);
  }
  const node = el("div", "toast");
  node.textContent = text;
  host.append(node);
  void node.offsetWidth;
  node.classList.add("in");
  window.setTimeout(() => {
    node.classList.remove("in");
    window.setTimeout(() => node.remove(), FADE_MS);
  }, read ? Math.max(SHOWN_MS, text.length * LETTER_MS) : SHOWN_MS);
}
