import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import { EXACT, stateFor } from "./setup";

/** The move language, one golden per move, so a change to any drawing has to be
 * looked at.
 *
 * They are taken off a page that renders the real `moves.ts` against the real
 * `theme.css`, not off the app. A chip no longer opens the moves board, because
 * a level change from a chip tap would move the chat bubbles below it, and the
 * board's own entry runs a live coach turn, which no golden can depend on. The
 * drawings are the thing under test, so the page under test is the drawings.
 *
 * Every clock is frozen at the same instant before each shot: the SVG timeline
 * with `setCurrentTime`, and the CSS animations through the Web Animations API.
 * A move runs an 8, 10 or 12 second loop, so the instant decides what is on
 * screen and it has to be the same one every run. */

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = join(HERE, "..", "..", "src");

/** Two thirds through the 8s story loop: past every move's first beat, before
 * the ones that end early have gone. */
const AT_MS = 5200;

interface Case {
  name: string;
  kind: string | null;
  shifts?: { symptom?: string; anxiety?: string; functioning?: string };
  three?: boolean;
}

const CASES: Case[] = [
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
function page(): string {
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

test.describe("the move language", () => {
  const url = page();

  for (const spec of CASES) {
    test(`the ${spec.name} drawing`, async ({ page: browser }) => {
      // the drawings do not change with the window, so one size is the story
      test.skip(test.info().project.name !== "phone");
      await browser.goto(url);
      await browser.evaluate((ms) => {
        for (const svg of document.querySelectorAll("svg")) {
          svg.pauseAnimations();
          svg.setCurrentTime(ms / 1000);
        }
        for (const animation of document.getAnimations()) {
          animation.pause();
          animation.currentTime = ms;
        }
      }, AT_MS);
      await expect(browser.locator(`#m-${spec.name}`)).toHaveScreenshot(
        `move-${spec.name}.png`,
        EXACT,
      );
    });
  }

  test("the board a coach's triangle opens", async ({ page: browser }) => {
    test.skip(test.info().project.name !== "phone");
    await browser.goto(url);
    await expect(browser.locator("#m-triangle-board")).toHaveScreenshot(
      "board-triangle.png",
      EXACT,
    );
  });
});

test.describe("what a chip does", () => {
  test.use({ storageState: stateFor("moves") });

  test("an offered chip goes into the message instead of aiming the picture", async ({
    page,
  }) => {
    await page.goto("/companion/");
    await expect(page.locator(".bub.coach").first()).toBeVisible();
    const offer = page.locator(".bub .chip.ask").first();
    await expect(offer).toHaveText("[winter 1993]");
    await offer.click();
    await expect(page.locator("#composer .chip")).toHaveCount(1);
    await expect(page.locator(".inbar")).toHaveScreenshot("offer-in-composer.png");
  });

  test("what the coach named stays lit on the picture", async ({ page }) => {
    await page.goto("/companion/");
    await expect(page.locator(".ss")).toBeVisible();
    await page.waitForTimeout(500);
    await expect(page.locator(".ss-t.on").first()).toBeVisible();
    await expect(page.locator(".pic")).toHaveScreenshot("spotlight-at-rest.png");
  });
});

test.describe("the timeline behind the menu", () => {
  test.use({ storageState: stateFor("three40") });

  test("the list of everything, with the banner", async ({ page }) => {
    await page.goto("/companion/");
    await page.locator("#menu-open").click();
    await expect(page.locator("#menu-body .row").first()).toBeVisible();
    await expect(page.locator("#menu-screen")).toHaveScreenshot("menu-list.png");
  });
});
