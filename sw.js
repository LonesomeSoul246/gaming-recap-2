// Gaming Recap – Service Worker (nur in der Handy-App auf GitHub Pages aktiv)
// App-Dateien und Bilder kommen sofort aus dem Speicher (schneller Start), werden im Hintergrund aktualisiert.
// Daten (data.enc usw.) immer frisch aus dem Netz, bei Funkloch aus dem Speicher.
const CACHE = "gaming-recap-e5e7d3f93248";
const SHELL = ["./", "./index.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png", "./apple-touch-icon.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE && k.startsWith("gaming-recap-")).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
const isData = p => /\.enc$/.test(p) || p.includes("/edits/") || p.includes("/app/");
const isStatic = p => /\/(index\.html)?$/.test(p) || /\.(webp|png|webmanifest)$/.test(p);
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (isStatic(url.pathname) && !isData(url.pathname)) {
    // Sofort aus dem Speicher, im Hintergrund nachladen (eine neue App-Version installiert sich über den Service Worker selbst)
    e.respondWith(caches.open(CACHE).then(c => c.match(e.request, {ignoreSearch: true}).then(hit => {
      const net = fetch(e.request, {cache: "no-cache"}).then(r => { if (r.ok) c.put(e.request, r.clone()); return r; }).catch(() => hit);
      return hit || net;
    })));
    return;
  }
  e.respondWith(fetch(e.request, {cache: "no-cache"}).then(r => {
    if (r.ok && !isData(url.pathname)) { const copy = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); }
    return r;
  }).catch(() => caches.match(e.request, {ignoreSearch: true}).then(r => r || caches.match("./index.html"))));
});
