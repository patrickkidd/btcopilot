/* Minimal offline shell: the built bundle is cached so the app opens without a
   network. Every /companion API call goes to the network untouched. */
const CACHE = "companion-v1";
const SHELL = [
  "/companion/",
  "/companion/static/web/app.js",
  "/companion/static/web/app.css",
  "/companion/manifest.webmanifest",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches
      .open(CACHE)
      .then((c) => c.addAll(SHELL))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  const shell =
    e.request.mode === "navigate" ||
    url.pathname.startsWith("/companion/static/web/");
  if (e.request.method !== "GET" || !shell) return;
  e.respondWith(
    fetch(e.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return response;
      })
      .catch(() =>
        caches.match(e.request).then((hit) => hit || caches.match("/companion/")),
      ),
  );
});
