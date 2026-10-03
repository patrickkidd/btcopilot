import { esc } from "../dom";
import type { Coverage } from "./coverage";
import { pkey, type Model } from "./model";
import { peopleOn, type ReportOpts, type ReportState } from "./report";

/** The gallery, version 5, Section A only (Patrick's own record): the proposal
 * whole, then four groups, each one heading with a tab strip of its frames; a
 * tab shows one frame alone, phone and desktop side by side, with its label and
 * caption (Patrick, 2026-10-02: he had no idea how to switch between P1 and
 * P4). Every frame carries a visible label: PROPOSAL (the recommended one in
 * its group), VIEW (another view of the same proposal) or ALTERNATIVE (a
 * different proposal). Each group says in one line whether its alternatives
 * exclude each other or combine, and which is recommended and why. The default
 * report is the recommended set, so every PROPOSAL frame is a piece of the one
 * screen P1 shows whole. No word of the record is written here: the captions
 * and the decisions are filled from the case at build time. */

export type View = "phone" | "desk";

/** A phone's screen and a desktop window at full size, in CSS pixels. */
export const SIZE: Record<View, { w: number; h: number }> = { phone: { w: 390, h: 844 }, desk: { w: 1024, h: 800 } };

export type Label = "PROPOSAL" | "VIEW" | "ALTERNATIVE";

export interface Frame5 {
  id: string;
  label: Label;
  title: string;
  caption: string;
  opts: Omit<ReportOpts, "desk">;
  state?: ReportState;
  /** The phone's own state where it differs (for example the slide-out open). */
  phoneState?: ReportState;
}

export interface Group5 {
  id: string;
  title: string;
  /** One line: exclude or combine, the recommended one, and why in one clause. */
  line: string;
  frames: Frame5[];
}

export const frameId = (spec: Frame5, view: View): string => `${spec.id}-${view === "desk" ? "d" : "p"}`;

/** The recommended set: headlines with the rail on the desktop, the coverage on
 * the family picture, the summary box at the top, the picture as the dashboard. */
const BASE: Omit<ReportOpts, "desk"> = { hierarchy: "collapsed", deskRail: true, coverage: "picture", summary: "box", dashboard: true };

export const GROUPS: Group5[] = [
  {
    id: "P",
    title: "P · The proposal, whole",
    line: "One screen: the recommended choice of every group below. Each group then shows its own alternatives against it.",
    frames: [
      {
        id: "P1",
        label: "PROPOSAL",
        title: "The case report as recommended",
        caption: "Ten headlines; the family picture, shaded by what the record holds, first on the phone, pinned on the desktop; the summary box above the levels.",
        opts: BASE,
      },
    ],
  },
  {
    id: "H",
    title: "H · How the ten levels are headlined and opened",
    line: "No alternative here: H2 is the one proposal, closed; H2b shows it with the reading open, H1 with the desktop rail lit at level 9. Recommended since the order stays in view once a level is open.",
    frames: [
      {
        id: "H2",
        label: "PROPOSAL",
        title: "Ten headlines, tap one to open",
        caption: "Each level is its title and one line until tapped; Open all opens every level. The summary box stays open above them.",
        opts: BASE,
      },
      {
        id: "H2b",
        label: "VIEW",
        title: "H2 with the reading open",
        caption: "Level 6 open: each line of the reading marked; one left off, one with not enough in the record; facts behind a second tap.",
        opts: BASE,
        state: { unfolded: [6], scrollTo: 6 },
      },
      {
        id: "H1",
        label: "VIEW",
        title: "Desktop: the rail lit at level 9",
        caption: "Under the header, ten words in two rows light the level on screen; a tap jumps there and opens it. The phone has no rail.",
        opts: BASE,
        state: { unfolded: [9], scrollTo: 9 },
      },
    ],
  },
  {
    id: "C",
    title: "C · One visual of what the record covers",
    line: "C1 and C4 exclude each other. C3 can be added to either (shown alone here), but S1's box already holds two of its three counts, so it is not recommended. Recommended: C4, since the gaps sit on the people they belong to.",
    frames: [
      {
        id: "C4",
        label: "PROPOSAL",
        title: "The coverage on the family picture",
        caption: "Each person shaded by what the record holds of them, dashed where it holds nobody; the years band under. Tap a person; drag the years.",
        opts: BASE,
      },
      {
        id: "C1",
        label: "ALTERNATIVE",
        title: "A people grid by generation and side",
        caption: "A cell per person in the record, shaded the same way, by generation and side of the family; dashed where nobody was asked about.",
        opts: { ...BASE, coverage: "grid" },
        state: { scrollTo: "cover" },
      },
      {
        id: "C3",
        label: "ALTERNATIVE",
        title: "Three numbers in one line",
        caption: "People, open questions, years with no dated fact; each opens its list. Shown alone, without C4's shading. S1's box holds two of the three.",
        opts: { ...BASE, coverage: "numbers" },
        state: { list: "years", scrollTo: "cover" },
      },
    ],
  },
  {
    id: "S",
    title: "S · The summary",
    line: "Exclusive. Recommended: S1; {stand} of {n} lines of his reading rest on dated facts, so the box shows the first and marks the rest.",
    frames: [
      {
        id: "S1",
        label: "PROPOSAL",
        title: "The summary box above the levels",
        caption: "Above the levels (on a phone, under the family card): the first line resting on dated facts, what the whole record covers, what changes it.",
        opts: BASE,
        phoneState: { scrollTo: "why" },
      },
      {
        id: "S2",
        label: "ALTERNATIVE",
        title: "The same lines under each level",
        caption: "No box; one row of what the record covers stays at the top; each guess carries its dated facts and open questions in place.",
        opts: { ...BASE, summary: "lines" },
        state: { scrollTo: 6, unfolded: [6, 7] },
      },
    ],
  },
  {
    id: "D",
    title: "D · The family picture's place",
    line: "Exclusive. Recommended: D1; the picture is the case's dashboard, pinned on the desktop and one tap away on the phone at every level.",
    frames: [
      {
        id: "D1",
        label: "PROPOSAL",
        title: "The family picture as the dashboard",
        caption: "Pinned on the desktop with the years band; on the phone the first card, open, above the summary box, plus a round header button.",
        opts: BASE,
      },
      {
        id: "D1b",
        label: "VIEW",
        title: "Phone: the picture slid out over level 8",
        caption: "The round button tapped while reading the choice: the whole picture and the years band over the report; back returns to the same place.",
        opts: BASE,
        state: { scrollTo: 8, unfolded: [8] },
        phoneState: { scrollTo: 8, unfolded: [8], famout: true },
      },
      {
        id: "D2",
        label: "ALTERNATIVE",
        title: "The picture as the first card only",
        caption: "Level 1 as a card like the others, first on the phone and the desktop alike; nothing is pinned and there is no button.",
        opts: { ...BASE, dashboard: false },
        state: { unfolded: [1] },
      },
    ],
  },
];

export const FRAMES5: Frame5[] = GROUPS.flatMap((g) => g.frames);

/** The words a caption may fill from the case. */
function fill(text: string, m: Model, cov: Coverage): string {
  const stand = cov.parts.filter((p) => !p.off && p.cover.enough).length;
  const words: Record<string, string> = {
    subject: m.view.subject.name,
    presenter: m.view.presenter,
    his: m.view.pronoun.his,
    him: m.view.pronoun.him,
    he: m.view.pronoun.he,
    stand: String(stand),
    n: String(cov.parts.length),
  };
  return text.replace(/\{(\w+)\}/g, (_, k: string) => words[k] ?? `{${k}}`);
}

/** The three decisions, each in at most forty words: the question, one example
 * from the record in words, the recommendation with one clause of reason. */
export function decisions(m: Model, cov: Coverage): string[] {
  const v = m.view;
  const stand = cov.parts.filter((p) => !p.off && p.cover.enough).length;
  const n = cov.parts.length;
  const c = cov.counts;
  const slot = cov.slots[0];
  const example = slot
    ? `the dashed place beside ${esc(m.people.get(slot.who)?.name ?? "")} says no brother or sister was asked about`
    : `${c.story} of ${c.people} people have something that happened to them in the record`;
  // the picture of the person's own family (the first card on the phone, the
  // first of the pinned pictures on the desktop) against the summary: how
  // many of the people on it the summary's own dated facts name
  const on = peopleOn(v.household);
  const first = cov.parts.find((p) => !p.off && p.cover.enough);
  const named = new Set((first?.cover.events ?? []).flatMap((e) => [e.person, ...e.others]).map(pkey));
  const k = on.filter((id) => named.has(id)).length;
  return [
    `<strong>The summary: a box above the levels (S1) or the same lines under each level (S2)?</strong> ` +
      `On ${esc(v.subject.name)}'s record ${stand} of ${n} lines of the reading rest on dated facts. ` +
      `<strong>Recommended: S1</strong>, one place answers why this reading.`,
    `<strong>The coverage visual: on the family picture (C4) or a people grid (C1)?</strong> ` +
      `Example: ${example}. ` +
      `<strong>Recommended: C4</strong>, the gaps sit on the people they belong to.`,
    `<strong>The family picture: pinned on the desktop, one tap away on the phone (D1), or the first card (D2)?</strong> ` +
      `The summary's facts name ${k || "none"} of the ${on.length} on the picture of ${esc(v.subject.name)}'s family. ` +
      `<strong>Recommended: D1</strong>, the family stays in view.`,
  ];
}

const LAB: Record<Label, string> = { PROPOSAL: "proposal", VIEW: "view", ALTERNATIVE: "alternative" };

function window_(spec: Frame5, view: View, title: string): string {
  const size = SIZE[view];
  return (
    `<iframe data-frame="${frameId(spec, view)}" title="${esc(title)}, ${view === "desk" ? "on a desktop" : "on a phone"}" ` +
    `width="${size.w}" height="${size.h}" loading="eager"></iframe>`
  );
}

function pane(spec: Frame5, m: Model, cov: Coverage, on: boolean): string {
  const title = fill(spec.title, m, cov);
  return (
    `<figure class="pane${on ? " on" : ""}" id="${spec.id}" data-pane="${spec.id}" role="tabpanel" aria-labelledby="tab-${spec.id}">` +
    `<figcaption><span class="lab ${LAB[spec.label]}">${spec.label}</span><h3>${esc(title)}</h3><p>${esc(fill(spec.caption, m, cov))}</p></figcaption>` +
    `<div class="pair"><div class="pv"><span class="vlab">Phone</span>${window_(spec, "phone", title)}</div>` +
    `<div class="dv"><span class="vlab">Desktop</span>${window_(spec, "desk", title)}</div></div></figure>`
  );
}

function group(g: Group5, m: Model, cov: Coverage): string {
  const tabs = g.frames
    .map((f, i) => `<button type="button" role="tab" id="tab-${f.id}" data-pane="${f.id}" aria-selected="${i === 0}" aria-controls="${f.id}">${f.id}<span class="lab ${LAB[f.label]}">${f.label}</span></button>`)
    .join("");
  return (
    `<section id="group-${g.id}"><h2>${esc(g.title)}</h2><p class="gline">${esc(fill(g.line, m, cov))}</p>` +
    `<div class="tabs5" role="tablist">${tabs}</div><div class="panes">${g.frames.map((f, i) => pane(f, m, cov, i === 0)).join("")}</div></section>`
  );
}

export function gallery5(m: Model, cov: Coverage): string {
  const v = m.view;
  return (
    `<h1>${esc(v.subject.name)}'s case report, version 5</h1>` +
    `<p class="lede">Each frame is the app at a phone's and a desktop's size, showing the report it makes from ${esc(v.subject.name)}'s whole record in the ten ruled levels, one line and a drawing each, the rest behind a tap.</p>` +
    `<ol class="decide">${decisions(m, cov)
      .map((d) => `<li>${d}</li>`)
      .join("")}</ol>` +
    GROUPS.map((g) => group(g, m, cov)).join("")
  );
}
