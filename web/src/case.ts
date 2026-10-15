import { pill } from "./chips";
import { draw, leastScale } from "./diagram";
import { closeX, esc } from "./dom";
import { Card, GUESS_CARDS, ORDER, TOO_LITTLE, type CaseView, type Fact, type Guess, type Held, type Stated, type Still, type Who } from "./caseview";
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
    case Card.WorkOn:
      return "What to work on";
    case Card.Effort:
      return "The effort";
  }
}

/** Which passages a card's book raises (the keys of the passages file). */
function bookOf(card: Card): string {
  switch (card) {
    case Card.Main:
      return "why";
    case Card.Family:
      return "1";
    case Card.Brought:
      return "2";
    case Card.Couple:
      return "3";
    case Card.Sides:
      return "4";
    case Card.Guesses:
      return "6";
    case Card.OwnPart:
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
/** What the card on what brought the person says before the coach has found it out (R-0850). */
export const NOT_ASKED = "Not asked yet.";
export const BRINGS = "What brings you here?";

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
const chip = (kind: ChipKind, target: string | number, face: string, mark = "") =>
  pill({ kind, target: String(target), label: face, tone: ChipTone.Data, bare: false }, face, mark);

/** The picture's own mark for a date it is unsure of: its key's hollow dot (R-0855). */
export const UNSURE = `<span class="ab-swatch ab-hollow"></span>`;

const factChip = (f: Fact) => chip(ChipKind.Event, f.id, f.face, f.sure ? "" : UNSURE);
const clusterChip = (c: { id: string; label: string }) => chip(ChipKind.Cluster, c.id, c.label);
/** What the app still needs to know, de-emphasized: the dashed amber chip (R-0850). */
const needs = (words: string) => `<span class="chip ask qmark dashed">? ${esc(words)}</span>`;
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
  `<div class="gbub">${bubble(g.text, g.facts, ask)}${chips([...g.facts.map(factChip), ...g.clusters.map(clusterChip), ...g.shown.map(personChip)])}</div>`;

/** A cluster under the coach's guess: its chip, then what holds for it and against it (R-0850). */
const held = (c: Held) => {
  const slot = (mark: string, words: string | null) => (words ? `<b>${mark}</b><span>${esc(words)}</span>` : "");
  const slots = c.for || c.against ? `<div class="slots">${slot("For", c.for)}${slot("Against", c.against)}</div>` : "";
  return `<div class="cl${c.mine ? " his" : ""}">${clusterChip(c)}${slots}</div>`;
};

/** A stored card's words in order, each part the person's own words inside
 * quotation marks or the coach's words around them. */
export function quoted(text: string): { quote: boolean; words: string }[] {
  const parts: { quote: boolean; words: string }[] = [];
  let last = 0;
  for (const m of text.matchAll(/\u201c([^\u201d]+)\u201d|"([^"]+)"/g)) {
    parts.push({ quote: false, words: text.slice(last, m.index) }, { quote: true, words: m[1] ?? m[2] });
    last = m.index + m[0].length;
  }
  parts.push({ quote: false, words: text.slice(last) });
  return parts.map((p) => ({ ...p, words: p.words.trim() })).filter((p) => /[\p{L}\p{N}]/u.test(p.words));
}

/** The person's own words in the statement bubble and the coach's around them
 * as plain card text; words with no quotation marks are all the person's (R-0863). */
function said(text: string): string {
  const user = (words: string) => `<div class="gbub"><div class="bub user">${esc(words)}</div></div>`;
  const parts = quoted(text);
  if (!parts.some((p) => p.quote)) return user(text);
  return parts.map((p) => (p.quote ? user(p.words) : lead(p.words))).join("");
}

const notEnough = (words = NOT_ENOUGH) => `<div class="gbub">${bubble(words)}</div>`;

/** A card the coach writes as one statement: its words, one chip per event and,
 * with `people`, per person it rests on; with too little, what it still needs
 * as the dashed amber chip (R-0850, R-0866). */
function stated(s: Stated, people = true): string {
  if (s.needs !== null) return `<div class="gbub">${bubble(`${TOO_LITTLE}.`)}</div>${s.needs ? needs(s.needs) : ""}`;
  const g = s.guess;
  if (!g) return notEnough();
  return `<div class="gbub">${bubble(g.text, g.facts)}${chips([...g.facts.map(factChip), ...(people ? g.shown.map(personChip) : [])])}</div>`;
}

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

function body(card: Card, v: CaseView): string {
  switch (card) {
    case Card.Main:
      return v.main ? guessBlock(v.main) : notEnough();
    case Card.Family:
      return stated(v.family);
    case Card.Brought: {
      // the person's own words with whose and when, else the coach's reading, else what it still needs (R-0850)
      const b = v.brought;
      if (!b) return lead(NOT_ASKED) + needs(BRINGS);
      return b.said ? said(b.text) + faint(b.said) : guessBlock(b);
    }
    case Card.Couple:
      return stated(v.couple, false);
    case Card.Sides:
      // the coach's statement on each side under that side's name (R-0866)
      return v.sideNotes.length ? v.sideNotes.map((s) => (s.label ? sublabel(s.label) : "") + stated(s.note)).join("") : notEnough();
    case Card.Guesses: {
      // the pattern, then each cluster with its for and against, each opening its cluster, then what it still needs (R-0850, R-0698, R-0201)
      const lead = v.guess ? `<div class="gbub">${bubble(v.guess.text, v.guess.facts)}</div>` : notEnough();
      const clusters = v.hypotheses.length ? `<div class="glist">${v.hypotheses.map(held).join("")}</div>` : "";
      return `<div class="glist">${lead}${clusters}${v.ask ? needs(v.ask) : ""}</div>`;
    }
    case Card.OwnPart: {
      // the moves, then the other way it could have gone, stated as the alternative (R-0850)
      const o = v.ownPart;
      const other = o.guess?.other ? `<span class="chip ask qmark">? ${esc(o.guess.other)}</span>` : "";
      const coach = o.guess ? guessBlock(o.guess, o.ask) + other : o.ask ? `<div class="gbub">${bubble("", [], o.ask)}</div>` : "";
      const own = o.answer ? `${sublabel(`${v.name}'s own view`)}<div class="bub user">${esc(o.answer)}</div>` : "";
      return coach || own ? coach + own : notEnough();
    }
    case Card.WorkOn: {
      // the focus, then the prognosis as its own sentence, then the aim in the person's words (R-0850)
      const w = v.work;
      if (!w.guesses.length) return notEnough(NOT_SAID);
      const aim = w.said ? `<span class="chip his">${esc(`You said: ${w.said}`)}</span>` : w.aim ? factChip(w.aim) : "";
      const work = w.guesses.map((g) => guessBlock(g) + (g.prognosis ? `<p class="prognosis">${esc(g.prognosis)}</p>` : "")).join("");
      return `<div class="glist">${work}</div>${aim ? chips([aim]) : ""}`;
    }
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
    `<p class="label">${n} · ${esc(name)}</p>${body(card, v)}${more}${book(bookOf(card), name)}</section>`
  );
}

/** The cards in order. On the phone the family card ends on the strip's own
 * family item, which opens the picture; on a wide window the picture stands
 * in the column beside the cards instead (R-0697, R-0866). */
export function cards(v: CaseView, wide: boolean): string {
  const button = wide ? "" : `<button type="button" class="famcard">${face(Card.Family, v)}</button>`;
  return `<div class="case">${ORDER.map((c) => card(c, v, c === Card.Family ? button : "")).join("")}</div>`;
}

/** The family picture for the column or the slide-out, as the approved
 * proposal draws it: the person's family, then each parent's side (R-0697);
 * the family card itself carries the title, so the picture shows none. */
export function dashboard(v: CaseView): string {
  const sides = v.sides.map((s) => `<div class="side"><p class="sub">${esc(s.label)}</p>${picture(v, s.still, s.label)}</div>`);
  return `<div class="case dash"><section class="level">${picture(v, v.household, `${v.name}'s family`)}${sides.join("")}</section></div>`;
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
