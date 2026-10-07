import { call, openNotification } from "./api";
import { el } from "./dom";
import { Feature, tap } from "./track";
import type { Delivery } from "./types";

/** The server's public key arrives base64url; the browser takes raw bytes. */
function bytes(key: string): Uint8Array<ArrayBuffer> {
  const b64 = key.replace(/-/g, "+").replace(/_/g, "/");
  const padded = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
  return new Uint8Array([...atob(padded)].map((c) => c.charCodeAt(0)));
}

/** The worker as registered and running; a registration that fails rejects
 * here rather than leaving `navigator.serviceWorker.ready` waiting forever. */
let running: Promise<ServiceWorkerRegistration> | null = null;

export function register(url: string): void {
  running = navigator.serviceWorker
    .register(url, { scope: "/app/" })
    .then(() => navigator.serviceWorker.ready);
}

function worker(): Promise<ServiceWorkerRegistration> {
  return running ?? Promise.reject(new Error("the service worker was never registered"));
}

/** Run inside a tap: a browser asks for permission only on one, and iOS only
 * when the request is the tap's first wait. iOS offers web push only to the
 * app added to the home screen. Says whether this browser can now be reached
 * by push. With permission already given it asks nothing and only subscribes
 * again. */
export async function subscribe(): Promise<boolean> {
  if (!supported()) return false;
  if ((await Notification.requestPermission()) !== "granted") return false;
  const [{ key }, registration] = await Promise.all([
    call<{ key: string }>("GET", "/push-subscriptions"),
    worker(),
  ]);
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: bytes(key),
  });
  await call("POST", "/push-subscriptions", subscription.toJSON());
  return true;
}

/** Whether this device can be reached by notifications, in the words the
 * account view says it in (R-0802). */
export enum Reach {
  On = "on",
  Off = "off",
  Blocked = "blocked",
  Unavailable = "unavailable",
  /** The worker that receives them could not start on this device. */
  Failed = "failed",
}

/** What the app does about notifications as it opens on this device. */
export enum Plan {
  /** Installed and never asked: the card that asks. */
  Card = "card",
  /** Allowed before but no subscription saved: subscribe again, asking nothing. */
  Quiet = "quiet",
  Nothing = "nothing",
}

export interface Device {
  supported: boolean;
  installed: boolean;
  permission: NotificationPermission;
  /** This browser's subscription is one the server holds. */
  saved: boolean;
  /** "Not now" was tapped on the card on this device. */
  declined: boolean;
}

export function reach(d: Device): Reach {
  if (!d.supported) return Reach.Unavailable;
  if (d.permission === "denied") return Reach.Blocked;
  return d.permission === "granted" && d.saved ? Reach.On : Reach.Off;
}

export function plan(d: Device): Plan {
  if (!d.supported) return Plan.Nothing;
  if (d.permission === "granted") return d.saved ? Plan.Nothing : Plan.Quiet;
  if (d.permission === "default" && d.installed && !d.declined) return Plan.Card;
  return Plan.Nothing;
}

const DECLINED = "fd-notifications-declined";

function supported(): boolean {
  return "PushManager" in window && "Notification" in window && "serviceWorker" in navigator;
}

export function installed(): boolean {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as { standalone?: boolean }).standalone === true
  );
}

function declined(): boolean {
  try {
    return window.localStorage.getItem(DECLINED) !== null;
  } catch {
    return false;
  }
}

function decline(): void {
  try {
    window.localStorage.setItem(DECLINED, String(Date.now()));
  } catch {
    // a device that refuses to remember asks again next time it opens
  }
}

async function saved(): Promise<boolean> {
  const [{ subscriptions }, registration] = await Promise.all([
    call<{ subscriptions: { endpoint: string }[] }>("GET", "/push-subscriptions"),
    worker(),
  ]);
  const mine = await registration.pushManager.getSubscription();
  return !!mine && subscriptions.some((s) => s.endpoint === mine.endpoint);
}

export async function device(): Promise<Device> {
  const can = supported();
  const permission = can ? Notification.permission : "denied";
  return {
    supported: can,
    installed: installed(),
    permission,
    saved: permission === "granted" ? await saved() : false,
    declined: declined(),
  };
}

/** The card that asks, once per device, in the home-screen card's own look. */
function card(): HTMLElement {
  const scrim = el("div", "hs-scrim");
  const box = el("div", "hs-card");
  box.append(
    el("div", "hs-ttl", "Turn on notifications"),
    el("div", "hs-say", "So the app can tell you when something is waiting for you, like a message from the coach."),
  );
  const later = el("button", "hs-later", "Not now");
  later.type = "button";
  later.addEventListener("click", () => {
    decline();
    scrim.remove();
  });
  const on = el("button", "hs-go", "Turn on notifications");
  on.type = "button";
  on.addEventListener("click", () => {
    tap(Feature.NotificationsOn);
    scrim.remove();
    void subscribe();
  });
  const acts = el("div", "hs-acts");
  acts.append(later, on);
  box.append(acts);
  scrim.append(box);
  return scrim;
}

/** As the app opens: subscribe again where permission was given and the
 * subscription was lost, or ask with the card where the app is installed and
 * nobody has been asked (R-0802). */
export async function offerNotifications(): Promise<void> {
  const next = plan(await device());
  if (next === Plan.Quiet) await subscribe();
  if (next === Plan.Card) document.body.append(card());
}

/** A tap on a notification, or on the link in its email, is counted opened
 * by the server and then lands where it points. The worker names the
 * notification in the address when it opens the app, and in a message when
 * the app is already open; both land through the one function. */
export function landing(land: (where: Delivery) => Promise<void>): void {
  const reach = async (id: number) => land(await openNotification(id));
  const id = new URLSearchParams(location.search).get("notification");
  if (id) {
    history.replaceState(null, "", location.pathname + location.hash);
    void reach(Number(id));
  }
  if ("serviceWorker" in navigator)
    navigator.serviceWorker.addEventListener(
      "message",
      (e) => void reach((e.data as { notification: number }).notification),
    );
}
