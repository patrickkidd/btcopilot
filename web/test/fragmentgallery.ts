/** Writes doc/chat-first/mockups/fragment.html. Every picture on that page is
 * produced by the shipping renderer, so the page shows what the code draws.
 * Run it with: node --experimental-strip-types is not enough (enums), so:
 *   npx esbuild test/fragmentgallery.ts --bundle --format=esm --platform=node \
 *     --outfile=/tmp/gal.mjs && node /tmp/gal.mjs
 */

import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import {
  AdoptLine,
  Apex,
  BondOrder,
  Loose,
  NameFit,
  Side,
  Single,
  Slash,
  TwinBar,
  Unnamed,
  UnknownMark,
  render,
  type Fragment,
  type Options,
} from "../src/fragment";
import {
  cases,
  adopted,
  ended,
  longName,
  loss,
  nogender,
  orphan,
  plain,
  single,
  twins,
  twoBonds,
  unnamed,
} from "./fragmentcases";

/** Run from the web/ directory. */
const root = join(process.cwd(), "..");
const mockups = join(root, "doc", "chat-first", "mockups");

const style = (() => {
  const source = readFileSync(join(mockups, "review.html"), "utf8");
  const open = source.indexOf("<style>");
  const close = source.indexOf("</style>", open);
  return source.slice(open, close + "</style>".length);
})();

enum Where {
  Ballot = "ballot",
  Editor = "editor",
}

type Choice = {
  letter: string;
  caption: string;
  fragment: Fragment;
  options: Partial<Options>;
};

type Row = {
  n: number;
  title: string;
  lead: string;
  where: Where;
  choices: Choice[];
};

const u = 40;

const frame = (where: Where, tag: string, svg: string, title: string) =>
  where === Where.Ballot
    ? `<div class="frame phone fr"><div class="app">
<div class="titlerow"><button class="sn-back" type="button">&#8249;</button><div class="ttl">Session 3 &middot; ballot &middot; 2 of 6</div><button class="avatar" type="button"><svg viewBox="0 0 22 22" width="24" height="24" aria-hidden="true"><circle cx="11" cy="7.5" r="4" fill="currentColor"></circle><path d="M3 20c0-4.4 3.6-7 8-7s8 2.6 8 7z" fill="currentColor"></path></svg></button></div>
<div class="card"><div class="progress">version <b>${tag}</b> &middot; ${title}</div><div class="fragwrap">${svg}</div>
<div class="take tap"><span>keep this version</span><span class="n">2 coders</span></div></div>
</div><div class="tagbadge">${tag}</div></div>`
    : `<div class="frame phone fr"><div class="app">
<div class="titlerow"><button class="sn-back" type="button">&#8249;</button><div class="ttl">Marcus Whitlock</div><button class="avatar" type="button"><svg viewBox="0 0 22 22" width="24" height="24" aria-hidden="true"><circle cx="11" cy="7.5" r="4" fill="currentColor"></circle><path d="M3 20c0-4.4 3.6-7 8-7s8 2.6 8 7z" fill="currentColor"></path></svg></button></div>
<div class="editor"><div class="sec">Family</div><div class="fragwrap">${svg}</div>
<div class="hint">${title}</div></div>
</div><div class="tagbadge">${tag}</div></div>`;

const rows: Row[] = [
  {
    n: 1,
    title: "No gender recorded",
    lead: "The desktop code draws a rounded box and nothing inside it. The written specification says a question mark goes inside.",
    where: Where.Ballot,
    choices: [
      {
        letter: "a",
        caption: "A rounded box, empty. You cannot tell an unrecorded person from one drawn quietly.",
        fragment: nogender(),
        options: { unknownMark: UnknownMark.None },
      },
      {
        letter: "b",
        caption: "A question mark inside the box. It reads as asking, and the amber question mark then means two things.",
        fragment: nogender(),
        options: { unknownMark: UnknownMark.Question },
      },
    ],
  },
  {
    n: 2,
    title: "The miscarriage triangle",
    lead: "The code points the triangle up. The specification says it points down.",
    where: Where.Ballot,
    choices: [
      {
        letter: "a",
        caption: "Apex at the top, as the desktop draws it today. Every existing diagram already looks like this.",
        fragment: loss(),
        options: { apex: Apex.Up },
      },
      {
        letter: "b",
        caption: "Apex at the bottom, as the written spec says. It breaks with every diagram already drawn.",
        fragment: loss(),
        options: { apex: Apex.Down },
      },
    ],
  },
  {
    n: 3,
    title: "The marks that say a bond ended",
    lead: "One mark for a separation, two for a divorce. With no custody recorded the code draws them straight up and down; the spec leans them.",
    where: Where.Ballot,
    choices: [
      {
        letter: "a",
        caption: "Straight marks. Nothing is implied about who the children stayed with.",
        fragment: ended(),
        options: { slash: Slash.Vertical },
      },
      {
        letter: "b",
        caption: "Leaning marks. They look like they mean something about custody when nothing was recorded.",
        fragment: ended(),
        options: { slash: Slash.Diagonal },
      },
    ],
  },
  {
    n: 4,
    title: "Where the twins' shared line sits",
    lead: "Two children born together are joined by one line, with a single riser to their parents' bar.",
    where: Where.Ballot,
    choices: [
      {
        letter: "a",
        caption: "A fixed short rise above the two children, as the code does it. The riser is long.",
        fragment: twins(),
        options: { twinBar: TwinBar.Fixed },
      },
      {
        letter: "b",
        caption: "Halfway up to the parents' bar, as the spec says. It floats between the two rows.",
        fragment: twins(),
        options: { twinBar: TwinBar.Midpoint },
      },
    ],
  },
  {
    n: 5,
    title: "The line to an adopted child",
    lead: "The code dashes it. Your own note asks for a solid line to every parent, with dashes kept for chosen parents.",
    where: Where.Ballot,
    choices: [
      {
        letter: "a",
        caption: "Dashed, as the desktop draws it. Adoption is visible at a glance, and dashes are then spent.",
        fragment: adopted(),
        options: { adoptLine: AdoptLine.Dashed },
      },
      {
        letter: "b",
        caption: "Solid, like any other child. Adoption is not visible in the drawing at all.",
        fragment: adopted(),
        options: { adoptLine: AdoptLine.Solid },
      },
    ],
  },
  {
    n: 6,
    title: "Which partner goes on the left",
    lead: "The code has no rule: people sit where the user put them. A fragment has to choose.",
    where: Where.Editor,
    choices: [
      {
        letter: "a",
        caption: "The man on the left always. Same-sex couples need a second rule.",
        fragment: plain(),
        options: { side: Side.MaleLeft },
      },
      {
        letter: "b",
        caption: "The older person on the left. It holds for every couple, and moves people when a birth year is corrected.",
        fragment: plain(),
        options: { side: Side.OlderLeft },
      },
      {
        letter: "c",
        caption: "Whoever the record wrote first. Nothing moves, and the sides mean nothing.",
        fragment: plain(),
        options: { side: Side.RecordOrder },
      },
    ],
  },
  {
    n: 7,
    title: "How far apart the children sit",
    lead: "Two person boxes apart is the specification's spacing. On a phone it costs width fast.",
    where: Where.Editor,
    choices: [
      {
        letter: "a",
        caption: "Two boxes apart. Roomy, and four children no longer fit across a phone.",
        fragment: loss(),
        options: { siblingGap: 2 },
      },
      {
        letter: "b",
        caption: "One and a half boxes. A little tight, one more child fits.",
        fragment: loss(),
        options: { siblingGap: 1.5 },
      },
      {
        letter: "c",
        caption: "One and a quarter boxes. Names start to collide.",
        fragment: loss(),
        options: { siblingGap: 1.25 },
      },
    ],
  },
  {
    n: 8,
    title: "Two bonds in a row",
    lead: "The middle person had two partners. Which one sits nearer them.",
    where: Where.Editor,
    choices: [
      {
        letter: "a",
        caption: "The earliest partner nearest, later ones further out. Time reads outward.",
        fragment: twoBonds(),
        options: { bondOrder: BondOrder.EarliestNearest },
      },
      {
        letter: "b",
        caption: "The current partner nearest. The life now is closest, and the order flips when a bond is added.",
        fragment: twoBonds(),
        options: { bondOrder: BondOrder.LatestNearest },
      },
    ],
  },
  {
    n: 9,
    title: "A parent with no partner recorded",
    lead: "The desktop cannot draw a bond with one person in it. The fragment has to draw something.",
    where: Where.Editor,
    choices: [
      {
        letter: "a",
        caption: "Half of the usual U: down, across, and the children hang from the stub. Nothing claims a second parent exists.",
        fragment: single(),
        options: { single: Single.HalfU },
      },
      {
        letter: "b",
        caption: "A faint empty partner in the usual place. It looks normal, and it invents a person.",
        fragment: single(),
        options: { single: Single.Ghost },
      },
      {
        letter: "c",
        caption: "A short line straight down and nothing else. Smallest, and the children hang off one point.",
        fragment: single(),
        options: { single: Single.NoStub },
      },
    ],
  },
  {
    n: 10,
    title: "A partner with no name",
    lead: "The record holds the person but not what they are called.",
    where: Where.Editor,
    choices: [
      {
        letter: "a",
        caption: "A faint shape and no words under it. Quiet, and easy to read as a drawing mistake.",
        fragment: unnamed(),
        options: { unnamed: Unnamed.Faint },
      },
      {
        letter: "b",
        caption: "A dash where the name goes. Clearly a blank, and it adds clutter to every such person.",
        fragment: unnamed(),
        options: { unnamed: Unnamed.Dashes },
      },
      {
        letter: "c",
        caption: "An amber question mark where the name goes. It asks you to fill it in, and spends the asking colour.",
        fragment: unnamed(),
        options: { unnamed: Unnamed.Asked },
      },
    ],
  },
  {
    n: 11,
    title: "A child whose parents are not in the record",
    lead: "There is no bond to hang the child from.",
    where: Where.Ballot,
    choices: [
      {
        letter: "a",
        caption: "A faint stub of bar with nobody on it, and an amber question mark. Honest, and it draws a bar that does not exist.",
        fragment: orphan(),
        options: { loose: Loose.Stub },
      },
      {
        letter: "b",
        caption: "A dashed line rising into nothing, with the question mark at its end. Nothing invented, harder to read.",
        fragment: orphan(),
        options: { loose: Loose.AskOnly },
      },
      {
        letter: "c",
        caption: "Two faint empty parents above them. Reads like a family, and invents two people.",
        fragment: orphan(),
        options: { loose: Loose.GhostBond },
      },
    ],
  },
  {
    n: 12,
    title: "A name too long for the box",
    lead: "The desktop has no rule. Phone width forces one.",
    where: Where.Editor,
    choices: [
      {
        letter: "a",
        caption: "Cut it with a trailing dot dot dot. One line always, and you may not be able to tell two people apart.",
        fragment: longName(),
        options: { nameFit: NameFit.Ellipsis },
      },
      {
        letter: "b",
        caption: "Break it over two lines. The whole name shows, and the rows grow taller.",
        fragment: longName(),
        options: { nameFit: NameFit.TwoLines },
      },
      {
        letter: "c",
        caption: "Shrink the type until it fits. The whole name shows, and long names get hard to read.",
        fragment: longName(),
        options: { nameFit: NameFit.Shrink },
      },
    ],
  },
];

const rowHtml = (row: Row) => {
  const frames = row.choices
    .map((choice) => {
      const svg = render(choice.fragment, { ...choice.options, u });
      const tag = `${row.n}${choice.letter}`;
      return `<div class="col">${frame(row.where, tag, svg, row.title)}<div class="mk-cap">${tag} &mdash; ${choice.caption}</div></div>`;
    })
    .join("\n");
  return `<div class="mk-sec"><h2><span>${row.n}</span>${row.title}</h2>
<p>${row.lead}</p>
<div class="mk-row">${frames}</div></div>`;
};

const hostile = cases
  .map((one) => {
    const svg = render(one.fragment, { u });
    const tag = `H${one.key}`;
    return `<div class="col">${frame(Where.Ballot, tag, svg, one.title)}<div class="mk-cap">${tag} &mdash; ${one.title}.</div></div>`;
  })
  .join("\n");

const extra = `
html, body { height: auto !important; overflow: visible !important; display: block !important; }
body { padding: 28px 20px 48px !important; background: var(--bg); }
.mk-h1 { font: 600 21px var(--sans); color: var(--ink); margin: 0 0 4px; }
.mk-lead { color: var(--faint); font: 14px/1.45 var(--sans); margin: 0 0 22px; max-width: 88ch; }
.mk-sec { margin-bottom: 44px; }
.mk-sec h2 { font: 600 16px var(--sans); color: var(--ink); margin: 0 0 4px; }
.mk-sec h2 span { color: var(--data); font: 12px var(--mono); margin-right: 8px; }
.mk-sec p { color: var(--faint); font: 13.5px/1.45 var(--sans); margin: 0 0 12px; max-width: 88ch; }
.mk-row { display: flex; gap: 22px; align-items: flex-start; overflow-x: auto; padding-bottom: 6px; flex-wrap: wrap; }
.col { flex: none; width: 393px; max-width: 100%; }
.frame.fr { position: relative; width: 393px; max-width: 100%; height: 620px; overflow: hidden; border: 1px solid var(--line); border-radius: 28px; background: var(--bg); box-shadow: 0 8px 24px var(--shadow); }
.frame.fr .app { max-width: none; height: 100%; display: flex; flex-direction: column; }
.mk-cap { font: 12px/1.45 var(--mono); color: var(--faint); margin: 6px 0 0; width: 100%; }
.tagbadge { position: absolute; top: 10px; left: 12px; z-index: 4; font: 500 12px var(--mono); color: var(--onaccent); background: var(--data); border-radius: 6px; padding: 2px 7px; }
.fragwrap { display: flex; justify-content: center; padding: 10px 0 14px; overflow-x: auto; }
.fragwrap svg { max-width: 100%; height: auto; }
.frame.fr .card { margin: 10px; padding: 12px; border: 1px solid var(--line); border-radius: 12px; background: var(--panel); }
.frame.fr .editor { padding: 12px; }
`;

const page = `<title>The Family Fragment</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
${style}
<style>${extra}</style>
<div class="mk-h1">The family fragment &mdash; one person, their parents&rsquo; bond above, their own bonds beside, the children under each</div>
<div class="mk-lead">Every picture on this page was drawn by the app&rsquo;s own fragment code, not by hand. The first twelve rows are the places where the desktop drawing code and the written specification disagree, or where neither says anything and a choice had to be made. Each alternative is drawn inside the screen it will live in &mdash; the ballot card a coder votes on, or the family block in the person editor. Answer by naming the frames you want, for example 2a, 6b, 9a. The last block draws the sixteen hard cases with the code&rsquo;s own way of doing things, so you can see nothing collides. Fictional people only.</div>
${rows.map(rowHtml).join("\n")}
<div class="mk-sec"><h2><span>H</span>The sixteen hard cases, drawn the code&rsquo;s way</h2>
<p>No choices here. This is what the renderer produces today for each awkward family, at phone width.</p>
<div class="mk-row">${hostile}</div></div>
`;

writeFileSync(join(mockups, "fragment.html"), page);
console.log("wrote", join(mockups, "fragment.html"));
