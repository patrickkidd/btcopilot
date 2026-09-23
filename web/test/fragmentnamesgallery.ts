/** Writes doc/mockups/fragment-names.html — the same family fragment
 * drawn twice, once with each person's name under the shape (the way it is
 * ruled and built today) and once with the name over it. Every picture comes
 * from the shipping renderer.
 * Run it from web/ with:
 *   npx esbuild test/fragmentnamesgallery.ts --bundle --format=esm --platform=node \
 *     --outfile=/tmp/names.mjs && node /tmp/names.mjs
 */

import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { NamePlace, render, type Fragment } from "../src/fragment";
import { longName, plain, twoBonds } from "./fragmentcases";
import { Where, frame, head, mockups, u } from "./galleryshell";

/** Corinne, with her parents' bond above her — the item on the ballot. */
const corinne = (): Fragment => ({ ...plain(), center: 5 });

type Row = {
  n: number;
  title: string;
  lead: string;
  fragment: Fragment;
  below: string;
  above: string;
};

const rows: Row[] = [
  {
    n: 1,
    title: "Corinne's parents, on the ballot card",
    lead: "The version card a coder votes on. Corinne is in the middle, her parents' bond above her, her brother beside her.",
    fragment: corinne(),
    below:
      "The name sits under the shape. Under a person who has children, the name has to share that space with the line dropping to them.",
    above:
      "The name sits over the shape. Over a person whose parents are in the record, the name has to share that space with the line coming down from their parents' bar.",
  },
  {
    n: 2,
    title: "A name too long for the box",
    lead: "The renderer cuts a long name to the box width plus one sibling gap and ends it with three dots, whichever side it is written on.",
    fragment: longName(),
    below:
      "The cut name runs along the bottom of the shape, clear of the children's row below it.",
    above:
      "The cut name runs along the top of the shape, and on the children's row it reaches up toward their parents' bar.",
  },
  {
    n: 3,
    title: "One person with two bonds in a row",
    lead: "The middle person had two partners, so the two bond lines share the one row.",
    fragment: twoBonds(),
    below:
      "Three names sit in a line under three shapes, below the bond lines that join them.",
    above:
      "Three names sit in a line over three shapes, in the same band as the bond lines that join them.",
  },
];

const pair = (row: Row) => {
  const below = render(row.fragment, { u, names: NamePlace.Below });
  const above = render(row.fragment, { u, names: NamePlace.Above });
  return `<div class="mk-sec"><h2><span>${row.n}</span>${row.title}</h2>
<p>${row.lead}</p>
<div class="mk-row">
<div class="col">${frame(Where.Ballot, `${row.n} below`, below, row.title)}<div class="mk-cap"><b>names below &mdash; what is built today</b> &mdash; ${row.below}</div></div>
<div class="col">${frame(Where.Ballot, `${row.n} above`, above, row.title)}<div class="mk-cap"><b>names above</b> &mdash; ${row.above}</div></div>
</div></div>`;
};

const page = `${head("Names below or above the shape")}
<div class="mk-h1">The family fragment &mdash; each person&rsquo;s name written under the shape, or over it</div>
<div class="mk-lead">Every picture here was drawn by the app&rsquo;s own fragment code. The left picture in each pair is what the app draws today: the name under the shape. The right picture is the same family with the name over the shape instead, and nothing else changed. What you give up either way is space: a name written over a shape shares that band with the line coming down from that person&rsquo;s parents, and a name written under a shape shares that band with the line dropping to that person&rsquo;s children. Fictional people only.</div>
${rows.map(pair).join("\n")}
`;

writeFileSync(join(mockups, "fragment-names.html"), page);
console.log("wrote", join(mockups, "fragment-names.html"));
