import "./drawer.css";
import { askedChip, chipOf } from "./chips";
import { CLUSTER, closeX, esc, flash, pathRow, slideOver, stepBtn, still } from "./dom";
import { leastScale } from "./diagram";
import { clusterStep } from "./picture";
import { kindForms, withKind } from "./rows";
import { family, familyStart, when, Told } from "./snapshots";
import type { Case, Chip, Timeline } from "./types";

/** The play-by-play drawer: a real drill-down that slides over the timeline and
 * the chat (R-0542). The path row with the close button at its right, the
 * coach's point, the years line, the picture, then the caption and the controls. Tapped through by hand with Back
 * and Next, or straight to a step by its event on the years line, the one way
 * in at random (Patrick, 2026-10-03); the dots only say where the reader is. It
 * never plays itself. The message box is covered. */

enum Act {
  Back = "back",
  Next = "next",
  Jump = "jump",
}

const f = (v: number) => v.toFixed(1);

/** The cluster's years on its own line: everything from those years dimmed,
 * this snapshot's events ringed, earlier ones solid, later ones hollow, and the
 * gap since the last snapshot drawn along the line. */
export function yearsLine(tl: Timeline, told: Told, i: number): string {
  const x0 = 26;
  const x1 = 364;
  const y = 34;
  const dated = told.eventIds.flatMap((id) => {
    const e = tl.events.find((e) => e.id === id);
    return e?.dateTime ? [{ id, t: when(e.dateTime) }] : [];
  });
  const ts = dated.map((e) => e.t);
  const t0 = Math.min(...ts);
  const t1 = Math.max(...ts, t0 + 1 / 12);
  const X = (t: number) => x0 + ((x1 - x0) * (t - t0)) / (t1 - t0);
  const own = new Map<number, number>();
  told.told.snapshots.forEach((s, j) => s.event_ids.forEach((id) => own.set(id, j)));
  let s = `<svg viewBox="0 0 390 62" aria-hidden="true"><line class="wl" x1="${x0}" y1="${y}" x2="${x1}" y2="${y}"/>`;
  if (i > 0)
    s += `<line class="wgap" x1="${f(X(told.steps[i - 1].t))}" y1="${y}" x2="${f(X(told.steps[i].t))}" y2="${y}"/>`;
  dated.forEach((e) => {
    const x = f(X(e.t));
    const j = own.get(e.id);
    if (j === undefined) s += `<circle class="wd dim" cx="${x}" cy="${y}" r="3.6"/>`;
    else if (j < i) s += `<circle class="wd" cx="${x}" cy="${y}" r="5"/>`;
    else if (j > i) s += `<circle class="wahead" cx="${x}" cy="${y}" r="4.4"/>`;
    else s += `<circle class="wring" cx="${x}" cy="${y}" r="10"/><circle class="wnow" cx="${x}" cy="${y}" r="6.5"/>`;
  });
  // each step's events answer a tap across the line's height, halfway to the
  // events on either side
  const hits = dated
    .filter((e) => own.has(e.id))
    .map((e) => ({ x: X(e.t), j: own.get(e.id)! }))
    .sort((a, b) => a.x - b.x);
  hits.forEach((h, k) => {
    const a = k ? (hits[k - 1].x + h.x) / 2 : 0;
    const b = k < hits.length - 1 ? (h.x + hits[k + 1].x) / 2 : 390;
    s +=
      `<rect class="whit" x="${f(a)}" y="0" width="${f(b - a)}" height="62" data-act="${Act.Jump}" data-i="${h.j}"/>`;
  });
  // the date stays whole inside the frame: a mono character is about 0.6 of the 12px font wide
  const date = told.steps[i].date;
  const half = date.length * 3.6 + 4;
  const cx = Math.min(Math.max(X(told.steps[i].t), half), 390 - half);
  s += `<text class="wlab" x="${f(cx)}" y="15" text-anchor="middle">${esc(date)}</text>`;
  s += `<text class="wyr" x="${x0}" y="57">${Math.floor(t0)}</text>`;
  s += `<text class="wyr" x="${x1}" y="57" text-anchor="end">${Math.floor(t1)}</text>`;
  return s + "</svg>";
}

/** What can say the kind of each of snapshot `i`'s events (Patrick, 2026-10-03). */
const saying = (told: Told, i: number) =>
  told.told.snapshots[i].event_ids.map((id) => told.tl.events.find((e) => e.id === id)!).flatMap(kindForms);

/** The controls and the caption under the picture for snapshot `i`. The
 * question of a play kept as a message is the amber chip that answers it
 * (R-0587); a play kept nowhere has no message to point at. */
export function below(told: Told, i: number, statement: number | null): string {
  const n = told.length;
  const back = stepBtn("‹ Back", `data-act="${Act.Back}"`, i === 0);
  const next = stepBtn("Next ›", `data-act="${Act.Next}"`, i === n - 1);
  // the whole family's top line says where the reader is, so it has no dots (R-0742)
  if (told.whole) return `<div class="step">${back}${next}</div>`;
  const shot = told.shot(i);
  const dots = Array.from(
    { length: n },
    (_, j) =>
      `<span class="dot${j === i ? " on" : ""}"></span>`,
  ).join("");
  return (
    `<div class="step">${back}` +
    `<div class="dots" aria-hidden="true">${dots}</div>` +
    `${next}</div>` +
    `<div class="cap" aria-live="polite"><div class="when"><span class="date">${esc(shot.date)}</span>` +
    (shot.gap ? `<span class="gap">${esc(shot.gap)}</span>` : "") +
    `</div><p class="fact">${withKind(shot.fact, saying(told, i))}</p>` +
    (shot.guess ? `<p class="guess">${esc(shot.guess)}</p>` : "") +
    (shot.question
      ? `<p class="ask">${statement === null ? esc(shot.question) : askedChip(statement, shot.question)}</p>`
      : "") +
    `</div>`
  );
}

/** Ruled 2026-09-27 (Q6): the picture shrinks so the longest caption of the
 * case fits below it, down to a floor; below the floor the whole drawer
 * scrolls. One height per phone and case, so nothing moves between snapshots. */
/** The coach's point over the drawer; a case nobody told has none. */
export const pointLine = (told: Told) =>
  told.told.point ? `<div class="point">${esc(told.told.point)}</div>` : "";

/** The years a case nobody told spans, as a cluster's label writes them. */
const spanOf = (told: Told) => {
  const [a, b] = [told.steps[0], told.steps[told.steps.length - 1]].map((s) => Math.floor(s.t));
  return a === b ? String(a) : `${a}–${b}`;
};

/** The drawer's top: the path row, the close button, which goes where the
 * path's cluster step goes, then the coach's point. The whole family hangs off
 * the timeline itself, and its close goes back there. */
export const head = (told: Told, cluster: string) =>
  told.whole
    ? `<div class="path">${pathRow(["Timeline", "Family"])}</div>` + closeX(` data-step="0"`) + `<div class="when"></div>`
    : `<div class="path">${pathRow(["Timeline", cluster, "explain"])}</div>` +
      closeX(` data-step="${CLUSTER}"`) +
      pointLine(told);

/** The whole family's top line: what happened at the step, in the events' own
 * words; its date is the label over the years line, said once. */
export const topLine = (told: Told, i: number) => {
  const snap = told.told.snapshots[i];
  return snap.fact ? `<span class="words">${withKind(snap.fact, saying(told, i))}</span>` : "";
};

export const pictureHeight = (natural: number, room: number, captions: number[], floor: number) =>
  Math.max(Math.min(natural, floor), Math.min(natural, room - Math.max(...captions)));

/** Where a drawn person and their words rest across the drawing, in the
 * frame's scroll coordinates: their place after a step's slide, never where
 * the slide has them now. */
function span(frame: HTMLElement, svg: SVGSVGElement, id: string): [number, number] {
  return reach(frame, svg, svg.querySelectorAll<SVGGraphicsElement>(`.p[data-id="${CSS.escape(id)}"], .pt[data-id="${CSS.escape(id)}"]`));
}

/** Where the marks `marks` rest across the drawing, as `span` reads a person. */
function reach(frame: HTMLElement, svg: SVGSVGElement, marks: Iterable<SVGGraphicsElement>): [number, number] {
  const m = svg.getScreenCTM()!;
  const from = frame.getBoundingClientRect().left + frame.clientLeft - frame.scrollLeft;
  let lo = Infinity;
  let hi = -Infinity;
  [...marks].forEach((g) => {
    const b = g.getBBox();
    if (!b.width) return;
    const slid = g.parentElement!.classList.contains("slid") ? (g.parentElement as unknown as SVGGraphicsElement).transform.baseVal.consolidate() : null;
    const dx = slid ? slid.matrix.e : 0;
    lo = Math.min(lo, m.a * (b.x + dx) + m.e - from);
    hi = Math.max(hi, m.a * (b.x + b.width + dx) + m.e - from);
  });
  return [lo, hi];
}

/** A picture wider than its frame, put on the people `ids` with their names
 * and ages whole inside the frame; when they reach wider than it, on `who`
 * and their words, as near the rest as that allows (R-0759). The play-by-play,
 * the Family drawer and the case report's pictures all open this way. */
export function frameOn(frame: HTMLElement, ids: string[], who: string, glide: boolean): void {
  if (frame.scrollWidth <= frame.clientWidth) return;
  const svg = frame.querySelector<SVGSVGElement>("svg")!;
  const spans = ids.map((id) => span(frame, svg, id));
  const lo = Math.min(...spans.map((s) => s[0]));
  const hi = Math.max(...spans.map((s) => s[1]));
  const w = frame.clientWidth;
  const [wl, wh] = span(frame, svg, who);
  const mid = hi - lo <= w ? (lo + hi) / 2 : Math.min(Math.max((lo + hi) / 2, wh - w / 2), wl + w / 2);
  const end = frame.scrollWidth - w;
  const clamp = (v: number, a: number, b: number) => Math.min(Math.max(v, a), b);
  const want = clamp(mid - w / 2, 0, end);
  // anywhere the step's people (or, when they reach wider, its person) stay
  // whole, the frame lands where it cuts the fewest other names, nearest
  // where it was headed: a name at the drawing's edge gets room (R-0759)
  const [a, b] = hi - lo <= w ? [hi - w, lo] : [wh - w, wl];
  // never more than a sixth of the frame from where it was headed, so the
  // people it was headed for stay near its middle
  const [from, to] = [clamp(Math.max(Math.min(a, b), want - w / 6), 0, end), clamp(Math.min(Math.max(a, b), want + w / 6), 0, end)];
  const names = [
    ...[...svg.querySelectorAll<SVGGElement>(".p[data-id]")].map((g) => span(frame, svg, g.dataset.id!)),
    ...[...svg.querySelectorAll<SVGTextElement>("text.evw")].map((t) => reach(frame, svg, [t])),
  ];
  const cuts = (l: number) => names.filter(([p, q]) => (p < l - 0.5 && l + 0.5 < q) || (p < l + w - 0.5 && l + w + 0.5 < q)).length;
  const left = [want, ...names.flatMap(([p, q]) => [p, q - w])]
    .map((l) => clamp(l, from, to))
    .reduce((best, l) => (cuts(l) < cuts(best) || (cuts(l) === cuts(best) && Math.abs(l - want) < Math.abs(best - want)) ? l : best));
  pan(frame, Math.round(left), glide && !still());
}

/** How long the frame takes to travel to a step's people: about 1,200 px a
 * second, never under half a second nor over two, eased in and out, from where
 * it stood to exactly where it lands, never past it (R-0778). */
export const PAN = {
  ms: (px: number) => Math.min(Math.max(Math.abs(px) / 1.2, 500), 2000),
  ease: (t: number) => (t < 0.5 ? 4 * t ** 3 : 1 - (2 - 2 * t) ** 3 / 2),
};
const panning = new WeakMap<HTMLElement, number>();

function pan(frame: HTMLElement, to: number, glide: boolean): void {
  if (panning.has(frame)) cancelAnimationFrame(panning.get(frame)!);
  const from = frame.scrollLeft;
  if (!glide || from === to) {
    frame.scrollLeft = to;
    return;
  }
  // a reader who takes the frame in hand stops it
  if (!panning.has(frame))
    for (const kind of ["pointerdown", "touchstart", "wheel"])
      frame.addEventListener(kind, () => cancelAnimationFrame(panning.get(frame)!), { passive: true });
  const t0 = performance.now();
  const ms = PAN.ms(to - from);
  const tick = (now: number) => {
    const t = Math.min((now - t0) / ms, 1);
    frame.scrollLeft = from + (to - from) * PAN.ease(t);
    if (t < 1) panning.set(frame, requestAnimationFrame(tick));
  };
  panning.set(frame, requestAnimationFrame(tick));
}

export class Drawer {
  private told: Told | null = null;
  private statement: number | null = null;
  private i = 0;
  private height: number | null = null;
  private edge = 0;
  private scale = 1;

  constructor(
    readonly panel: HTMLElement,
    /** A tap on the path row: which step of it, the timeline first, and the
     * events the case is about. */
    private readonly back: (step: number, events: number[]) => void,
    /** A tap on the question's chip, once the drawer has gone back to the
     * cluster, so the message box it goes into is in sight. */
    private readonly answer: (chip: Chip) => void,
  ) {
    panel.classList.add("pbp");
    panel.hidden = true;
    panel.addEventListener("click", (e) => this.tap(e));
  }

  /** Slide the drawer in on the first snapshot of a told case, and the message
   * it was kept as. */
  open(tl: Timeline, told: Case, statement: number | null): void {
    this.show(new Told(tl, told), statement, 0);
  }

  /** Slide the drawer in on the whole family at the first date holding more
   * than births; Back and Next step through its history (R-0742). */
  openFamily(tl: Timeline): void {
    const c = family(tl);
    this.show(new Told(tl, c, true), null, familyStart(tl, c));
  }

  /** Whether the whole family is up. */
  family(): boolean {
    return this.panel.classList.contains("in") && !!this.told?.whole;
  }

  private show(told: Told, statement: number | null, i: number): void {
    this.told = told;
    this.statement = statement;
    this.i = i;
    this.height = null;
    const cluster = told.tl.clusters.find((c) => c.id === told.told.cluster_id);
    this.panel.classList.toggle("whole", told.whole);
    this.panel.innerHTML =
      head(this.told, cluster ? clusterStep(cluster) : spanOf(told)) +
      `<div class="lv"><div class="wire"></div><div class="draw"></div><div class="scroll"></div></div>`;
    slideOver(this.panel, true);
    this.render(false);
    this.onMoved?.();
  }

  close(): void {
    slideOver(this.panel, false);
    this.onMoved?.();
  }

  /** Told when the drawer comes up or goes down, so the address says so. */
  onMoved?: () => void;

  /** The message whose telling is up, while the drawer is. */
  at(): number | null {
    return this.panel.classList.contains("in") && !this.told?.whole ? this.statement : null;
  }

  /** One snapshot of the telling that is up, its caption lit the way a
   * message is lit in the thread (R-0055). */
  to(step: number): void {
    if (!this.told) return;
    this.i = Math.min(Math.max(step, 0), this.told.length - 1);
    this.render();
    flash(this.panel.querySelector<HTMLElement>(".cap")!);
  }

  /** Put away from outside, as its cross puts it away. */
  leave(): void {
    if (this.told && this.panel.classList.contains("in")) this.back(this.told.whole ? 0 : CLUSTER, this.told.eventIds);
  }

  /** `glide`: the frame travels to the step's person; on opening it is put
   * there at once, so it never opens on the empty width between. */
  private render(glide = true): void {
    const told = this.told!;
    const q = (sel: string) => this.panel.querySelector<HTMLElement>(sel)!;
    q(".wire").innerHTML = yearsLine(told.tl, told, this.i);
    if (told.whole) q(".when").innerHTML = topLine(told, this.i);
    const shot = told.shot(this.i);
    const draw = q(".draw");
    // the new drawing is the same width, so the frame sets off from where it stood
    const was = draw.scrollLeft;
    draw.innerHTML = shot.svg;
    q(".scroll").innerHTML = below(told, this.i, this.statement);
    this.fit();
    draw.scrollLeft = was;
    const lit = [...draw.querySelectorAll<SVGElement>('.hl.now[data-mark^="hl:"]')].map((m) => m.dataset.mark!.slice(3));
    draw.dataset.who = shot.who;
    // the whole family opens on the record's own person, at every width (R-0759)
    if (told.whole && !glide) frameOn(draw, [told.cast.index], told.cast.index, false);
    else frameOn(draw, lit.length ? lit : [shot.who], shot.who, glide);
  }

  private fit(): void {
    const told = this.told!;
    const lv = this.panel.querySelector<HTMLElement>(".lv")!;
    const draw = lv.querySelector<HTMLElement>(".draw")!;
    const L = told.layout;
    if (this.height === null) {
      const sc = lv.querySelector<HTMLElement>(".scroll")!;
      const keep = sc.innerHTML;
      const captions = told.steps.map((_, j) => {
        sc.innerHTML = below(told, j, this.statement);
        return sc.offsetHeight;
      });
      sc.innerHTML = keep;
      // the picture's box keeps its own padding and rule above the drawing
      const style = getComputedStyle(draw);
      const padding = parseFloat(style.paddingTop);
      this.edge = padding + parseFloat(style.paddingBottom) + parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth);
      const least = leastScale(L, padding);
      this.scale = Math.max(lv.clientWidth / L.vw, least);
      const room = lv.clientHeight - lv.querySelector<HTMLElement>(".wire")!.offsetHeight - this.edge;
      this.height = pictureHeight(L.h * this.scale, room, captions, L.h * least);
      this.scale = Math.min(this.scale, this.height / L.h);
    }
    draw.style.height = `${this.height + this.edge}px`;
    const svg = draw.querySelector<SVGSVGElement>("svg")!;
    svg.style.width = L.vw * this.scale > lv.clientWidth ? `${Math.ceil(L.vw * this.scale)}px` : "";
  }

  private tap(e: Event): void {
    const step = (e.target as Element).closest<HTMLElement>("[data-step]");
    if (step) return this.back(Number(step.dataset.step), this.told!.eventIds);
    const chip = (e.target as Element).closest<HTMLElement>("button.chip[data-kind]");
    if (chip) {
      this.back(CLUSTER, this.told!.eventIds);
      return this.answer(chipOf(chip));
    }
    const b = (e.target as Element).closest<HTMLElement>("[data-act]");
    if (!b || !this.told) return;
    const act = b.dataset.act as Act;
    const n = this.told.length;
    if (act === Act.Next) this.i = Math.min(this.i + 1, n - 1);
    else if (act === Act.Back) this.i = Math.max(this.i - 1, 0);
    else if (act === Act.Jump) this.i = Number(b.dataset.i);
    this.render();
    // a keyboard tap keeps its place
    if ((e as MouseEvent).detail === 0)
      this.panel.querySelector<HTMLElement>(`[data-act="${act}"]:not([disabled])`)?.focus();
  }
}
