import { expect, test, type Page, type Route } from "./fixtures";
import { shell, stateFor, username } from "./setup";

/** The vote by pairing and Patrick's look over the pairings, on the app's own
 * page with the review answered from fixtures: one pairing per screen, the
 * opinions without names, a pick and a drop that both un-tap, and before the
 * vote opens, joins and splits on the same card; every card of a pairing shows
 * the same places, accented in every card where the opinions disagree, and
 * identical cards are one; on the look every opinion is one box picked whole,
 * one entry taken out from the split list (R-0963, R-0965, R-0966, R-0967,
 * R-0970). */

const CUT = 2;
const line = (statement_id: number, text: string) => ({ statement_id, who: "Dana", text });
const LONG = line(
  52,
  "My stepfather and I were never close. Even now a visit with him wears me out, and my " +
    "cousins say the same about him, so it is not only me. I split my weeks between two " +
    "houses as a kid. We moved in with him in 1994.",
);

const event = (fields: Record<string, unknown>) => ({
  kind: "shift",
  dateTime: "1994-01-01",
  datePrecision: "year",
  dateCertainty: "approximate",
  ...fields,
});

/** Three pairings: four coders on one move, two of them alike and one with a
 * joined move and shift; a person; a couple. */
const ITEMS = [
  {
    id: 41,
    item_kind: "event",
    status: "disputed",
    coders: 4,
    not_coded: 0,
    people: [],
    line: LONG,
    pairing_reason: "The same move into the stepfather's house, told four ways.",
    pairing_confidence: "unsure",
    opinions: [
      { coding_id: 1, item_id: 11, person_name: "Dana Reyes", line: LONG, item: event({ anxiety: "up", title: "Stress at the new house" }) },
      { coding_id: 2, item_id: 21, person_name: "Dana Reyes", line: LONG, item: event({ anxiety: "up", title: "House was tense" }) },
      { coding_id: 3, item_id: 31, person_name: "Dana Reyes", line: LONG, item: event({ anxiety: "up", title: "Living with stepfather" }) },
      { coding_id: 3, item_id: 32, person_name: "Dana Reyes", line: LONG, item: event({ kind: "noted", title: "Moved into his house" }) },
      {
        coding_id: 4,
        item_id: 41,
        person_name: "Dana Reyes",
        toward_names: ["Lou Reyes"],
        line: LONG,
        item: event({ dateTime: "1900-01-01", relationship: "conflict", relationshipTargets: [70], title: "Fights with stepfather" }),
      },
    ],
  },
  {
    id: 42,
    item_kind: "person",
    status: "disputed",
    coders: 4,
    not_coded: 1,
    people: [],
    line: null,
    pairing_reason: "Lou, named by three.",
    pairing_confidence: "sure",
    opinions: [1, 2, 3].map((coding) => ({
      coding_id: coding,
      item_id: 7,
      line: line(53, "Lou is my stepfather."),
      item: { id: 7, name: "Lou", gender: coding === 3 ? "female" : "male" },
    })),
  },
  {
    id: 43,
    item_kind: "event",
    status: "disputed",
    coders: 4,
    not_coded: 2,
    people: [],
    line: line(60, "Mom died in 2003."),
    pairing_reason: "The mother's death.",
    pairing_confidence: "likely",
    opinions: [1, 2].map((coding) => ({
      coding_id: coding,
      item_id: 90 + coding,
      person_name: "Mara Reyes",
      line: line(60, "Mom died in 2003."),
      item: event({ kind: "death", dateTime: coding === 1 ? "2003-01-01" : "2003-06-01", datePrecision: coding === 1 ? "year" : "month", anxiety: null }),
    })),
  },
];

const cut = (ballot: string) => ({
  id: CUT,
  diagram_id: 1,
  sitting_id: 5,
  start_statement_id: 50,
  end_statement_id: 60,
  meeting_date: null,
  vote_opened_at: ballot === "open" ? "2026-11-16T00:00:00" : null,
  ratified_at: null,
  nudged_at: null,
  session: "A Sleep Problem",
  owner: "Dana",
  end_order: null,
  cut_day: null,
  started: true,
  agreement: null,
  ballot,
  pairing_agent: null,
});

interface Sent {
  method: string;
  path: string;
  body: unknown;
}

/** Answers every request the review screens make, and keeps what was sent. */
async function review(page: Page, state: { ballot: string }): Promise<Sent[]> {
  const sent: Sent[] = [];
  await page.route("**/review/**", async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/review/, "") + url.search;
    const body = request.postData() ? JSON.parse(request.postData()!) : null;
    const json = (answer: unknown, status = 200) => route.fulfill({ status, json: answer });
    if (request.method() !== "GET") sent.push({ method: request.method(), path, body });
    if (path === "/codings") return json({ id: 1 });
    if (path === `/cuts/${CUT}` && request.method() === "PATCH") {
      state.ballot = "open";
      return json(cut(state.ballot));
    }
    if (path === `/cuts/${CUT}`) return json(cut(state.ballot));
    if (path.startsWith("/cuts")) return json([cut(state.ballot)]);
    if (path.startsWith("/items?")) return json(ITEMS);
    if (path === "/items" && body.opinions)
      return json({
        items: [{ ...ITEMS[0], opinions: ITEMS[0].opinions.filter((one) => one.item_id !== body.opinions[0].item_id) }, { ...ITEMS[0], id: 44, pairing_confidence: "sure", opinions: ITEMS[0].opinions.filter((one) => one.item_id === body.opinions[0].item_id) }],
        deleted: [],
      });
    if (path === "/items") {
      state.ballot = "building";
      return json({ ballot: "building" }, 202);
    }
    if (/^\/items\/\d+$/.test(path)) return json({ items: [], deleted: [] });
    const vote = /^\/items\/(\d+)\/vote$/.exec(path);
    if (vote && request.method() === "PUT") return json({ id: 1, review_item_id: Number(vote[1]), ...body });
    if (vote) return json({ id: 1 });
    if (path.startsWith("/turns"))
      return json({
        turns: [50, 60].map((id) => ({ id, sitting_id: 5 })),
        sittings: [{ id: 5, started: "2026-10-01T10:00:00" }],
      });
    if (path.startsWith("/agenda")) return json({ meeting_date: null, cut_ids: [CUT], flagged_rules: [] });
    return json([]);
  });
  return sent;
}

/** Nothing on the screen spills sideways or out of the card it sits in. */
async function holds(page: Page): Promise<void> {
  const out = await page.evaluate(() => {
    const wide = document.documentElement.scrollWidth > window.innerWidth;
    const spills = [...document.querySelectorAll("#ballot-screen .pv-card *")].filter((one) => {
      const box = one.getBoundingClientRect();
      const card = one.closest(".pv-card")!.getBoundingClientRect();
      return box.width > 0 && (box.left < card.left - 0.5 || box.right > card.right + 0.5);
    }).length;
    const bar = document.querySelector("#ballot-bar")!.getBoundingClientRect();
    return { wide, spills, barBottom: Math.round(bar.bottom), height: window.innerHeight };
  });
  expect(out.wide).toBe(false);
  expect(out.spills).toBe(0);
  expect(out.barBottom).toBe(out.height);
}

function errors(page: Page): string[] {
  const seen: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") seen.push(message.text());
  });
  page.on("pageerror", (error) => seen.push(error.message));
  return seen;
}

/** A reload or a pasted address abandons the reads the page had in flight,
 * which WebKit reports as failed loads and Chromium as failed fetches; only
 * those are let go. */
async function leave(seen: string[], go: () => Promise<unknown>): Promise<void> {
  const from = seen.length;
  await go();
  seen.push(...seen.splice(from).filter((one) => !/: (Load failed|Failed to fetch)$/.test(one)));
}

const caption = (page: Page) => page.locator("#ballot-caption");

/** Every entry of one kind on screen shows the same places, and each place is
 * accented in every card of that kind or in none (R-0967). */
async function samePlaces(page: Page): Promise<void> {
  const places = await page.evaluate(() =>
    [...document.querySelectorAll("#ballot-screen .pv-entry")].map((entry) => ({
      kind: entry.querySelector(".pv-tag")?.textContent ?? "",
      lit: [...entry.querySelectorAll(".pv-l1 > *, .pv-l2 > :not(.pv-arrow), .pv-l3 > *")].map((one) =>
        one.classList.contains("pv-diff"),
      ),
    })),
  );
  expect(places.length).toBeGreaterThan(1);
  for (const one of places)
    expect(one.lit).toEqual(places.find((other) => other.kind === one.kind)!.lit);
}

/** How sure each pairing is reads the same on its dot, its chip and, for an
 * unsure one, the strip's badge, in light and in dark, three colours apart
 * (R-0972). */
async function agree(page: Page): Promise<void> {
  for (const theme of ["light", "dark"]) {
    await page.evaluate((one) => document.documentElement.setAttribute("data-theme", one), theme);
    const seen = await page.evaluate(() => {
      const paint = (one: Element) => getComputedStyle(one);
      const chip = document.querySelector("#ballot-screen .pv-ask .tok")!;
      const badge = [...document.querySelectorAll("#ballot-screen .caption .tok")].find((one) =>
        one.textContent!.endsWith("unsure"),
      )!;
      const dots = [...document.querySelectorAll("#ballot-screen circle.mark")];
      const fill = (state: string) => [...new Set(dots.filter((one) => one.classList.contains(state)).map((one) => paint(one).fill))];
      return {
        chip: [paint(chip).color, paint(chip).borderColor],
        badge: [paint(badge).color, paint(badge).borderColor],
        now: paint(document.querySelector("#ballot-screen circle.d-on")!).fill,
        unsure: fill("c-unsure"),
        likely: fill("c-likely"),
        sure: fill("c-sure"),
      };
    });
    expect(seen.chip).toEqual(seen.badge);
    expect(seen.now).toBe(seen.chip[1]);
    expect(seen.unsure).toEqual([seen.chip[1]]);
    expect(seen.likely).toHaveLength(1);
    expect(seen.sure).toHaveLength(1);
    expect(new Set([...seen.unsure, ...seen.likely, ...seen.sure]).size).toBe(3);
  }
  await page.evaluate(() => document.documentElement.removeAttribute("data-theme"));
}

/** Scrolled to its end, the pairing's last line stands above the bar. */
async function clear(page: Page): Promise<void> {
  const gap = await page.evaluate(() => {
    const body = document.querySelector("#ballot-body")!;
    body.scrollTop = body.scrollHeight;
    const last = body.lastElementChild!.getBoundingClientRect();
    return document.querySelector("#ballot-bar")!.getBoundingClientRect().top - last.bottom;
  });
  expect(gap).toBeGreaterThanOrEqual(0);
}

test.describe("the vote by pairing", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0965, R-0966, R-0967, R-0252
  test("one pairing per screen, opinions without names, a pick and a drop that both un-tap", async ({ page }) => {
    const seen = errors(page);
    const sent = await review(page, { ballot: "open" });
    await page.goto(`/app/vote/${CUT}`);
    await expect(page.locator("#title")).toContainText("ballot · 1 of 3");
    await expect(page.locator("#ballot-view circle")).toHaveCount(3);
    await expect(caption(page)).toContainText("3 open");
    // the conversation's order: the move, said first, then the stepfather, then the death
    await expect(page).toHaveURL(new RegExp(`/app/vote/${CUT}/41$`));
    await expect(caption(page)).toContainText("now · 1994");
    const depth = await page.evaluate(() => history.length);
    await page.locator("#ballot-view circle").nth(1).click();
    await expect(page.locator("#title")).toContainText("ballot · 2 of 3");
    // a step changes the pairing in the address in place, and a reload comes back to it
    await expect(page).toHaveURL(new RegExp(`/app/vote/${CUT}/42$`));
    expect(await page.evaluate(() => history.length)).toBe(depth);
    await leave(seen, () => page.reload());
    await expect(page.locator("#title")).toContainText("ballot · 2 of 3");
    await expect(page.locator(".pv-tag").first()).toHaveText("person");
    // the name all agree on is plain; the gender they split on is accented in every card
    await expect(page.locator(".pv-label")).toHaveCount(2);
    await expect(page.locator(".pv-l3 .chip.pv-diff")).toHaveText(["male", "female"]);
    await expect(page.locator(".pv-l2 .pv-diff")).toHaveCount(0);
    await samePlaces(page);
    // a date given to the year and one given to the month, both estimates, read as the year
    await page.locator("#ballot-view circle").nth(2).click();
    await expect(caption(page)).toContainText("now · 2003");
    await expect(page.locator(".pv-card")).not.toContainText(/Jan|Jun/);
    await page.locator("#ballot-view circle").nth(0).click();
    await expect(page.locator("#title")).toContainText("ballot · 1 of 3");

    // the passage is cut to two lines until tapped
    await expect(page.locator("#bl-quote.clip")).toBeVisible();
    // two coders said the same thing: four versions read as three opinions
    await expect(page.locator(".pv-label")).toHaveText(["opinion 1", "opinion 2", "opinion 3"]);
    await expect(page.locator(".pv-card")).not.toContainText(/coder 1|ballot1|coders? (said|wrote)|no sure date/);
    await expect(page.locator(".pv-card")).toContainText("no date yet");
    await expect(page.locator(".pv-diff", { hasText: "Lou Reyes" })).toBeVisible();
    // what a coder did not record keeps its place as an empty chip, accented with the place,
    // on the shifts only: the noted event holds none of a shift's places
    const noted = page.locator(".pv-entry", { has: page.locator(".pv-tag", { hasText: "noted" }) });
    await expect(noted).toHaveCount(1);
    await expect(noted).not.toContainText("recorded");
    await expect(page.locator(".chip.pv-diff", { hasText: "no one recorded" })).toHaveCount(2);
    await expect(page.locator(".chip.pv-diff", { hasText: "no anxiety recorded" })).toHaveCount(1);
    await expect(page.locator(".chip.pv-diff", { hasText: "no relationship recorded" })).toHaveCount(2);
    await samePlaces(page);
    await holds(page);
    await clear(page);

    const opinion = page.locator(".opinion.pv").first();
    await opinion.click();
    await expect(opinion).toHaveClass(/ on/);
    await expect(caption(page)).toContainText("2 open");
    await page.locator(".opinion.pv").first().click();
    await expect(page.locator(".opinion.pv.on")).toHaveCount(0);
    await expect(caption(page)).toContainText("3 open");

    await page.locator("#bl-drop").click();
    await expect(page.locator("#bl-drop")).toHaveClass(/ on/);
    await page.locator("#bl-drop").click();
    await expect(page.locator("#bl-drop")).not.toHaveClass(/ on/);

    await page.locator("#bl-quote").click();
    await expect(page.locator("#bl-quote.clip")).toHaveCount(0);

    const votes = sent.filter((one) => one.path.endsWith("/vote"));
    expect(votes.map((one) => one.method)).toEqual(["PUT", "DELETE", "PUT", "DELETE"]);
    expect(votes[0].path).toBe("/items/41/vote");
    expect(votes[0].body).toMatchObject({ choice: "opinion" });
    expect(seen).toEqual([]);
    await page.screenshot({ path: test.info().outputPath("pairing.png") });
  });
});

test.describe("Patrick's look over the pairings", () => {
  test.use({ storageState: stateFor("moves") });

  const roles = (to: string) =>
    shell(
      [
        "from btcopilot.extensions import db",
        "from btcopilot.models import User",
        `User.query.filter_by(username="${username("moves")}").one().roles = "${to}"`,
        "db.session.commit()",
        "",
      ].join("\n"),
    );

  test.beforeEach(() => roles("admin"));
  test.afterEach(() => roles("subscriber"));

  // R-0961, R-0963, R-0967, R-0970, R-0972, R-0974
  test("builds the ballot, shows it building, then the unsure pairings first to split and join before the vote opens", async ({
    page,
  }) => {
    const seen = errors(page);
    const state = { ballot: "none" };
    const sent = await review(page, state);
    await page.goto("/app/account/meeting");
    await page.locator(".tb-build").click();
    await expect(page.locator(".tb-cut")).toContainText("building the ballot");
    await expect(page.locator(".tb-vote")).toHaveCount(0);
    state.ballot = "built";
    await expect(page.locator(".tb-pairs")).toBeVisible({ timeout: 8000 });
    await expect(page.locator(".tb-cut")).toContainText("the ballot is built");

    await page.locator(".tb-pairs").click();
    await expect(page.locator("#title")).toContainText("pairings · 1 of 3");
    await expect(page).toHaveURL(new RegExp(`/app/pairings/${CUT}/41$`));
    // a step changes the pairing in the address in place, and a reload comes back to it
    const depth = await page.evaluate(() => history.length);
    await page.locator("#pr-next").click();
    await expect(page).toHaveURL(new RegExp(`/app/pairings/${CUT}/43$`));
    expect(await page.evaluate(() => history.length)).toBe(depth);
    await leave(seen, () => page.reload());
    await expect(page.locator("#title")).toContainText("pairings · 2 of 3");
    // an address naming a pairing a join took away opens the one nearest it
    await leave(seen, () => page.goto(`/app/pairings/${CUT}/40`));
    await expect(page.locator("#title")).toContainText("pairings · 1 of 3");
    await expect(page).toHaveURL(new RegExp(`/app/pairings/${CUT}/41$`));
    // the card asks its one question, how sure the call was a mark beside it,
    // the call's reason under its own label (R-0963, R-0972)
    await expect(page.locator(".pv-ask h3")).toHaveText("Are these the same thing?");
    await expect(page.locator(".pv-ask .tok")).toHaveText("unsure");
    await expect(page.locator(".pv-why .pv-label")).toHaveText("why paired");
    await expect(page.locator(".pv-why .note")).toContainText("told four ways");
    await agree(page);
    // the two coders who wrote the same thing are one card here too
    await expect(page.locator(".pv-ops .pv-label")).toHaveCount(3);
    await samePlaces(page);
    // every opinion is one box; a coder's two entries are rows inside one, no row picked alone
    await expect(page.locator(".opinion.pv")).toHaveCount(3);
    await expect(page.locator("[data-entry]")).toHaveCount(0);
    const several = page.locator(".opinion.pv.many");
    await expect(several.locator(".pv-many")).toHaveText(/wrote 2 separate events/);
    await expect(several.locator(".pv-entry")).toHaveCount(2);
    await expect(page.locator("#pr-split")).toHaveText("split…");
    await expect(page.locator("#pr-split")).toBeEnabled();
    // a tap on the merged box takes both coders' entries, and a second tap lets go
    const twins = page.locator(".opinion.pv:not(.many)").filter({ hasNotText: "Fights" });
    const corner = { position: { x: 12, y: 8 } };
    await twins.click(corner);
    await expect(twins).toHaveClass(/ on/);
    await twins.click(corner);
    await expect(twins).not.toHaveClass(/ on/);
    // a tap on a row picks its whole box
    await several.locator(".pv-entry").first().click(corner);
    await expect(several).toHaveClass(/ on/);
    await several.locator(".pv-entry").first().click(corner);
    await expect(several).not.toHaveClass(/ on/);
    // with nothing picked, split lists the box's entries, the list only as tall as its rows
    await page.locator("#pr-split").click();
    const list = page.locator(".bl-sheet.pv-split.in");
    await expect(list.locator(".cf-t")).toHaveText(/^Take which entry out of opinion \d\?$/);
    await expect(list.locator(".pv-row")).toHaveCount(2);
    await expect(list.locator(".pv-row .rsub")).toContainText([/shift$/, /noted$/]);
    const tall = await list.evaluate((one) => one.getBoundingClientRect().height);
    expect(tall).toBeLessThan(page.viewportSize()!.height / 2);
    await list.locator(".pv-row", { hasText: "noted" }).click();
    await expect(page.locator("#title")).toContainText("pairings · 1 of 4");
    // the shift left behind now reads as the merged opinion and joins it
    await expect(page.locator(".opinion.pv.many")).toHaveCount(0);
    await expect(page.locator(".pv-ops .pv-label")).toHaveCount(2);

    await page.locator("#pr-join").click();
    // only pairings of events are offered to join an event, each with its mark; the one
    // split off from this passage first, the rest by year, a search over them with the
    // keyboard down until it is tapped (R-0974)
    const join = page.locator(".bl-sheet.in");
    await expect(join.locator(".cf-t")).toHaveText("Join with which pairing?");
    const find = join.locator('input[type="search"]');
    await expect(find).toBeVisible();
    await expect(find).not.toBeFocused();
    await expect(join.locator("[data-section] > .pv-label")).toHaveText([
      "From the same part of the conversation",
      "All, by year",
    ]);
    await expect(join.locator(".pv-row")).toHaveCount(2);
    const death = join.locator('.pv-row[data-join="43"]');
    await expect(join.locator('[data-section="all"] .pv-row')).toHaveAttribute("data-join", "43");
    await expect(death.locator(".tok.c-likely")).toHaveText("likely");
    await expect(death.locator(".pv-jy")).toHaveText("2003");
    await expect(death.locator(".pv-tag")).toHaveText("death");
    await expect(death.locator(".pv-jw")).toHaveText("Mara Reyes");
    await expect(join.locator('[data-section="near"] .pv-jy')).toHaveText("1994");
    // the sheet's slide up ends before the picture is taken
    await page.waitForTimeout(400);
    for (const scheme of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: scheme });
      await page.screenshot({ path: test.info().outputPath(`join-${scheme}.png`) });
    }
    await page.emulateMedia({ colorScheme: "light" });
    await find.fill("nothing like this");
    await expect(join.locator(".pv-row:visible")).toHaveCount(0);
    await expect(join.locator(".none")).toHaveText("nothing matches");
    await find.fill("2003");
    await expect(join.locator(".pv-row:visible")).toHaveCount(1);
    await expect(join.locator('[data-section="near"]')).toBeHidden();
    await expect(join.locator(".none")).toBeHidden();
    await death.click();

    await page.locator("#coding-back").click();
    await page.locator(".tb-vote").click();
    await expect(page.locator(".plnote", { hasText: "The vote is open." })).toBeVisible();
    // once the vote is open the pairings are shut: their address shows the agenda's row
    await leave(seen, () => page.goto(`/app/pairings/${CUT}/41`));
    await expect(page.locator(".plnote", { hasText: "The vote is open." })).toBeVisible();
    await expect(page.locator("#ballot-screen")).toBeHidden();
    await expect(page.locator("#pr-join")).toHaveCount(0);

    const writes = sent.map((one) => `${one.method} ${one.path}`);
    expect(writes).toEqual(["POST /items", "POST /items", "PATCH /items/41", `PATCH /cuts/${CUT}`]);
    expect(sent[1].body).toEqual({ cut_id: CUT, opinions: [{ coding_id: 3, item_id: 32 }] });
    expect((sent[2].body as { opinions: unknown[] }).opinions).toHaveLength(6);
    expect(seen).toEqual([]);
  });
});
