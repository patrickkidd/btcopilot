import { el } from "./dom";

/** One line the app says about what it just did, then takes back. */
const SHOWN_MS = 1500;
const FADE_MS = 220;

let host: HTMLElement | null = null;

export function toast(text: string): void {
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
  }, SHOWN_MS);
}
