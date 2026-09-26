import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { hush, say } from "../src/speech";

/** WebKit on iOS: speak() is dropped, silently, until one is made during a tap. */
interface Reading {
  text: string;
  onend: (() => void) | null;
}

function iosVoice() {
  const heard: string[] = [];
  const cut: Reading[] = [];
  let unlocked = false;
  let now: Reading | null = null;
  const voice = {
    tapping: false,
    heard,
    /** Readings cancelled but whose end event has not arrived yet. */
    cut,
    cancel: () => {
      if (now) cut.push(now);
      now = null;
    },
    speak: (u: Reading) => {
      if (voice.tapping) unlocked = true;
      else if (!unlocked) return;
      heard.push(u.text);
      now = u;
    },
    finish: () => now?.onend?.(),
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
      onend: (() => void) | null = null;
      onerror: (() => void) | null = null;
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

// R-0099
it("a reply's play button reads it aloud from its own tap, with speak replies off", () => {
  voice.tapping = true;
  say("She stopped calling in 1992.", () => {});
  expect(voice.heard).toContain("She stopped calling in 1992.");
});

// R-0099
it("the play button goes back to play however the reading stops", () => {
  const on = new Set<string>();
  const play = (name: string, text: string) => {
    say(text, () => on.delete(name));
    on.add(name);
  };
  voice.tapping = true;
  play("first", "Your mother moved first.");
  voice.finish();
  expect(on.size).toBe(0);
  play("first", "Your mother moved first.");
  play("second", "Then your father did.");
  expect([...on]).toEqual(["second"]);
  hush();
  expect(on.size).toBe(0);
  play("first", "Your mother moved first.");
  say("A new reply arrived.");
  expect(on.size).toBe(0);
});

// R-0099
it("a stopped reading's late end does not stop the same reply read again", () => {
  let on = false;
  const play = () => {
    say("Your mother moved first.", () => (on = false));
    on = true;
  };
  voice.tapping = true;
  play();
  hush();
  play();
  for (const late of voice.cut) late.onend?.();
  expect(on).toBe(true);
});
