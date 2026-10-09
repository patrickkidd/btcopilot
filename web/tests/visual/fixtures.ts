import { test as base } from "@playwright/test";

export * from "@playwright/test";

/** Every browser a test starts is silent: the coach's replies and the
 * play-by-play are never read aloud on the machine running the tests. Only
 * Chromium has a mute switch, so the page's voice is replaced in every engine
 * by one that finishes each reading at once without a sound. */
export const test = base.extend<{ silent: void }>({
  silent: [
    async ({ context }, use) => {
      await context.addInitScript(() => {
        window.speechSynthesis.speak = (reading: SpeechSynthesisUtterance) =>
          void setTimeout(() => reading.dispatchEvent(new Event("end")));
      });
      await use();
    },
    { auto: true },
  ],
});
