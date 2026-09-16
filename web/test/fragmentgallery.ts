/** Writes doc/chat-first/mockups/fragment.html — the record of what was ruled
 * about the family fragment (R-0325). Every picture is produced by the shipping
 * renderer, so the page shows what the code now draws, and only that: the rows
 * keep their numbers and letters so the ruling can still be read off the page,
 * but each row shows one picture, the ruled one.
 * Run it from web/ with:
 *   npx esbuild test/fragmentgallery.ts --bundle --format=esm --platform=node \
 *     --outfile=/tmp/gal.mjs && node /tmp/gal.mjs
 */

import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { render, type Fragment } from "../src/fragment";
import {
  cases,
  adopted,
  ended,
  genericParent,
  genericPartner,
  longName,
  loss,
  nogender,
  orphan,
  plain,
  twins,
  twoBonds,
} from "./fragmentcases";
import { Where, frame, head, mockups, u } from "./galleryshell";

type Row = {
  n: number;
  title: string;
  lead: string;
  where: Where;
  /** The letter Patrick named, or the sentence he ruled when none fitted. */
  ruled: string;
  caption: string;
  fragment: Fragment;
};

const rows: Row[] = [
  {
    n: 1,
    title: "No gender recorded",
    lead: "The written specification wanted a question mark inside the shape. The desktop code draws nothing inside it.",
    where: Where.Ballot,
    ruled: "a",
    caption: "A rounded box with nothing inside it. The amber question mark stays free to mean one thing only: the fragment is asking you something.",
    fragment: nogender(),
  },
  {
    n: 2,
    title: "The miscarriage triangle",
    lead: "The specification pointed the triangle down; the desktop code points it up.",
    where: Where.Ballot,
    ruled: "a",
    caption: "The point at the top, as every diagram already drawn on the desktop has it.",
    fragment: loss(),
  },
  {
    n: 3,
    title: "The marks that say a bond ended",
    lead: "One mark for a separation, two for a divorce. The specification leaned them toward the parent the children stayed with.",
    where: Where.Ballot,
    ruled: "a",
    caption: "Straight up and down. Nothing is implied about who the children stayed with, because nothing about that was recorded.",
    fragment: ended(),
  },
  {
    n: 4,
    title: "Where the twins' shared line sits",
    lead: "Two children born together are joined by one line, with a single riser to their parents' bar.",
    where: Where.Ballot,
    ruled: "a",
    caption: "A short fixed rise above the two children, the way the desktop draws it.",
    fragment: twins(),
  },
  {
    n: 5,
    title: "The line to an adopted child",
    lead: "A note in the reproductive-scenarios plan asked for a solid line to every parent.",
    where: Where.Ballot,
    ruled: "a",
    caption: "Dashed, the way the desktop draws it. Adoption is visible at a glance.",
    fragment: adopted(),
  },
  {
    n: 6,
    title: "Which partner goes on the left",
    lead: "The desktop has no rule: people sit where the user put them. A fragment has to choose.",
    where: Where.Editor,
    ruled: "a",
    caption: "The man on the left, the woman on the right. With no man in the bond the older person goes left, then whoever the record wrote first.",
    fragment: plain(),
  },
  {
    n: 7,
    title: "How far apart the children sit",
    lead: "Sibling spacing costs phone width fast.",
    where: Where.Editor,
    ruled: "a",
    caption: "Two person boxes apart, centre to centre, as the picture was drawn.",
    fragment: loss(),
  },
  {
    n: 8,
    title: "One person with two bonds",
    lead: "The middle person had two partners. The two bonds have to share the same row.",
    where: Where.Editor,
    ruled: "a",
    caption: "The two bond lines overlap side to side, one reaching further right than the other. The earlier bond sits left, the later one right, ordered by when the bond started and otherwise by the order the record holds them in.",
    fragment: twoBonds(),
  },
  {
    n: 9,
    title: "A partner nobody named",
    lead: "None of the three drawn answers was taken: no half bond, no faint invented partner, no bare stub.",
    where: Where.Editor,
    ruled: "none of a, b, c",
    caption: "The partner is a real person in the record, named for their relation — Marcus's partner — and the fragment draws them like anybody else. Putting that person in the record is the scribe's and the coach's work, not the drawing's.",
    fragment: genericPartner(),
  },
  {
    n: 10,
    title: "A parent nobody named",
    lead: "None of the three drawn answers was taken: no faint nameless shape, no dash, no amber question mark where the name goes.",
    where: Where.Editor,
    ruled: "none of a, b, c",
    caption: "The parent is a real person in the record, named for their relation — Marcus's mother — and the fragment draws them like anybody else, with that name under the shape.",
    fragment: genericParent(),
  },
  {
    n: 11,
    title: "A child whose parents' bond is not in the record",
    lead: "None of the three drawn answers was taken: no faint stub of bar, no line rising into nothing, no invented pair of parents.",
    where: Where.Ballot,
    ruled: "none of a, b, c",
    caption: "The child stands alone on the children's row with no line above them. Nothing is drawn that the record does not hold.",
    fragment: orphan(),
  },
  {
    n: 12,
    title: "A name too long for the box",
    lead: "The desktop has no rule. Phone width forces one.",
    where: Where.Editor,
    ruled: "a",
    caption: "Cut the name and end it with three dots, always on one line.",
    fragment: longName(),
  },
];

const rowHtml = (row: Row) => {
  const tag = `${row.n}`;
  const svg = render(row.fragment, { u });
  return `<div class="mk-sec"><h2><span>${row.n}</span>${row.title}</h2>
<p>${row.lead}</p>
<div class="mk-row"><div class="col">${frame(row.where, tag, svg, row.title)}<div class="mk-cap"><b>ruled: ${row.ruled}</b> &mdash; ${row.caption}</div></div></div></div>`;
};

const hostile = cases
  .map((one) => {
    const svg = render(one.fragment, { u });
    const tag = `H${one.key}`;
    return `<div class="col">${frame(Where.Ballot, tag, svg, one.title)}<div class="mk-cap">${tag} &mdash; ${one.title}.</div></div>`;
  })
  .join("\n");

const page = `${head("The Family Fragment")}
<div class="mk-h1">The family fragment &mdash; one person, their parents&rsquo; bond above, their own bonds beside, the children under each</div>
<div class="mk-lead">Every picture on this page was drawn by the app&rsquo;s own fragment code, not by hand. The twelve rows below were the places where the desktop drawing code and the written specification disagreed, or where neither said anything. All twelve are now decided, and each row shows the one way the code draws it, with the answer named above the words. Rows 9, 10 and 11 were answered with something none of the drawn pictures offered, and the words say what. The last block draws the sixteen hard cases, so you can see nothing collides. Fictional people only.</div>
${rows.map(rowHtml).join("\n")}
<div class="mk-sec"><h2><span>H</span>The sixteen hard cases</h2>
<p>No choices here. This is what the renderer produces for each awkward family, at phone width.</p>
<div class="mk-row">${hostile}</div></div>
`;

writeFileSync(join(mockups, "fragment.html"), page);
console.log("wrote", join(mockups, "fragment.html"));
