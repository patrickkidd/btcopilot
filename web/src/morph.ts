/** A view drawn again from the record changes in place: the elements on
 * screen are kept, matched to the new drawing by the item they show, and only
 * what differs is changed, so no list or card is rebuilt, nothing flashes, and
 * every scroll position and open card stays where it was. */

/** The attributes that say which item an element shows. */
const KEYS = ["id", "data-event", "data-person", "data-q", "data-card", "data-cluster", "data-statement", "data-key"];

function key(node: Node): string | null {
  if (!(node instanceof Element)) return null;
  for (const name of KEYS) {
    const value = node.getAttribute(name);
    if (value !== null) return `${node.tagName}|${name}|${value}`;
  }
  return null;
}

const same = (a: Node, b: Node) =>
  a.nodeType === b.nodeType && (!(a instanceof Element) || a.tagName === (b as Element).tagName);

/** One node made to match another, keeping the node itself. */
function patch(from: Node, to: Node): void {
  if (!(from instanceof Element) || !(to instanceof Element)) {
    if (from.nodeValue !== to.nodeValue) from.nodeValue = to.nodeValue;
    return;
  }
  for (const { name } of [...from.attributes]) if (!to.hasAttribute(name)) from.removeAttribute(name);
  for (const { name, value } of [...to.attributes]) if (from.getAttribute(name) !== value) from.setAttribute(name, value);
  // a handler set on the new drawing's element is the one the kept element answers with
  const fromEl = from as HTMLElement;
  const toEl = to as HTMLElement;
  if (toEl.onclick !== fromEl.onclick) fromEl.onclick = toEl.onclick;
  children(from, to);
}

/** The children of `from` made to match those of `to`, in order: a child that
 * shows an item is kept wherever it was, any other is matched by position and
 * kind, and only what is new is added and what is gone removed. */
function children(from: Node, to: Node): void {
  const old = [...from.childNodes];
  const byKey = new Map<string, Node>();
  for (const node of old) {
    const k = key(node);
    if (k !== null) byKey.set(k, node);
  }
  const used = new Set<Node>();
  let free = 0;
  let cursor: Node | null = from.firstChild;
  for (const next of [...to.childNodes]) {
    const k = key(next);
    let match: Node | undefined;
    if (k !== null) match = byKey.get(k);
    else {
      while (free < old.length && (used.has(old[free]) || key(old[free]) !== null)) free++;
      if (free < old.length && same(old[free], next)) match = old[free];
    }
    if (match && !used.has(match) && same(match, next)) {
      used.add(match);
      if (match !== cursor) from.insertBefore(match, cursor);
      patch(match, next);
      cursor = match.nextSibling;
    } else from.insertBefore(next, cursor);
  }
  for (const node of old) if (!used.has(node)) node.parentNode?.removeChild(node);
}

/** A container's contents made to match this drawing, in place. */
export function morph(container: Element, html: string): void {
  // nothing on screen yet to keep
  if (!container.firstChild) return void (container.innerHTML = html);
  const drawing = document.createElement("template");
  drawing.innerHTML = html;
  children(container, drawing.content);
}

/** An element made to match another drawn afresh, keeping the element. */
export function morphInto(from: Element, to: Element): void {
  if (from.tagName !== to.tagName) return void from.replaceWith(to);
  patch(from, to);
}
