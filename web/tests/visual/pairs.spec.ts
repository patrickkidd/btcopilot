import { expect, test, type Page, type Route } from "@playwright/test";
import { flask, stateFor, username } from "./setup";
import { deadTaps, tap, watchDom } from "./gate";

/** Blind pairs (R-0599): the conversation once, two replies with no model
 * named, and a pick of left, right or tie with a one-line note. The pairs are
 * served by a stand-in for the review's endpoints, so the page is checked on
 * hostile words: a reply of 60 characters with no space to break on, a unicode
 * name, and a long line of the conversation. */

const WHO = username("empty");
const roles = (...names: string[]) =>
  flask("admin", "run", "--", "users", "roles", WHO, ...names, "--yes");

const LONG = "Zoë-Ångström-Nørgaard-Łukasiewicz-Þórðardóttir-Tromsø-Ålesund";
const PAIRS = [
  {
    id: 1,
    source: "shadow",
    context: [
      { who: "user", text: `My aunt ${LONG} moved the year my father got sick, and nobody said why.` },
      { who: "coach", text: "What year was that, roughly?" },
      { who: "user", text: "It was 1998, I think." },
    ],
    left: LONG,
    right: "Who in the family noticed first that your father was unwell?",
  },
  {
    id: 2,
    source: "replay",
    context: [{ who: "user", text: "My mother started calling her sister every night." }],
    left: "Every night, from the start?",
    right: "Was that new for her, or had they always been close?",
  },
];

async function serve(page: Page) {
  const waiting = [...PAIRS];
  const tally: Record<string, { model: string; won: number; lost: number; tied: number }> = {};
  await page.route("**/review/pairs", (route: Route) => route.fulfill({ json: waiting }));
  await page.route("**/review/picks", (route: Route) =>
    route.fulfill({ json: Object.values(tally) }),
  );
  await page.route("**/review/picks/*", async (route: Route) => {
    const { choice, note } = route.request().postDataJSON();
    const pair = waiting.shift()!;
    for (const [side, model] of [["left", "model-a"], ["right", "model-b"]]) {
      const row = (tally[model] ??= { model, won: 0, lost: 0, tied: 0 });
      if (choice === "tie") row.tied++;
      else if (choice === side) row.won++;
      else row.lost++;
    }
    await route.fulfill({
      json: { id: pair.id, choice, note, left: "model-a", right: "model-b" },
    });
  });
}

const layout = (page: Page) =>
  page.evaluate(() => {
    const body = document.getElementById("pairs-body")!;
    const outer = body.getBoundingClientRect();
    const boxes = [...body.querySelectorAll(".pr-card, .pr-ctx, .pr-note, .pr-pick")];
    return {
      outside: boxes.filter((b) => {
        const r = b.getBoundingClientRect();
        return r.left < outer.left - 0.5 || r.right > outer.right + 0.5;
      }).length,
      sideways: document.documentElement.scrollWidth > window.innerWidth,
      named: /model-a|model-b/.test(body.querySelector(".pr-two")?.textContent ?? ""),
    };
  });

test.use({ storageState: stateFor("empty") });
test.beforeAll(() => roles("admin", "subscriber"));
test.afterAll(() => roles("subscriber"));

// R-0599
test("two replies are picked blind and the page moves on", async ({ page }, info) => {
  const errors: string[] = [];
  const failed: string[] = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("requestfailed", (r) => failed.push(r.url()));
  page.on("response", (r) => r.status() >= 400 && failed.push(`${r.status()} ${r.url()}`));
  await watchDom(page);
  await serve(page);

  await page.goto("/app/");
  await page.locator("#account").click();
  await tap(page, page.locator(".sn-pane.in .sn-row", { hasText: "Better replies" }));
  await expect(page.locator("#pairs-screen .pr-card")).toHaveCount(2);
  await expect(page.locator(".sn-pane.in:not(.under)")).toHaveAttribute("data-page", "pairs-screen");
  await expect(page.locator("#title")).toHaveText("Better replies");
  expect(await layout(page)).toEqual({ outside: 0, sideways: false, named: false });
  await expect(page.locator("#pairs-body .plnote")).toHaveText("2 left to pick");
  await page.screenshot({ path: info.outputPath(`pairs-${info.project.name}.png`) });

  await page.locator(".pr-note").fill("names the aunt back");
  await tap(page, page.locator('.pr-pick[data-choice="left"]'));
  await expect(page.locator("#pairs-body .plnote")).toHaveText("1 left to pick");
  await expect(page.locator(".toasts")).toContainText("model-a");
  await expect(page.locator("#pairs-body .sn-row")).toHaveCount(2);
  expect(await layout(page)).toEqual({ outside: 0, sideways: false, named: false });

  await tap(page, page.locator('.pr-pick[data-choice="tie"]'));
  await expect(page.locator("#pairs-body .none")).toHaveText("Nothing to compare yet.");
  await expect(page.locator("#pairs-body .sn-row").first()).toContainText("won 1 · lost 0 · tied 1");

  expect(deadTaps).toEqual([]);
  expect(errors).toEqual([]);
  expect(failed).toEqual([]);
});
