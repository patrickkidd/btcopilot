import { pill } from "./chips";
import type { Layout } from "./diagram";
import { esc } from "./dom";
import { ChipKind, ChipTone, type Case, type Chip, type Cluster, type Timeline } from "./types";

/** The case page: a record read as a presented case, in the order ruled on
 * 2026-10-01 (who is in the family, what brought them, the couple, each
 * parent's own family, the timeline, the reading, the person's own part, where
 * there was a choice, what to work on, the effort). Facts and guesses are two
 * layers the eye tells apart: a fact is a plain card, a guess is an amber box
 * that says so and shows what it rests on behind its first tap. Nothing is
 * filled in: a gap says "not in the record". This module holds what the page
 * is made of: the shape of a case as the page reads it (CaseView), and the
 * page's own pieces of markup. The levels are composed in casepage.ts; the
 * pictures come from diagram.ts and the line from picture.ts. */

/** One dated line of the record, the date written as far as the record holds it. */
export interface Row {
  date: string;
  text: string;
}

/** A chip into the record: a person, an event or a cluster, and the words on the chip. */
export interface Ref {
  kind: ChipKind.Person | ChipKind.Event | ChipKind.Cluster;
  id: string;
  label: string;
}

/** A family picture standing still: the app's layout of a cast, or the layout's
 * own words for why it refused the picture. */
export interface Still {
  layout: Layout | null;
  fault: string | null;
  label: string;
  /** Whether the picture draws the "?" shape for a parent the record does not hold. */
  unknownParent: boolean;
}

/** A guess: its words, what it rests on in the record, and what the record
 * does not hold about it. */
export interface Guess {
  text: string;
  rests: Ref[];
  gaps: string[];
}

/** A cluster of the line with its telling: the case the drawer tells, why the
 * app cannot tell it when it cannot, and the steps the record does not date. */
export interface ClusterView {
  cluster: Cluster;
  title: string;
  told: Case;
  fault: string | null;
  undated: string[];
}

export interface SidePicture {
  sub: string | null;
  still: Still;
  /** The children of the couple in the record, or the gap. */
  kids: string;
  gaps: string[];
}

/** One side of the family under level 4. */
export interface SideView {
  label: string;
  text: string;
  pics: SidePicture[];
  /** The record's undated events about people on this side. */
  undated: string[];
}

/** A question a viewer pinned to a cluster or a person. */
export interface PinView {
  to: Ref;
  text: string;
}

/** Where there was a choice: one dated step of the person's own. */
export interface Choice {
  date: string;
  /** The event the step is the words of, as the app's id, or null. */
  event: string | null;
  step: string;
  /** Whose words the step is in. */
  part: string;
  facts: string[];
  /** A question on the step written in the record; null when the record holds none. */
  question: string | null;
}

/** A case as the page reads it. Every string is as the page shows it: the
 * record's own words, or the record's gaps said as gaps. */
export interface CaseView {
  key: string;
  title: string;
  subject: { id: string; name: string };
  /** Presented by the person themself, or by a professional about them. */
  self: boolean;
  presenter: string;
  /** The professional whose reading may get a box of its own. */
  pro: string | null;
  pronoun: { he: string; his: string; him: string };
  header: string | null;
  account: string;
  tl: Timeline;
  /** The pictures' "now": the record's last date, as a year with its fraction. */
  now: number;
  recordEnd: { closed: boolean; date: string };
  // level 1
  household: Still;
  siblings: string;
  householdGaps: string[];
  undrawn: string | null;
  // level 2
  asked: string;
  whatBrought: string;
  flares: Row[];
  ownUndated: string[];
  // level 3
  couple: { text: string; rows: Row[]; gaps: string[] };
  // level 4
  sides: SideView[];
  looseUndated: string[];
  // level 5
  clusters: ClusterView[];
  stacked: string[];
  pins: PinView[];
  notHeld: string[];
  // levels 6 to 10
  reading: Guess;
  ownPart: Guess;
  choice: Choice;
  workOn: Guess;
  effort: { text: string; guess: Guess | null; gaps: string[] };
  /** The record's last dated events: where things stand now, in facts. */
  outcome: Row[];
}

/** One numbered level of the page. */
export const level = (n: number, title: string, inner: string, cls = ""): string =>
  `<section class="level${cls ? ` ${cls}` : ""}" data-level="${n}">` +
  `<p class="label">${n} · ${esc(title)}</p>${inner}</section>`;

/** A line of the record that stands on its own under a level. */
export const line = (text: string): string => `<p>${esc(text)}</p>`;

/** A small heading inside a level. */
export const sublabel = (text: string): string => `<p class="sublabel">${esc(text)}</p>`;

/** What the record does not hold, said as such and never filled in. */
export const gapLine = (text: string): string => `<p class="gapline">${esc(text)}</p>`;

/** A quiet line under a picture or a list: a legend, who else the record holds. */
export const faint = (text: string): string => `<p class="faint">${esc(text)}</p>`;

/** The record's dated lines, oldest first. */
export const dateList = (rows: Row[]): string =>
  `<ul class="dates">${rows.map((r) => `<li><span class="d">${esc(r.date)}</span><span>${esc(r.text)}</span></li>`).join("")}</ul>`;

/** A chip naming a person, an event or a cluster of the record, the thread's own chip. */
export const nameChip = (ref: Ref): string => {
  const chip: Chip = { kind: ref.kind, target: ref.id, label: ref.label, tone: ChipTone.Data, bare: false };
  return pill(chip, ref.label);
};

/** The family on a picture, drawn by diagram.ts, standing still. */
export const familyPicture = (svg: string): string => `<div class="fam">${svg}</div>`;

/** A guess: an amber box that says whose guess it is and who may reject it,
 * with what it rests on in the record behind its first tap. */
export function guessBox(label: string, text: string, rests: string, extra = ""): string {
  return (
    `<div class="guessbox"><p class="label">${esc(label)}</p><p>${esc(text)}</p>${extra}` +
    `<button class="basis-open" type="button">what this rests on</button>` +
    `<div class="basis">${rests}</div></div>`
  );
}

/** What a guess rests on: chips for the people and events the record names, or
 * the gap where it names none. */
export const basis = (chips: string[]): string =>
  chips.length ? `<p class="sublabel">Rests on, in the record:</p>${chips.join(" ")}` : `<p class="sublabel">What this rests on: not in the record.</p>`;

/** Where there was a choice: the one dated step of the person's own in the
 * green box (the colour of a move), whose words it is in, and the facts under
 * it plain. A question on the step is a guess and goes in the amber box, or is
 * a gap. */
export function choiceBox(o: { when: string; step: string; part: string; facts: string[]; question: string }): string {
  return (
    `<div class="choice"><p class="did">${o.when} ${esc(o.step)}</p><p class="part">${esc(o.part)}</p></div>` +
    `<p class="sublabel">The facts under it:</p><ul class="facts">${o.facts.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>` +
    o.question
  );
}

/** The clusters of the line, each its own chip: the tap is the first tap, the same as on the line. */
export const clusterChips = (chips: string[]): string => `<div class="clusters">${chips.join("")}</div>`;

/** A question a viewer pinned to a cluster or a person. */
export const pin = (chip: string, text: string): string =>
  `<div class="pin">${chip}<p>${esc(text)}</p><p class="pinby">pinned by a viewer</p></div>`;

export const pins = (rows: string[]): string => (rows.length ? `<div class="pins">${sublabel("Pinned by viewers")}${rows.join("")}</div>` : "");

/** One side of the family under level 4. */
export const side = (label: string, inner: string): string => `<div class="side"><p class="sub">${esc(label)}</p>${inner}</div>`;

/** The whole page, in the thread's place. */
export const casePage = (inner: string): string => `<div class="case">${inner}</div>`;

/** The page's own taps: the first tap on a guess shows what it rests on. Every
 * chip on the page is the thread's chip and does what a chip does in the app:
 * it aims the picture (lens.ts aim), and nothing else; a chip naming a person
 * aims nothing (chips.ts aimedEvents), as in the app. */
export function wireCase(root: HTMLElement, onChip: (chip: HTMLElement) => void): void {
  root.addEventListener("click", (e) => {
    const el = e.target as HTMLElement;
    const open = el.closest<HTMLElement>(".basis-open");
    if (open) {
      open.closest(".guessbox")?.classList.toggle("open");
      return;
    }
    const chip = el.closest<HTMLElement>("button.chip[data-kind]");
    if (chip && root.contains(chip)) onChip(chip);
  });
}
