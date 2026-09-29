import "./drawer.css";
import { askedChip, chipOf } from "./chips";
import { CLUSTER, closeX, esc, pathRow, slideOver, stepBtn } from "./dom";
import { NAME, type Layout } from "./diagram";
import { when, Told } from "./snapshots";
import type { Case, Chip, Timeline } from "./types";

/** The play-by-play drawer: a real drill-down that slides over the timeline and
 * the chat (R-0542). The path row with the close button at its right, the
 * coach's point, the years line, the picture, then the caption and the controls. Tapped through by hand with Back,
 * the dots and Next; it never plays itself. The message box is covered. */

enum Act {
  Back = "back",
  Next = "next",
  Dot = "dot",
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
  const cx = Math.min(Math.max(X(told.steps[i].t), 40), 350);
  s += `<text class="wlab" x="${f(cx)}" y="15" text-anchor="middle">${esc(told.steps[i].date)}</text>`;
  s += `<text class="wyr" x="${x0}" y="57">${Math.floor(t0)}</text>`;
  s += `<text class="wyr" x="${x1}" y="57" text-anchor="end">${Math.floor(t1)}</text>`;
  return s + "</svg>";
}

/** The controls and the caption under the picture for snapshot `i`. The
 * question of a play kept as a message is the amber chip that answers it
 * (R-0587); a play kept nowhere has no message to point at. */
export function below(told: Told, i: number, statement: number | null): string {
  const n = told.length;
  const shot = told.shot(i);
  const dots = Array.from(
    { length: n },
    (_, j) =>
      `<button class="dot${j === i ? " on" : ""}" type="button" data-act="${Act.Dot}" data-i="${j}" aria-label="Snapshot ${j + 1}"${j === i ? ' aria-current="step"' : ""}></button>`,
  ).join("");
  return (
    `<div class="step">${stepBtn("‹ Back", `data-act="${Act.Back}"`, i === 0)}` +
    `<div class="dots">${dots}</div><span class="count">${i + 1} of ${n}</span>` +
    `${stepBtn("Next ›", `data-act="${Act.Next}"`, i === n - 1)}</div>` +
    `<div class="cap" aria-live="polite"><div class="when"><span class="date">${esc(shot.date)}</span>` +
    (shot.gap ? `<span class="gap">${esc(shot.gap)}</span>` : "") +
    `</div><p class="fact">${esc(shot.fact)}</p>` +
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
 * path's cluster step goes, then the coach's point. */
export const head = (told: Told, years: string) =>
  `<div class="path">${pathRow(["Timeline", years, "explain"])}</div>` +
  closeX(` data-step="${CLUSTER}"`) +
  pointLine(told);

export const pictureHeight = (natural: number, room: number, captions: number[], floor: number) =>
  Math.max(Math.min(natural, floor), Math.min(natural, room - Math.max(...captions)));

/** Decided 2026-09-27: the shrink stops where labels would go under 13px,
 * shapes under 36px or the family's margin under 20px; below that the drawer
 * scrolls. A row already shrunk to fit the phone's width stays as it is. */
const LEAST = { label: 13, shape: 36, margin: 20 };
export const leastScale = (L: Layout, padding: number) =>
  Math.max(LEAST.label / NAME, LEAST.shape / L.w, (LEAST.margin - padding) / L.my);

export class Drawer {
  private told: Told | null = null;
  private statement: number | null = null;
  private i = 0;
  private height: number | null = null;
  private edge = 0;

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
    this.told = new Told(tl, told);
    this.statement = statement;
    this.i = 0;
    this.height = null;
    const years = tl.clusters.find((c) => c.id === told.cluster_id)?.label ?? spanOf(this.told);
    this.panel.innerHTML =
      head(this.told, years) +
      `<div class="lv"><div class="wire"></div><div class="draw"></div><div class="scroll"></div></div>`;
    slideOver(this.panel, true);
    this.render();
  }

  close(): void {
    slideOver(this.panel, false);
  }

  /** Put away from outside, as its cross puts it away. */
  leave(): void {
    if (this.told && this.panel.classList.contains("in")) this.back(CLUSTER, this.told.eventIds);
  }

  private render(): void {
    const told = this.told!;
    const q = (sel: string) => this.panel.querySelector<HTMLElement>(sel)!;
    q(".wire").innerHTML = yearsLine(told.tl, told, this.i);
    q(".draw").innerHTML = told.shot(this.i).svg;
    q(".scroll").innerHTML = below(told, this.i, this.statement);
    this.fit();
  }

  private fit(): void {
    const told = this.told!;
    const lv = this.panel.querySelector<HTMLElement>(".lv")!;
    const draw = lv.querySelector<HTMLElement>(".draw")!;
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
      const natural = (lv.clientWidth * told.layout.h) / told.layout.vw;
      const room = lv.clientHeight - lv.querySelector<HTMLElement>(".wire")!.offsetHeight - this.edge;
      this.height = pictureHeight(natural, room, captions, told.layout.h * leastScale(told.layout, padding));
    }
    draw.style.height = `${this.height + this.edge}px`;
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
    else if (act === Act.Dot) this.i = Number(b.dataset.i);
    this.render();
    // a keyboard tap keeps its place
    if ((e as MouseEvent).detail === 0)
      this.panel.querySelector<HTMLElement>(`[data-act="${act}"]:not([disabled])`)?.focus();
  }
}
