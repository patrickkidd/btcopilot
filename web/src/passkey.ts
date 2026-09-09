import * as api from "./api";
import { el } from "./dom";
import type { Passkey } from "./types";

/** Signing in by emailed code works everywhere and is slow every time. A key
 * held by the phone — Face ID, a fingerprint — replaces it after the first
 * sign-in. The card asks once per device and never stands in the way. */

const REMEMBER = "fd-passkey-asked";
const AGAIN_AFTER_DAYS = 30;

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

/** What to call it on the phone in the reader's hand. */
export function deviceWords(): string {
  return /iphone|ipad|ipod|macintosh|android/i.test(navigator.userAgent)
    ? "Face ID or fingerprint"
    : "device sign-in";
}

export async function available(): Promise<boolean> {
  if (!window.PublicKeyCredential) return false;
  try {
    return await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
  } catch {
    return false;
  }
}

function fromB64(value: string): Uint8Array {
  const raw = atob(value.replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

function toB64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let out = "";
  for (const byte of bytes) out += String.fromCharCode(byte);
  return btoa(out).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** Make a key on this device and hand the public half to the server. */
export async function addPasskey(): Promise<Passkey> {
  const options = await api.passkeyRegisterOptions();
  const credential = (await navigator.credentials.create({
    publicKey: {
      ...options,
      challenge: fromB64(options.challenge),
      user: { ...options.user, id: fromB64(options.user.id) },
      excludeCredentials: (options.excludeCredentials ?? []).map((c) => ({
        ...c,
        id: fromB64(c.id),
      })),
    } as unknown as PublicKeyCredentialCreationOptions,
  })) as PublicKeyCredential | null;
  if (!credential) throw new Error("no credential");
  const response = credential.response as AuthenticatorAttestationResponse;
  return api.addPasskey({
    id: credential.id,
    rawId: toB64(credential.rawId),
    type: credential.type,
    response: {
      clientDataJSON: toB64(response.clientDataJSON),
      attestationObject: toB64(response.attestationObject),
      transports: response.getTransports ? response.getTransports() : [],
    },
  });
}

function card(done: () => void): HTMLElement {
  const scrim = el("div", "hs-scrim");
  const box = el("div", "hs-card");
  box.append(
    el("div", "hs-ttl", `Sign in faster next time`),
    el(
      "div",
      "hs-say",
      `Use ${deviceWords()} on this phone instead of waiting for a code`,
    ),
  );

  const buttons = el("div", "hs-acts");
  const later = el("button", "hs-later", "Not now");
  later.type = "button";
  const set = el("button", "hs-go", "Set up");
  set.type = "button";

  const close = () => {
    remember();
    scrim.remove();
    done();
  };

  later.addEventListener("click", close);
  set.addEventListener("click", () => {
    set.disabled = true;
    void addPasskey()
      .then(close)
      .catch(() => {
        set.disabled = false;
        box.append(
          el("div", "hs-say", "That did not work. You can set it up later in your account."),
        );
      });
  });
  buttons.append(later, set);
  box.append(buttons);
  scrim.append(box);
  scrim.addEventListener("click", (event) => {
    if (event.target === scrim) close();
  });
  return scrim;
}

/** Ask once, on a device that can do it and has no key yet. `next` is what the
 * page would have offered instead, so two cards never stack. */
export async function offerPasskey(next: () => void): Promise<void> {
  const last = asked();
  if (last && Date.now() - last < AGAIN_AFTER_DAYS * 86_400_000) return next();
  if (!(await available())) return next();
  let existing: Passkey[];
  try {
    existing = await api.passkeys();
  } catch {
    return next();
  }
  if (existing.length) return next();
  document.body.append(card(next));
}
