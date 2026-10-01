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

/** While a phone's keyboard is up, the picture and the speak replies row step
 * aside so the chat keeps the room above the message box, on its newest words
 * (Patrick, 2026-10-01). The keyboard is up when the message box has the focus
 * on a touch screen and the visible area is shorter than the tallest it has
 * been at this width; a hardware keyboard on a tablet shrinks nothing, so
 * nothing folds. */
export const fold = (composer: HTMLElement, screen: HTMLElement, toEnd: () => void): void => {
  const seen = window.visualViewport!;
  let width = seen.width;
  let tall = seen.height;
  const check = () => {
    if (seen.scale > 1) return;
    if (seen.width !== width) [width, tall] = [seen.width, seen.height];
    tall = Math.max(tall, seen.height);
    const up = touch() && document.activeElement === composer && seen.height < tall - KEYBOARD_PX;
    if (up === screen.classList.contains("typing")) return;
    screen.classList.toggle("typing", up);
    if (up) toEnd();
  };
  seen.addEventListener("resize", check);
  composer.addEventListener("focus", check);
  composer.addEventListener("blur", check);
};
