import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { hush, say } from "../src/speech";

/** WebKit on iOS: speak() is dropped, silently, until one is made during a tap. */
function iosVoice() {
  const heard: string[] = [];
  let unlocked = false;
  const voice = {
    tapping: false,
    heard,
    cancel: () => {},
    speak: (u: { text: string }) => {
      if (voice.tapping) unlocked = true;
      else if (!unlocked) return;
      heard.push(u.text);
    },
  };
  return voice;
}

let voice: ReturnType<typeof iosVoice>;

beforeEach(() => {
  voice = iosVoice();
  vi.stubGlobal("window", { speechSynthesis: voice });
  vi.stubGlobal(
    "SpeechSynthesisUtterance",
    class {
      constructor(public text: string) {}
    },
  );
});

afterEach(() => vi.unstubAllGlobals());

it("a reply that arrives after the send tap is spoken on iOS", () => {
  voice.tapping = true;
  hush();
  voice.tapping = false;
  say("Your mother's move to Anchorage came first.");
  expect(voice.heard).toContain("Your mother's move to Anchorage came first.");
});
