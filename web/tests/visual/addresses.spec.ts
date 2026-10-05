import { expect, test, type Page } from "@playwright/test";
import { flask, shell, stateFor, username } from "./setup";
import { mockTurn } from "./turn";

/** Every view and object in the app has an address (R-0055): the bar follows
 * the app, back steps back through it, the app opened at an address lands
 * there, and the coach, a notice or a link puts the app anywhere. */

const title = (page: Page) => page.locator("#title");
const pane = (page: Page, name: string) => page.locator(`.sn-pane.in[data-page="${name}"]`);
const row = (page: Page, label: string) =>
  pane(page, "root")
    .locator(".sn-row")
    .filter({ has: page.locator(".sn-lbl", { hasText: new RegExp(`^${label}$`) }) });

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
    await expect(page).toHaveURL(/\/app\/account$/);
    await row(page, "Coach").click();
    await expect(pane(page, "coach")).toBeVisible();
    await expect(page).toHaveURL(/\/app\/account\/coach$/);

    await page.goBack();
    await expect(page).toHaveURL(/\/app\/account$/);
    await expect(pane(page, "coach")).toHaveCount(0);
    await expect(pane(page, "root")).toBeVisible();

    await page.goBack();
    await expect(page).toHaveURL(/\/app\/$/);
    await expect(page.locator(".sn-pane")).toHaveCount(0);
    await expect(page.locator("#chat")).toBeVisible();
  });

  // R-0055
  test("opened at the Coach page's address, the app lands on the Coach page", async ({ page }) => {
    await page.goto("/app/account/coach");
    await expect(pane(page, "coach")).toBeVisible();
    await expect(title(page)).toHaveText("Coach");
    await expect(page).toHaveURL(/\/app\/account\/coach$/);
  });

  // R-0055
  test("opened at a message's address, the app lights that message in the thread", async ({
    page,
  }) => {
    await page.goto("/app/");
    const statement = await said(page);
    await page.goto(`/app/chat/${statement}`);
    await expect(page.locator(`.bub.traced[data-statement="${statement}"]`)).toBeInViewport();
    await expect(page).toHaveURL(new RegExp(`/app/chat/${statement}$`));
  });

  // R-0055
  test("a coach reply that navigates to a cluster opens it on the picture and carries a chip that goes there again", async ({
    page,
  }) => {
    await page.goto("/app/");
    const { clusters } = await (await page.request.get("/app/timeline")).json();
    const cluster = clusters[0] as { id: string; title: string };
    const at = `/app/cluster/${cluster.id}`;
    await mockTurn(page, {
      statement: "There it is.",
      statement_id: 9701,
      did: [
        {
          type: "tool_call",
          name: "navigate",
          args: { address: at },
          names: { it: `the cluster ${cluster.title}` },
          refusal: null,
        },
        { type: "navigate", address: at },
      ],
    });
    await page.locator("#composer").fill("Where is it?");
    await page.locator("#send").click();

    await expect(page.locator('#path [data-step="0"]')).toBeVisible();
    await expect(page.locator("#path")).toContainText(cluster.title);
    await expect(page).toHaveURL(new RegExp(`${at}$`));
    const chip = page.locator('.bub .did button.chip[data-kind="place"]');
    await expect(chip).toHaveText(`the cluster ${cluster.title}`);

    await page.locator('#path [data-step="0"]').click();
    await expect(page).toHaveURL(/\/app\/$/);
    await chip.click();
    await expect(page.locator("#path")).toContainText(cluster.title);
    await expect(page).toHaveURL(new RegExp(`${at}$`));
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
    await expect(page).toHaveURL(new RegExp(`/app/sessions/${session.id}$`));
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
    await expect(page).toHaveURL(/\/app\/account\/notices$/);

    await page.goto("/app/account/notices");
    await expect(pane(page, "notices").locator(".sn-row")).toHaveCount(2);
    await expect(title(page)).toHaveText("Notices");
    await page.locator("#settings-back").click();
    await expect(pane(page, "root")).toBeVisible();
    await expect(page).toHaveURL(/\/app\/account$/);
  });
});
