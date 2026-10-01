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
  const place = () =>
    page.evaluate(async () => {
      // the chat follows a resize of the box a frame later
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      return {
        page: window.scrollY,
        chat: document.getElementById("chat")!.scrollTop,
        bottom: document.getElementById("composer")!.getBoundingClientRect().bottom,
      };
    });
  // the box grows to its cap in six lines and the chat shrinks to make room;
  // ten lines past that nothing outside the box may move
  let before = await place();
  for (let n = 1; n <= 18; n++) {
    await page.keyboard.type(`line ${n}`);
    await page.keyboard.press("Shift+Enter");
    if (n === 8) before = await place();
  }
  const box = await composer.evaluate((n) => ({
    top: n.scrollTop,
    seen: n.clientHeight,
    all: n.scrollHeight,
  }));
  expect(box.all).toBeGreaterThan(box.seen);
  expect(box.top + box.seen).toBeGreaterThanOrEqual(box.all - 1);
  // the box scrolls, never the page or the chat, and the box stops growing at its cap
  const after = await place();
  expect(after).toEqual(before);
});
