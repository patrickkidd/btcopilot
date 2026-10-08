import { pill } from "./chips";
import { draw, leastScale } from "./diagram";
import { closeX, esc } from "./dom";
import { Card, GUESS_CARDS, ORDER, type CaseView, type Fact, type Guess, type Still, type Who } from "./caseview";
import { ChipKind, ChipTone, type Passages } from "./types";

/** The case report's markup, card by card, as the approved proposal draws it
 * (R-0713): the titles Patrick reviewed (R-0716), a coach's guess as the
 * chat's own coach bubble on the white card (R-0698), the facts it rests on as
 * one-line chips, every card's book button (R-0691), and the strip of cards
 * (R-0702). Every word comes from the CaseView; this module writes none of its
 * own about the record. */

/** The card titles, as Patrick reviewed them (R-0716), card one's renamed (R-0821). */
export function title(card: Card, v: CaseView): string {
  switch (card) {
    case Card.Main:
      return "Executive Summary";
    case Card.Family:
      return "Who is in the family";
    case Card.Brought:
      return `What brought ${v.name}`;
    case Card.Couple:
      return v.married ? "The couple since they met" : `${v.name}'s parents and partners, stage by stage`;
    case Card.Sides:
      return "Each parent's own family";
    case Card.Guesses:
      return "The coach's guess";
    case Card.OwnPart:
      return `${v.name}'s own part`;
    case Card.Choice:
      return "Where there was a choice";
    case Card.WorkOn:
      return "What to work on, what to expect";
    case Card.Effort:
      return "The effort";
  }
}

/** The strip's short names for the same cards. */
function short(card: Card, v: CaseView): string {
  switch (card) {
    case Card.Main:
      return "Executive Summary";
    case Card.Family:
      return "The family";
    case Card.Brought:
      return `What brought ${v.him}`;
    case Card.Couple:
      return v.married ? "The couple" : "Parents and partners";
    case Card.Sides:
      return "Each parent's family";
    case Card.Guesses:
      return "The coach's guess";
    case Card.OwnPart:
      return `${v.name}'s part`;
    case Card.Choice:
      return "The choice";
    case Card.WorkOn:
      return "What to work on";
    case Card.Effort:
      return "The effort";
  }
}

/** Which passages a card's book raises (the keys of the passages file). */
function bookOf(card: Card, v: CaseView): string {
  switch (card) {
    case Card.Main:
      return "why";
    case Card.Family:
      return "1";
    case Card.Brought:
      return "2";
    case Card.Couple:
      return v.married ? "3" : "3s";
    case Card.Sides:
      return "4";
    case Card.Guesses:
      return "6";
    case Card.OwnPart:
    case Card.Choice:
      return "7a";
    case Card.WorkOn:
      return "9a";
    case Card.Effort:
      return "10";
  }
}

/** The strip's own book: why these cards, in this order. */
export const ORDER_BOOK = "order";
export const ORDER_TITLE = "Why these cards, in this order";

/** What a guess card says when the coach has put nothing on it (R-0699, Patrick, 2026-10-04). */
export const NOT_ENOUGH = "Not enough in the diagram to make a guess yet. Chat more with me so I have more to go on.";
/** What the work card says when the person has not said what they are working on (R-0740). */
export const NOT_SAID = "You haven't said yet what you're working on. Chat more with me about it.";

const lead = (text: string) => (text ? `<p class="lead">${esc(text)}</p>` : "");
const sublabel = (text: string) => `<p class="sublabel">${esc(text)}</p>`;
const faint = (text: string) => `<p class="faint">${esc(text)}</p>`;

const UNKNOWN_NOTE = "?: the other parent, unnamed.";

export const BOOK_ICON =
  `<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round">` +
  `<path d="M12 6.5C10 5 7.5 4.5 4 4.5v13c3.5 0 6 .5 8 2 2-1.5 4.5-2 8-2v-13c-3.5 0-6 .5-8 2zM12 6.5v13"/></svg>`;

export const book = (key: string, of: string) =>
  `<button type="button" class="book" data-book="${key}" data-title="${esc(of)}" aria-label="the passages behind this">${BOOK_ICON}</button>`;

export const familyIcon = (size: number) =>
  `<svg viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6">` +
  `<rect x="3" y="3" width="6" height="6"/><circle cx="18" cy="6" r="3"/><path d="M6 9v3h12V9M12 12v3"/><rect x="9" y="15" width="6" height="6"/></svg>`;

/** A chip of the thread: a tap does what a chip does on the case report. */
const chip = (kind: ChipKind, target: string | number, face: string) =>
  pill({ kind, target: String(target), label: face, tone: ChipTone.Data, bare: false }, face);

const factChip = (f: Fact) => chip(ChipKind.Event, f.id, f.face);
const personChip = (p: Who) => chip(ChipKind.Person, p.id, p.name);
const chips = (inner: string[]) => (inner.length ? `<div class="chips">${inner.join("")}</div>` : "");

/** The coach's chat bubble (chat.ts): its "Coach" label lights all the guess's
 * facts together, then its words, then any question it asks as the amber chip. */
function bubble(words: string, facts: Fact[] = [], ask: string | null = null): string {
  const who = facts.length
    ? `<button type="button" class="who lall" data-target="${facts.map((f) => f.id).join(",")}">Coach</button>`
    : `<div class="who">Coach</div>`;
  const question = ask ? ` <span class="chip ask qmark">? ${esc(ask)}</span>` : "";
  return `<div class="bub coach">${who}${esc(words)}${question}</div>`;
}

const guessBlock = (g: Guess, ask: string | null = null) =>
  `<div class="gbub">${bubble(g.text, g.facts, ask)}${chips([...g.facts.map(factChip), ...g.people.map(personChip)])}</div>`;

const notEnough = (words = NOT_ENOUGH) => `<div class="gbub">${bubble(words)}</div>`;

/** What the person said, under the coach's line it rests on: their own words
 * in their own bubble, each dated, oldest first (R-0707). Nothing when the
 * guess rests on no message and no dated event. */
const saidBlock = (v: CaseView, g: Guess) =>
  g.said.length
    ? sublabel(`${v.name}'s own words`) + g.said.map((s) => `<div class="bub user">${esc(s.words)}</div>${s.when ? faint(s.when) : ""}`).join("")
    : "";

/** The top padding of a family's frame on the report, as casereport.css gives it. */
const FAM_PAD = 4;

/** A family standing still, drawn by the app's own drawing, or the layout's
 * own words for why it cannot be. */
export function picture(v: CaseView, still: Still, label: string): string {
  const L = still.layout;
  if (!L) return faint(`The family picture cannot be drawn: ${still.fault ?? "unknown"}.`);
  const bonds = L.bonds.map((b) => ({ a: b.a, b: b.b, st: b.st, married: b.married, fresh: 0, hot: false }));
  const unknown = Object.keys(L.P).some((k) => k.startsWith("unknown-"));
  const svg = draw(L, { t: v.now, bonds, marks: [], died: new Set<string>(), moves: [], kin: [], label });
  // never drawn under the drawer's floor: a wider family pans in its frame (R-0759)
  const least = Math.ceil(L.vw * leastScale(L, FAM_PAD));
  const you = Object.keys(L.P).find((k) => L.P[k].you);
  const who = you ? ` data-who="${esc(you)}"` : "";
  return `<div class="fam" style="--least:${least}px"${who}>${svg}</div>${unknown ? faint(UNKNOWN_NOTE) : ""}`;
}

/** One side of the family: the one fold on the report (R-0689), its words
 * under its heading, then its pictures. */
const fold = (label: string, inner: string) =>
  `<details class="side" open><summary class="sub">${esc(label)}</summary><div class="sidein">${inner}</div></details>`;

function body(card: Card, v: CaseView): string {
  switch (card) {
    case Card.Main:
      return v.main ? guessBlock(v.main) : notEnough();
    case Card.Family:
      return picture(v, v.household, `${v.name}'s family`);
    case Card.Brought: {
      const b = v.brought;
      const course = [
        ...(b.first ? [factChip(b.first)] : []),
        ...(b.latest ? [factChip(b.latest)] : []),
        ...b.clusters.map((c) => chip(ChipKind.Cluster, c.id, c.label)),
      ];
      return lead(b.lead) + (course.length ? sublabel("The trouble's course, dated") + chips(course) : "") + lead(b.asked);
    }
    case Card.Couple:
      if (v.married) return lead(v.couple.lead) + chips(v.couple.facts.map(factChip));
      return v.stages
        .map((row) => `<div class="stage">${sublabel(row.label)}${row.stages.map((st) => chips([factChip(st.head), ...st.facts.map(factChip)])).join("")}</div>`)
        .join("");
    case Card.Sides:
      return v.sides.map((s) => fold(s.label, lead(s.lead) + picture(v, s.still, s.label))).join("");
    case Card.Guesses: {
      const ask = v.ask ? `<div class="gbub">${bubble("", [], v.ask)}</div>` : "";
      return `<div class="glist">${v.guesses.length ? v.guesses.map((g) => guessBlock(g)).join("") : notEnough()}${ask}</div>`;
    }
    case Card.OwnPart: {
      const o = v.ownPart;
      const coach = o.guess ? guessBlock(o.guess, o.ask) : o.ask ? `<div class="gbub">${bubble("", [], o.ask)}</div>` : "";
      const own = o.answer ? `${sublabel(`${v.name}'s own view`)}<div class="bub user">${esc(o.answer)}</div>` : "";
      return coach || own ? coach + own : notEnough();
    }
    case Card.Choice:
      return v.choice.guess ? guessBlock(v.choice.guess, v.choice.ask) : v.choice.ask ? `<div class="gbub">${bubble("", [], v.choice.ask)}</div>` : notEnough();
    case Card.WorkOn:
      // under each guess, what the person said they are working on, in their own words (R-0707)
      return v.work.guesses.length
        ? chips(v.work.aim ? [factChip(v.work.aim)] : []) + `<div class="glist">${v.work.guesses.map((g) => guessBlock(g) + saidBlock(v, g)).join("")}</div>`
        : notEnough(NOT_SAID);
    case Card.Effort:
      return lead(v.effort);
  }
}

/** One card, numbered as its item in the strip. A guess card always draws its
 * body; a record card with nothing in it is its title and its book (R-0710). */
export function card(card: Card, v: CaseView, more = ""): string {
  const n = ORDER.indexOf(card) + 1;
  const name = title(card, v);
  return (
    `<section class="level${GUESS_CARDS.has(card) ? " guess" : ""}" data-card="${card}">` +
    `<p class="label">${n} · ${esc(name)}</p>${body(card, v)}${more}${book(bookOf(card, v), name)}</section>`
  );
}

/** The cards in order. On the phone the family card holds one control, the
 * strip's own family item, which opens the picture; on a wide window the
 * family stands in the column beside the cards instead (R-0697). */
export function cards(v: CaseView, wide: boolean): string {
  const family = wide
    ? ""
    : `<section class="level fam1" data-card="${Card.Family}"><button type="button" class="famcard">${face(Card.Family, v)}</button></section>`;
  return `<div class="case">${ORDER.map((c) => (c === Card.Family ? family : card(c, v))).join("")}</div>`;
}

/** The family card for the column or the slide-out, as the approved proposal
 * draws it: the person's family, then each parent's side (R-0697). */
export function dashboard(v: CaseView): string {
  const sides = v.sides.map((s) => `<div class="side"><p class="sub">${esc(s.label)}</p>${picture(v, s.still, s.label)}</div>`);
  return `<div class="case dash">${card(Card.Family, v, sides.join(""))}</div>`;
}

/** A strip item's face: its number, the family button's icon on the family's, its name. */
const face = (c: Card, v: CaseView) => `<b>${ORDER.indexOf(c) + 1}</b>${c === Card.Family ? familyIcon(16) : ""}${esc(short(c, v))}`;

/** The strip: one item per card, in the cards' order, and its book (R-0702). */
export const rail = (v: CaseView) =>
  ORDER.map((c) => `<button type="button" data-jump="${c}">${face(c, v)}</button>`).join("") + book(ORDER_BOOK, ORDER_TITLE);

/** The sheet a book button raises: the card's title and its passages, each with its reference (R-0691). */
export function passages(all: Passages, key: string, of: string): string {
  const list = (all[key] ?? []).map((p) => `<blockquote>${esc(p.text)}</blockquote><p class="bk-by">${esc(p.by)}</p>`).join("");
  return `${closeX()}<div class="cf-t">${esc(of)}</div><p class="bk-sub">The passages behind this</p><div class="bk-list">${list}</div>`;
}
