import { expect, test, type BrowserContext, type Page } from "./fixtures";
import { flask, stateFor, username } from "./setup";

/** A coach notification in a real browser, through the app's own service
 * worker. The push arrives the way a push service delivers it. No browser
 * under test can tap a notification, so the tap is the worker's own
 * notificationclick handler run on the notification it showed: the browser
 * refuses it the window focus a real tap brings, and nothing else differs. */
// The headless shell cannot show notifications; full Chromium can.
test.use({ storageState: stateFor("three40"), channel: "chromium" });

/** What the test reaches in the worker's own global scope. */
type Scope = {
  registration: ServiceWorkerRegistration;
  NotificationEvent: new (type: string, init: { notification: Notification }) => Event;
};

async function deliver(page: Page, context: BrowserContext, payload: object): Promise<void> {
  const cdp = await context.newCDPSession(page);
  const registered = new Promise<string>((resolve) =>
    cdp.on("ServiceWorker.workerRegistrationUpdated", ({ registrations }) => {
      const app = registrations.find((r) => r.scopeURL.endsWith("/app/"));
      if (app) resolve(app.registrationId);
    }),
  );
  await cdp.send("ServiceWorker.enable");
  await cdp.send("ServiceWorker.deliverPushMessage", {
    origin: new URL(page.url()).origin,
    registrationId: await registered,
    data: JSON.stringify(payload),
  });
  await cdp.detach();
}

// R-0055
test("a push shows one notification of each kind at a time, and a tap opens the thread at its message", async ({
  page,
  context,
  baseURL,
}) => {
  await context.grantPermissions(["notifications"], { origin: baseURL });
  await page.goto("/app/");
  await page.waitForFunction(() => navigator.serviceWorker.controller !== null);
  const [worker] = context.serviceWorkers();
  expect(new URL(worker.url()).pathname).toBe("/app/sw.js");

  const timeline = await (await page.request.get("/app/timeline")).json();
  const [where] = Object.values(timeline.coded_in) as { statement_id: number }[];
  const sent = flask("app", "notify", username("three40"), String(where.statement_id));
  const id = Number(sent.trim().split("\n").at(-1)!.split(" ")[0]);

  const shown = () =>
    worker.evaluate(async () =>
      (await (self as unknown as Scope).registration.getNotifications()).map((n) => [
        n.body,
        n.tag,
        n.data.id,
      ]),
    );
  const task = ["A coding task is waiting for you.", "task", id + 1];
  await deliver(page, context, { id: id - 1, kind: "coach", body: "An older message." });
  await deliver(page, context, { id: task[2], kind: task[1], body: task[0] });
  await deliver(page, context, { id, kind: "coach", body: "Tell me what you remember about it." });
  // a coding task never replaces an unread coach message, nor the other way
  await expect
    .poll(async () => (await shown()).sort())
    .toEqual([["Tell me what you remember about it.", "coach", id], task].sort());

  const opened = page.waitForResponse((r) => r.url().endsWith(`/app/notifications/${id}`));
  await worker.evaluate(async () => {
    const scope = self as unknown as Scope;
    const [notification] = await scope.registration.getNotifications({ tag: "coach" });
    self.dispatchEvent(new scope.NotificationEvent("notificationclick", { notification }));
  });
  expect((await opened).ok()).toBe(true);
  await expect(page.locator(`.bub.traced[data-statement="${where.statement_id}"]`)).toBeVisible();
  expect(await shown()).toEqual([task]);

  // the app was closed: the worker opens it with the notification in the address
  await page.goto(`/app/?notification=${id}`);
  await expect(page.locator(`.bub.traced[data-statement="${where.statement_id}"]`)).toBeVisible();
  expect(new URL(page.url()).search).toBe("");
});
