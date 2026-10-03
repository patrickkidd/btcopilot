import { basis, dateList, faint, gapLine, guessBox, level, nameChip, side as sideBox, sublabel, type CaseView, type Guess, type Still } from "../case";
import { CasePage, clusterRef, stillSvg, TITLES, type PageState } from "../casepage";
import { bar, type Layout } from "../diagram";
import { esc, flash, slideOver } from "../dom";
import { ChipKind, ChipTone, type Chip } from "../types";
import { PBP, PIC } from "./chrome";
import type { CEvent } from "./casefile";
import { stripItems, type Band, type Coverage, type GridCell, type GuessCover, type PartCover, type Slot, type StripItem } from "./coverage";
import { coupleRecord, fullDate, labelOf, pkey, type Model } from "./model";

/** The case report, version 5: the ruled ten levels on the app's own pieces,
 * each level one line of words and a drawn element, the rest behind a tap
 * (Patrick, 2026-10-02: a lot of prose in a new feature is a flag; nothing
 * on the page may imply more than the record holds). The report is its own
 * screen with its own header: the person's name, "Case report", who presents.
 * Four things vary by frame and are chosen here by options: how the ten levels
 * are headlined (headlines that open, a rail, on the desktop or everywhere),
 * the one visual of what the record covers (on the family picture, a people
 * grid, a years band, three numbers), the summary (a box at the top, or the
 * same lines under each level), and whether the family picture is the case's
 * dashboard (pinned on the desktop, a round button on the phone) or the first
 * card only. */

export type Hierarchy = "none" | "rail" | "collapsed";
export type CoverageForm = "picture" | "grid" | "band" | "numbers" | "none";
export type Summary = "box" | "lines";

export interface ReportOpts {
  hierarchy: Hierarchy;
  /** The rail under the header on the desktop as well, whatever the hierarchy. */
  deskRail: boolean;
  coverage: CoverageForm;
  summary: Summary;
  dashboard: boolean;
  desk: boolean;
}

/** The card a report may be scrolled to: a level by number, the summary box
 * ("why") or the card of what the record covers ("cover"). */
export type ScrollTo = number | "why" | "cover";

/** The state a report is opened in, on top of the page's own. */
export interface ReportState extends PageState {
  /** The card scrolled to the top of the screen. */
  scrollTo?: ScrollTo;
  /** Levels opened past their one line. */
  open?: number[];
  /** The reading's line opened on what it rests on. */
  part?: string;
  /** The family picture slid out over the report (phone, dashboard). */
  famout?: boolean;
  /** Headlines: which levels are open; none means all closed. */
  unfolded?: number[];
  /** The three numbers: which list is open. */
  list?: string;
}

/** The short names of the ten levels for a rail, in Patrick's words. */
export const SHORT = (v: CaseView): string[] => [
  "The family",
  `What brought ${v.pronoun.him}`,
  "The couple",
  "Each parent's family",
  "One timeline",
  "The reading",
  `${v.subject.name}'s part`,
  "The choice",
  "What to work on",
  "The effort",
];

/** The first sentence of a text and the rest; the words are not changed. */
export function firstSentence(text: string): [string, string] {
  const m = text.match(/^[\s\S]*?[.!?]["”’']?(?=\s+[A-Z"“‘(]|\s*$)/);
  if (!m) return [text.trim(), ""];
  return [m[0].trim(), text.slice(m[0].length).trim()];
}

// ---- the page's own small pieces ----

/** How many words a line shows before the tail of its sentence waits behind a tap. */
const WORDS = 12;

/** A text cut at a few words: the words shown, and the words that wait. */
export function cut(text: string, n = WORDS): [string, string] {
  const words = text.trim().split(/\s+/).filter(Boolean);
  if (words.length <= n) return [words.join(" "), ""];
  return [words.slice(0, n).join(" "), words.slice(n).join(" ")];
}

/** The words shown and the tail of the sentence behind them, as one span each. */
const headTail = (text: string, n = WORDS): string => {
  const [head, tail] = cut(text, n);
  return `<span class="head${tail ? " cut" : ""}">${esc(head)}</span>${tail ? `<span class="tail" hidden> ${esc(tail)}</span>` : ""}`;
};

const lead = (text: string) => (text ? `<p class="lead">${headTail(text)}</p>` : "");
/** The one line a closed headline shows for its level; hidden once the level is open. */
const foldLine = (html: string) => `<p class="lead fold">${html}</p>`;
const rest = (inner: string) => (inner.trim() ? `<div class="rest" hidden>${inner}</div><button type="button" class="more">more</button>` : "");
const note = () => `<p class="note faint" aria-live="polite"></p>`;

/** A chip with short words on its face and the whole label behind it: the
 * thread's chip, so a tap does what a chip does in the app. */
function shortChip(kind: ChipKind, target: string, face: string, full: string, tone = "data"): string {
  return `<button type="button" class="chip ${tone}" data-kind="${kind}" data-target="${esc(target)}" data-full="${esc(full)}" title="${esc(full)}">${esc(face)}</button>`;
}

const dateChip = (m: Model, e: CEvent): string => {
  const d = m.dates.get(e.id);
  const when = d ? fullDate(d) : "no date";
  return shortChip(ChipKind.Event, pkey(e.id), when, `${when} · ${labelOf(m, e)}`);
};

const clusterChip = (m: Model, id: string): string => {
  const cl = m.view.clusters.find((c) => c.cluster.id === id);
  if (!cl) return "";
  const ref = clusterRef(cl);
  return shortChip(ChipKind.Cluster, ref.id, cl.cluster.label, ref.label);
};

/** One of the coach's open questions as a chip: its first words on the face, the whole question on the tap. */
const qChip = (q: { id: string; text: string }): string => {
  const [head, tail] = cut(q.text, 6);
  return `<button type="button" class="chip ask qchip" data-q="${esc(q.id)}" title="${esc(q.text)}">${esc(head)}${tail ? " …" : ""}</button>`;
};

const mark = (enough: boolean) => `<span class="mk${enough ? "" : " thin"}" aria-hidden="true"></span>`;
/** The mark of one of the reading's lines: filled where it stands, hollow where
 * the record is thin, dashed where the page left the line off. */
const markOf = (p: PartCover) => (p.off ? `<span class="mk off" aria-hidden="true"></span>` : mark(p.cover.enough));
/** Where a line is left off, the page says so in place of the line; its words
 * stay off the page (the one wording rule, words.ts). */
const LEFT_OFF = "Left off this page: it says what caused what";

/** The reading's lines counted, every line: standing, thin, left off. */
function standingOf(cov: Coverage): { first: PartCover | null; stand: number; thin: number; off: number; n: number; marks: string } {
  const kept = cov.parts.filter((p) => !p.off);
  const first = kept.find((p) => p.cover.enough) ?? null;
  const stand = kept.filter((p) => p.cover.enough).length;
  const off = cov.parts.length - kept.length;
  return { first, stand, thin: kept.length - stand, off, n: cov.parts.length, marks: cov.parts.map(markOf).join("") };
}

/** The count in words: "2 of 4 lines rest on dated facts; 1 not enough in the
 * record; 1 left off". A thin line may rest on one dated fact, so it is never
 * called unsupported: the record holds not enough for it. */
function standingLine(cov: Coverage, short = false): string {
  const { stand, thin, off, n } = standingOf(cov);
  const head = `${stand} of ${n} lines rest on dated facts`;
  if (short) return head;
  return head + (thin ? `; ${thin} not enough in the record` : "") + (off ? `; ${off} left off` : "");
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** When no open question bears on a guess: the record's open questions are
 * counted, and none of them touches these facts; only an empty record has
 * "no open question in the record". */
const noQuestion = (cov: Coverage): string => {
  const n = cov.open.length;
  if (!n) return "no open question in the record";
  return n === 1 ? "1 open question, not on these facts" : `${n} open questions, none on these facts`;
};

/** Where the record is thin for a reading, the page says this instead of the
 * reading (Patrick, 2026-10-02); the words themselves wait behind a tap. */
const NOT_ENOUGH = "Not enough in the record to choose a reading";

/** How far the record reaches around a guess, in one line; terse where it stands in the level itself. */
function covLine(g: GuessCover, terse = false): string {
  const facts = `${plural(g.dated, "dated fact")}${g.years ? ` · ${g.years}` : ""}`;
  if (!g.enough) return `${terse ? NOT_ENOUGH.toLowerCase() : NOT_ENOUGH} · ${g.why}`;
  return terse ? `rests on ${facts}` : `Rests on ${facts} · ${g.people.map((p) => p.name).join(", ")}`;
}

/** The first words of a text for a closed headline, cut at the page's few words. */
const firstWords = (text: string): string => {
  const [head, tail] = cut(firstSentence(text)[0]);
  return `${esc(head)}${tail ? " …" : ""}`;
};

/** A guess's one line when its level is a closed headline: the mark, the first
 * words of the guess, the count of what it rests on; a thin guess says not
 * enough in the record, its words waiting behind the tap. */
function guessFold(g: GuessCover | null, text: string): string {
  if (!g) return firstWords(text);
  if (!g.enough) return `${mark(false)}${esc(NOT_ENOUGH)} · ${esc(g.why ?? "")}`;
  return `${mark(true)}${firstWords(text)} · ${plural(g.dated, "dated fact")}${g.years ? ` · ${g.years}` : ""}`;
}

/** What the whole record covers, in one line of counts. */
export function coversLine(cov: Coverage): string {
  const c = cov.counts;
  const years = c.birth != null ? ` · ${c.lifeYears - c.emptyYears} of ${c.lifeYears} years since ${c.birth} hold a dated fact` : "";
  return `${plural(c.people, "person", "people")} in the record, ${c.story} with something that happened to them${years}`;
}

/** The chips a guess rests on: its dated facts oldest first, then the people it names. */
const restChips = (m: Model, p: PartCover): string[] => [
  ...p.cover.events.map((e) => dateChip(m, e)),
  ...p.rests.filter((r) => r.kind === ChipKind.Person).map((r) => nameChip(r)),
];

// ---- drawn elements ----

const VW = 360;

/** A dated strip: the record's dated events of one kind as dots on the years
 * of the person's life, each dot the date it stands on, each a tap that aims
 * the timeline at that event. */
export function stripSvg(items: StripItem[], from: number, to: number): string {
  if (!items.length) return "";
  const reach = Math.max(1, to - from);
  const x = (t: number) => 10 + ((t - from) / reach) * (VW - 20);
  // the dates take turns under and over the line, each row's words clear of the last
  const rows: number[] = [];
  const placed = items.map((it) => {
    const w = it.date.length * 6.6 + 6;
    const cx = x(it.t);
    // a label at either end stays inside the strip
    const lx = Math.min(Math.max(cx, w / 2), VW - w / 2);
    let r = 0;
    while (rows[r] != null && rows[r] > lx - w / 2) r++;
    rows[r] = lx + w / 2;
    return { it, cx, lx, r };
  });
  const under = Math.ceil(rows.length / 2);
  const over = Math.floor(rows.length / 2);
  const axis = 8 + over * 13 + (over ? 8 : 0);
  const H = axis + 18 + under * 13;
  let out = `<line class="wl" x1="10" y1="${axis}" x2="${VW - 10}" y2="${axis}"/>`;
  for (let y = Math.ceil(from / 10) * 10; y <= to; y += 10) out += `<line class="wl" x1="${x(y).toFixed(1)}" y1="${axis - 4}" x2="${x(y).toFixed(1)}" y2="${axis + 4}"/>`;
  placed.forEach(({ it, cx, lx, r }) => {
    const k = Math.floor(r / 2);
    const below = r % 2 === 0;
    const ly = below ? axis + 18 + k * 13 : axis - 11 - k * 13;
    const tick = below ? `<line class="wl" x1="${cx.toFixed(1)}" y1="${axis + 5}" x2="${cx.toFixed(1)}" y2="${ly - 10}"/>` : `<line class="wl" x1="${cx.toFixed(1)}" y1="${axis - 5}" x2="${cx.toFixed(1)}" y2="${ly + 3}"/>`;
    out +=
      `<g class="si" data-event="${esc(it.event)}" data-full="${esc(`${it.date} · ${it.label}`)}" role="button" tabindex="0" aria-label="${esc(`${it.date} · ${it.label}`)}">` +
      `<circle class="wd" cx="${cx.toFixed(1)}" cy="${axis}" r="4.5"/>` +
      (k || !below ? tick : "") +
      `<text class="wyr" x="${lx.toFixed(1)}" y="${ly}" text-anchor="middle">${esc(it.date)}</text></g>`;
  });
  return `<div class="fam strip"><svg class="ss" viewBox="0 0 ${VW} ${H}" role="img" aria-label="dated strip">${out}</svg></div>`;
}

const runLabel = (r: { from: number; to: number }) => (r.from === r.to ? String(r.from) : `${r.from}–${r.to}`);

/** The years band: a cell per year from the record's first dated fact to its
 * last date, dark where the record holds a dated fact, light where it holds
 * none; the person's birth marked; the longest empty run of their life named.
 * Drawn in HTML so its words keep one size at every width. A cell is a few
 * pixels wide, so the cells are the drawing only: the whole row is one wide
 * hit area that says the year under the finger, and a finger dragged along it
 * reads year by year (the arrow keys do the same); the label is a tap that
 * lists every empty run. */
export function bandHtml(b: Band): string {
  const n = b.cells.length;
  if (!n) return "";
  const pct = (y: number) => (((y - b.from) / n) * 100).toFixed(2);
  const cells = b.cells.map((c) => `<span class="yc n${Math.min(c.n, 2)}" data-year="${c.year}"></span>`).join("");
  // the decades under the band; on a narrow screen every other one is drawn
  let ticks = "";
  for (let y = Math.ceil(b.from / 10) * 10, i = 0; y <= b.to; y += 10, i++) {
    const x = Number(pct(y));
    if (x > 4 && x < 96) ticks += `<span class="wyr${i % 2 ? " odd" : ""}" style="left:${pct(y)}%">${y}</span>`;
  }
  const born = b.birth != null ? `<div class="bornrow"><span class="born" style="left:${pct(b.birth + 0.5)}%">born</span></div>` : "";
  let gap = "";
  if (b.empty) {
    const x0 = Number(pct(b.empty.from));
    const x1 = Number(pct(b.empty.to + 1));
    const mid = (x0 + x1) / 2;
    const at = mid > 75 ? `right:${(100 - x1).toFixed(2)}%` : mid < 25 ? `left:${x0.toFixed(2)}%` : `left:${mid.toFixed(2)}%;transform:translateX(-50%)`;
    const label = `${runLabel(b.empty)} · nothing in the record`;
    gap =
      `<div class="gaprow"><span class="gapb" style="left:${x0.toFixed(2)}%;width:${(x1 - x0).toFixed(2)}%"></span>` +
      `<button type="button" class="wlab" data-runs="${b.runs.length}" style="${at}" title="every run of years with nothing in the record">${esc(label)}</button></div>`;
  }
  const row =
    `<div class="cells" role="slider" tabindex="0" aria-label="the years; tap or drag to read one" ` +
    `aria-valuemin="${b.from}" aria-valuemax="${b.to}" aria-valuenow="${b.to}" aria-valuetext="${b.to}" data-from="${b.from}" data-to="${b.to}">` +
    `${cells}<i class="ycur" hidden></i></div>`;
  return `<div class="fam band" aria-label="years with a dated fact">${born}${row}<div class="ticks">${ticks}</div>${gap}</div>`;
}

/** What the record covers, drawn small: the people as squares, filled where
 * something that happened to them is in the record; the years as a band. The
 * words say what a filled square and a dark cell mean. */
function coversRow(cov: Coverage, his: string): string {
  const c = cov.counts;
  const b = cov.band;
  const n = cov.people.length;
  const dots = cov.people.map((p, i) => `<rect class="pd${p.tier === "story" ? " story" : ""}" x="${i * 9 + 0.5}" y="0.5" width="7" height="7"><title>${esc(p.name)}</title></rect>`).join("");
  const cw = 120 / Math.max(1, b.cells.length);
  const cells = b.cells.map((y, i) => `<rect class="yc n${Math.min(y.n, 2)}" x="${(i * cw).toFixed(2)}" y="0" width="${(cw + 0.2).toFixed(2)}" height="8"><title>${y.year}: ${plural(y.n, "dated fact")}</title></rect>`).join("");
  const born = b.birth != null ? `<path class="born" d="M${((b.birth - b.from + 0.5) * cw - 3).toFixed(1)} 12 h6 l-3 -4 z"/>` : "";
  const years = c.birth != null ? `<span class="cv"><svg viewBox="0 0 120 12" width="120" aria-hidden="true">${cells}${born}</svg><span>dated facts in ${c.lifeYears - c.emptyYears} of ${esc(his)} ${c.lifeYears} years</span></span>` : "";
  // the squares shrink to the room they have, never past the box's edge
  return `<div class="covers"><span class="cv"><svg viewBox="0 0 ${n * 9} 8" width="${n * 9}" style="max-width:100%" aria-hidden="true">${dots}</svg><span>${c.story} of ${n} people: something happened to them</span></span>${years}</div>`;
}

/** The one row of what the record covers as a small card, where no summary box carries it. */
const coversCard = (cov: Coverage, his: string) => `<section class="level cover" data-level="0"><p class="label">What the record covers</p>${coversRow(cov, his)}</section>`;

/** The family picture with the coverage drawn on it: each person's shape marked
 * by what the record holds of them, and each a tap that says so. */
function shade(svg: string, cov: Coverage): string {
  return svg.replace(/<g class="p" data-id="([^"]+)">/g, (_, id: string) => {
    const p = cov.byKey.get(id);
    if (!p) return `<g class="p name" data-id="${id}">`;
    return `<g class="p ${p.tier}" data-id="${id}" role="button" tabindex="0" aria-label="${esc(p.name)}">`;
  });
}

const roleShape = (what: string, x: number, y: number, e: number): string => {
  const female = /\b(mother|sister|daughter|grandmother)\b/.test(what) && !/\band\b/.test(what);
  const male = /\b(father|brother|son|grandfather)\b/.test(what) && !/\band\b/.test(what);
  if (female) return `<circle class="shape" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${e.toFixed(1)}"/>`;
  return `<rect class="shape" x="${(x - e).toFixed(1)}" y="${(y - e).toFixed(1)}" width="${(2 * e).toFixed(1)}" height="${(2 * e).toFixed(1)}"${male ? "" : ` rx="${(e * 0.45).toFixed(1)}"`}/>`;
};

/** The dashed places drawn into a picture: above a person whose parent the
 * record does not hold, or beside a person on their parents' line where the
 * record holds no brother or sister. Only pictures that hold the person get
 * the slot, and a sibling's slot goes where the parents' line is drawn. */
function withSlots(svg: string, still: Still, slots: Slot[]): string {
  const L: Layout | null = still.layout;
  if (!L) return svg;
  const W = L.w;
  const E = W / 2;
  const kidOf = (k: string) => L.kids.find((b) => b.kids.includes(k));
  const mine = slots.filter((s) => {
    const k = pkey(s.who);
    if (!L.P[k]) return false;
    return s.rel === "parent" ? !kidOf(k) : !!kidOf(k);
  });
  if (!mine.length) return svg;
  const vb = svg.match(/viewBox="([^"]+)"/);
  if (!vb) return svg;
  const [x0, y0, vw, vh] = vb[1].split(/\s+/).map(Number);
  let minY = y0;
  let maxY = y0 + vh;
  let maxX = x0 + vw;
  let add = "";
  mine.forEach((s) => {
    const k = pkey(s.who);
    let x = L.x[k];
    let y = L.y[k];
    let kin = "";
    if (s.rel === "parent") {
      const children = L.kids.filter((b) => b.of.includes(k)).flatMap((b) => b.kids);
      const step = children.length ? Math.max(...children.map((c) => L.y[c])) - y : 2.6 * W;
      y = y - step;
      kin = `<path class="kin dash" d="M${x.toFixed(1)} ${(y + E).toFixed(1)} V${(L.y[k] - (L.P[k].you ? E + W * 0.1 : E)).toFixed(1)}"/>`;
    } else {
      const brood = kidOf(k)!;
      const row = Object.keys(L.P).filter((id) => Math.abs(L.y[id] - y) < 1);
      x = Math.max(...row.map((id) => L.x[id])) + 3 * W;
      const [a, b] = brood.of;
      const k2 = L.P[b] ? bar(L, { a, b }) : { x1: L.x[a], y: L.y[a] + E + W / 2.2 };
      kin = `<path class="kin dash" d="M${x.toFixed(1)} ${(y - E).toFixed(1)} V${k2.y.toFixed(1)} H${Math.min(k2.x1, L.x[k]).toFixed(1)}"/>`;
    }
    const lw = Math.max(s.role[0].length, s.role[1].length) * 7.6;
    add +=
      kin +
      `<g class="p slot" data-slot="${esc(s.id)}" role="button" tabindex="0" aria-label="${esc(`${s.role[0]} ${s.role[1]}: ${s.question ? "asked, no answer yet" : "not in the record, not asked"}`)}">` +
      roleShape(s.role[1], x, y, E) +
      `<text class="age" x="${x.toFixed(1)}" y="${(y + 4.5).toFixed(1)}">?</text>` +
      `<text class="lbn nh" x="${x.toFixed(1)}" y="${(y + E + 14).toFixed(1)}" text-anchor="middle">${esc(s.role[0])}</text>` +
      `<text class="lbd nh" x="${x.toFixed(1)}" y="${(y + E + 27).toFixed(1)}" text-anchor="middle">${esc(s.role[1])}</text></g>`;
    minY = Math.min(minY, y - E - 6);
    maxY = Math.max(maxY, y + E + 32);
    maxX = Math.max(maxX, x + Math.max(lw / 2, E) + 6);
  });
  return svg.replace(vb[0], `viewBox="${x0} ${minY.toFixed(1)} ${(maxX - x0).toFixed(1)} ${(maxY - minY).toFixed(1)}"`).replace("</svg>", `${add}</svg>`);
}

/** The key to the coverage on a picture: the shapes themselves, a few words each. */
const KEY =
  `<div class="key">` +
  `<span><svg viewBox="0 0 16 16"><rect class="k story" x="2" y="2" width="12" height="12"/></svg>something happened to them</span>` +
  `<span><svg viewBox="0 0 16 16"><rect class="k dates" x="2" y="2" width="12" height="12"/></svg>dates or a mention</span>` +
  `<span><svg viewBox="0 0 16 16"><rect class="k name" x="2" y="2" width="12" height="12"/></svg>a name only</span>` +
  `<span><svg viewBox="0 0 16 16"><rect class="k slot" x="2" y="2" width="12" height="12"/></svg>nobody in the record, not asked</span></div>`;

function picture(v: CaseView, still: Still, cov: Coverage, shaded: boolean): string {
  if (!still.layout) return gapLine(`The app's layout cannot draw this picture: ${still.fault ?? "unknown"}.`);
  let svg = stillSvg(v, still);
  if (shaded) svg = withSlots(shade(svg, cov), still, cov.slots);
  return `<div class="fam${shaded ? " cov" : ""}">${svg}</div>`;
}

/** The people a picture draws, by the app's ids; the "?" for an unrecorded parent is no one. */
export const peopleOn = (still: Still): string[] => Object.keys(still.layout?.P ?? {}).filter((k) => !k.startsWith("unknown-"));

const SHAPE = (sex: string, cls: string) =>
  sex === "F"
    ? `<circle class="${cls}" cx="12" cy="12" r="9"/>`
    : `<rect class="${cls}" x="3" y="3" width="18" height="18"${sex === "M" ? "" : ' rx="4"'}/>`;

/** The people grid: a column per side of the family, a row per generation, a
 * cell per person in the record shaded by what the record holds of them, and a
 * dashed cell where a parent's brothers and sisters were never asked about. */
export function gridHtml(cov: Coverage): string {
  const g = cov.grid;
  const cell = (c: GridCell): string => {
    if (c.person) {
      const p = c.person;
      return `<button type="button" class="cell ${p.tier}" data-person="${esc(p.id)}" title="${esc(p.name)}"><svg viewBox="0 0 24 24" aria-hidden="true">${SHAPE(p.sex, "shape")}</svg><span>${esc(p.name)}</span></button>`;
    }
    const s = c.slot!;
    return `<button type="button" class="cell slot" data-slot="${esc(s.id)}" title="${esc(`${s.role[0]} ${s.role[1]}`)}"><svg viewBox="0 0 24 24" aria-hidden="true">${SHAPE(/mother|sister/.test(s.role[1]) && !/\band\b/.test(s.role[1]) ? "F" : /father|brother/.test(s.role[1]) && !/\band\b/.test(s.role[1]) ? "M" : "?", "shape")}<text x="12" y="16" text-anchor="middle">?</text></svg><span>${esc(s.role[0])} ${esc(s.role[1])}</span></button>`;
  };
  // the column heads in few words: "Father's side", not "His father's side"
  const head = (label: string) => label.replace(/^(His|Her|Their) (\w)/, (_, __, c: string) => c.toUpperCase());
  let html = `<div class="grid" style="--cols:${g.sides.length}"><div class="gh corner"></div>${g.sides.map((s) => `<div class="gh">${esc(head(s.label))}</div>`).join("")}`;
  g.gens.forEach((gen) => {
    html += `<div class="gl">${esc(gen.label)}</div>`;
    // people the record links to no one in the family: one row across the sides
    if (gen.gen == null) {
      html += `<div class="gc wide">${g.cells.filter((c) => c.gen == null).map(cell).join("")}</div>`;
      return;
    }
    g.sides.forEach((s) => {
      const cells = g.cells.filter((c) => c.gen === gen.gen && c.side === s.key);
      html += `<div class="gc">${cells.map(cell).join("")}</div>`;
    });
  });
  // the names fill the card, so the key waits behind the tap
  return `${html}</div>${note()}${rest(KEY)}`;
}

/** Three plain numbers in one line, each a tap to its list. */
export function numbersHtml(m: Model, cov: Coverage): string {
  const c = cov.counts;
  const v = m.view;
  const people = cov.people.map((p) => `<li><button type="button" class="pl" data-person="${esc(p.id)}">${esc(p.name)}</button> <span class="faint">${p.tier === "story" ? plural(p.story, "thing that happened", "things that happened") : p.tier === "dates" ? "dates or a mention only" : "a name only"}</span></li>`).join("");
  const open = cov.open.length ? cov.open.map((q) => `<li>${esc(q.text)} <span class="faint">asked ${esc(q.askedAt)}, no answer yet</span></li>`).join("") : `<li class="faint">No open question in the record.</li>`;
  const runs = cov.band.runs.map(runLabel);
  const years = runs.length ? `<li>${esc(runs.join(" · "))}</li>` : `<li class="faint">Every year since ${c.birth} holds a dated fact.</li>`;
  return (
    `<div class="nums">` +
    `<button type="button" class="num" data-list="people"><b>${c.people}</b><span>people in the record</span></button>` +
    `<button type="button" class="num" data-list="open"><b>${c.open}</b><span>open questions</span></button>` +
    `<button type="button" class="num" data-list="years"><b>${c.emptyYears}</b><span>years of ${esc(v.pronoun.his)} life with no dated fact</span></button>` +
    `</div>` +
    `<ul class="numlist" data-for="people" hidden>${people}</ul>` +
    `<ul class="numlist" data-for="open" hidden>${open}</ul>` +
    `<ul class="numlist" data-for="years" hidden>${years}</ul>${note()}`
  );
}

/** The card at the top that says what the record covers, in one visual. */
function coverCard(m: Model, cov: Coverage, form: CoverageForm): string {
  const inner = form === "grid" ? gridHtml(cov) : form === "numbers" ? numbersHtml(m, cov) : "";
  if (!inner) return "";
  return `<section class="level cover" data-level="0"><p class="label">What the record covers</p>${inner}</section>`;
}

// ---- the summary ----

/** The reading's lines, one row each: the mark of whether it stands, its words,
 * and behind a tap its dated facts and the open questions that bear on it. With
 * the summary under each level the coverage line stands in the row itself. A
 * line the record is thin for shows "not enough in the record to choose a
 * reading" and what is thin, in place of its words; the words wait behind the
 * tap with the rest. */
function partRows(m: Model, cov: Coverage, under: boolean): string {
  return `<ol class="parts">${cov.parts
    .map((p: PartCover) => {
      if (p.off) return `<li class="part off" data-part="${esc(p.id)}"><p class="pt">${markOf(p)}<span class="ptext">${esc(LEFT_OFF)}</span></p></li>`;
      const g = p.cover;
      const inPlace = under || !g.enough;
      const more =
        (g.enough ? "" : `<p class="faint">${esc(p.text)}</p>`) +
        (inPlace ? "" : `<p class="cov">${esc(covLine(g))}</p>`) +
        basis(restChips(m, p)) +
        `<p class="sublabel">Would change if</p>` +
        (g.bears.length ? `<div class="qs">${g.bears.map(qChip).join("")}</div>` : `<p class="faint">${noQuestion(cov)}</p>`);
      const line = g.enough ? headTail(p.text, under ? 10 : WORDS) : esc(NOT_ENOUGH);
      return (
        `<li class="part${g.enough ? "" : " thin"}" data-part="${esc(p.id)}">` +
        `<button type="button" class="pt">${mark(g.enough)}<span class="ptext">${line}</span></button>` +
        (inPlace ? `<p class="cov">${esc(g.enough ? covLine(g, true) : g.why ?? "")}</p>` : "") +
        `<div class="pmore" hidden>${more}</div></li>`
      );
    })
    .join("")}</ol>`;
}

const krow = (k: string, inner: string) => `<div class="krow"><span class="k">${esc(k)}</span><div class="kv">${inner}</div></div>`;

/** The summary box: the reading's first line that rests on dated facts, marked
 * a guess; what it rests on (the guess's own reach), what the whole record
 * covers, what would change it, and where the reading's other lines stand.
 * With no line standing, the box says not enough in the record to choose a
 * reading. */
function summaryBox(m: Model, cov: Coverage): string {
  const v = m.view;
  const { first, marks } = standingOf(cov);
  const rejecter = v.self ? "yours to reject" : `for ${v.subject.name} to reject`;
  const standing = standingLine(cov);
  const rests = first
    ? krow("Rests on", first.cover.events.length ? `<div class="chips">${first.cover.events.map((e) => dateChip(m, e)).join("")}</div>` : `<span class="faint">not in the record</span>`)
    : "";
  const bears = first ? krow("Would change if", first.cover.bears.length ? `<div class="qs">${first.cover.bears.map(qChip).join("")}</div>` : `<span class="faint">${noQuestion(cov)}</span>`) : "";
  return (
    `<section class="level why" data-level="0"><p class="label">Why this reading</p>` +
    `<div class="guessbox${first ? "" : " thin"}"><p class="label">A guess, ${esc(rejecter)}</p>` +
    (first ? `<p class="lead">${headTail(first.text, 10)}</p>` : `<p class="lead">${mark(false)}${esc(NOT_ENOUGH)}</p>`) +
    rests +
    krow("The record covers", coversRow(cov, v.pronoun.his)) +
    bears +
    krow("The reading", `<button type="button" class="jump" data-jump="6">${marks} ${esc(standing)}</button>`) +
    `${note()}</div></section>`
  );
}

// ---- the ten levels ----

interface Ctx {
  m: Model;
  v: CaseView;
  cov: Coverage;
  o: ReportOpts;
  /** The years a strip runs over: the person's life, or the record's reach. */
  from: number;
  to: number;
}

const card = (n: number, c: Ctx, inner: string, cls = "") => level(n, TITLES[n](c.v), inner, cls);

const legendText = (v: CaseView) =>
  "Solid line: a marriage in the record; dashed: no marriage date in the record. One slash: separated; two: divorced. X: died. " +
  `The number is the age ${v.recordEnd.closed ? `at the record's last date (${v.recordEnd.date})` : "now"}, or at death for someone marked X, where a birth date is in the record.`;

const UNKNOWN_NOTE = "?: the other parent is not in the record.";

/** Level 1: the person's own family on a picture, with the coverage on it when
 * that is the chosen visual; the rest behind a tap. Its headline counts who is
 * on the picture. */
function level1(c: Ctx, cls = ""): string {
  const { v, cov } = c;
  const shaded = c.o.coverage === "picture";
  const on = peopleOn(v.household);
  const story = on.filter((k) => cov.byKey.get(k)?.tier === "story").length;
  const fold = `${plural(on.length, "person", "people")} on the picture${shaded ? `, ${story} with something that happened to them` : ""}`;
  const [first, more] = firstSentence(v.siblings);
  return card(
    1,
    c,
    foldLine(esc(fold)) +
      picture(v, v.household, cov, shaded) +
      (shaded ? bandHtml(cov.band) + note() + KEY : "") +
      lead(first) +
      rest([more ? `<p>${esc(more)}</p>` : "", ...v.householdGaps.map(gapLine), v.undrawn ? faint(v.undrawn) : "", faint(`${legendText(v)}${v.household.unknownParent ? ` ${UNKNOWN_NOTE}` : ""}`)].join("")),
    cls,
  );
}

function level2(c: Ctx): string {
  const { m, v } = c;
  const flares = m.file.events.filter((e) => e.person === m.subject.id && e.symptom && m.dates.get(e.id));
  const [first, more] = firstSentence(v.whatBrought);
  const strip = flares.length ? sublabel("The trouble's course, dated") + stripSvg(stripItems(m, flares), c.from, c.to) + note() : gapLine("Dates of each flare-up: not in the record.");
  return card(2, c, lead(first) + strip + rest([more ? `<p>${esc(more)}</p>` : "", `<p>${esc(v.asked)}</p>`, flares.length ? dateList(v.flares) : "", ...v.ownUndated.map(gapLine)].join("")));
}

function level3(c: Ctx): string {
  const { m, v } = c;
  const couple = coupleRecord(m);
  const [first, more] = firstSentence(v.couple.text);
  const strip = couple.events.length ? stripSvg(stripItems(m, couple.events), c.from, c.to) + note() : "";
  return card(3, c, lead(first) + strip + rest([more ? `<p>${esc(more)}</p>` : "", couple.events.length ? dateList(v.couple.rows) : "", ...v.couple.gaps.map(gapLine)].join("")));
}

function level4(c: Ctx): string {
  const { v, cov } = c;
  const shaded = c.o.coverage === "picture";
  const heads = v.sides.map((s) => `${s.label}: ${plural(s.pics.reduce((n, p) => n + peopleOn(p.still).length, 0), "person", "people")} on the picture`).join(" · ");
  const sides = v.sides
    .map((s) => {
      const [first] = firstSentence(s.text);
      return sideBox(s.label, s.pics.map((p) => (p.sub ? sublabel(p.sub) : "") + picture(v, p.still, cov, shaded)).join("") + lead(first));
    })
    .join("");
  const more = v.sides
    .map((s) => {
      const [, m2] = firstSentence(s.text);
      return sublabel(s.label) + (m2 ? `<p>${esc(m2)}</p>` : "") + s.pics.map((p) => (p.still.unknownParent ? faint(UNKNOWN_NOTE) : "") + (p.kids ? `<p>${esc(p.kids)}</p>` : "") + p.gaps.map(gapLine).join("")).join("") + s.undated.map(gapLine).join("");
    })
    .join("");
  return card(4, c, foldLine(esc(heads)) + sides + (shaded ? note() : "") + rest(more + v.looseUndated.map(gapLine).join("")));
}

function level5(c: Ctx): string {
  const { v, cov } = c;
  const chips = v.clusters.map((cl) => nameChip(clusterRef(cl)));
  const notes = v.clusters.flatMap((cl) => [
    ...cl.undated.map((u) => gapLine(`${cl.cluster.label}: no date in the record for one step, ${u}; the telling leaves it out.`)),
    ...(cl.fault ? [gapLine(`${cl.cluster.label}: the app cannot tell this cluster: ${cl.fault}.`)] : []),
  ]);
  const years = cov.band.from === cov.band.to ? String(cov.band.from) : `${cov.band.from}–${cov.band.to}`;
  const band = c.o.coverage === "band";
  return card(
    5,
    c,
    PIC +
      (band ? bandHtml(cov.band) + note() : "") +
      lead(`${plural(v.clusters.length, "cluster")} on the line · ${years}`) +
      `<div class="clusters">${chips.join("")}</div>` +
      rest([...notes, v.stacked.length ? faint(v.stacked.join(" ")) : "", v.notHeld.length ? `<div class="notheld">${sublabel("Not in the record")}<ul>${v.notHeld.map((u) => `<li>${esc(u)}</li>`).join("")}</ul></div>` : ""].join("")),
  );
}

const rejecter = (v: CaseView) => (v.self ? "yours to reject" : `for ${v.subject.name} to reject`);

/** A guess as one line and a drawn element: the mark of whether it stands, its
 * dated facts as chips, the coverage line in the box when the summary stands
 * under each level, else behind the tap. A guess the record is thin for shows
 * "not enough in the record to choose a reading" and what is thin in place of
 * its words, which wait behind the tap. */
function guessCard(c: Ctx, g: Guess, cover: GuessCover | null, level: number, extraRest = ""): string {
  const { v } = c;
  const under = c.o.summary === "lines";
  const thin = cover ? !cover.enough : false;
  const inPlace = under || thin;
  const [first, more] = firstSentence(g.text);
  const chips = cover ? cover.events.map((e) => dateChip(c.m, e)).join("") : g.rests.map((r) => nameChip(r)).join(" ");
  const cov = cover ? `<p class="cov">${esc(thin ? (cover.why ?? "") : covLine(cover, under))}</p>` : "";
  const bears = cover ? `<p class="sublabel">Would change if</p>` + (cover.bears.length ? `<div class="qs">${cover.bears.map(qChip).join("")}</div>` : `<p class="faint">${noQuestion(c.cov)}</p>`) : "";
  // how this level ties to the reading: the cluster of the line they share a dated fact in
  const tie = c.cov.ties.find((t) => t.level === level);
  const ties = tie ? `<p class="cov">${tie.cluster ? `shares a cluster with the reading ${clusterChip(c.m, tie.cluster)}` : "no dated fact shared with the reading"}</p>` : "";
  const lead = thin ? `<p class="lead">${mark(false)}${esc(NOT_ENOUGH)}</p>` : `<p class="lead">${cover ? mark(true) : ""}${headTail(first)}</p>`;
  const said = thin ? `<p class="faint">${esc(g.text)}</p>` : more ? `<p>${esc(more)}</p>` : "";
  return (
    `<div class="guessbox${thin ? " thin" : ""}"><p class="label">A guess, ${esc(rejecter(v))}</p>` +
    lead +
    (thin ? cov : "") +
    (chips ? `<div class="chips">${chips}</div>` : basis([])) +
    (under ? (thin ? "" : cov) + bears : "") +
    ties +
    rest([said, inPlace ? "" : cov, under ? "" : bears, ...g.gaps.map(gapLine), extraRest].join("")) +
    `${note()}</div>`
  );
}

function level6(c: Ctx): string {
  const { v, cov } = c;
  if (!v.reading.text.trim()) return card(6, c, gapLine(`${v.presenter}'s reading: left off this page; every sentence of it says what produces what.`));
  const under = c.o.summary === "lines";
  const { first, marks } = standingOf(cov);
  // closed: every line's mark, the first standing line's first words, the count
  const fold = `${marks} ${first ? `${firstWords(first.text)} · ` : ""}${esc(standingLine(cov, true))}`;
  return card(
    6,
    c,
    foldLine(fold) +
      `<div class="guessbox"><p class="label">A guess, ${esc(rejecter(v))}</p>${partRows(c.m, cov, under)}${note()}</div>` +
      v.reading.gaps.map(gapLine).join(""),
  );
}

const level7 = (c: Ctx) => card(7, c, foldLine(guessFold(c.cov.ownPart, c.v.ownPart.text)) + guessCard(c, c.v.ownPart, c.cov.ownPart, 7));

function level8(c: Ctx): string {
  const { v, m } = c;
  const ch = v.choice;
  const when = ch.event ? nameChip({ kind: ChipKind.Event, id: ch.event, label: ch.date }) : `<span class="d">${esc(ch.date)}</span>`;
  const question = ch.question
    ? guessBox(`A question, ${rejecter(v)}`, ch.question, basis([]))
    : gapLine("A question on this step: not in the record.");
  const fold = `${esc(ch.date)} · ${firstWords(ch.step)}${m.file.levels["8_choice"].quote ? ` · in ${esc(v.pronoun.his)} own words` : ""}`;
  return card(
    8,
    c,
    foldLine(fold) +
      `<div class="choice"><p class="did">${when} <span class="lead">${esc(ch.step)}</span></p><p class="part">${esc(ch.part)}</p></div>` +
      rest(`<p class="sublabel">The facts under it:</p><ul class="facts">${ch.facts.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>${question}`),
  );
}

const level9 = (c: Ctx) => card(9, c, foldLine(guessFold(c.cov.workOn, c.v.workOn.text)) + guessCard(c, c.v.workOn, c.cov.workOn, 9, gapLine("What to expect: not in the record.")));

function level10(c: Ctx): string {
  const e = c.v.effort;
  if (e.guess) return card(10, c, foldLine(guessFold(c.cov.effort, e.guess.text)) + guessCard(c, e.guess, c.cov.effort, 10) + e.gaps.map(gapLine).join(""));
  const [first, more] = firstSentence(e.text);
  return card(10, c, lead(first) + rest([more ? `<p>${esc(more)}</p>` : "", ...e.gaps.map(gapLine)].join("")));
}

/** The family picture as the dashboard: the person's family, each parent's
 * side, and the coverage on all of it with the years band when the picture is
 * the chosen coverage visual. */
function dashboard(c: Ctx): string {
  const { v, cov } = c;
  const shaded = c.o.coverage === "picture";
  return (
    `<div class="case dash"><section class="level" data-level="1"><p class="label">1 · ${esc(TITLES[1](v))}</p>` +
    picture(v, v.household, cov, shaded) +
    (shaded ? bandHtml(cov.band) : "") +
    v.sides.map((s) => sideBox(s.label, s.pics.map((p) => picture(v, p.still, cov, shaded)).join(""))).join("") +
    note() +
    (shaded ? KEY : "") +
    `</section></div>`
  );
}

/** The ten levels in the ruled order, the chosen coverage card and the summary
 * box between the first and the second: a case opens on who is in the family.
 * On a desktop with the dashboard, level 1 stands in the pinned column and the
 * box stands above the levels; on a phone with the dashboard level 1 is the
 * first card, open, and the box stands under it. */
function words(c: Ctx): string {
  const { m, cov, o } = c;
  const top = coverCard(m, cov, o.coverage);
  // with the summary's lines under each level, the one row of what the whole
  // record covers still stands at the top, so every guess is read against it
  const box = o.summary === "box" ? summaryBox(m, cov) : top ? "" : coversCard(cov, c.v.pronoun.his);
  const folded = o.hierarchy === "collapsed";
  const one = o.desk && o.dashboard ? "" : level1(c, folded && o.dashboard ? "on" : "");
  return `<div class="case${folded ? " folded" : ""}">${one}${top}${box}${level2(c)}${level3(c)}${level4(c)}${level5(c)}${level6(c)}${level7(c)}${level8(c)}${level9(c)}${level10(c)}<p class="account">${esc(c.v.account)}</p></div>`;
}

const OPEN_ALL = `<button type="button" class="openall">Open all</button>`;

/** The rail of the ten levels; with headlines, Open all sits at its end. A
 * level pinned in the dashboard column never scrolls by: its word is marked
 * so the tap on it can light the pinned card instead. */
const rail = (v: CaseView, withOpenAll: boolean, pinned: number | null) =>
  `<nav class="rail" aria-label="the ten levels">${SHORT(v)
    .map((s, i) => `<button type="button" data-jump="${i + 1}"${i + 1 === pinned ? ` data-pinned="1" title="pinned on the left"` : ""}><b>${i + 1}</b>${esc(s)}</button>`)
    .join("")}${withOpenAll ? OPEN_ALL : ""}</nav>`;

const foldrow = () => `<div class="foldrow"><span class="faint">Tap a level to open it</span>${OPEN_ALL}</div>`;

/** The round button in the header that slides the family picture out over the report. */
const FAB =
  `<button type="button" class="fab" aria-label="who is in the family">` +
  `<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6">` +
  `<rect x="3" y="3" width="6" height="6"/><circle cx="18" cy="6" r="3"/><path d="M6 9v3h12V9M12 12v3"/><rect x="9" y="15" width="6" height="6"/></svg></button>`;

/** The report's own header: the person's name, "Case report", who presents, and
 * on a phone with the dashboard the round button. */
const header = (v: CaseView, fab: boolean) =>
  `<div class="titlerow report"><div class="ttlwrap"><div class="ttl"><span class="ttl-name">${esc(v.subject.name)}</span><span class="ttl-tail">&nbsp;· Case report</span></div><span class="by">presented by ${esc(v.presenter)}</span></div>${fab ? FAB : ""}</div>`;

function ctx(m: Model, cov: Coverage, o: ReportOpts): Ctx {
  const from = cov.counts.birth ?? cov.band.from;
  return { m, v: m.view, cov, o, from, to: cov.band.to };
}

/** The whole report in the app's frame. */
export function reportFrame(m: Model, cov: Coverage, o: ReportOpts, attrs = ""): string {
  const c = ctx(m, cov, o);
  const v = m.view;
  const folded = o.hierarchy === "collapsed";
  const withRail = o.hierarchy === "rail" || (o.deskRail && o.desk);
  const under = (withRail ? rail(v, folded, o.desk && o.dashboard ? 1 : null) : "") + (folded && !withRail ? foldrow() : "");
  const aside = o.desk && o.dashboard ? `<aside class="pinned left"><div class="scroller">${dashboard(c)}</div></aside>` : "";
  const phoneDash = !o.desk && o.dashboard;
  const famout = phoneDash
    ? `<div class="slideover famout" hidden><div class="ovbar"><button class="backbtn" type="button" aria-label="back to the report"></button><span class="ovt">${esc(TITLES[1](v))}</span></div><div class="scroller">${dashboard(c)}</div></div>`
    : "";
  return (
    `<div class="app report${o.desk ? " wide" : ""}${o.dashboard ? " dash" : ""}"${attrs}>` +
    header(v, phoneDash) +
    under +
    `<div class="split">${aside}<div class="screen"><div class="chat">${words(c)}</div>${PBP}</div></div>` +
    famout +
    `</div>`
  );
}

/** The report mounted: the page's own wiring (the timeline, the drawer, the
 * chips) and the report's taps (more, headlines, the rail, the people on a
 * shaded picture, the cells, the band, the numbers, the round button). */
export class CaseReport {
  readonly page: CasePage;
  private readonly chat: HTMLElement | null;
  private readonly rail: HTMLElement | null;

  constructor(
    readonly root: HTMLElement,
    readonly m: Model,
    readonly cov: Coverage,
    readonly o: ReportOpts,
  ) {
    this.page = new CasePage(root, m.view);
    this.chat = root.querySelector<HTMLElement>(".chat");
    this.rail = root.querySelector<HTMLElement>(".rail");
    // the chat screen's "in chat" chip has no chat to go to on a report: taken
    // out of the row under the picture whenever the app redraws that row
    const caption = root.querySelector<HTMLElement>(".pic .caption");
    if (caption) {
      const strip = () => caption.querySelectorAll("#cap-trace").forEach((el) => el.remove());
      new MutationObserver(strip).observe(caption, { childList: true });
      strip();
    }
    root.addEventListener("click", (e) => this.tap(e));
    root.addEventListener("keydown", (e) => {
      const t = e.target as HTMLElement;
      if ((e.key === "Enter" || e.key === " ") && t.matches?.(".si, .p.slot, .fam.cov .p[data-id]")) {
        e.preventDefault();
        this.tap(e);
      }
      // the years band read with the arrow keys, a year at a time
      if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && t.matches?.(".fam.band .cells")) {
        e.preventDefault();
        const now = Number(t.getAttribute("aria-valuenow"));
        this.sayYear(t, now + (e.key === "ArrowLeft" ? -1 : 1));
      }
    });
    // the years band read under a finger: a tap says the year under it, a
    // finger dragged along the band reads year by year
    root.addEventListener("pointerdown", (e) => {
      const cells = (e.target as HTMLElement).closest<HTMLElement>(".fam.band .cells");
      if (!cells) return;
      cells.setPointerCapture?.(e.pointerId);
      this.scrub(cells, e.clientX);
      const move = (ev: PointerEvent) => this.scrub(cells, ev.clientX);
      const up = () => {
        cells.removeEventListener("pointermove", move);
        cells.removeEventListener("pointerup", up);
        cells.removeEventListener("pointercancel", up);
      };
      cells.addEventListener("pointermove", move);
      cells.addEventListener("pointerup", up);
      cells.addEventListener("pointercancel", up);
    });
    if (this.rail && this.chat) {
      this.chat.addEventListener("scroll", () => this.follow(), { passive: true });
      this.follow();
    }
  }

  private levelOf(n: number): HTMLElement | null {
    return this.root.querySelector<HTMLElement>(`.chat .level[data-level="${n}"]`);
  }

  /** The card a scroll is asked to: a level by number, the summary box or the coverage card. */
  private cardOf(to: ScrollTo): HTMLElement | null {
    if (typeof to === "number") return this.levelOf(to);
    return this.root.querySelector<HTMLElement>(`.chat .level.${to === "why" ? "why" : "cover"}`);
  }

  /** The width the app's timeline was last given here. */
  private picWidth = 0;

  /** The app's timeline measures the width it has; mounted inside a closed
   * headline it has none and draws itself at a stand-in width, at its left
   * end. When a level opens and the picture has a width it did not have, the
   * record is given to it again: it draws itself at that width and parks at
   * the present, as the app parks a line drawn anew (R-0381). A window resize
   * the app handles itself. */
  private remeasure(): void {
    const view = this.root.querySelector<HTMLElement>(".pic .view");
    const w = view?.clientWidth ?? 0;
    if (!w || w === this.picWidth) return;
    this.picWidth = w;
    this.page.lens?.picture.setData(this.m.view.tl);
  }

  /** The level a rail tap asked for, kept lit while the scroll it caused settles
   * (the last levels cannot reach the top of a short screen). */
  private asked: { level: number; until: number } | null = null;

  /** The rail lights the level at the top of the screen and scrolls itself so
   * the lit word is in view. */
  private follow(): void {
    const chat = this.chat;
    const rail = this.rail;
    if (!chat || !rail) return;
    if (this.asked && Date.now() > this.asked.until) this.asked = null;
    const levels = [...chat.querySelectorAll<HTMLElement>(".level[data-level]")].filter((l) => Number(l.dataset.level) > 0);
    const top = chat.scrollTop + 12;
    let current = levels[0];
    for (const l of levels) if (l.offsetTop - chat.offsetTop <= top) current = l;
    const lit = this.asked ? String(this.asked.level) : current?.dataset.level;
    let on: HTMLElement | null = null;
    rail.querySelectorAll<HTMLElement>("[data-jump]").forEach((b) => {
      const is = b.dataset.jump === lit;
      b.classList.toggle("on", is);
      if (is) on = b;
    });
    if (!on) return;
    const rb = rail.getBoundingClientRect();
    const bb = (on as HTMLElement).getBoundingClientRect();
    if (bb.left < rb.left + 8) rail.scrollLeft += bb.left - rb.left - 8;
    else if (bb.right > rb.right - 8) rail.scrollLeft += bb.right - rb.right + 8;
  }

  /** To a card: scrolled to the top, opened if it is a headline, and on a
   * reader's tap ringed with the app's own light for what a jump points at
   * (R-0055), so a tap on the level already on screen is answered too. */
  private jump(to: ScrollTo, tapped = false): void {
    const l = this.cardOf(to);
    if (!l) {
      // a level pinned in the dashboard column: its card lit with the app's own
      // ring, back at the column's top, and its word lit on the rail a moment
      const pinned = this.root.querySelector<HTMLElement>(`.pinned .level[data-level="${to}"]`);
      if (pinned && typeof to === "number") {
        flash(pinned, true);
        this.asked = { level: to, until: Date.now() + 1200 };
        this.follow();
        window.setTimeout(() => this.follow(), 1250);
      }
      return;
    }
    if (!this.chat) return;
    if (typeof to === "number") this.asked = { level: to, until: Date.now() + 600 };
    this.chat.scrollTop = Math.max(0, l.offsetTop - this.chat.offsetTop - 8);
    if (this.o.hierarchy === "collapsed" && typeof to === "number") l.classList.add("on");
    this.remeasure();
    if (tapped) flash(l, true);
    this.follow();
  }

  /** The tail of a cut sentence shown or hidden, with its ellipsis. */
  private tails(within: Element, show: boolean): void {
    within.querySelectorAll<HTMLElement>(".tail").forEach((t) => (t.hidden = !show));
    within.querySelectorAll<HTMLElement>(".head").forEach((h) => h.classList.toggle("cut", !show && !!h.nextElementSibling));
  }

  private say(where: Element, text: string): void {
    const host = where.closest(".level, .dash, .guessbox")?.querySelector<HTMLElement>(".note") ?? where.closest(".level")?.querySelector<HTMLElement>(".note");
    if (host) host.textContent = text;
  }

  /** The note for a person: name, dates, what the record holds of them, and the
   * first few of their dated facts in the record's words; and the picture aimed at them. */
  private sayPerson(where: Element, id: string | undefined, byKey: boolean): void {
    const p = byKey ? this.cov.byKey.get(id ?? "") : this.cov.byId.get(id ?? "");
    if (!p) return;
    const what = p.tier === "story" ? `${plural(p.story, "thing that happened to", "things that happened to")} ${p.sex === "F" ? "her" : p.sex === "M" ? "him" : "them"} in the record` : p.tier === "dates" ? "dates or a mention only" : "a name only";
    const own = stripItems(
      this.m,
      this.m.file.events.filter((e) => e.person === p.id && e.text.trim()),
    );
    const shown = own.slice(0, 3).map((it) => `${it.date} ${it.label}`);
    const tail = own.length > shown.length ? `; and ${own.length - shown.length} more` : "";
    this.say(where, `${p.name}${p.dates ? ` · ${p.dates}` : ""} · ${what}${shown.length ? ` — ${shown.join("; ")}${tail}` : ""}.`);
    this.page.lens?.aim({ kind: ChipKind.Person, target: p.key, label: p.name, tone: ChipTone.Data, bare: false });
  }

  /** The year under a finger on the band, from where it is along the row. */
  private scrub(cells: HTMLElement, clientX: number): void {
    const box = cells.getBoundingClientRect();
    if (!box.width) return;
    const from = Number(cells.dataset.from);
    const to = Number(cells.dataset.to);
    const year = from + Math.floor(((clientX - box.left) / box.width) * (to - from + 1));
    this.sayYear(cells, year);
  }

  /** The band's readout for one year: the marker on the band, the slider's
   * value, and the note of what that year holds. */
  private sayYear(cells: HTMLElement, year: number): void {
    const from = Number(cells.dataset.from);
    const to = Number(cells.dataset.to);
    const y = Math.min(to, Math.max(from, year));
    const cell = this.cov.band.cells.find((c) => c.year === y);
    if (!cell) return;
    const cur = cells.querySelector<HTMLElement>(".ycur");
    if (cur) {
      cur.hidden = false;
      cur.style.left = `${(((y - from + 0.5) / (to - from + 1)) * 100).toFixed(2)}%`;
    }
    cells.setAttribute("aria-valuenow", String(y));
    cells.setAttribute("aria-valuetext", `${y}: ${plural(cell.n, "dated fact")}`);
    const shown = cell.labels.slice(0, 4);
    const tail = cell.labels.length > shown.length ? `; and ${cell.labels.length - shown.length} more` : "";
    this.say(cells, `${cell.year}: ${plural(cell.n, "dated fact")}${shown.length ? ` — ${shown.join("; ")}${tail}` : ""}.`);
  }

  private tap(e: Event): void {
    const el = e.target as HTMLElement;
    const hit = (sel: string) => el.closest<HTMLElement>(sel);
    const more = hit(".more");
    if (more) {
      const lv = more.closest<HTMLElement>(".level, .guessbox");
      const open = !!lv?.classList.toggle("open");
      const r = more.previousElementSibling as HTMLElement | null;
      if (r?.classList.contains("rest")) r.hidden = !open;
      if (lv) this.tails(lv, open);
      more.textContent = open ? "less" : "more";
      return;
    }
    const pt = hit(".pt");
    if (pt) {
      const li = pt.closest<HTMLElement>(".part")!;
      const open = li.classList.toggle("open");
      const pm = li.querySelector<HTMLElement>(".pmore");
      if (pm) pm.hidden = !open;
      this.tails(li, open);
      return;
    }
    // a fact chip: the app's chip aims the timeline (casepage.ts), which stands
    // in level 5; that level opens so the aimed event is lit when the reader
    // reaches it, and the fact's date and words are said under the chips
    const fact = hit(`.chip[data-kind="${ChipKind.Event}"][data-target]`);
    if (fact) {
      const full = fact.dataset.full ?? fact.textContent ?? "";
      this.say(fact, full);
      const l5 = this.levelOf(5);
      if (l5 && this.o.hierarchy === "collapsed" && !l5.classList.contains("on")) {
        l5.classList.add("on");
        this.remeasure();
        this.page.lens?.aim({ kind: ChipKind.Event, target: fact.dataset.target!, label: full, tone: ChipTone.Data, bare: false });
      }
      return;
    }
    // a cut line opens on its own tap
    const line = hit(".lead:has(.tail)");
    if (line && !hit(".level > .label")) {
      const tail = line.querySelector<HTMLElement>(".tail");
      if (tail) this.tails(line, tail.hidden);
      return;
    }
    const jump = hit("[data-jump]");
    if (jump) {
      this.jump(Number(jump.dataset.jump), true);
      return;
    }
    const all = hit(".openall");
    if (all) {
      const c = this.root.querySelector(".chat .case");
      const folded = c?.classList.toggle("folded");
      all.textContent = folded ? "Open all" : "Close all";
      this.remeasure();
      return;
    }
    const q = hit(".qchip");
    if (q) {
      const found = this.cov.questions.find((x) => x.id === q.dataset.q);
      if (found) this.say(q, `${found.text} — asked ${found.askedAt}${found.state === "resolved" ? ", answered" : ", no answer yet"}.`);
      return;
    }
    const slot = hit("[data-slot]");
    if (slot) {
      const s = this.cov.slots.find((x) => x.id === slot.dataset.slot);
      if (s) this.say(slot, `${s.role[0]} ${s.role[1]}: ${s.question ? `asked ${s.question.askedAt}, no answer yet. ${s.question.text}` : "not in the record; the coach has not asked."}`);
      return;
    }
    const shaded = hit(".fam.cov .p[data-id]");
    if (shaded) {
      this.sayPerson(shaded, shaded.dataset.id, true);
      return;
    }
    const person = hit("[data-person]");
    if (person) {
      this.sayPerson(person, person.dataset.person, false);
      return;
    }
    // a tap on the band is read on pointerdown; a click with no place (a
    // keyboard's, or one sent to a cell) reads the cell it names, or the year
    // the band last read
    const band = hit(".fam.band .cells");
    if (band) {
      const me = e as MouseEvent;
      if (me.clientX || me.clientY) return;
      const cell = hit(".yc[data-year]");
      this.sayYear(band, cell ? Number(cell.dataset.year) : Number(band.getAttribute("aria-valuenow")));
      return;
    }
    const label = hit(".wlab[data-runs]");
    if (label) {
      const runs = this.cov.band.runs.map(runLabel);
      this.say(label, runs.length ? `Years of ${this.m.view.pronoun.his} life with nothing in the record: ${runs.join(" · ")}.` : "Every year of life holds a dated fact.");
      return;
    }
    const num = hit(".num[data-list]");
    if (num) {
      const card = num.closest(".level")!;
      card.querySelectorAll<HTMLElement>(".numlist").forEach((l) => (l.hidden = !(l.dataset.for === num.dataset.list && l.hidden)));
      card.querySelectorAll<HTMLElement>(".num").forEach((b) => b.classList.toggle("on", b === num && !card.querySelector<HTMLElement>(`.numlist[data-for="${num.dataset.list}"]`)!.hidden));
      return;
    }
    const si = hit(".si[data-event]");
    if (si) {
      const chip: Chip = { kind: ChipKind.Event, target: si.dataset.event!, label: si.dataset.full ?? "", tone: ChipTone.Data, bare: false };
      this.page.lens?.aim(chip);
      this.say(si, si.dataset.full ?? "");
      return;
    }
    if (hit(".fab")) {
      this.famout(true);
      return;
    }
    if (hit(".famout .backbtn")) {
      this.famout(false);
      return;
    }
    if (this.o.hierarchy === "collapsed") {
      const head = hit(".case.folded .level > .label, .case.folded .level:not(.on) > .lead.fold");
      if (head) {
        head.closest(".level")?.classList.toggle("on");
        this.remeasure();
      }
    }
  }

  famout(up: boolean): void {
    const panel = this.root.querySelector<HTMLElement>(".famout");
    if (panel) slideOver(panel, up);
  }

  start(state: ReportState): void {
    this.page.start(state);
    (state.open ?? []).forEach((n) => this.levelOf(n)?.querySelector<HTMLElement>(".more")?.click());
    (state.unfolded ?? []).forEach((n) => this.levelOf(n)?.classList.add("on"));
    if (state.unfolded?.length) this.remeasure();
    if (state.part) this.root.querySelector<HTMLElement>(`.chat .level[data-level="6"] .part[data-part="${state.part}"] .pt`)?.click();
    if (state.list) this.root.querySelector<HTMLElement>(`.num[data-list="${state.list}"]`)?.click();
    if (state.scrollTo) this.jump(state.scrollTo);
    if (state.famout) this.famout(true);
    if (this.rail) this.follow();
  }
}
