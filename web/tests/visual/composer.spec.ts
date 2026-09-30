import { expect, test } from "@playwright/test";
import { stateFor } from "./setup";

test.use({ storageState: stateFor("moves") });

// R-0368
test("Shift-Return past the box's height keeps the new line in view", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("fd-home-screen-asked", String(Date.now())));
  await page.goto("/app/");
  await expect(page.locator(".bub").first()).toBeVisible();
  const composer = page.locator("#composer");
  await composer.click();
  for (let n = 1; n <= 10; n++) {
    await page.keyboard.type(`line ${n}`);
    await page.keyboard.press("Shift+Enter");
  }
  const box = await composer.evaluate((n) => ({
    top: n.scrollTop,
    seen: n.clientHeight,
    all: n.scrollHeight,
  }));
  expect(box.all).toBeGreaterThan(box.seen);
  expect(box.top + box.seen).toBeGreaterThanOrEqual(box.all - 1);
});
