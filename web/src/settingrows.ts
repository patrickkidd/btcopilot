import { el, esc } from "./dom";

/** The account view's rows, which the coding guidelines are drawn with too. */

export function group(rows: HTMLElement[], head?: string): HTMLElement {
  const wrap = el("div");
  if (head) wrap.append(el("div", "sn-hd", esc(head)));
  const box = el("div", "sn-grp");
  box.append(...rows);
  wrap.append(box);
  return wrap;
}

export function tapRow(label: string, value: string, go: () => void): HTMLElement {
  const row = el("div", "sn-row push");
  row.append(
    el("div", "sn-lbl", esc(label)),
    el("div", "sn-val", esc(value)),
    el("div", "sn-chev", "›"),
  );
  row.addEventListener("click", go);
  return row;
}

/** A page of the auditor's coding guide, read inside the app rather than in a
 * tab of its own, which an app put on the home screen cannot come back from
 * (R-0567). */
export function guideFrame(src: string, title: string): HTMLIFrameElement {
  const frame = el("iframe");
  frame.title = title;
  frame.src = src;
  return frame;
}

/** Back one page inside the guide when a link in it was followed; false on
 * the page it opened on, where back leaves the guide. Its links stay on the
 * app's own pages, so the frame's address is readable. */
export function frameBack(frame: HTMLIFrameElement): boolean {
  const view = frame.contentWindow!;
  if (view.location.href === new URL(frame.getAttribute("src")!, location.href).href) return false;
  view.history.back();
  return true;
}
