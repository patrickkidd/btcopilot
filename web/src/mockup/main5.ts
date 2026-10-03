import "../theme.css";
import "../drawer.css";
import FRAME_CSS from "./frame5.css?inline";
import GALLERY_CSS from "./gallery5.css?inline";
import { esc } from "../dom";
import type { CaseInput } from "./casefile";
import { FONTS } from "./chrome";
import { coverage, type Coverage } from "./coverage";
import { FRAMES5, frameId, gallery5, SIZE, type Frame5, type View } from "./gallery5";
import { build, type Model } from "./model";
import { CaseReport, reportFrame, type ReportState } from "./report";
import { COINED, scan } from "./words";

/** Two sheets: the page around the frames (gallery5.css), and the report's own
 * rules inside a frame's window (frame5.css), each its own file since the CSS
 * minifier strips the comment a marker would ride on.
 *
 * Version 5 of the gallery renders from one case (Patrick's record), its page
 * file and its questions file, inlined by mockup/build5.mjs as window.__CASES__.
 * One bundle runs in two places. In the gallery's window it writes the
 * explanation, the decisions, the groups with their tabs and one iframe per
 * frame and view, and gives each iframe a document of its own. In a frame's
 * window the bundle builds the case, writes the report (report.ts) into the
 * body and mounts it. A critic reaches each frame's window through
 * window.__FRAMES__ once window.__READY__ has settled, and the frame's model,
* coverage and report through that window's __REPORT__. */

export interface FrameMount {
  spec: Frame5;
  view: View;
  m: Model;
  cov: Coverage;
  report: CaseReport;
}

interface FrameAt {
  id: string;
  view: View;
}

declare global {
  interface Window {
    __CASES__?: CaseInput[];
    __FRAME__?: FrameAt;
    __REPORT__?: FrameMount;
    __FRAMES__?: Record<string, Window>;
    __READY__?: Promise<void>;
    __frameReady?: (id: string, win: Window, faults: string[]) => void;
  }
}

/** The words a critic flags: a card over eighty visible words is an issue;
 * forty to eighty is prose to optimize later (Patrick, 2026-10-02). */
const PROSE_ISSUE = 80;
const PROSE_WATCH = 40;

const visibleWords = (el: HTMLElement): number => (el.innerText ?? "").trim().split(/\s+/).filter(Boolean).length;

/** The page's own guard over a frame: no theory word, no coined word, every
 * rewording and cut fired, every picture drawn, every pill on its line, no card
 * over the prose line. */
function faultsOf(m: Model, root: HTMLElement, where: string): string[] {
  const faults: string[] = [];
  const text = [...root.querySelectorAll<HTMLElement>(".titlerow, .chat, .pinned, .famout, .rail, .pinsum, .foldrow")].map((el) => el.textContent ?? "").join(" ");
  const bad = scan(text);
  if (bad.length) faults.push(`${where}: forbidden words on the page: ${bad.join(", ")}`);
  const coined = scan(text, COINED);
  if (coined.length) faults.push(`${where}: coined words on the page: ${coined.join(", ")}`);
  const stale = m.words.unfired();
  if (stale.length) faults.push(`${where}: rewordings or cuts that matched nothing: ${stale.length}`);
  if (m.household.fault) faults.push(`${where}: household picture: ${m.household.fault}`);
  m.sides.forEach((s) => s.pics.forEach((p) => p.pic.fault && faults.push(`${where}: ${s.label}: ${p.pic.fault}`)));
  root.querySelectorAll<SVGSVGElement>(".pic .view svg").forEach((svg) => {
    const box = svg.getAttribute("viewBox")?.split(/\s+/).map(Number);
    if (!box || box.length !== 4) return;
    svg.querySelectorAll<SVGRectElement>("rect.pill").forEach((r) => {
      const end = Number(r.getAttribute("x")) + Number(r.getAttribute("width"));
      if (end > box[2]) faults.push(`${where}: the ${r.dataset.cluster} pill ends at ${end.toFixed(1)}, past the line's ${box[2]}`);
    });
  });
  const watch: string[] = [];
  root.querySelectorAll<HTMLElement>(".chat .level").forEach((lv) => {
    const n = visibleWords(lv);
    const id = `level ${lv.dataset.level}`;
    if (n > PROSE_ISSUE) faults.push(`${where}: ${id} shows ${n} words`);
    else if (n > PROSE_WATCH) watch.push(`${id} ${n}`);
  });
  if (watch.length) console.info(`${where}: prose to optimize later: ${watch.join(", ")}`);
  return faults;
}

function banner(main: HTMLElement, faults: string[]): void {
  if (!faults.length) return;
  console.error(faults);
  const p = document.createElement("p");
  p.className = "fault";
  p.textContent = faults.join(" · ");
  main.prepend(p);
}

function frameDoc(css: string, bundle: string, at: FrameAt, title: string): string {
  return (
    `<!doctype html><html lang="en"><head><meta charset="utf-8">` +
    `<meta name="viewport" content="width=device-width, initial-scale=1"><title>${esc(title)}</title>` +
    `${FONTS}<style>${css}</style><style>${FRAME_CSS}</style></head><body>` +
    `<script>window.__FRAME__=${JSON.stringify(at)};</script>` +
    `<script type="module">${bundle}</script></body></html>`
  );
}

/** The state a frame is published in: the spec's, the phone's own where it
 * differs, and "thin" for the reading's line that has not enough to stand on. */
function stateOf(spec: Frame5, view: View, cov: Coverage): ReportState {
  const s: ReportState = { ...(spec.state ?? {}), ...(view === "phone" ? (spec.phoneState ?? {}) : {}) };
  if (s.part === "thin") s.part = cov.parts.find((p) => !p.off && !p.cover.enough)?.id ?? cov.parts.find((p) => !p.off)?.id;
  return s;
}

/** In a frame's window: the one report this frame shows, mounted as the app mounts its screen. */
function mountFrame(at: FrameAt): void {
  const spec = FRAMES5.find((f) => f.id === at.id);
  if (!spec) throw new Error(`no frame ${at.id}`);
  const input = (window.parent.__CASES__ ?? [])[0];
  if (!input) throw new Error(`no case for frame ${at.id}`);
  const m = build(input);
  const cov = coverage(m, input.questions);
  const opts = { ...spec.opts, desk: at.view === "desk" };
  const id = frameId(spec, at.view);
  document.body.innerHTML = reportFrame(m, cov, opts, ` data-frame="${id}" data-case="${esc(m.file.case)}" data-view="${at.view}"`);
  const root = document.body.querySelector<HTMLElement>(".app");
  if (!root) throw new Error("the frame has no .app");
  const report = new CaseReport(root, m, cov, opts);
  report.start(stateOf(spec, at.view, cov));
  window.__REPORT__ = { spec, view: at.view, m, cov, report };
  window.parent.__frameReady?.(id, window, faultsOf(m, root, id));
}

/** In the gallery's window: the words around the frames, the tabs, and a window for each frame. */
function mountGallery(main: HTMLElement): void {
  document.head.insertAdjacentHTML("beforeend", FONTS);
  const style = document.createElement("style");
  style.textContent = GALLERY_CSS;
  document.head.append(style);
  const input = (window.__CASES__ ?? [])[0];
  if (!input) {
    main.innerHTML = `<p class="lede">No case files were inlined into this page.</p>`;
    return;
  }
  const m = build(input);
  const cov = coverage(m, input.questions);
  main.innerHTML = gallery5(m, cov);
  const faults: string[] = [];
  const text = main.textContent ?? "";
  const bad = scan(text);
  if (bad.length) faults.push(`gallery: forbidden words: ${bad.join(", ")}`);
  const coined = scan(text, COINED);
  if (coined.length) faults.push(`gallery: coined words: ${coined.join(", ")}`);
  main.querySelectorAll<HTMLElement>("figcaption p").forEach((p) => {
    const n = (p.textContent ?? "").trim().split(/\s+/).length;
    if (n > 25) faults.push(`caption ${p.closest<HTMLElement>(".pane")?.dataset.pane ?? "?"} has ${n} words`);
  });
  // the tabs: one frame of a group on screen at a time, phone and desktop side by side
  const show = (id: string) => {
    const pane = main.querySelector<HTMLElement>(`.pane[data-pane="${id}"]`);
    const section = pane?.closest("section");
    if (!pane || !section) return;
    section.querySelectorAll<HTMLElement>(".pane").forEach((p) => p.classList.toggle("on", p === pane));
    section.querySelectorAll<HTMLElement>(".tabs5 [data-pane]").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.pane === id)));
    scale();
  };
  main.addEventListener("click", (e) => {
    const tab = (e.target as HTMLElement).closest<HTMLElement>(".tabs5 [data-pane]");
    if (tab?.dataset.pane) {
      show(tab.dataset.pane);
      history.replaceState(null, "", `#${tab.dataset.pane}`);
    }
  });
  const css = document.getElementById("app-css")?.textContent;
  const bundle = document.getElementById("bundle")?.textContent;
  const windows = [...main.querySelectorAll<HTMLIFrameElement>("iframe[data-frame]")];
  const frames: Record<string, Window> = {};
  window.__FRAMES__ = frames;
  if (!css || !bundle) {
    faults.push("the frames need the built page: node web/mockup/build5.mjs inlines the app's stylesheet and the bundle");
    banner(main, faults);
    window.__READY__ = Promise.resolve();
    return;
  }
  let left = windows.length;
  window.__READY__ = new Promise<void>((resolve) => {
    window.__frameReady = (id, win, found) => {
      frames[id] = win;
      faults.push(...found);
      if (--left === 0) {
        banner(main, faults);
        resolve();
      }
    };
  });
  windows.forEach((w) => {
    const [id, v] = w.dataset.frame!.split("-");
    const view: View = v === "d" ? "desk" : "phone";
    w.srcdoc = frameDoc(css, bundle, { id, view }, w.title);
  });
  // each window at its own size, drawn smaller only where the page gives it less room
  const scale = () => {
    main.querySelectorAll<HTMLElement>(".pane.on .pv").forEach((pv) => pv.style.setProperty("--scale", String(Math.min(1, pv.clientWidth / SIZE.phone.w))));
    main.querySelectorAll<HTMLElement>(".pane.on .dv").forEach((dv) => dv.style.setProperty("--scale", String(Math.min(1, dv.clientWidth / SIZE.desk.w))));
  };
  const hash = location.hash.replace(/^#/, "");
  if (hash && FRAMES5.some((f) => f.id === hash)) show(hash);
  scale();
  window.addEventListener("resize", scale);
}

const at = window.__FRAME__;
if (at) mountFrame(at);
else {
  const main = document.getElementById("gallery");
  if (!main) throw new Error("no #gallery to render into");
  mountGallery(main);
}
