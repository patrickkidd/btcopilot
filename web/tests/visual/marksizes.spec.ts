import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** Every mark the play-by-play draws for one event, each on its own snapshot of
 * the Whitlock stand-in family, measured on screen in the real drawer: on its
 * own date in the emphasis colour, and on the next snapshot carried in grey.
 * The snapshots are drawn by the real `snapshots.ts`, bundled for the page. */

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB = join(HERE, "..", "..");

/** The event behind each snapshot, and where its mark is found once drawn.
 * Marks drawn around a person (the death X, anxiety's spikes) take the
 * person's size, and an arrow or the fusion bands take the distance between
 * two people, so only the marks that stand on their own are held to one size. */
const SHOWN = [
  { name: "separated", id: 201, marks: ".slash", sized: true },
  { name: "symptom", id: 203, marks: '[data-mark^="cross:"] :is(rect, line, polygon)', sized: true },
  { name: "divorced", id: 204, marks: ".slash", sized: true },
  { name: "cutoff", id: 301, marks: '[data-mark$=":cutoff"] :is(.mv-wall, .mv-strike)', sized: true },
  { name: "distance", id: 302, marks: '[data-mark$=":distance"] .mv-wall', sized: true },
  { name: "conflict", id: 303, marks: '[data-mark$=":conflict"] .mv-burst', sized: true },
  { name: "projection", id: 304, marks: '[data-mark$=":projection"] .s-out line', sized: false },
  { name: "fusion", id: 305, marks: '[data-mark$=":fusion"] .mv-band', sized: false },
  { name: "anxiety", id: 306, marks: ".spikes line", sized: false },
  { name: "death", id: 119, marks: '.p[data-id="1"] .xd', sized: false },
  { name: "toward", id: 131, marks: '[data-mark$=":toward"] :is(line, polygon)', sized: false },
  { name: "away", id: 132, marks: '[data-mark$=":away"] :is(line, polygon)', sized: false },
];

/** The Whitlock record with one event per move it lacks, told one event a
 * snapshot in date order: each snapshot's svg, and the next one's. */
function bundle(): string {
  const out = mkdtempSync(join(tmpdir(), "fd-symbols-"));
  const entry = join(out, "entry.ts");
  writeFileSync(
    entry,
    `import { Told } from ${JSON.stringify(join(WEB, "src", "snapshots.ts"))};
import { CORINNE, DELPHINE, ERROL, MARCUS, event, timeline } from ${JSON.stringify(join(WEB, "test", "whitlock.ts"))};
const tl = timeline();
const added = [
  [301, MARCUS, { relationship: "cutoff", relationshipTargets: [ERROL] }],
  [302, MARCUS, { relationship: "distance", relationshipTargets: [DELPHINE] }],
  [303, MARCUS, { relationship: "conflict", relationshipTargets: [DELPHINE] }],
  [304, DELPHINE, { relationship: "projection", relationshipTargets: [CORINNE] }],
  [305, DELPHINE, { relationship: "fusion", relationshipTargets: [CORINNE] }],
  [306, MARCUS, { anxiety: "up" }],
] as const;
added.forEach(([id, who, over], i) => tl.events.push(event(id, "1983-0" + (i + 1) + "-15", "shift", who, over)));
const at = (id: number) => tl.events.find((e) => e.id === id)!;
const ids = ${JSON.stringify(SHOWN.map((s) => s.id))}.sort((a, b) => at(a).dateTime!.localeCompare(at(b).dateTime!));
const t = new Told(tl, {
  cluster_id: null,
  point: "Every mark the play-by-play draws.",
  snapshots: ids.map((id) => ({ date: at(id).dateTime!, event_ids: [id], fact: String(id), guess: null })),
  question: null,
});
(window as any).SHOTS = Object.fromEntries(
  ids.map((id, i) => [id, { now: t.shot(i).svg, was: i + 1 < ids.length ? t.shot(i + 1).svg : null }]),
);
`,
  );
  const js = join(out, "symbols.js");
  execFileSync(join(WEB, "node_modules", ".bin", "esbuild"), [entry, "--bundle", "--format=iife", `--outfile=${js}`], {
    stdio: "pipe",
  });
  return readFileSync(js, "utf8");
}

interface Size {
  name: string;
  tone: string;
  w: number;
  h: number;
  stroke: number;
  colour: string;
}

/** The marks' union box in their own drawing frame, so a mark keeps its size
 * whatever angle it is drawn at, scaled to the screen; strokes included. */
const measure = (page: Page, id: number, name: string, selector: string, tone: "now" | "was") =>
  page.evaluate(
    ({ id, name, selector, tone }): Size | null => {
      const svg = (window as any).SHOTS[id][tone];
      if (!svg) return null;
      const draw = document.querySelector("#pbp .draw")!;
      draw.querySelector("svg")!.outerHTML = svg;
      const root = draw.querySelector("svg")!;
      // a divorce's two slashes are one mark, whichever of them is lit
      const els = [...root.querySelectorAll<SVGGraphicsElement>(selector)].filter(
        (el) => el.matches(".slash") || !!el.closest(".now, .pop") === (tone === "now"),
      );
      if (!els.length) throw new Error(`no ${selector} drawn for ${name}`);
      const ctm = root.getScreenCTM()!;
      const scale = Math.hypot(ctm.a, ctm.b);
      const frame = els[0].parentElement as unknown as SVGGraphicsElement;
      let [x0, y0, x1, y1] = [Infinity, Infinity, -Infinity, -Infinity];
      let stroke = 0;
      els.forEach((el) => {
        const b = el.getBBox();
        const m = frame.getScreenCTM()!.inverse().multiply(el.getScreenCTM()!);
        const s = parseFloat(getComputedStyle(el).strokeWidth) || 0;
        stroke = Math.max(stroke, s);
        [
          [b.x, b.y],
          [b.x + b.width, b.y],
          [b.x, b.y + b.height],
          [b.x + b.width, b.y + b.height],
        ].forEach(([x, y]) => {
          const p = new DOMPoint(x, y).matrixTransform(m);
          x0 = Math.min(x0, p.x - s / 2);
          y0 = Math.min(y0, p.y - s / 2);
          x1 = Math.max(x1, p.x + s / 2);
          y1 = Math.max(y1, p.y + s / 2);
        });
      });
      // the lit one of a divorce's two slashes is the second
      const paint = getComputedStyle(els[els.length - 1]);
      const r = (v: number) => Math.round(v * scale * 10) / 10;
      return {
        name,
        tone,
        w: r(x1 - x0),
        h: r(y1 - y0),
        stroke: r(stroke),
        colour: paint.stroke !== "none" ? paint.stroke : paint.fill,
      };
    },
    { id, name, selector, tone },
  );

async function open(page: Page) {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.locator(".bub.coach[data-play]").last().click();
  await expect(page.locator("#pbp .draw svg")).toBeVisible();
  await page.addScriptTag({ content: bundle() });
  await page.addStyleTag({ content: "#pbp *, #pbp { animation: none !important; transition: none !important; }" });
}

/** The emphasis colour and the grey of a carried mark, as the page paints them. */
const paints = (page: Page) =>
  page.evaluate(() => {
    const probe = document.createElement("i");
    document.querySelector("#pbp")!.append(probe);
    const read = (v: string) => ((probe.style.color = `var(${v})`), getComputedStyle(probe).color);
    const out = { now: read("--move"), was: read("--faint") };
    probe.remove();
    return out;
  });

const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2;
};

test.use({ storageState: stateFor("whitlock") });

// R-0679, R-0552
test("every mark the play-by-play draws is of one size, the current one in the emphasis colour", async ({ page }) => {
  await open(page);
  const sizes: Size[] = [];
  for (const s of SHOWN)
    for (const tone of ["now", "was"] as const) {
      const size = await measure(page, s.id, s.name, s.marks, tone);
      if (size) sizes.push(size);
    }

  const sized = sizes.filter((s) => SHOWN.find((x) => x.name === s.name)!.sized);
  const mid = median(sized.map((s) => Math.max(s.w, s.h)));
  const off = sized.filter((s) => Math.max(s.w, s.h) < 0.75 * mid || Math.max(s.w, s.h) > 1.33 * mid);
  expect(off.map((s) => `${s.name} ${s.tone} ${Math.max(s.w, s.h)} against ${mid}`)).toEqual([]);

  const paint = await paints(page);
  const now = sizes.filter((s) => s.tone === "now" && s.colour !== paint.now);
  expect(now.map((s) => `${s.name} ${s.colour}`)).toEqual([]);
  // a death X returns to plain ink after its date, not grey
  const was = sizes.filter((s) => s.tone === "was" && s.name !== "death" && s.colour !== paint.was);
  expect(was.map((s) => `${s.name} ${s.colour}`)).toEqual([]);
});
