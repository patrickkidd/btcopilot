import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { Page } from "@playwright/test";

/** A page that renders the real `moves.ts` against the real `theme.css`, one
 * cell per move, so a drawing can be looked at without a coach turn.
 *
 * DRAWINGS_SRC names another copy of `web/src` to render instead, so a copy can
 * be broken to see a test fail without touching the shared checkout. */

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = process.env.DRAWINGS_SRC ?? join(HERE, "..", "..", "src");

export interface Case {
  name: string;
  kind: string | null;
  shifts?: { symptom?: string; anxiety?: string; functioning?: string };
  three?: boolean;
}

export const CASES: Case[] = [
  { name: "toward", kind: "toward" },
  { name: "away", kind: "away" },
  { name: "distance", kind: "distance" },
  { name: "cutoff", kind: "cutoff" },
  { name: "conflict", kind: "conflict" },
  { name: "fusion", kind: "fusion" },
  { name: "defined-self", kind: "defined-self" },
  { name: "inside", kind: "inside", three: true },
  { name: "outside", kind: "outside", three: true },
  { name: "overfunctioning", kind: "overfunctioning" },
  { name: "underfunctioning", kind: "underfunctioning" },
  { name: "projection", kind: "projection" },
  { name: "anxiety", kind: null, shifts: { anxiety: "up" } },
  { name: "symptom-up", kind: null, shifts: { symptom: "up" } },
  { name: "symptom-down", kind: null, shifts: { symptom: "down" } },
  { name: "functioning-down", kind: null, shifts: { functioning: "down" } },
  { name: "functioning-up", kind: null, shifts: { functioning: "up" } },
];

/** The drawings do not change with the window, so one size is the whole story. */
export function drawings(): string {
  const out = mkdtempSync(join(tmpdir(), "fd-moves-"));
  const bundle = join(out, "moves.js");
  const entry = join(out, "entry.ts");
  writeFileSync(
    entry,
    `export * from ${JSON.stringify(join(SRC, "moves.ts"))};\n` +
      `export { triangle } from ${JSON.stringify(join(SRC, "board.ts"))};\n`,
  );
  execFileSync(
    join(HERE, "..", "..", "node_modules", ".bin", "esbuild"),
    [entry, "--bundle", "--format=esm", `--outfile=${bundle}`],
    { stdio: "pipe" },
  );
  const html = `<!doctype html><meta charset="utf-8"><style>
${readFileSync(join(SRC, "theme.css"), "utf8")}
body { margin: 0; background: var(--bg); }
.cell { width: 390px; height: 220px; }
</style><div id="root"></div><script type="module">
${readFileSync(bundle, "utf8")}
const cases = ${JSON.stringify(CASES)};
const W = 390, CY = 100, H = 220;
const pair = [
  { id: 1, name: "Ann", gender: "female" },
  { id: 2, name: "Bo", gender: "male" },
];
const trio = [...pair, { id: 3, name: "Cy", gender: "female" }];
const root = document.getElementById("root");
for (const spec of cases) {
  const figures = ring(spec.three ? trio : pair, W, CY, 17, H);
  const shifts = Object.assign(
    { symptom: null, anxiety: null, functioning: null },
    spec.shifts ?? {},
  );
  const drawn = draw(spec.kind, figures[0], figures[1] ?? null, shifts, figures[2] ?? null);
  const classes = new Map([[figures[0].id, drawn.actor + " mover"]]);
  if (figures[1] && drawn.target) classes.set(figures[1].id, drawn.target);
  if (figures[2] && drawn.third) classes.set(figures[2].id, drawn.third);
  const ghosts = new Map();
  if (drawn.ghosts.actor) ghosts.set(figures[0].id, drawn.ghosts.actor);
  if (figures[1] && drawn.ghosts.target) ghosts.set(figures[1].id, drawn.ghosts.target);
  const body = drawn.marks + figures
    .map((f) => figure(f, classes.get(f.id) ?? "", ghosts.get(f.id) ?? "", drawn.steps[f.id]))
    .join("");
  const cell = document.createElement("div");
  cell.className = "cell";
  cell.id = "m-" + spec.name;
  cell.innerHTML =
    '<div class="ss" style="height:' + H + 'px"><svg viewBox="0 0 ' + W + ' ' + H +
    '"><g class="cast">' + body + '</g></svg></div>';
  root.append(cell);
}
// the board a coach's triangle view opens, which only a coach turn can reach
// in the app and so cannot be driven from a golden there
const tri = document.createElement("div");
tri.className = "cell";
tri.id = "m-triangle-board";
tri.style.height = "264px";
tri.innerHTML =
  '<div class="ss board" style="height:264px">' +
  triangle(trio.map((p) => ({ ...p, primary: false })), W).svg +
  '</div>';
root.append(tri);
</script>`;
  const file = join(out, "moves.html");
  writeFileSync(file, html);
  return "file://" + file;
}

/** Hold every clock at one instant: the SVG timeline and the CSS animations. */
export const freeze = (page: Page, ms: number) =>
  page.evaluate((at) => {
    for (const svg of document.querySelectorAll("svg")) {
      svg.pauseAnimations();
      svg.setCurrentTime(at / 1000);
    }
    for (const animation of document.getAnimations()) {
      animation.pause();
      animation.currentTime = at;
    }
  }, ms);
