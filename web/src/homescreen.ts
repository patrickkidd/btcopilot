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
    box.append(
      el("div", "hs-say", "Tap the Share button, then Add to Home Screen"),
      appleSteps(),
    );
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
      el(
        "div",
        "hs-say",
        "Use your browser's menu and choose Add to Home screen",
      ),
    );
    const got = el("button", "hs-go", "Got it");
    got.type = "button";
    got.addEventListener("click", close);
    buttons.append(later, got);
  }

  later.addEventListener("click", close);
  box.append(buttons);
  scrim.append(box);
  scrim.addEventListener("click", (event) => {
    if (event.target === scrim) close();
  });
  return scrim;
}

export function offerHomeScreen(): void {
  if (installed()) return;
  const last = asked();
  if (last && Date.now() - last < AGAIN_AFTER_DAYS * 86_400_000) return;
  document.body.append(card());
}
