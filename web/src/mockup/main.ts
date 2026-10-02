import "../theme.css";
import "../drawer.css";
import galleryCss from "./gallery.css?inline";
import { CasePage } from "../casepage";
import { esc } from "../dom";
import type { CaseInput } from "./casefile";
import { FONTS } from "./chrome";
import { FRAMES, frame, frameId, gallery, published, SIZE, type FrameSpec, type View } from "./gallery";
import { build, type Model } from "./model";
import { COINED, scan } from "./words";

/** The gallery's sheet in two parts: the page around the frames, and after
 * the marker the few rules a frame's window needs (the dead controls' looks),
 * which the app's own sheet has no reason to hold. */
const FRAME_CSS_MARK = "/* @frame */";
const [GALLERY_CSS, FRAME_CSS = ""] = galleryCss.split(FRAME_CSS_MARK);

/** The gallery renders from the case files and their page files, inlined by
 * mockup/build.mjs as window.__CASES__. One bundle runs in two places. In the
 * gallery's window it writes the explanation, the decisions, the captions and
 * one iframe per frame, and gives each iframe a document of its own: the app's
 * stylesheet, which frame it is, and this same bundle. In a frame's window the
 * bundle builds that one case, writes the app's own frame (gallery.ts frame)
 * into the body and mounts the case page on it (casepage.ts), so the app's
 * rules on the window's width hold at the frame's own size, and the page
 * scrolls inside the app's screen as on a phone. A critic reaches each frame's
 * window through window.__FRAMES__ once window.__READY__ has settled, and the
 * frame's model and page through that window's __PAGE__. */

export interface FrameMount {
  spec: FrameSpec;
  view: View;
  m: Model;
  page: CasePage;
}

/** Which frame a window is: written into the frame's document by the gallery. */
interface FrameAt {
  id: string;
  view: View;
}

declare global {
  interface Window {
    __CASES__?: CaseInput[];
    __FRAME__?: FrameAt;
    __PAGE__?: FrameMount;
    __FRAMES__?: Record<string, Window>;
    __READY__?: Promise<void>;
    __frameReady?: (id: string, win: Window, faults: string[]) => void;
  }
}

/** The page's own guard over a frame: no theory word, no coined word, every
 * rewording and cut fired, every picture drawn. The words checked are the
 * page's own (the title row, the words in the thread's place and the pinned
 * column); the list screen's rows are the app's own rows and carry the
 * record's codes as the record holds them. */
function faultsOf(m: Model, root: HTMLElement, where: string): string[] {
  const faults: string[] = [];
  const text = [...root.querySelectorAll<HTMLElement>(".titlerow, .chat, .pinned")].map((el) => el.textContent ?? "").join(" ");
  const bad = scan(text);
  if (bad.length) faults.push(`${where}: forbidden words on the page: ${bad.join(", ")}`);
  const coined = scan(text, COINED);
  if (coined.length) faults.push(`${where}: coined words on the page: ${coined.join(", ")}`);
  const stale = m.words.unfired();
  if (stale.length) faults.push(`${where}: rewordings or cuts that matched nothing: ${stale.length}`);
  if (m.household.fault) faults.push(`${where}: household picture: ${m.household.fault}`);
  m.sides.forEach((s) => s.pics.forEach((p) => p.pic.fault && faults.push(`${where}: ${s.label}: ${p.pic.fault}`)));
  // every cluster's pill ends inside the line it is drawn on, so each can be seen and tapped
  root.querySelectorAll<SVGSVGElement>(".pic .view svg").forEach((svg) => {
    const box = svg.getAttribute("viewBox")?.split(/\s+/).map(Number);
    if (!box || box.length !== 4) return;
    svg.querySelectorAll<SVGRectElement>("rect.pill").forEach((r) => {
      const end = Number(r.getAttribute("x")) + Number(r.getAttribute("width"));
      if (end > box[2]) faults.push(`${where}: the ${r.dataset.cluster} pill ends at ${end.toFixed(1)}, past the line's ${box[2]}`);
    });
  });
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

/** A frame's document: the app's font links and stylesheet, the frame part of
 * the gallery's sheet, which frame this is, and the bundle. */
function frameDoc(css: string, bundle: string, at: FrameAt, title: string): string {
  return (
    `<!doctype html><html lang="en"><head><meta charset="utf-8">` +
    `<meta name="viewport" content="width=device-width, initial-scale=1"><title>${esc(title)}</title>` +
    `${FONTS}<style>${css}</style><style>${FRAME_CSS}</style></head><body>` +
    `<script>window.__FRAME__=${JSON.stringify(at)};</script>` +
    `<script type="module">${bundle}</script></body></html>`
  );
}

/** In a frame's window: the one case page this frame shows, mounted as the app mounts its screen. */
function mountFrame(at: FrameAt): void {
  const spec = FRAMES.find((f) => f.id === at.id);
  if (!spec) throw new Error(`no frame ${at.id}`);
  const inputs = window.parent.__CASES__ ?? [];
  const input = inputs.find((c) => c.file.case === spec.case);
  if (!input) throw new Error(`no case ${spec.case} for frame ${at.id}`);
  const m = build(input);
  document.body.innerHTML = frame(m, spec, at.view);
  const root = document.body.querySelector<HTMLElement>(".app");
  if (!root) throw new Error("the frame has no .app");
  const page = new CasePage(root, m.view);
  page.start(published(m, spec.id));
  window.__PAGE__ = { spec, view: at.view, m, page };
  window.parent.__frameReady?.(frameId(spec, at.view), window, faultsOf(m, root, frameId(spec, at.view)));
}

/** In the gallery's window: the words around the frames, and a window for each frame. */
function mountGallery(main: HTMLElement): void {
  // the gallery's words read in the app's fonts, loaded as index.html loads them
  document.head.insertAdjacentHTML("beforeend", FONTS);
  const style = document.createElement("style");
  style.textContent = GALLERY_CSS;
  document.head.append(style);
  const inputs = window.__CASES__ ?? [];
  if (!inputs.length) {
    main.innerHTML = `<p class="lede">No case files were inlined into this page.</p>`;
    return;
  }
  const models = new Map<string, Model>(inputs.map((c) => [c.file.case, build(c)]));
  main.innerHTML = gallery(
    models,
    inputs.map((c) => c.file.case),
  );
  const faults: string[] = [];
  // the gallery's own words: no theory word, no coined word, no caption over forty words
  const text = main.textContent ?? "";
  const bad = scan(text);
  if (bad.length) faults.push(`gallery: forbidden words: ${bad.join(", ")}`);
  const coined = scan(text, COINED);
  if (coined.length) faults.push(`gallery: coined words: ${coined.join(", ")}`);
  main.querySelectorAll("figcaption p").forEach((p, i) => {
    const n = (p.textContent ?? "").trim().split(/\s+/).length;
    if (n > 40) faults.push(`caption ${FRAMES[i]?.id ?? i} has ${n} words`);
  });
  // each frame's window: the app's stylesheet and this bundle, as build.mjs inlined them
  const css = document.getElementById("app-css")?.textContent;
  const bundle = document.getElementById("bundle")?.textContent;
  const windows = [...main.querySelectorAll<HTMLIFrameElement>("iframe[data-frame]")];
  const frames: Record<string, Window> = {};
  window.__FRAMES__ = frames;
  if (!css || !bundle) {
    faults.push("the frames need the built page: node web/mockup/build.mjs inlines the app's stylesheet and the bundle");
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
  // each window drawn no larger than the room its box has; the desktop at half size
  const scale = () => {
    main.querySelectorAll<HTMLElement>(".pv").forEach((pv) => pv.style.setProperty("--scale", String(Math.min(1, pv.clientWidth / SIZE.phone.w))));
    main.querySelectorAll<HTMLElement>(".dv").forEach((dv) => dv.style.setProperty("--scale", String(Math.min(0.5, dv.clientWidth / SIZE.desk.w))));
  };
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
