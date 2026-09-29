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
    await expect(page.locator("#view .ss-name")).toContainText(cluster.title);
    await expect(page).toHaveURL(new RegExp(`${at}$`));
    const chip = page.locator('.bub .did button.chip[data-kind="place"]');
    await expect(chip).toHaveText(`the cluster ${cluster.title}`);

    await page.locator('#path [data-step="0"]').click();
    await expect(page).toHaveURL(/\/app\/$/);
    await chip.click();
    await expect(page.locator("#view .ss-name")).toContainText(cluster.title);
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
});

test.describe("a notice pointing at an address", () => {
  test.use({ storageState: stateFor("notice") });

  test.beforeEach(() => {
    flask("app", "fixtures", "notice");
  });

  // R-0055
  test("a notice whose link is the Notices address opens the account view with its Notices lit", async ({
    page,
  }) => {
    shell(
      [
        "from btcopilot.extensions import db",
        "from btcopilot.models import Audience, Notice, Notification, NotificationChannel, NotificationKind, User",
        `user = User.query.filter_by(username="${username("notice")}").one()`,
        'notice = Notice(title="Your notices", body="All of them, in one place.", link="/app/account/notices", audience=Audience.People, user_ids=[user.id])',
        "db.session.add(notice)",
        "db.session.flush()",
        "db.session.add(Notification(user_id=user.id, kind=NotificationKind.Notice, notice_id=notice.id, channel=NotificationChannel.App))",
        "db.session.commit()",
        "",
      ].join("\n"),
    );
    await page.goto("/app/");
    const strip = page.locator(".strip");
    await expect(strip.locator(".strip-t")).toHaveText("Your notices");
    await strip.locator(".strip-m").click();
    await strip.getByRole("button", { name: "Open" }).click();

    await expect(pane(page, "root")).toBeVisible();
    await expect(pane(page, "root").locator('[data-group="notices"].traced')).toBeVisible();
    await expect(page).toHaveURL(/\/app\/account\/notices$/);
  });
});
