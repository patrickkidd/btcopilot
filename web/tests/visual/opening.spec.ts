import { expect, test, type Page, type Route } from "./fixtures";
import { shell, stateFor, username } from "./setup";
import { mockTurn, STREAM } from "./turn";

/** Opening a diagram is one step (FD-366): whatever was still coming for the
 * diagram before is cancelled, every screen starts empty and is drawn only
 * from the diagram opened last. These walk the races the audit named, against
 * stand-in diagrams that live only in the page: what is read by their id is
 * answered here. */

test.use({ storageState: stateFor("moves") });

const OWN = "FD-362 visual fixture";

interface Stand {
  id: number;
  name: string;
  /** The thread's newest page; the family's own record stands in for its record. */
  thread: Record<string, unknown>[];
  /** Held until the spec lets the reads by this id answer. */
  hold?: Promise<void>;
  access?: string;
}

const diagram = (one: Stand) => ({
  id: one.id,
  name: one.name,
  session_count: 0,
  last_activity: null,
  free: false,
  owned: one.access === undefined,
  access: one.access ?? "own",
  owner: "Someone Else",
});

/** A line of a stand-in thread, in the server's shape. */
const line = (id: number, text: string) => ({
  id,
  session_id: 1,
  role: "user",
  text,
  kind: "turn",
  cluster_id: null,
  case: null,
  digest: null,
  turn_id: null,
  tools: [],
  unfinished: false,
  failure: null,
  sitting: null,
});

/** The account lists the stand-ins beside the fixture's own diagram, and
 * everything read by a stand-in's id is answered from it. */
async function stand(page: Page, ...ones: Stand[]): Promise<void> {
  await page.route(/\/app\/account$/, async (route) => {
    const real = await (await route.fetch()).json();
    await route.fulfill({
      json: { ...real, diagrams: [...real.diagrams, ...ones.filter((o) => !o.access).map(diagram)] },
    });
  });
  for (const one of ones) {
    await page.route(new RegExp(`/app/diagrams/${one.id}/select$`), async (route) => {
      await one.hold;
      await route.fulfill({ json: diagram(one) });
    });
    await page.route(new RegExp(`/app/(statements|sessions|timeline)\\?diagram_id=${one.id}$`), async (route: Route) => {
      await one.hold;
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/statements")) return route.fulfill({ json: one.thread });
      if (path.endsWith("/sessions")) return route.fulfill({ json: [] });
      return route.fulfill({ response: await route.fetch({ url: route.request().url().split("?")[0] }) });
    });
  }
}

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(400);
};

const diagramsPage = (page: Page) => page.locator('.sn-pane[data-page="diagrams"]');

async function openDiagrams(page: Page): Promise<void> {
  await page.locator("#account").click();
  await page.locator('.sn-pane[data-page="root"] .sn-row.push', { hasText: "Diagrams" }).click();
  await expect(diagramsPage(page)).toBeVisible();
  await page.waitForTimeout(300);
}

/** Opens a diagram from its row in the diagrams list. */
async function switchTo(page: Page, name: string): Promise<void> {
  await openDiagrams(page);
  await diagramsPage(page).locator(".sn-row", { hasText: name }).click();
  await gone(page);
}

/** The stack slid away, its pages gone with it. */
async function gone(page: Page): Promise<void> {
  await expect(page.locator(".sn-stack")).toBeHidden();
  await expect(page.locator(".sn-pane")).toHaveCount(0);
}

/** The rows that carry the tick, by name. */
const ticked = (page: Page, within = ".sn-pane[data-page=\"diagrams\"]") =>
  page
    .locator(`${within} .sn-row:not([hidden])`)
    .evaluateAll((rows) =>
      rows
        .filter((r) => r.querySelector(".sn-tick")?.textContent?.trim())
        .map((r) => r.querySelector(".sn-t")?.textContent),
    );

const later = () => {
  let go!: () => void;
  const held = new Promise<void>((resolve) => (go = resolve));
  return { held, go };
};

// R-0369, R-0243
test("a turn still streaming when the diagram switches never draws into the new chat", async ({ page }) => {
  const stream = later();
  await mockTurn(page, { statement: "Words for the family before.", statement_id: 9701, hold: stream.held });
  await stand(page, { id: 987001, name: "Second family", thread: [line(987101, "Said in the second family.")] });
  await settle(page);
  await page.locator("#composer").fill("Tell me more.");
  const following = page.waitForRequest(STREAM);
  await page.locator("#send").click();
  await following;
  await switchTo(page, "Second family");
  await expect(page.locator("#title")).toHaveText("Second family");
  await expect(page.locator("#chat")).toContainText("Said in the second family.");
  stream.go();
  await page.waitForTimeout(800);
  await expect(page.locator("#chat")).not.toContainText("Words for the family before.");
  await expect(page.locator("#chat")).not.toContainText("Tell me more.");
  await expect(page.locator("#chat .typing")).toHaveCount(0);
});

/** The server's side of a turn left running on the fixture's own diagram:
 * its newest sitting names the turn while it runs, and its thread carries the
 * words and the reply, or the words marked unfinished, once it has ended. */
async function away(page: Page) {
  const turn = {
    running: null as string | null,
    ended: [] as Record<string, unknown>[],
  };
  let sittings: Record<string, unknown>[] = [];
  await page.route(/\/app\/sessions\?diagram_id=\d+$/, async (route) => {
    sittings = await (await route.fetch()).json();
    await route.fulfill({ json: [{ ...sittings[0], turn: turn.running }, ...sittings.slice(1)] });
  });
  // the mocked turn's own sitting is not on the server, so every sitting is
  // answered from the list
  await page.route(/\/app\/sessions\/\d+$/, async (route) => {
    const id = Number(new URL(route.request().url()).pathname.split("/").at(-1));
    const newest = id === sittings[0]?.id;
    await route.fulfill({ json: { id, statements: [], turn: newest ? turn.running : null } });
  });
  await page.route(/\/app\/statements\?diagram_id=\d+$/, async (route) => {
    const real = await (await route.fetch()).json();
    await route.fulfill({ json: [...real, ...turn.ended] });
  });
  return turn;
}

/** Sends on the fixture's own diagram and goes to the second family while the
 * coach is still answering. */
async function sendAndLeave(page: Page, turn: { running: string | null }): Promise<void> {
  await settle(page);
  await page.locator("#composer").fill("Tell me more.");
  const following = page.waitForRequest(STREAM);
  await page.locator("#send").click();
  await following;
  turn.running = "t1";
  await switchTo(page, "Second family");
  await expect(page.locator("#chat")).toContainText("Said in the second family.");
}

const SECOND: Stand = { id: 987001, name: "Second family", thread: [line(987101, "Said in the second family.")] };
const BROKE = /did not finish that turn/;

// R-0369
test("coming back while the coach is still answering follows the same turn to its reply", async ({ page }) => {
  const stream = later();
  await mockTurn(page, { statement: "Words for the family before.", statement_id: 9701, hold: stream.held });
  const turn = await away(page);
  await stand(page, SECOND);
  await sendAndLeave(page, turn);
  const following = page.waitForRequest(STREAM);
  await switchTo(page, OWN);
  await following;
  await expect(page.locator("#chat .typing")).toBeVisible();
  stream.go();
  await expect(page.locator("#chat")).toContainText("Words for the family before.");
  await expect(page.locator("#chat")).not.toContainText(BROKE);
  await expect(page.locator("#chat .typing")).toHaveCount(0);
  // the finished reply reads the record and sittings again, still in flight
  await page.unrouteAll({ behavior: "ignoreErrors" });
});

// R-0369
test("coming back after the coach finished shows the saved reply and what it did", async ({ page }) => {
  const stream = later();
  await mockTurn(page, { statement: "Words for the family before.", statement_id: 9701, hold: stream.held });
  const turn = await away(page);
  await stand(page, SECOND);
  await sendAndLeave(page, turn);
  stream.go();
  turn.running = null;
  turn.ended = [
    { ...line(9700, "Tell me more."), turn_id: "t1" },
    {
      ...line(9701, "Words for the family before."),
      role: "coach",
      turn_id: "t1",
      tools: [{ name: "edit_person", args: { name: "Nell" }, names: { it: "Nell" }, refusal: null }],
    },
  ];
  await switchTo(page, OWN);
  await expect(page.locator("#chat")).toContainText("Tell me more.");
  await expect(page.locator("#chat")).toContainText("Words for the family before.");
  await expect(page.locator("#chat")).toContainText("Nell");
  await expect(page.locator("#chat")).not.toContainText(BROKE);
  await expect(page.locator("#chat .typing")).toHaveCount(0);
});

// R-0182
test("coming back to a turn the server could not finish says so once", async ({ page }) => {
  const stream = later();
  await mockTurn(page, { statement: "Words for the family before.", statement_id: 9701, hold: stream.held });
  const turn = await away(page);
  await stand(page, SECOND);
  await sendAndLeave(page, turn);
  turn.running = null;
  turn.ended = [
    { ...line(9700, "Tell me more."), turn_id: "t1", unfinished: true, failure: "The coach did not finish that turn." },
  ];
  await switchTo(page, OWN);
  await expect(page.locator("#chat")).toContainText("Tell me more.");
  await expect(page.locator("#chat .warn", { hasText: BROKE })).toHaveCount(1);
});

// R-0243
test("a page of older chat still loading when the diagram switches is dropped", async ({ page }) => {
  const older = later();
  const full = Array.from({ length: 50 }, (_, i) => line(988100 + i, `Line ${i} of the long thread.`));
  await stand(page, { id: 987002, name: "Long family", thread: full });
  await page.route(/\/app\/statements\?before=\d+&diagram_id=987002$/, async (route) => {
    await older.held;
    await route.fulfill({ json: [line(988001, "An older line from the long family.")] });
  });
  await settle(page);
  await switchTo(page, "Long family");
  await expect(page.locator("#chat")).toContainText("Line 49 of the long thread.");
  const reading = page.waitForRequest(/statements\?before=/);
  await page.locator("#chat").evaluate((chat) => {
    chat.scrollTop = 0;
    chat.dispatchEvent(new Event("scroll"));
  });
  await reading;
  await switchTo(page, OWN);
  await expect(page.locator("#title")).toHaveText(OWN);
  older.go();
  await page.waitForTimeout(800);
  await expect(page.locator("#chat")).not.toContainText("An older line from the long family.");
  await expect(page.locator("#chat")).not.toContainText("of the long thread.");
});

// R-0243
test("two switches close together draw only the diagram opened last", async ({ page }) => {
  const slow = later();
  await stand(
    page,
    { id: 987003, name: "Slow family", thread: [line(987301, "Said in the slow family.")], hold: slow.held },
    { id: 987004, name: "Quick family", thread: [line(987401, "Said in the quick family.")] },
  );
  await settle(page);
  await openDiagrams(page);
  await diagramsPage(page).locator(".sn-row", { hasText: "Slow family" }).click();
  await gone(page);
  await switchTo(page, "Quick family");
  await expect(page.locator("#chat")).toContainText("Said in the quick family.");
  slow.go();
  await page.waitForTimeout(800);
  await expect(page.locator("#title")).toHaveText("Quick family");
  await expect(page.locator("#chat")).not.toContainText("Said in the slow family.");
  await openDiagrams(page);
  expect(await ticked(page)).toEqual(["Quick family"]);
});

test.describe("an admin's search results", () => {
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

  /** The person found by name, and their diagrams slid in as a page of their own. */
  const find = async (page: Page) => {
    await diagramsPage(page).locator('input[aria-label="Find a person"]').fill("Someone");
    await diagramsPage(page).locator(".sn-row", { hasText: "Someone Else" }).click();
    await expect(page.locator(".sn-theirs .sn-row", { hasText: "Their family" })).toBeVisible();
  };

  // R-0243, R-0630, R-0632
  test("carry the tick only on the diagram open, whichever diagram that is", async ({ page }) => {
    const theirs: Stand = { id: 987005, name: "Their family", thread: [line(987501, "Said in their family.")], access: "admin-view" };
    await stand(page, theirs);
    await page.route(/\/app\/users\?q=/, (route) =>
      route.fulfill({ json: [{ id: 987900, username: "new@fd362-fixture.invalid", name: "Someone Else" }] }),
    );
    await page.route(/\/app\/diagrams\?user_id=987900$/, (route) => route.fulfill({ json: [diagram(theirs)] }));
    await settle(page);
    await openDiagrams(page);
    expect(await ticked(page)).toEqual([OWN]);
    await find(page);
    expect(await ticked(page, ".sn-theirs")).toEqual([]);
    await page.locator(".sn-theirs .sn-row", { hasText: "Their family" }).click();
    await gone(page);
    await expect(page.locator("#viewing-who")).toHaveText("Viewing Someone Else's diagram, read-only");
    await expect(page.locator("#chat")).toContainText("Said in their family.");
    await openDiagrams(page);
    await find(page);
    expect(await ticked(page, ".sn-theirs")).toEqual(["Their family"]);
    // the open one returns to its chat
    await page.locator(".sn-theirs .sn-row", { hasText: "Their family" }).click();
    await gone(page);
    await expect(page.locator("#chat")).toContainText("Said in their family.");
    await openDiagrams(page);
    await diagramsPage(page).locator('input[aria-label="Find a person"]').fill("");
    await diagramsPage(page).locator(".sn-row", { hasText: OWN }).click();
    await gone(page);
    await expect(page.locator("#viewing")).toBeHidden();
    await expect(page.locator("#title")).toHaveText(OWN);
    await openDiagrams(page);
    expect(await ticked(page)).toEqual([OWN]);
  });
});
