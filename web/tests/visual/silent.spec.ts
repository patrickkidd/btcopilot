import { expect, test } from "./fixtures";

// R-0099
test("no browser a test starts can read anything aloud", async ({ page }) => {
  await page.goto("/");
  const voice = await page.evaluate(() => window.speechSynthesis.speak.toString());
  expect(voice).not.toContain("[native code]");
  const ended = await page.evaluate(
    () =>
      new Promise<boolean>((done) => {
        const reading = new SpeechSynthesisUtterance("a reply");
        reading.onend = () => done(!window.speechSynthesis.speaking);
        window.speechSynthesis.speak(reading);
      }),
  );
  expect(ended).toBe(true);
});
