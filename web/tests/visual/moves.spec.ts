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
    await page.goto("/personal/");
    await expect(page.locator(".bub.coach").first()).toBeVisible();
    const offer = page.locator(".bub .chip.ask").first();
    await expect(offer).toHaveText("[winter 1993]");
    await offer.click();
    await expect(page.locator("#composer .chip")).toHaveCount(1);
    await expect(page.locator(".inbar")).toHaveScreenshot("offer-in-composer.png");
  });

  test("what the coach named stays lit on the picture", async ({ page }) => {
    await page.goto("/personal/");
    await expect(page.locator(".ss")).toBeVisible();
    await page.waitForTimeout(500);
    await expect(page.locator(".ss-t.on").first()).toBeVisible();
    await expect(page.locator(".pic")).toHaveScreenshot("spotlight-at-rest.png");
  });
});

test.describe("the timeline behind the menu", () => {
  test.use({ storageState: stateFor("three40") });

  test("the list of everything, with the banner", async ({ page }) => {
    await page.goto("/personal/");
    await page.locator("#menu-open").click();
    await expect(page.locator("#menu-body .row").first()).toBeVisible();
    await expect(page.locator("#menu-screen")).toHaveScreenshot("menu-list.png");
  });

  test("the editor's fields, text centred in the box", async ({ page }) => {
    await page.goto("/personal/");
    await page.locator("#menu-open").click();
    await page.locator("#menu-body .row").first().click();
    await expect(page.locator(".editor .segs").first()).toBeVisible();
    // The word fields sit below the fold; a fixed offset keeps the shot stable.
    await page.locator("#menu-body").evaluate((body) => {
      body.scrollTop = 420;
    });
    await expect(page.locator("#menu-screen")).toHaveScreenshot("menu-editor.png");
  });
});

/** The editor shows a second person, a child and the shift block only for the
 * kinds `EventForm.qml` shows them for. These assert behaviour, not pixels. */
test.describe("the editor's fields by kind", () => {
  test.use({ storageState: stateFor("editable") });

  const openEditor = async (page: import("@playwright/test").Page) => {
    await page.goto("/personal/");
    await page.locator("#menu-open").click();
    await page.locator("#menu-body .row").first().click();
    await expect(page.locator(".editor .segs").first()).toBeVisible();
  };
  const pick = (page: import("@playwright/test").Page, group: string, value: string) =>
    page.locator(`.segs[data-name="${group}"] .seg[data-value="${value}"]`).click();
  const block = (page: import("@playwright/test").Page, name: string) =>
    page.locator(`.editor [data-block="${name}"]`);

  for (const [kind, spouse, child] of [
    ["shift", false, false],
    ["death", false, false],
    ["married", true, false],
    ["bonded", true, false],
    ["separated", true, false],
    ["divorced", true, false],
    ["moved", true, false],
    ["birth", true, true],
    ["adopted", true, true],
  ] as [string, boolean, boolean][]) {
    test(`${kind} shows ${spouse ? "a" : "no"} second person and ${child ? "a" : "no"} child`, async ({
      page,
    }) => {
      await openEditor(page);
      await pick(page, "kind", kind);
      await expect(block(page, "pair")).toBeVisible({ visible: spouse });
      await expect(block(page, "child")).toBeVisible({ visible: child });
      await expect(block(page, "shift")).toBeVisible({ visible: kind === "shift" });
    });
  }

  test("the second person is named for the kind", async ({ page }) => {
    await openEditor(page);
    await pick(page, "kind", "married");
    await expect(page.locator('.editor [data-label="spouse"]')).toHaveText("Partner 2");
    await pick(page, "kind", "birth");
    await expect(page.locator('.editor [data-label="person"]')).toHaveText("Parent 1");
    await expect(page.locator('.editor [data-label="spouse"]')).toHaveText("Parent 2");
    await pick(page, "kind", "moved");
    await expect(page.locator('.editor [data-label="spouse"]')).toHaveText("Partner");
  });

  test("targets appear with a relationship, triangles only inside and outside", async ({
    page,
  }) => {
    await openEditor(page);
    await pick(page, "kind", "shift");
    // these tests write to the record they open, so the one that saves leaves a
    // relationship behind for the next run: start from none whatever is there
    await pick(page, "relationship", "");
    await expect(block(page, "targets")).toBeHidden();
    await pick(page, "relationship", "conflict");
    await expect(block(page, "targets")).toBeVisible();
    await expect(page.locator('.editor [data-label="targets"]')).toHaveText("Other(s)");
    await expect(block(page, "triangles")).toBeHidden();
    await pick(page, "relationship", "inside");
    await expect(block(page, "triangles")).toBeVisible();
    await expect(page.locator('.editor [data-label="triangles"]')).toHaveText("Outside(s)");
    await expect(page.locator('.editor [data-label="person"]')).toHaveText("Person");
    await pick(page, "relationship", "overfunctioning");
    await expect(page.locator('.editor [data-label="person"]')).toHaveText("Overfunctioner");
  });

  test("a relationship saves with two targets", async ({ page }) => {
    await openEditor(page);
    await pick(page, "kind", "shift");
    await pick(page, "relationship", "conflict");
    const targets = page.locator('.segs[data-name="relationshipTargets"] .seg');
    // whatever a previous run left on comes off first, so two is two
    for (const chip of await page
      .locator('.segs[data-name="relationshipTargets"] .seg.on')
      .all())
      await chip.click();
    await targets.nth(0).click();
    await targets.nth(1).click();
    const saved = page.waitForResponse(
      (r) => /\/personal\/events/.test(r.url()) && r.request().method() === "PATCH",
    );
    await page.locator(".editor .save").click();
    const body = (await saved).request().postDataJSON();
    expect(body.relationship).toBe("conflict");
    expect(body.relationshipTargets).toHaveLength(2);
    // The row is redrawn from the record, so the codes prove the write stuck.
    await expect(page.locator("#menu-body .r2").first()).toContainText("R conflict");
  });
});
