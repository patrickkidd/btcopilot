import { call } from "./api";
import type { CodedIn } from "./types";

/** Where a tap on a notification opens the thread. */
type Open = (where: CodedIn) => Promise<void>;

/** The server's public key arrives base64url; the browser takes raw bytes. */
function bytes(key: string): Uint8Array<ArrayBuffer> {
  const b64 = key.replace(/-/g, "+").replace(/_/g, "/");
  const padded = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
  return new Uint8Array([...atob(padded)].map((c) => c.charCodeAt(0)));
}

/** Run inside the tap that asks the coach to message first: a browser asks
 * for permission only on a tap. iOS offers web push only to the app added to
 * the home screen; wherever push is refused or missing, the coach emails
 * instead. Says whether this browser can now be reached by push. */
export async function subscribe(): Promise<boolean> {
  if (!("PushManager" in window)) return false;
  if ((await Notification.requestPermission()) !== "granted") return false;
  const [{ key }, worker] = await Promise.all([
    call<{ key: string }>("GET", "/push-subscriptions"),
    navigator.serviceWorker.ready,
  ]);
  const subscription = await worker.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: bytes(key),
  });
  await call("POST", "/push-subscriptions", subscription.toJSON());
  return true;
}

async function reach(id: number, open: Open): Promise<void> {
  await open(await call<CodedIn>("PATCH", `/notifications/${id}`, { opened: true }));
}

/** A tap on a notification, or on the link in its email, opens the thread at
 * the message it points to, and the server counts it opened. The worker names
 * the notification in the address when it opens the app, and in a message
 * when the app is already open. */
export function landing(open: Open): void {
  const id = new URLSearchParams(location.search).get("notification");
  if (id) {
    history.replaceState(null, "", location.pathname + location.hash);
    void reach(Number(id), open);
  }
  if ("serviceWorker" in navigator)
    navigator.serviceWorker.addEventListener("message", (e) =>
      void reach((e.data as { notification: number }).notification, open),
    );
}
