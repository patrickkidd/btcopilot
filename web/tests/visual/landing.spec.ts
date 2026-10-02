import { expect, test, type Page } from "@playwright/test";
import { flask, stateFor, username } from "./setup";

/** A tapped notification lands where it points from wherever the app is. The
 * tap arrives the way the worker hands it to an app already open: a message
 * naming the notification (tests/visual/push.spec.ts drives the worker). */
test.use({ storageState: stateFor("three40") });

/** A coach notification for a message that coded the fixture's picture. */
async function notified(page: Page): Promise<{ id: number; statement: number }> {
  const timeline = await (await page.request.get("/app/timeline")).json();
  const [where] = Object.values(timeline.coded_in) as { statement_id: number }[];
  const sent = flask("app", "notify", username("three40"), String(where.statement_id));
  return { id: Number(sent.trim().split("\n").at(-1)!.split(" ")[0]), statement: where.statement_id };
}

const tap = (page: Page, id: number) =>
  page.evaluate(
    (notification) =>
      navigator.serviceWorker.dispatchEvent(new MessageEvent("message", { data: { notification } })),
    id,
  );

const lit = (page: Page, statement: number) => page.locator(`.bub.traced[data-statement="${statement}"]`);

// R-0055
test("a tap on a coach notification with the sessions drawer open puts the drawer away and lights its message in the thread", async ({
  page,
}) => {
  await page.goto("/app/");
  const { id, statement } = await notified(page);
  // the door shows only for Patrick and a professional, which no fixture is
  await page.locator("#sessions-open").evaluate((b) => ((b as HTMLElement).hidden = false));
  await page.locator("#sessions-open").click();
  await expect(page.locator("#sessions-sheet")).toBeVisible();

  await tap(page, id);
  await expect(lit(page, statement)).toBeInViewport();
  await expect(page.locator("#sessions-sheet")).toBeHidden();
});

// R-0055
test("a tap on a coach notification from the account view's Coach page closes the account view and lights its message in the thread", async ({
  page,
}) => {
  await page.goto("/app/");
  const { id, statement } = await notified(page);
  await page.locator("#account").click();
  await page
    .locator('.sn-pane[data-page="root"] .sn-row')
    .filter({ has: page.locator(".sn-lbl", { hasText: /^Coach$/ }) })
    .click();
  await expect(page.locator('.sn-pane.in[data-page="coach"]')).toBeVisible();

  await tap(page, id);
  await expect(lit(page, statement)).toBeInViewport();
  await expect(page.locator(".sn-pane")).toHaveCount(0);
  await expect(page.locator("#title")).not.toHaveText("Coach");
});
