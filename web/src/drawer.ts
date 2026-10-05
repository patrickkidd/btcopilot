import "./drawer.css";
import { askedChip, chipOf } from "./chips";
import { CLUSTER, closeX, esc, flash, pathRow, slideOver, stepBtn } from "./dom";
import { LEAST, NAME, type Layout } from "./diagram";
import { kindForms, withKind } from "./rows";
import { family, when, Told } from "./snapshots";
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
export const head = (told: Told, years: string) =>
  told.whole
    ? `<div class="path">${pathRow(["Timeline", "Family"])}</div>` + closeX(` data-step="0"`) + `<div class="when"></div>`
    : `<div class="path">${pathRow(["Timeline", years, "explain"])}</div>` +
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

/** Decided 2026-09-27: the shrink stops where labels would go under 13px,
 * shapes under 36px or the family's margin under 20px; below that the drawer
 * scrolls. A row already shrunk to fit the phone's width stays as it is.
 * Re-ruled 2026-10-04: a picture wider than the drawer keeps this size and
 * scrolls sideways in its own frame. */
export const leastScale = (L: Layout, padding: number) =>
  Math.max(LEAST.label / NAME, LEAST.shape / L.w, (LEAST.margin - padding) / L.my);

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

  /** Slide the drawer in on the whole family as the record stands today, its
   * last step; Back steps into its history (R-0742). */
  openFamily(tl: Timeline): void {
    const told = new Told(tl, family(tl), true);
    this.show(told, null, told.length - 1);
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
    const years = told.tl.clusters.find((c) => c.id === told.told.cluster_id)?.label ?? spanOf(told);
    this.panel.classList.toggle("whole", told.whole);
    this.panel.innerHTML =
      head(this.told, years) +
      `<div class="lv"><div class="wire"></div><div class="draw"></div><div class="scroll"></div></div>`;
    slideOver(this.panel, true);
    this.render();
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

  private render(): void {
    const told = this.told!;
    const q = (sel: string) => this.panel.querySelector<HTMLElement>(sel)!;
    q(".wire").innerHTML = yearsLine(told.tl, told, this.i);
    if (told.whole) q(".when").innerHTML = topLine(told, this.i);
    const shot = told.shot(this.i);
    q(".draw").innerHTML = shot.svg;
    q(".scroll").innerHTML = below(told, this.i, this.statement);
    this.fit();
    this.centre(shot.who);
  }

  /** The person the step is about in the middle of the frame, when the picture is wider than it. */
  private centre(who: string): void {
    const draw = this.panel.querySelector<HTMLElement>(".draw")!;
    if (draw.scrollWidth <= draw.clientWidth) return;
    draw.scrollTo({ left: this.told!.layout.x[who] * this.scale - draw.clientWidth / 2, behavior: "smooth" });
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
