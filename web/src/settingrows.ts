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

/** The guide's links stay on the app's own pages, so the frame's address is
 * readable: on the page it opened on, or on one a link led to. */
const opened = (frame: HTMLIFrameElement): boolean =>
  frame.contentWindow!.location.href === new URL(frame.getAttribute("src")!, location.href).href;

/** A page of the auditor's coding guide, read inside the app rather than in a
 * tab of its own, which an app put on the home screen cannot come back from
 * (R-0567). The title row names the page showing: the name it was opened by,
 * and each page a link in it leads to by that page's own title. */
export function guideFrame(
  src: string,
  title: string,
  onTitle: (title: string) => void,
): HTMLIFrameElement {
  const frame = el("iframe");
  frame.title = title;
  frame.src = src;
  frame.addEventListener("load", () =>
    onTitle(opened(frame) ? title : frame.contentDocument!.title),
  );
  return frame;
}

/** Back one page inside the guide when a link in it was followed; false on
 * the page it opened on, where back leaves the guide. */
export function frameBack(frame: HTMLIFrameElement): boolean {
  if (opened(frame)) return false;
  frame.contentWindow!.history.back();
  return true;
}
