/** Mouse drag to scroll. A wheel and a touch drag work on an overflow
 * container on their own; a mouse drag does not, and UI_STANDARDS requires
 * every scroll area to take all four. Momentum carries the surface on after
 * the button comes up, so it feels the same on a desktop as on a phone.
 *
 * A drag never starts on words. Dragging the surface and selecting a line of
 * it are the same gesture, so the one that wins is decided by where the press
 * landed: on the words themselves it selects, anywhere else it scrolls. */

const FRICTION = 0.94;
/** Below this the surface has stopped. */
const STILL = 0.4;
/** A press that moves less than this was a tap, not a drag. */
const SLOP = 4;

/** Whether the press landed on a line of text the reader may select, rather
 * than on the space around it. The element's own text is measured, so pressing
 * in a bubble's padding still drags the thread. */
function onWords(target: Element, x: number, y: number): boolean {
  if (getComputedStyle(target).userSelect === "none") return false;
  const range = document.createRange();
  for (const node of target.childNodes) {
    if (node.nodeType !== Node.TEXT_NODE || !node.textContent?.trim()) continue;
    range.selectNodeContents(node);
    for (const box of range.getClientRects())
      if (x >= box.left && x <= box.right && y >= box.top && y <= box.bottom)
        return true;
  }
  return false;
}

export function dragScroll(host: HTMLElement): void {
  let from: { y: number; top: number } | null = null;
  let last = 0;
  let speed = 0;
  let dragging = false;
  let coasting = 0;

  const coast = () => {
    if (Math.abs(speed) < STILL) return;
    host.scrollTop -= speed;
    speed *= FRICTION;
    coasting = requestAnimationFrame(coast);
  };

  host.addEventListener("pointerdown", (e) => {
    if (e.pointerType !== "mouse" || e.button !== 0) return;
    const target = e.target as Element;
    if (target instanceof Element && onWords(target, e.clientX, e.clientY)) return;
    cancelAnimationFrame(coasting);
    speed = 0;
    from = { y: e.clientY, top: host.scrollTop };
    last = e.clientY;
  });

  host.addEventListener("pointermove", (e) => {
    if (!from) return;
    const moved = e.clientY - from.y;
    if (!dragging && Math.abs(moved) < SLOP) return;
    if (!dragging) {
      dragging = true;
      host.setPointerCapture(e.pointerId);
      host.classList.add("dragging");
    }
    host.scrollTop = from.top - moved;
    speed = e.clientY - last;
    last = e.clientY;
    e.preventDefault();
  });

  const release = () => {
    if (!from) return;
    from = null;
    if (!dragging) return;
    dragging = false;
    host.classList.remove("dragging");
    coast();
  };
  host.addEventListener("pointerup", release);
  host.addEventListener("pointercancel", release);
  // A drag that ends on a control must not also click it.
  host.addEventListener(
    "click",
    (e) => {
      if (host.classList.contains("dragging")) e.stopPropagation();
    },
    true,
  );
}
