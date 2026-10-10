import { expect, test, type Page } from "./fixtures";
import { at, flask, publicId, shell, stateFor, username } from "./setup";
import { mockTurn } from "./turn";

/** Every view and object in the app has an address (R-0055): the bar follows
 * the app, back steps back through it, the app opened at an address lands
 * there, and the coach, a notice or a link puts the app anywhere. Every address
 * is under the diagram the app is on, named by its public id. */

const title = (page: Page) => page.locator("#title");
const pane = (page: Page, name: string) => page.locator(`.sn-pane.in[data-page="${name}"]`);
const row = (page: Page, label: string) =>
  pane(page, "root")
    .locator(".sn-row")
    .filter({ has: page.locator(".sn-lbl", { hasText: new RegExp(`^${label}$`) }) });

/** The public id in the page's address. */
const keyIn = (page: Page): string => /\/app\/diagram\/([a-z0-9]+)/.exec(page.url())![1];

/** A message that coded the fixture's picture, and so is on its thread. */
async function said(page: Page): Promise<number> {
  const timeline = await (await page.request.get("/app/timeline")).json();
  const [where] = Object.values(timeline.coded_in) as { statement_id: number }[];
  return where.statement_id;
}

test.describe("on the fixture with three people over forty years", () => {
  test.use({ storageState: stateFor("three40") });

  // R-0055
  test("back after opening the account view's Coach page returns to the account view, then to the chat", async ({
    page,
  }) => {
    await page.goto("/app/");
    await page.locator("#account").click();
    await expect(pane(page, "root")).toBeVisible();
    await expect(page).toHaveURL(at("account"));
    await row(page, "Coach").click();
    await expect(pane(page, "coach")).toBeVisible();
    await expect(page).toHaveURL(at("account/coach"));

    await page.goBack();
    await expect(page).toHaveURL(at("account"));
    await expect(pane(page, "coach")).toHaveCount(0);
    await expect(pane(page, "root")).toBeVisible();

    await page.goBack();
    await expect(page).toHaveURL(at(""));
    await expect(page.locator(".sn-pane")).toHaveCount(0);
    await expect(page.locator("#chat")).toBeVisible();
  });

  // R-0055
  test("opened at the Coach page's address, the app lands on the Coach page", async ({ page }) => {
    await page.goto("/app/account/coach");
    await expect(pane(page, "coach")).toBeVisible();
    await expect(title(page)).toHaveText("Coach");
    await expect(page).toHaveURL(at("account/coach"));
  });

  // R-0055
  test("opened at a message's address, the app lights that message in the thread", async ({
    page,
  }) => {
    await page.goto("/app/");
    const statement = await said(page);
    await page.goto(`/app/chat/${statement}`);
    await expect(page.locator(`.bub.traced[data-statement="${statement}"]`)).toBeInViewport();
    await expect(page).toHaveURL(at(`chat/${statement}`));
  });

  // R-0055
  test("a coach reply that navigates to a cluster opens it on the picture and carries a chip that goes there again", async ({
    page,
  }) => {
    await page.goto("/app/");
    const { clusters } = await (await page.request.get("/app/timeline")).json();
    const cluster = clusters[0] as { id: string; title: string };
    const to = `/app/cluster/${cluster.id}`;
    await mockTurn(page, {
      statement: "There it is.",
      statement_id: 9701,
      did: [
        {
          type: "tool_call",
          name: "navigate",
          args: { address: to },
          names: { it: `the cluster ${cluster.title}` },
          refusal: null,
        },
        { type: "navigate", address: to },
      ],
    });
    await page.locator("#composer").fill("Where is it?");
    await page.locator("#send").click();

    await expect(page.locator('#path [data-step="0"]')).toBeVisible();
    await expect(page.locator("#path")).toContainText(cluster.title);
    await expect(page).toHaveURL(at(`cluster/${cluster.id}`));
    const chip = page.locator('.bub .did button.chip[data-kind="place"]');
    await expect(chip).toHaveText(`the cluster ${cluster.title}`);

    await page.locator('#path [data-step="0"]').click();
    await expect(page).toHaveURL(at(""));
    await chip.click();
    await expect(page.locator("#path")).toContainText(cluster.title);
    await expect(page).toHaveURL(at(`cluster/${cluster.id}`));
  });

  // R-0857, R-0858
  test("the address carries the diagram's public id, never its row number", async ({ page }) => {
    await page.goto("/app/");
    await expect(page).toHaveURL(at(""));
    const [own] = (await (await page.request.get("/app/diagrams")).json()) as {
      id: number;
      public_id: string;
      current: boolean;
    }[];
    expect(own.current).toBe(true);
    expect(keyIn(page)).toBe(own.public_id);
    expect(page.url()).not.toContain(`/diagram/${own.id}`);
    expect(own.public_id).toMatch(/^[a-z0-9]{10}$/);
  });

  // R-0859
  test("opened at /app/ or at a place without a diagram, the app lands on the person's own diagram and fills its id in", async ({
    page,
  }) => {
    const own = publicId("three40");
    await page.goto("/app/");
    await expect(page).toHaveURL(`/app/diagram/${own}/`);
    await page.goto("/app/account/coach");
    await expect(pane(page, "coach")).toBeVisible();
    await expect(page).toHaveURL(`/app/diagram/${own}/account/coach`);
    // the push link's address, whose query the landing reads and then drops
    await page.goto("/app/?notification=0");
    await expect(page).toHaveURL(`/app/diagram/${own}/`);
    await expect(page.locator("#chat")).toBeVisible();
  });

  // R-0860
  test("a link to a diagram the person cannot open shows one plain page", async ({ page }) => {
    const theirs = publicId("one");
    for (const path of [`/app/diagram/${theirs}/`, `/app/diagram/${theirs}/account`, "/app/diagram/nope2nope2/"]) {
      const opened = await page.goto(path);
      expect(opened!.status()).toBe(404);
      await expect(page.getByText("You do not have access to this diagram.")).toBeVisible();
      await expect(page.locator("#chat")).toHaveCount(0);
    }
    await page.getByRole("link", { name: "Open your own diagram" }).click();
    await expect(page.locator("#chat")).toBeVisible();
    await expect(page).toHaveURL(`/app/diagram/${publicId("three40")}/`);
  });
});

test.describe("the sessions drawer, as Patrick", () => {
  test.use({ storageState: stateFor("three40") });

  const roles = (to: string) =>
    shell(
      [
        "from btcopilot.extensions import db",
        "from btcopilot.models import User",
        `User.query.filter_by(username="${username("three40")}").one().roles = "${to}"`,
        "db.session.commit()",
        "",
      ].join("\n"),
    );

  test.beforeEach(() => roles("admin"));
  test.afterEach(() => roles("subscriber"));

  // R-0055
  test("opened at a session's address, the drawer comes up with that session's row lit", async ({
    page,
  }) => {
    await page.goto("/app/");
    const [session] = (await (await page.request.get("/app/sessions")).json()) as { id: number }[];
    await page.goto(`/app/sessions/${session.id}`);
    await expect(page.locator("#sessions-sheet")).toBeVisible();
    await expect(page.locator(`#sessions-sheet .row.traced[data-id="${session.id}"]`)).toBeVisible();
    await expect(page).toHaveURL(at(`sessions/${session.id}`));
  });

  // R-0055
  test("with the page's worker in control, a session's address and forward to the account view still show the app", async ({
    page,
  }) => {
    await page.goto("/app/");
    await page.waitForFunction(() => navigator.serviceWorker.controller !== null);
    const [session] = (await (await page.request.get("/app/sessions")).json()) as { id: number }[];
    const opened = await page.goto(`/app/sessions/${session.id}`);
    expect(opened!.fromServiceWorker()).toBe(true);
    await expect(page.locator("#sessions-sheet")).toBeVisible();

    // the account view reads its own address, and the browser kept that read
    const account = page.locator('.sn-pane[data-page="root"]');
    await page.goto("/app/account");
    await expect(account).toBeVisible();
    await page.waitForLoadState("networkidle");
    await page.goBack();
    await expect(page.locator("#sessions-sheet")).toBeVisible();
    await page.goForward();
    await expect(account).toBeVisible();
  });

  // R-0861
  test("an admin opening another person's diagram sees its id in the address, and their own again on the way back", async ({
    page,
  }) => {
    const mine = publicId("three40");
    const theirs = publicId("one");
    await page.goto("/app/");
    await expect(page).toHaveURL(`/app/diagram/${mine}/`);
    await page.locator("#account").click();
    await row(page, "Diagrams").click();
    const diagrams = pane(page, "diagrams");
    await diagrams.getByLabel("Find a person").fill(username("one"));
    await diagrams.locator(".sn-find .sn-row", { hasText: username("one") }).first().click();
    await page.locator(".sn-theirs .sn-row").first().click();
    await expect(page.locator("#viewing")).toBeVisible();
    await expect(page).toHaveURL(`/app/diagram/${theirs}/`);

    // back through the history reopens the admin's own diagram
    await page.goBack();
    await expect(page).toHaveURL(new RegExp(`/app/diagram/${mine}/`));
    await expect(page.locator("#viewing")).toBeHidden();
    await page.goForward();
    await expect(page).toHaveURL(`/app/diagram/${theirs}/`);
    await expect(page.locator("#viewing")).toBeVisible();

    await page.locator("#viewing-back").click();
    await expect(page.locator("#viewing")).toBeHidden();
    await expect(page).toHaveURL(`/app/diagram/${mine}/`);
  });
});

test.describe("the account view's Notices", () => {
  test.use({ storageState: stateFor("notice") });

  test.beforeEach(() => {
    flask("app", "fixtures", "notice");
  });

  // R-0055
  test("open as their own page from the Notices row on the account view and from their address", async ({
    page,
  }) => {
    await page.goto("/app/");
    await page.locator("#account").click();
    await expect(pane(page, "root").locator(".sn-row", { hasText: "Coach messages can now come weekly" })).toHaveCount(0);
    await row(page, "Notices").click();
    await expect(pane(page, "notices").locator(".sn-row")).toHaveCount(2);
    await expect(title(page)).toHaveText("Notices");
    await expect(page).toHaveURL(at("account/notices"));

    await page.goto("/app/account/notices");
    await expect(pane(page, "notices").locator(".sn-row")).toHaveCount(2);
    await expect(title(page)).toHaveText("Notices");
    await page.locator("#settings-back").click();
    await expect(pane(page, "root")).toBeVisible();
    await expect(page).toHaveURL(at("account"));
  });
});
