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

/** How many pages each guide frame has been read through, a page read twice
 * counted twice, and whether the next page to land is a step back. */
interface Visits {
  depth: number;
  back: boolean;
}
const visits = new WeakMap<HTMLIFrameElement, Visits>();

/** A page of the auditor's coding guide, read inside the app rather than in a
 * tab of its own, which an app put on the home screen cannot come back from
 * (R-0567). The title row names the page showing by its own first heading,
 * however it was reached. The guide's links stay on the app's own pages, so
 * the frame's page is readable. */
export function guideFrame(
  src: string,
  title: string,
  onTitle: (title: string) => void,
): HTMLIFrameElement {
  const frame = el("iframe");
  frame.title = title;
  frame.src = src;
  const read: Visits = { depth: 0, back: false };
  visits.set(frame, read);
  const landed = () => {
    read.depth += read.back ? -1 : 1;
    read.back = false;
    // an error page has no heading; the row keeps the name the guide was opened by
    onTitle(frame.contentDocument!.querySelector("h1")?.textContent ?? title);
  };
  frame.addEventListener("load", () => {
    landed();
    // a link to a place on the same page lands without loading it
    frame.contentWindow!.addEventListener("hashchange", landed);
  });
  return frame;
}

/** Back one page inside the guide, through every page read in the order read;
 * false on the first, where back leaves the guide. */
export function frameBack(frame: HTMLIFrameElement): boolean {
  const read = visits.get(frame)!;
  if (read.depth <= 1) return false;
  read.back = true;
  frame.contentWindow!.history.back();
  return true;
}
