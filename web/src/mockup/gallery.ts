import { column, words, type PageState } from "../casepage";
import { esc } from "../dom";
import { INBAR, MENU, PBP, PIC, SPEAKROW, titlerow } from "./chrome";
import type { Model } from "./model";

/** The gallery: one explanation, the decisions, the frames in one section per
 * case, and under them one collapsed note on where each level comes from. The
 * page's assumptions, cuts and rewordings live in fd336/verdict.md, never on
 * Patrick's page. No word of a record is written here: every caption, heading
 * and published state is filled from the case's page file at build time.
 *
 * Each frame is the app in a window of its own: an iframe the size of a
 * phone's screen or a desktop's, so the app's own rules on the window's width
 * (theme.css) hold inside it as they do on a phone or a desktop, and the page
 * scrolls inside the app's screen, under its title row and over its speak row,
 * as it does on a phone. The gallery's window holds the words around the
 * frames and nothing of the app. */

export type View = "phone" | "desk";

/** A phone's screen and a desktop window, in CSS pixels. */
export const SIZE: Record<View, { w: number; h: number }> = { phone: { w: 390, h: 820 }, desk: { w: 840, h: 800 } };

export interface FrameSpec {
  id: string;
  title: string;
  caption: string;
  case: string;
  /** The desktop: the timeline at the top of the screen, or at level 5 among the words. */
  deskOrder: "under" | "ruled";
  outcomeFirst?: boolean;
  proBox?: boolean;
  pins?: boolean;
}

/** A frame's window is named by its frame and its view: "P1-p", "P1-d". */
export const frameId = (spec: FrameSpec, view: View): string => `${spec.id}-${view === "desk" ? "d" : "p"}`;

/** The state a frame of a case is published in: the page file's. */
export const published = (m: Model, id: string): PageState => m.page.published?.[id] ?? {};

/** The words a caption may fill from a case: {subject}, {presenter}, {his},
 * {him}, {he}, {title}, {opened} (the published cluster's years), {pinned}
 * (the years of the cluster the first pin is on). */
function fill(text: string, m: Model, id: string): string {
  const years = (cluster: string | undefined) => m.view.clusters.find((c) => c.cluster.id === cluster)?.cluster.label ?? "";
  const words: Record<string, string> = {
    subject: m.view.subject.name,
    presenter: m.view.presenter,
    his: m.view.pronoun.his,
    him: m.view.pronoun.him,
    he: m.view.pronoun.he,
    title: m.view.title,
    opened: years(published(m, id).cluster),
    pinned: years(m.page.pins.find((p) => p.to.kind === "cluster")?.to.id),
  };
  return text.replace(/\{(\w+)\}/g, (_, k: string) => words[k] ?? `{${k}}`);
}

export const FRAMES: FrameSpec[] = [
  {
    id: "P1",
    title: "{subject}'s page, the reading last",
    caption:
      "The ruled order, one to ten, top to bottom: the family on a picture, what brought {him}, the couple, each parent's own family, one timeline, then the reading, {his} own part, the choice, what to work on, the effort.",
    case: "patrick",
    deskOrder: "ruled",
  },
  {
    id: "P2",
    title: "{subject}'s page, where things stand now at the top",
    caption:
      "{subject}'s page with one card of where things stand now above the picture: the record's last dated events, facts only. Kerr opened one presentation with the outcome; the written sources do not. A trial on this record only.",
    case: "patrick",
    deskOrder: "ruled",
    outcomeFirst: true,
  },
  {
    id: "P3",
    title: "Desktop: picture and timeline on one screen",
    caption:
      "The app's wide layout: the family picture in the column beside the screen, the timeline at the top of the screen where the app keeps it, the words scrolling under it. The {opened} cluster is open; the row offers explain.",
    case: "patrick",
    deskOrder: "under",
  },
  {
    id: "P4",
    title: "The telling, mid-step",
    caption:
      "The second tap, explain: the {opened} cluster told in the app's drawer, one dated step at a time, each step one person's move in the record's words. Back, the dots and Next, as the drawer steps everywhere.",
    case: "patrick",
    deskOrder: "under",
  },
  {
    id: "L1",
    title: "{subject}: {presenter}'s page, the reading in a box of its own",
    caption:
      "A tinted header: {presenter}'s notes of what {subject} said, one member's account, the others not heard. Every guess is an amber box labelled {presenter}'s, for {subject} to reject; a line says the coach has not read this case.",
    case: "client-l",
    deskOrder: "under",
    proBox: true,
  },
  {
    id: "L2",
    title: "{subject}, without {presenter}'s box",
    caption:
      '{subject}\'s page without the box: each guess is labelled "A guess, for {subject} to reject", with what it rests on. Only the quoted text, "The professional wrote", says a professional wrote it; nothing names {presenter}.',
    case: "client-l",
    deskOrder: "under",
    proBox: false,
  },
  {
    id: "A1",
    title: "{subject}: {presenter}'s page, with viewers' questions pinned",
    caption:
      "{subject}'s page from {presenter}'s write-up. Two viewers' questions are pinned under the timeline, one to the {pinned} cluster and one to {subject} herself. The message box is dead: nothing here posts to the coach.",
    case: "anna",
    deskOrder: "under",
    pins: true,
  },
];

/** The three decisions, each self-contained with its own example from the record it is drawn on. */
function decisions(models: Map<string, Model>): string[] {
  const a = models.get("patrick")!;
  const b = models.get("client-l")!;
  const last = a.view.outcome.map((r) => `${r.date}, ${r.text}`).join("; ");
  return [
    fill(
      `<strong>A where-things-stand-now card above the picture, or not.</strong> {subject}'s record is drawn both ways. One way puts the record's last dated events above the picture: "${esc(last)}." The other opens on the picture and keeps every reading after the facts, as the written sources place it. <strong>Recommended: the picture first.</strong> The sources that place a reading put it after the facts, and the last dated events already stand at the right end of the timeline.`,
      a,
      "P2",
    ),
    fill(
      `<strong>On a professional's page about a client, the professional's own reading in a box of its own, or not.</strong> {subject}'s page is drawn both ways. With the box, every guess in the professional's words is labelled "A guess, {presenter}'s, for {subject} to reject", and a line above the reading says the coach has not read this case. Without it, the label reads "A guess, for {subject} to reject", and only the quoted text, "The professional wrote", says a professional wrote it: nothing names {presenter}, and nothing says the coach has not read the case. <strong>Recommended: the box.</strong> A page a professional presents must name whose guess the reading is.`,
      b,
      "L1",
    ),
    fill(
      `<strong>On the desktop, the timeline at the top of the screen, or at level 5 among the words.</strong> {subject}'s desktop is drawn both ways, in the app's own wide layout: the family picture stands in the column beside the screen either way. At the top of the screen, where the app keeps its timeline, picture and timeline stay in view while the words scroll under the line. At level 5, the timeline is a card among the words at its ruled place, after each parent's family and before the reading, and only the picture stays in view. <strong>Recommended: the top of the screen.</strong> {subject}'s test of the desktop is what the extra screen space adds in ease of use; two things on one screen is that, and the phone keeps the ruled order either way.`,
      a,
      "P3",
    ),
  ];
}

const SOURCES: string[] = [
  "1 Who is in the family, on a picture: Bowen, Basic Series 3; Kerr and Bowen 1988, Family Evaluation, ch. 10. The place in the order is a proposal.",
  "2 What brought them, dated: Kerr and Bowen 1988, ch. 10; Bowen 1978, Family Therapy in Clinical Practice, ch. 9.",
  "3 The couple since they met: Kerr and Bowen 1988, ch. 10; Bowen 1978, ch. 9.",
  "4 Each parent's own family, his side and hers: Bowen 1978, ch. 9; Kerr and Bowen 1988, ch. 10.",
  "5 All of it on one timeline, read for time sequence, never for a cause: Bowen 1978, ch. 9. The ruled order's word is \"calendar\", Bowen's; the page uses Patrick's and the app's word, \"timeline\", for the one thing. Patrick picks.",
  "6 The reading, for the therapist, after the facts: Bowen 1978, ch. 9. Its place is a proposal; Kerr once opened with the outcome.",
  "7 The person's own part, never blame: Bowen 1978, ch. 10 and ch. 20.",
  "8 Where there was a choice: Patrick's phrase, 2026-10-01; its definition is a proposal.",
  "9 What to work on, what to expect, with guesses about raising functioning: Kerr and Bowen 1988, ch. 10; Patrick, 2026-10-01.",
  "10 The effort, last and longest: Bowen 1978, ch. 10 and ch. 20.",
];

/** The account's initial in the title row's account button, as settings.ts
 * marks it: the presenter's, whose page it is. */
const initial = (m: Model): string => m.view.presenter.trim().charAt(0).toUpperCase();

/** One case page in the app's own frame, taken from index.html: the title row,
 * the screen with the thread's place taken by the page, the speak row, the
 * message box (mounted dead: nothing on a case page posts to the coach), the
 * drawer's host, the list screen. On a wide window the app stands its pinned
 * column beside the screen; the page puts the family picture there, and the
 * timeline either at the top of the screen, where the app keeps it, or at its
 * ruled place among the words (the third decision, drawn both ways). */
export function frame(m: Model, spec: FrameSpec, view: View): string {
  const desk = view === "desk";
  const under = desk && spec.deskOrder === "under";
  const v = m.view;
  const body = words(v, {
    outcomeFirst: !!spec.outcomeFirst,
    proBox: !!spec.proBox,
    pins: !!spec.pins,
    lineAt5: under ? null : PIC,
    pictureAt1: !desk,
  });
  const aside = desk ? `<aside class="pinned"><div class="scroller">${column(v)}</div></aside>` : `<aside class="pinned" hidden></aside>`;
  return (
    `<div class="app${desk ? " wide" : ""}" data-frame="${frameId(spec, view)}" data-case="${esc(m.file.case)}" data-view="${view}">` +
    titlerow(v.title, initial(m)) +
    `<div class="split"><div class="screen">${under ? PIC : ""}<div class="chat">${body}</div>${SPEAKROW}${INBAR}${PBP}</div>${aside}</div>${MENU}</div>`
  );
}

/** The frame's own window, filled by the gallery (main.ts) with the app's
 * stylesheet and the one bundle, which mounts the frame it is told. */
function window_(spec: FrameSpec, view: View, title: string): string {
  const size = SIZE[view];
  return (
    `<iframe data-frame="${frameId(spec, view)}" title="${esc(title)}, ${view === "desk" ? "on a desktop" : "on a phone"}" ` +
    `width="${size.w}" height="${size.h}" loading="eager"></iframe>`
  );
}

function figure(spec: FrameSpec, models: Map<string, Model>): string {
  const m = models.get(spec.case);
  if (!m) throw new Error(`no case ${spec.case} for frame ${spec.id}`);
  const title = fill(spec.title, m, spec.id);
  return (
    `<figure id="${spec.id}"><div class="pair">` +
    `<div class="pv"><span class="vlab">Phone</span>${window_(spec, "phone", title)}</div>` +
    `<div class="dv"><span class="vlab">Desktop, half size</span>${window_(spec, "desk", title)}</div>` +
    `</div><figcaption><h3><span class="id">${spec.id}</span>${esc(title)}</h3><p>${esc(fill(spec.caption, m, spec.id))}</p></figcaption></figure>`
  );
}

export function gallery(models: Map<string, Model>, order: string[]): string {
  const sections = order
    .map((id) => {
      const m = models.get(id)!;
      const frames = FRAMES.filter((f) => f.case === id);
      return `<section><h2>${esc(m.page.heading)}</h2><div class="frames">${frames.map((f) => figure(f, models)).join("")}</div></section>`;
    })
    .join("");
  const origins = order.map((id) => models.get(id)!.page.lede).join("; ");
  return (
    `<h1>A case page in the ruled order</h1>` +
    `<p class="lede">Each frame is the app itself, running in a window the size of a phone's screen or a desktop's, showing the read-only page it would make from a record, in the ten-level order ruled on 1 October: the family on a picture, then the facts in time, then the reading and the guesses, the effort last. The page scrolls inside the app's screen, as on a phone. Facts are plain cards; every guess is an amber box that says so, and its first tap (a hover on the desktop) shows what it rests on. Where there was a choice, the one dated step of the person's own is a green box, the colour of a move in the app, with the facts plain under it. Nothing is filled in: a gap says "not in the record". The message box at the foot is the app's own, dead: nothing on the page posts to the coach. On the timeline the first tap on a cluster looks at it; the chip that then appears, explain, tells it in the app's drawer, one dated step at a time, each step one person's move in the record's words. The desktop frames are drawn at half size; on a narrow window every frame shrinks to fit. The three decisions below are independent of each other. ${esc(origins)}.</p>` +
    `<ol class="decide">${decisions(models)
      .map((d) => `<li>${d}</li>`)
      .join("")}</ol>` +
    sections +
    `<details class="src"><summary>Where this comes from</summary><ul>${SOURCES.map((s) => `<li>${esc(s)}</li>`).join("")}</ul></details>`
  );
}
