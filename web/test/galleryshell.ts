/** What the two fragment pages in doc/mockups share: where they are
 * written, the app's own stylesheet, and the phone frame each picture sits in.
 * Run from the web/ directory. */

import { readFileSync } from "node:fs";
import { join } from "node:path";

export const root = join(process.cwd(), "..");
export const mockups = join(root, "doc", "mockups");

/** Pixels per person box. */
export const u = 40;

export const style = (() => {
  const source = readFileSync(join(mockups, "review.html"), "utf8");
  const open = source.indexOf("<style>");
  const close = source.indexOf("</style>", open);
  return source.slice(open, close + "</style>".length);
})();

export enum Where {
  Ballot = "ballot",
  Editor = "editor",
}

const AVATAR = `<button class="avatar" type="button"><svg viewBox="0 0 22 22" width="24" height="24" aria-hidden="true"><circle cx="11" cy="7.5" r="4" fill="currentColor"></circle><path d="M3 20c0-4.4 3.6-7 8-7s8 2.6 8 7z" fill="currentColor"></path></svg></button>`;

export const frame = (where: Where, tag: string, svg: string, title: string) =>
  where === Where.Ballot
    ? `<div class="frame phone fr"><div class="app">
<div class="titlerow"><button class="sn-back" type="button">&#8249;</button><div class="ttl">Session 3 &middot; ballot &middot; 2 of 6</div>${AVATAR}</div>
<div class="card"><div class="progress">version <b>${tag}</b> &middot; ${title}</div><div class="fragwrap">${svg}</div>
<div class="take tap"><span>keep this version</span><span class="n">2 coders</span></div></div>
</div><div class="tagbadge">${tag}</div></div>`
    : `<div class="frame phone fr"><div class="app">
<div class="titlerow"><button class="sn-back" type="button">&#8249;</button><div class="ttl">Marcus Whitlock</div>${AVATAR}</div>
<div class="editor"><div class="sec">Family</div><div class="fragwrap">${svg}</div>
<div class="hint">${title}</div></div>
</div><div class="tagbadge">${tag}</div></div>`;

export const extra = `
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
.mk-cap b { color: var(--ink); }
.tagbadge { position: absolute; top: 10px; left: 12px; z-index: 4; font: 500 12px var(--mono); color: var(--onaccent); background: var(--data); border-radius: 6px; padding: 2px 7px; }
.fragwrap { display: flex; justify-content: center; padding: 10px 0 14px; overflow-x: auto; }
.fragwrap svg { max-width: 100%; height: auto; }
.frame.fr .card { margin: 10px; padding: 12px; border: 1px solid var(--line); border-radius: 12px; background: var(--panel); }
.frame.fr .editor { padding: 12px; }
`;

export const head = (title: string) => `<title>${title}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
${style}
<style>${extra}</style>
`;
