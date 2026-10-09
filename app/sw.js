// Service worker: app shell offline, always-fresh feed, audio straight from the network.
const SHELL = "wb-shell-v3";
const SHELL_FILES = ["./", "index.html", "app.css", "app.js", "manifest.webmanifest",
  "icons/icon-192.png", "icons/icon-512.png", "icons/apple-touch-icon.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== SHELL).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  // Audio uses range requests; let the browser handle those directly.
  if (url.pathname.includes("/audio/")) return;

  if (url.pathname.endsWith("feed.json")) {
    // network first, cached copy when offline
    e.respondWith(fetch(e.request).then((res) => {
      const copy = res.clone();
      caches.open(SHELL).then((c) => c.put("feed.json", copy));
      return res;
    }).catch(() => caches.match("feed.json")));
    return;
  }

  // shell: serve cached, refresh in the background
  e.respondWith(caches.match(e.request, { ignoreSearch: true }).then((hit) => {
    const fresh = fetch(e.request).then((res) => {
      if (res.ok) caches.open(SHELL).then((c) => c.put(e.request, res.clone()));
      return res;
    }).catch(() => hit);
    return hit || fresh;
  }));
});
