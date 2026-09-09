import { el } from "./dom";

/** Putting the app on the home screen is the one thing the reader has to do
 * for themselves, and nobody is there to tell them how. The card says it once
 * per device, in the words of the phone they are holding, and never stands in
 * the way of the chat. */

const REMEMBER = "fd-home-screen-asked";
const AGAIN_AFTER_DAYS = 7;

/** Chrome offers the install itself, but only through an event that arrives
 * before the card is built, so it is caught as the module loads. */
let offer: BeforeInstallPromptEvent | null = null;
window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  offer = event as BeforeInstallPromptEvent;
});

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
}

function installed(): boolean {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as { standalone?: boolean }).standalone === true
  );
}

function asked(): number {
  try {
    return Number(window.localStorage.getItem(REMEMBER)) || 0;
  } catch {
    return 0;
  }
}

function remember(): void {
  try {
    window.localStorage.setItem(REMEMBER, String(Date.now()));
  } catch {
    // a phone that refuses to remember asks again next time, which is fine
  }
}

function isApple(): boolean {
  return (
    /iphone|ipad|ipod/i.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
  );
}

/** The share button rising out of the toolbar and the row it opens, drawn in
 * the card so the reader recognises what to tap before they tap it. */
function appleSteps(): HTMLElement {
  const box = el("div", "hs-show");
  box.innerHTML = `
    <div class="hs-phone">
      <div class="hs-sheet"><span class="hs-row">Add to Home Screen</span></div>
      <div class="hs-bar">
        <span class="hs-share" aria-hidden="true">
          <svg width="18" height="22" viewBox="0 0 18 22">
            <path d="M9 2v11M5 6l4-4 4 4" stroke="currentColor" stroke-width="1.8"
                  stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            <path d="M3.5 10H2v10h14V10h-1.5" stroke="currentColor" stroke-width="1.8"
                  stroke-linecap="round" stroke-linejoin="round" fill="none"/>
          </svg>
        </span>
      </div>
    </div>`;
  return box;
}

const SHARE_ICON =
  '<svg class="hs-inline" width="14" height="17" viewBox="0 0 18 22" aria-hidden="true">' +
  '<path d="M9 2v11M5 6l4-4 4 4" stroke="currentColor" stroke-width="1.8" ' +
  'stroke-linecap="round" stroke-linejoin="round" fill="none"/>' +
  '<path d="M3.5 10H2v10h14V10h-1.5" stroke="currentColor" stroke-width="1.8" ' +
  'stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>';

/** No phone lets a page add itself to the home screen, so the card has to
 * say every tap: where the button is, what it looks like, and what to tap
 * next. Nothing is assumed known. */
function appleWords(): string[] {
  const chrome = /CriOS/i.test(navigator.userAgent);
  const firefox = /FxiOS/i.test(navigator.userAgent);
  const find = chrome
    ? [
        "Look at the top of this screen, at the bar with the web address in it.",
        `At the right end of that bar is a small square with an arrow pointing up out of it ${SHARE_ICON}. Tap it.`,
      ]
    : firefox
      ? [
          "Look at the bottom right of this screen and tap the three short lines. A menu opens.",
          `In that menu tap <b>Share</b> — the row with a square and an arrow pointing up ${SHARE_ICON}.`,
        ]
      : [
          "Look at the very bottom of this screen, at the bar with the web address in it. If you do not see it, scroll up a little and it comes back.",
          `At the right end of that bar, tap the three dots in a circle <b>···</b>. A menu opens. If it has a row that says <b>Add to Home Screen</b>, tap that and go to step 4. If not, tap <b>Share</b> — the row with a small square and an arrow pointing up out of it ${SHARE_ICON}.`,
        ];
  return [
    ...find,
    "A list slides up from the bottom. Slide it upward with your finger until you see a row that says <b>Add to Home Screen</b>, with a plus sign in a square beside it. Tap that row.",
    "At the top right of the screen, tap <b>Add</b>.",
    "Close the browser. There is now a Family Diagram icon on your home screen. From now on, open it from there, like any app.",
  ];
}

function steps(words: string[]): HTMLElement {
  const list = el("ol", "hs-steps");
  for (const w of words) {
    const li = el("li");
    li.innerHTML = w;
    list.append(li);
  }
  return list;
}

function card(): HTMLElement {
  const scrim = el("div", "hs-scrim");
  const box = el("div", "hs-card");
  box.append(el("div", "hs-ttl", "Put Family Diagram on your home screen"));

  const buttons = el("div", "hs-acts");
  const later = el("button", "hs-later", "Not now");
  later.type = "button";

  const close = () => {
    remember();
    scrim.remove();
  };

  if (isApple()) {
    box.append(steps(appleWords()), appleSteps());
    const got = el("button", "hs-go", "Got it");
    got.type = "button";
    got.addEventListener("click", close);
    buttons.append(later, got);
  } else if (offer) {
    box.append(el("div", "hs-say", "It opens like an app, with no browser around it"));
    const add = el("button", "hs-go", "Add to home screen");
    add.type = "button";
    add.addEventListener("click", () => {
      void offer?.prompt();
      close();
    });
    buttons.append(later, add);
  } else {
    box.append(
      steps([
        "Look at the top right of this screen and tap the three dots stacked on top of each other. A menu opens.",
        "In that menu tap <b>Add to Home screen</b>.",
        "Tap <b>Add</b>.",
        "Close the browser. There is now a Family Diagram icon on your home screen. From now on, open it from there, like any app.",
      ]),
    );
    const got = el("button", "hs-go", "Got it");
    got.type = "button";
    got.addEventListener("click", close);
    buttons.append(later, got);
  }

  later.addEventListener("click", close);
  box.append(buttons);
  scrim.append(box);
  // A tap anywhere but the card closes it, and still reaches what it tapped.
  const away = (event: Event) => {
    if (!box.contains(event.target as Node)) {
      document.removeEventListener("pointerdown", away, true);
      close();
    }
  };
  setTimeout(() => document.addEventListener("pointerdown", away, true));
  return scrim;
}

export function offerHomeScreen(): void {
  if (installed()) return;
  const last = asked();
  if (last && Date.now() - last < AGAIN_AFTER_DAYS * 86_400_000) return;
  document.body.append(card());
}

/** The card on demand, whatever was remembered: the badge in the header is
 * for the reader who said "not now" and changed their mind. */
export function showHomeScreen(): void {
  if (document.querySelector(".hs-scrim")) return;
  document.body.append(card());
}

/** The badge lives while the app runs in a browser and goes once installed. */
export function homeScreenBadge(button: HTMLElement, open: () => void): void {
  button.hidden = installed();
  button.addEventListener("click", open);
}
