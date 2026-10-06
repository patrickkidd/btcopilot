import "./drawer.css";
import type { Books } from "./books";
import { book } from "./case";
import { askedChip, chipOf } from "./chips";
import { CLUSTER, closeX, esc, flash, pathRow, slideOver, stepBtn, still } from "./dom";
import { leastScale, type Layout } from "./diagram";
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
/** The Family view's book: what the family diagram is for (R-0779). */
export const FAMILY_BOOK = "family";
const FAMILY_TITLE = "What the family diagram is for";

/** The Family view's path: whose family a tap put the picture on, after
 * "Family", which goes back to the step's own people (R-0779). */
const familyPath = (whose: string | null) =>
  pathRow(whose ? ["Timeline", "Family", `${whose}'s family`] : ["Timeline", "Family"]) + book(FAMILY_BOOK, FAMILY_TITLE);

export const head = (told: Told, cluster: string) =>
  told.whole
    ? `<div class="path">${familyPath(null)}</div>` + closeX(` data-step="0"`) + `<div class="when"></div><p class="also"></p>`
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
export function frameOn(
  frame: HTMLElement,
  ids: string[],
  who: string,
  glide: boolean,
  marks: SVGGraphicsElement[] = [],
  /** Others the frame holds too, but only when everyone fits. */
  also: string[] = [],
  /** Stay where it stands while `ids` and their `marks` are all in sight. */
  stay = false,
): void {
  if (frame.scrollWidth <= frame.clientWidth) return;
  const svg = frame.querySelector<SVGSVGElement>("svg")!;
  const w = frame.clientWidth;
  const seen = ([p, q]: [number, number]) => p >= frame.scrollLeft - 0.5 && q <= frame.scrollLeft + w + 0.5;
  if (stay && [...ids.map((id) => span(frame, svg, id)), ...marks.map((m) => reach(frame, svg, [m]))].every(seen)) return;
  const people = ids.map((id) => span(frame, svg, id));
  const base = [...people, ...marks.map((m) => reach(frame, svg, [m]))];
  const others = also.map((id) => span(frame, svg, id));
  const fits = (s: [number, number][]) => Math.max(...s.map((x) => x[1])) - Math.min(...s.map((x) => x[0])) <= w;
  // everyone involved with their marks; failing that everyone involved, the
  // marks giving way; failing that the step's own people and their marks
  const spans = [[...base, ...others], [...people, ...others]].find(fits) ?? base;
  const lo = Math.min(...spans.map((s) => s[0]));
  const hi = Math.max(...spans.map((s) => s[1]));
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
  /** The tallest caption under the picture, measured once per telling. */
  private caption = 0;
  /** In the Family view, whom the frame is the three generations around, and
   * the frame itself, drawn over every date (R-0783). */
  private centre = "";
  private frame: Told | null = null;
  /** The frame was just put on a new person: it opens on them and their
   * parents and partners, sliding from where the tapped person stood. */
  private moved: { id: string; x: number; y: number } | null = null;

  constructor(
    readonly panel: HTMLElement,
    /** A tap on the path row: which step of it, the timeline first, and the
     * events the case is about. */
    private readonly back: (step: number, events: number[]) => void,
    /** A tap on the question's chip, once the drawer has gone back to the
     * cluster, so the message box it goes into is in sight. */
    private readonly answer: (chip: Chip) => void,
    /** The books of the screen the drawer is on; a screen with no Family view has none. */
    private readonly books: Books | null = null,
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

  /** Slide the drawer in on the three generations around the record's own
   * person, at the first date holding more than births; Back and Next step
   * through the dates on that one frame (R-0742, R-0775, R-0783). */
  openFamily(tl: Timeline): void {
    const c = family(tl);
    const whole = new Told(tl, c, true);
    this.centre = whole.cast.index;
    this.frame = null;
    this.moved = null;
    this.show(whole, null, familyStart(tl, c));
  }

  /** The four generations around `id` when they fit the drawer's width with
   * names at their readable size, else the three (R-0784). */
  private framed(id: string): Told {
    const told = this.told!;
    const four = told.centred(id, true);
    const three = told.centred(id);
    if (Object.keys(four.cast.people).length === Object.keys(three.cast.people).length) return three;
    const lv = this.panel.querySelector<HTMLElement>(".lv")!;
    const draw = lv.querySelector<HTMLElement>(".draw")!;
    const padding = parseFloat(getComputedStyle(draw).paddingTop);
    // the room under the years line and over the foot, both ways
    const tall = lv.clientHeight - lv.querySelector<HTMLElement>(".wire")!.offsetHeight - 2 * padding;
    const L = four.layout;
    return Math.min(lv.clientWidth / L.vw, tall / L.h) >= leastScale(L, padding) ? four : three;
  }

  /** The frame put on the three generations around `id`, at the same date. */
  private recentre(id: string, from: Element | null): void {
    if (id === this.centre) return;
    const at = from?.getBoundingClientRect();
    this.centre = id;
    this.frame = null;
    this.height = null;
    this.moved = { id, x: at ? at.left + at.width / 2 : NaN, y: at ? at.top + at.height / 2 : NaN };
    this.render(false);
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
    this.caption = 0;
    const cluster = told.tl.clusters.find((c) => c.id === told.told.cluster_id);
    this.panel.classList.toggle("whole", told.whole);
    // the Family view's Back and Next stand in a row of their own at the
    // drawer's foot, so they keep their place whatever each step draws (R-0782)
    this.panel.innerHTML =
      head(this.told, cluster ? clusterStep(cluster) : spanOf(told)) +
      `<div class="lv"><div class="wire"></div><div class="draw"></div><div class="scroll"></div></div>` +
      (told.whole ? `<div class="foot"></div>` : "");
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
    // the Family view draws one frame over every date (R-0783)
    if (told.whole) this.frame ??= this.framed(this.centre);
    const view = told.whole ? this.frame! : told;
    const shot = view.shot(this.i);
    if (told.whole) {
      const away = told.outside(this.i, view).map((id) => `<button type="button" class="also-who" data-centre="${esc(id)}">${esc(told.cast.people[id].name.split(" ")[0])}</button>`);
      q(".when").innerHTML = topLine(told, this.i);
      q(".also").innerHTML = away.length ? `Also on this date: ${away.join(", ")}` : "";
      q(".path").innerHTML = familyPath(this.centre === told.cast.index ? null : view.layout.P[this.centre].name);
    }
    const draw = q(".draw");
    // the new drawing is the same width, so the frame sets off from where it stood
    const was = draw.scrollLeft;
    draw.innerHTML = shot.svg;
    q(told.whole ? ".foot" : ".scroll").innerHTML = below(told, this.i, this.statement);
    this.fit(view.layout);
    draw.scrollLeft = was;
    const lit = [...draw.querySelectorAll<SVGElement>('.hl.now[data-mark^="hl:"]')].map((m) => m.dataset.mark!.slice(3));
    // a step with a move is framed on whoever makes it, whole, with as much of
    // the move as the frame holds, and everyone it reaches when they fit
    const who = shot.mover ?? shot.who;
    draw.dataset.who = who;
    const ids = [...(shot.mover ? [shot.mover, ...shot.reach, ...lit] : lit.length ? lit : [shot.who]), ...shot.couple];
    // a person the frame was just put on opens with their parents and
    // partners, sliding in from where they were tapped
    const kin = (id: string) => [
      ...view.cast.kids.filter((k) => k.kids.includes(id)).flatMap((k) => k.of),
      ...view.cast.bonds.filter((b) => b.a === id || b.b === id).flatMap((b) => [b.a, b.b]),
    ];
    const moved = this.moved;
    this.moved = null;
    if (moved) {
      frameOn(draw, [...new Set([moved.id, ...kin(moved.id)])].filter((id) => !id.startsWith("unknown-")), moved.id, false);
      const now = draw.querySelector(`.p[data-id="${CSS.escape(moved.id)}"] .shape`)?.getBoundingClientRect();
      if (now && !Number.isNaN(moved.x) && !still())
        draw.querySelector("svg")!.animate(
          [{ transform: `translate(${moved.x - (now.left + now.width / 2)}px, ${moved.y - (now.top + now.height / 2)}px)` }, { transform: "none" }],
          { duration: 450, easing: "ease-in-out" },
        );
    } else
      frameOn(
        draw,
        [...new Set(ids)],
        who,
        glide,
        shot.mover ? [...draw.querySelectorAll<SVGGraphicsElement>(`.fore [data-mark^="move:${CSS.escape(shot.mover)}>"]`)] : [],
        // everyone the step involves, when they all fit
        shot.involved,
        // the Family view's one frame holds still while a date's people are in sight (R-0784)
        told.whole && glide,
      );
  }

  private fit(L: Layout): void {
    const told = this.told!;
    const lv = this.panel.querySelector<HTMLElement>(".lv")!;
    const draw = lv.querySelector<HTMLElement>(".draw")!;
    if (this.height === null) {
      const sc = lv.querySelector<HTMLElement>(".scroll")!;
      if (!this.caption && !told.whole) {
        const keep = sc.innerHTML;
        this.caption = Math.max(
          ...told.steps.map((_, j) => {
            sc.innerHTML = below(told, j, this.statement);
            return sc.offsetHeight;
          }),
        );
        sc.innerHTML = keep;
      }
      const captions = [this.caption];
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
    // a drawing as wide as its frame to within a pixel does not scroll
    svg.style.width = L.vw * this.scale > lv.clientWidth + 1 ? `${Math.ceil(L.vw * this.scale)}px` : "";
  }

  private tap(e: Event): void {
    if (this.books?.tap(e.target as Element)) return;
    // in the Family view a tap on someone, or on a name under the title,
    // puts the frame on their three generations, at the same date (R-0783)
    const person = this.told?.whole ? (e.target as Element).closest<SVGGElement>(".draw :is(.p, .pt)[data-id]") : null;
    if (person && !person.dataset.id!.startsWith("unknown-")) {
      const shape = this.panel.querySelector(`.draw .p[data-id="${CSS.escape(person.dataset.id!)}"] .shape`);
      return this.recentre(person.dataset.id!, shape);
    }
    const named = (e.target as Element).closest<HTMLElement>("[data-centre]");
    if (named) return this.recentre(named.dataset.centre!, null);
    const step = (e.target as Element).closest<HTMLElement>("[data-step]");
    // "Family" in the path puts the frame back on the record's own person
    if (step && this.told?.whole && step.dataset.step === "1") return this.recentre(this.told.cast.index, null);
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
