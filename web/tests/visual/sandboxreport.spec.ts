import { expect, test } from "./fixtures";
import { flask, flaskRunning } from "./setup";

// The coach's offer to send the person's words, raised by hand: the admin
// command puts it on the person's next turn, and the feedback sheet comes up
// with the words once the reply is done. One real turn on whatever model the
// sandbox runs; SANDBOX_LIVE=1 says the walk may make it.

const WORDS = "This app should have a way to import GenoPro files";

test.skip(
  !process.env.SANDBOX_URL || !process.env.SANDBOX_LIVE,
  "needs a sandbox with its worker and model; set SANDBOX_URL and SANDBOX_LIVE=1",
);
test.describe.configure({ timeout: 240_000 });

// R-0056
test("the report offer command raises the feedback sheet with the words after the next reply", async ({
  page,
}, info) => {
  const email = `report-${info.project.name}-${Date.now()}@fd362-fixture.invalid`;
  const link = flask("admin", "users", "invite", email).match(/\/app\/invite\/\S+/)![0];
  await page.goto(link);
  await expect(page.locator("#composer")).toBeVisible();

  const offer = flaskRunning("admin", "report", "offer", email, WORDS, "--wait", "200");
  let printed = "";
  offer.stdout!.on("data", (chunk) => (printed += chunk));
  offer.stderr!.on("data", (chunk) => (printed += chunk));
  await expect.poll(() => printed, { timeout: 30_000 }).toContain("waiting");

  await page.locator("#composer").fill("My brother moved away last spring.");
  await page.locator("#send").click();
  const sheet = page.locator(".fs-sheet.rp");
  await expect(sheet.locator(".cf-t")).toHaveText("Send this as feedback?", { timeout: 200_000 });
  await expect(sheet.locator(".rp-v")).toHaveText(WORDS);
  expect(printed).toContain("offered feedback");
});
