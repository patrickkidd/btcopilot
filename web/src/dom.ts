export function esc(value: string): string {
  return value.replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string,
  );
}

export function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className?: string,
  html?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (html !== undefined) node.innerHTML = html;
  return node;
}

export function $(id: string): HTMLElement {
  const node = document.getElementById(id);
  if (!node) throw new Error(`No element #${id}`);
  return node;
}

/** A screen's title in two parts. The name is the part that gives way when the
 * row runs out of width; the tail says which stretch of the conversation is on
 * screen and has to stay readable, so at phone width a long name ellipsises
 * and "· up to Sep 4" stays. */
export interface Title {
  name: string;
  tail: string;
}

export function setTitle(title: string | Title): void {
  const host = $("title");
  if (typeof title === "string") {
    host.textContent = title;
    return;
  }
  const name = el("span", "ttl-name");
  name.textContent = title.name;
  const tail = el("span", "ttl-tail");
  tail.textContent = ` · ${title.tail}`;
  host.replaceChildren(name, tail);
}
