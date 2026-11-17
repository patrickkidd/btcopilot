import { expect, test, type Page, type Route } from "./fixtures";
import { shell, stateFor, username } from "./setup";

/** The vote by pairing and Patrick's look over the pairings, on the app's own
 * page with the review answered from fixtures: one pairing per screen, the
 * opinions without names, a pick and a drop that both un-tap, and before the
 * vote opens, joins and splits on the same card; every card of a pairing shows
 * the same places, accented in every card where the opinions disagree, and
 * identical cards are one (R-0963, R-0965, R-0966, R-0967). */

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
        item: event({ dateTime: "1900-01-01", relationship: "conflict", title: "Fights with stepfather" }),
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

const caption = (page: Page) => page.locator("#ballot-caption");

/** Every entry on screen shows the same places, and each place is accented in
 * every card or in none (R-0967). */
async function samePlaces(page: Page): Promise<void> {
  const places = await page.evaluate(() =>
    [...document.querySelectorAll("#ballot-screen .pv-entry")].map((entry) =>
      [...entry.querySelectorAll(".pv-l1 > *, .pv-l2 > :not(.pv-arrow), .pv-l3 > *")].map((one) =>
        one.classList.contains("pv-diff"),
      ),
    ),
  );
  expect(places.length).toBeGreaterThan(1);
  for (const one of places) expect(one).toEqual(places[0]);
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
    // the person comes first, as the ballot walks people before events
    await expect(page.locator(".pv-tag").first()).toHaveText("person");
    // the name all agree on is plain; the gender they split on is accented in every card
    await expect(page.locator(".pv-label")).toHaveCount(2);
    await expect(page.locator(".pv-l3 .chip.pv-diff")).toHaveText(["male", "female"]);
    await expect(page.locator(".pv-l2 .pv-diff")).toHaveCount(0);
    await samePlaces(page);
    await page.locator("#ballot-view circle").nth(1).click();
    await expect(page.locator("#title")).toContainText("ballot · 2 of 3");

    // the passage is cut to two lines until tapped
    await expect(page.locator("#bl-quote.clip")).toBeVisible();
    // two coders said the same thing: four versions read as three opinions
    await expect(page.locator(".pv-label")).toHaveText(["opinion 1", "opinion 2", "opinion 3"]);
    await expect(page.locator(".pv-card")).not.toContainText(/coder 1|ballot1|coders? (said|wrote)/);
    await expect(page.locator(".pv-card")).toContainText("no sure date");
    await expect(page.locator(".pv-diff", { hasText: "Lou Reyes" })).toBeVisible();
    // what a coder did not record keeps its place as an empty chip, accented with the place
    await expect(page.locator(".chip.pv-diff", { hasText: "no one recorded" })).toHaveCount(3);
    await expect(page.locator(".chip.pv-diff", { hasText: "no anxiety recorded" })).toHaveCount(2);
    await expect(page.locator(".chip.pv-diff", { hasText: "no relationship recorded" })).toHaveCount(3);
    await samePlaces(page);
    await holds(page);

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

  // R-0961, R-0963, R-0967
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
    // a reload comes back to the look on the same cut
    await expect(page).toHaveURL(new RegExp(`/app/pairings/${CUT}$`));
    await page.reload();
    await expect(page.locator("#title")).toContainText("pairings · 1 of 3");
    await expect(page.locator(".pv-card .progress")).toHaveText("unsure");
    await expect(page.locator(".pv-card .note").first()).toContainText("told four ways");
    // the two coders who wrote the same thing are one card here too
    await expect(page.locator(".pv-label")).toHaveCount(3);
    await samePlaces(page);
    await expect(page.locator("#pr-split")).toBeDisabled();
    // a tap on the merged card's entry takes both coders' entries, and a second tap lets go
    const twins = page.locator('[data-entry~="1:11"][data-entry~="2:21"]');
    await twins.click();
    await expect(twins).toHaveClass(/ on/);
    await twins.click();
    await expect(twins).not.toHaveClass(/ on/);
    const entry = page.locator('[data-entry="4:41"]');
    await entry.click();
    await expect(entry).toHaveClass(/ on/);
    await expect(page.locator("#pr-split")).toBeEnabled();
    await page.locator("#pr-split").click();
    await expect(page.locator("#title")).toContainText("pairings · 1 of 4");
    await expect(page.locator(".pv-label")).toHaveCount(2);

    await page.locator("#pr-join").click();
    // only pairings of events are offered to join an event
    await expect(page.locator(".bl-sheet .pv-row")).toHaveCount(2);
    await page.locator('.bl-sheet .pv-row[data-join="43"]').click();

    await page.locator("#coding-back").click();
    await page.locator(".tb-vote").click();
    await expect(page.locator(".plnote", { hasText: "The vote is open." })).toBeVisible();

    const writes = sent.map((one) => `${one.method} ${one.path}`);
    expect(writes).toEqual(["POST /items", "POST /items", "PATCH /items/41", `PATCH /cuts/${CUT}`]);
    expect(sent[1].body).toEqual({ cut_id: CUT, opinions: [{ coding_id: 4, item_id: 41 }] });
    expect((sent[2].body as { opinions: unknown[] }).opinions).toHaveLength(6);
    expect(seen).toEqual([]);
  });
});
