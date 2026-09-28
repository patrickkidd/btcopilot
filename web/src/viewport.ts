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
