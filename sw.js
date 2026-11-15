// Gaming Recap – Service Worker (nur in der Handy-App auf GitHub Pages aktiv)
const CACHE = "gaming-recap-306182fa05b0";
const SHELL = ["./", "./index.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png", "./apple-touch-icon.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE && k.startsWith("gaming-recap-")).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  // Netz zuerst, bei Funkloch aus dem Speicher
  // no-cache: immer beim Server nachfragen, damit Updates sofort ankommen
  e.respondWith(fetch(e.request, {cache: "no-cache"}).then(r => {
    if (r.ok && !url.pathname.endsWith("data.enc")) { const copy = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); }
    return r;
  }).catch(() => caches.match(e.request, {ignoreSearch: true}).then(r => r || caches.match("./index.html"))));
});
