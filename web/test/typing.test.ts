import { expect, it, vi } from "vitest";

vi.stubGlobal("window", {
  BOOTSTRAP: { user: { username: "c", admin: false, pro: false, coder: true } },
  matchMedia: () => ({ matches: true }),
});

const { Coding } = await import("../src/coding");
const { Typing } = await import("../src/typing");
const { onReturn } = await import("../src/keyboard");

const SAID =
  "Add Robert Lewis Kidd as the father of Louann. " +
  "Add that he moved to Bartlesville in 1930 approximate.";
const LAST = "in 1930 approximate.";

/** A message box with an iPhone keyboard on it. While dictation still hears
 * the last phrase, the phrase is in the box but the keyboard's own. Taking
 * the focus away, or emptying the box under it, ends dictation, and the
 * keyboard hands the phrase over a moment later: in place when its words are
 * still there, at the caret of an emptied box when they are not. */
class Box extends EventTarget {
  textContent = "";
  dataset: Record<string, string> = {};
  private held: string | null = null;

  set innerHTML(words: string) {
    this.textContent = words;
    this.release();
  }

  dictate(settled: string, phrase: string): void {
    this.textContent = settled + phrase;
    this.held = phrase;
    this.dispatchEvent(new Event("compositionstart"));
  }

  blur(): void {
    this.release();
  }

  private release(): void {
    const phrase = this.held;
    if (phrase === null) return;
    setTimeout(() => {
      if (this.held === null) return;
      if (!this.textContent.endsWith(phrase)) this.textContent += phrase;
      this.held = null;
      this.dispatchEvent(new Event("compositionend"));
    });
  }
}

/** The coding screen's send, on a box and a scribe that records what it
 * was sent. */
function coding(box: Box) {
  const sent: string[] = [];
  const screen = Object.assign(Object.create(Coding.prototype), {
    composer: box,
    typing: new Typing(box as unknown as HTMLElement),
    thread: { coding_id: 9, turns: [{ id: 3, client: true }] },
    picked: 3,
    sending: false,
    list: { querySelector: () => null, querySelectorAll: () => [] },
    after() {},
    picture: { openCluster: () => null },
    caption: { innerHTML: "", querySelector: () => null },
    async scribe(_turn: number, said: string) {
      sent.push(said);
      // the answer lands and the screen is drawn again
      screen.paint();
    },
  });
  vi.stubGlobal("document", {
    createElement: () => ({ className: "", innerHTML: "", dataset: {} }),
  });
  return { screen, sent };
}

// R-0883
it("sends dictation's last phrase with the rest and leaves the box empty", async () => {
  const box = new Box();
  const { screen, sent } = coding(box);
  box.dictate(SAID.slice(0, -LAST.length), LAST);
  await screen.say();
  expect(sent).toEqual([SAID]);
  await new Promise((done) => setTimeout(done));
  expect(box.textContent).toBe("");
});

// R-0883
it("sends once when the send button is tapped twice while the keyboard holds words", async () => {
  const box = new Box();
  const { screen, sent } = coding(box);
  box.dictate(SAID.slice(0, -LAST.length), LAST);
  await Promise.all([screen.say(), screen.say()]);
  expect(sent).toEqual([SAID]);
  expect(box.textContent).toBe("");
});

// R-0610, R-0883
it("sends once when Return and the send button both fire", async () => {
  const box = new Box();
  const { screen, sent } = coding(box);
  const says: Promise<void>[] = [];
  onReturn(box as unknown as HTMLElement, () => says.push(screen.say()));
  box.textContent = SAID;
  const enter = Object.assign(new Event("keydown", { cancelable: true }), {
    key: "Enter",
    shiftKey: false,
    altKey: false,
    isComposing: false,
  });
  box.dispatchEvent(enter);
  says.push(screen.say());
  await Promise.all(says);
  expect(enter.defaultPrevented).toBe(true);
  expect(sent).toEqual([SAID]);
  expect(box.textContent).toBe("");
});
