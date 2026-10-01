import { still } from "./dom";
import { touch } from "./keyboard";

/** The app fills the part of the screen the reader can see. When a phone's
 * keyboard comes up, iOS leaves the page its full height and slides the
 * keyboard over it, so the chat box and the newest words end up underneath.
 * Here the app takes the visible height and follows the visible area when iOS
 * pans it, so the whole screen shifts up to fit the keyboard the way a native
 * app does. Pinched in, the visible area is a magnifier over the full screen,
 * not a smaller screen, so the app keeps its full height. */
export const fit = (): void => {
  const seen = window.visualViewport!;
  const root = document.documentElement.style;
  const size = () => {
    if (seen.scale > 1) {
      root.removeProperty("--seen-h");
      root.removeProperty("--seen-top");
      return;
    }
    root.setProperty("--seen-h", `${seen.height}px`);
    root.setProperty("--seen-top", `${seen.pageTop}px`);
  };
  seen.addEventListener("resize", size);
  seen.addEventListener("scroll", size);
  size();
};

/** How much shorter than its tallest the visible area is with a keyboard up;
 * a phone's toolbar collapsing is less than this, a keyboard is more. */
const KEYBOARD_PX = 120;

/** How far up from the newest bubble the reader scrolls before the picture folds. */
export const AWAY_PX = 48;

/** What the chat holds of the strip: what it calls as it is scrolled, and what
 * opens the full picture. */
export interface Fold {
  scrolled: (stuck: boolean, away: boolean) => void;
  open: () => void;
}

/** How long the picture takes to fold or open. */
const FOLD_MS = 250;

/** The picture folds to a strip under the title row while a phone's keyboard is
 * up or the reader has scrolled up the chat, and opens again when the keyboard
 * goes down, the reader is back on the newest bubble, or the strip is tapped
 * (Patrick, 2026-10-01, frame A1). The keyboard is up when the message box has
 * the focus on a touch screen and the visible area is shorter than the tallest
 * it has been at this width; a hardware keyboard on a tablet shrinks nothing.
 * The speak replies row steps aside only while the keyboard is up. Returns what
 * the chat calls as it is scrolled — whether it is on its newest bubble, and
 * whether the reader moved up past the strip's threshold — and what opens the
 * full picture. */
export const fold = (
  composer: HTMLElement,
  screen: HTMLElement,
  toEnd: () => void,
): Fold => {
  const seen = window.visualViewport!;
  const pic = screen.querySelector<HTMLElement>(":scope > .pic")!;
  const label = pic.querySelector<HTMLElement>(":scope > .pin-label")!;
  const view = pic.querySelector<HTMLElement>(":scope > .view")!;
  // the strip is the picture's own line slid up into a shorter box, so the one
  // motion is the box's height and how far the line and its name row are slid
  const look = () => ({
    height: `${pic.offsetHeight}px`,
    label: getComputedStyle(label),
    view: getComputedStyle(view).marginTop,
  });
  let width = seen.width;
  let tall = seen.height;
  let typing = false;
  let scrolled = false;
  const set = () => {
    const on = typing || scrolled;
    if (on === screen.classList.contains("folded")) return;
    const a = look();
    const [top, shown] = [a.label.marginTop, a.label.opacity];
    // turned back halfway, it sets out from where it is
    for (const one of [pic, label, view]) for (const motion of one.getAnimations()) motion.cancel();
    screen.classList.toggle("folded", on);
    if (still()) return pic.classList.remove("folding");
    const b = look();
    const timing = { duration: FOLD_MS, easing: "ease" };
    pic.classList.add("folding");
    label.animate([{ marginTop: top, opacity: shown }, { marginTop: b.label.marginTop, opacity: b.label.opacity }], timing);
    view.animate([{ marginTop: a.view }, { marginTop: b.view }], timing);
    pic.animate([{ height: a.height }, { height: b.height }], timing).onfinish = () =>
      pic.classList.remove("folding");
  };
  const check = () => {
    if (seen.scale > 1) return;
    if (seen.width !== width) [width, tall] = [seen.width, seen.height];
    tall = Math.max(tall, seen.height);
    const up = touch() && document.activeElement === composer && seen.height < tall - KEYBOARD_PX;
    if (up === typing) return;
    typing = up;
    screen.classList.toggle("typing", up);
    set();
    if (up) toEnd();
  };
  seen.addEventListener("resize", check);
  composer.addEventListener("focus", check);
  composer.addEventListener("blur", check);
  const open = () => {
    scrolled = false;
    composer.blur();
    set();
  };
  // A mark on the strip is picked as the full picture picks it, and the picture
  // opens with it once the tap has been read where it landed (Patrick,
  // 2026-10-01); a tap anywhere else on the strip only opens it.
  pic.addEventListener(
    "click",
    (e) => {
      if (!screen.classList.contains("folded") || (e.target as Element).closest("[data-target]")) return;
      e.stopPropagation();
      e.preventDefault();
      open();
    },
    true,
  );
  pic.addEventListener("click", () => {
    if (screen.classList.contains("folded")) open();
  });
  return {
    open,
    scrolled: (stuck, away) => {
      if (stuck) scrolled = false;
      else if (away) scrolled = true;
      set();
    },
  };
};
