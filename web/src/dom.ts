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

/** The path: where the reader is, from the whole timeline down, each earlier
 * step the way back to it (R-0540). A picked event at its end is written in the
 * picked colour, as its words on the picture are (Patrick, 2026-10-01). */
export const pathRow = (steps: string[], picked = false): string =>
  steps
    .map((step, i) =>
      i < steps.length - 1
        ? `<button type="button" class="step" data-step="${i}"><span>${esc(step)}</span></button>`
        : `<span class="here${picked ? " on" : ""}">${esc(step)}</span>`,
    )
    .join(`<span class="sep" aria-hidden="true"> \u203a </span>`);

/** A path row too long for its line gives way a whole word at a time, never
 * cut inside one: the steps between become an ellipsis first, then the last
 * step loses words from its end. */
export function fitPath(row: HTMLElement): void {
  row.classList.add("words");
  const over = () => row.scrollWidth > row.clientWidth + 1;
  row.querySelectorAll<HTMLElement>(".step:not(:first-child) > span").forEach((s) => {
    if (over()) s.textContent = "\u2026";
  });
  const here = row.querySelector<HTMLElement>(".here");
  const words = here?.textContent!.split(" ") ?? [];
  while (here && over() && words.length > 1) {
    words.pop();
    here.textContent = `${words.join(" ")}\u2026`;
  }
}

/** The path's step that goes back to the open cluster. */
export const CLUSTER = 1;

/** The app's close button: a cross in the top-right corner of the box it sits
 * in (R-0317). */
export const closeX = (attrs = "") =>
  `<button class="cardx" type="button" aria-label="close"${attrs}>×</button>`;

/** A step back or forward, the same pill wherever steps are walked. */
export const stepBtn = (label: string, attrs: string, off: boolean) =>
  `<button class="stepbtn" type="button" ${attrs}${off ? " disabled" : ""}>${label}</button>`;

export function $(id: string): HTMLElement {
  const node = document.getElementById(id);
  if (!node) throw new Error(`No element #${id}`);
  return node;
}

/** How long a panel takes to travel up over what it covers, matched to the
 * sessions sheet's own motion in the stylesheet. */
const SLIDE_MS = 280;

const sliding = new WeakMap<HTMLElement, number>();

/** Bring a full-screen panel up over everything beneath it, or send it back
 * down: the events and people list travels the way the sessions sheet does,
 * full height, and is only taken out of the page once it has landed (R-0345). */
/** How long a lit item stays ringed after an address or a jump points at it. */
const FLASH_MS = 2200;

/** The nearest box that scrolls the item, if one does. */
function scroller(item: HTMLElement): HTMLElement | null {
  for (let box = item.parentElement; box; box = box.parentElement) {
    const y = getComputedStyle(box).overflowY;
    if ((y === "auto" || y === "scroll") && box.scrollHeight > box.clientHeight) return box;
  }
  return null;
}

/** How long a glide may take to land, however often it is stopped. */
const GLIDE_MS = 2000;
/** Frames the box must hold still before a glide counts as stopped. */
const STILL = 3;
const HANDS = ["wheel", "touchstart", "pointerdown", "keydown"];

/** Glide `box` until `to()` is where it stands. Something on the page may
 * stop a glide partway — the box changing size as the picture folds sets its
 * scroll — so it goes on from where it stopped, until it lands, the reader
 * takes the scroll in hand, or the time is up. */
function glide(box: HTMLElement, to: () => number): void {
  const go = () => box.scrollTo({ top: to(), behavior: "smooth" });
  const until = performance.now() + GLIDE_MS;
  let held = false;
  const hold = () => (held = true);
  for (const kind of HANDS) box.addEventListener(kind, hold, { once: true, passive: true });
  let last = Number.NaN;
  let still = 0;
  const done = () => {
    for (const kind of HANDS) box.removeEventListener(kind, hold);
  };
  const check = () => {
    if (held || performance.now() > until) return done();
    still = box.scrollTop === last ? still + 1 : 0;
    last = box.scrollTop;
    if (still >= STILL) {
      if (Math.abs(box.scrollTop - to()) <= 1) return done();
      still = 0;
      go();
    }
    requestAnimationFrame(check);
  };
  go();
  requestAnimationFrame(check);
}

/** The one light for whatever an address or a jump points at: a message, a
 * sitting's line, a row in a drawer or a list. The box that scrolls the item
 * glides it to the middle, or to the top for a line that starts what follows
 * it, and the item is ringed while it settles; a reader who asks for less
 * motion gets the jump without the glide. Never `scrollIntoView`: the outer
 * page must not move (UI_STANDARDS). */
export function flash(item: HTMLElement, top = false): void {
  const box = scroller(item);
  if (box) {
    const to = () => {
      const outer = box.getBoundingClientRect();
      const at = item.getBoundingClientRect();
      const room = top ? 0 : (outer.height - at.height) / 2;
      const end = box.scrollHeight - box.clientHeight;
      return Math.min(end, Math.max(0, box.scrollTop + (at.top - outer.top) - room));
    };
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) box.scrollTop = to();
    else glide(box, to);
  }
  item.classList.remove("traced");
  void item.offsetWidth;
  item.classList.add("traced");
  window.setTimeout(() => item.classList.remove("traced"), FLASH_MS);
}

export function slideOver(panel: HTMLElement, up: boolean): void {
  window.clearTimeout(sliding.get(panel));
  if (up) {
    panel.hidden = false;
    void panel.offsetWidth;
    panel.classList.add("in");
    return;
  }
  panel.classList.remove("in");
  sliding.set(
    panel,
    window.setTimeout(() => {
      panel.hidden = true;
    }, SLIDE_MS),
  );
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

/** Patrick alone runs the agenda, the meeting and the guidelines (R-0346). */
export function isAdmin(): boolean {
  return window.BOOTSTRAP.user?.admin === true;
}

export function isCoder(): boolean {
  return window.BOOTSTRAP.user?.coder === true;
}

/** The reader asked the system for less motion. */
export const still = (): boolean =>
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

/** The thread's room above its first words: what its scroll cannot take up,
 * near the top as its box grows or on the fraction of a pixel a scroll
 * rounds away, held in the padding over the first words (R-0570). */
const ROOM = "--room";

/** Move the thread's words up by `by` pixels as a scroll of exactly that
 * would, room first given back to the scroll and the rest held as room. */
export const shift = (list: HTMLElement, by: number): void => {
  const to = list.scrollTop - (parseFloat(list.style.getPropertyValue(ROOM)) || 0) + by;
  list.style.setProperty(ROOM, `${Math.max(0, -to)}px`);
  list.scrollTop = to;
  list.style.setProperty(ROOM, `${list.scrollTop - to}px`);
};
