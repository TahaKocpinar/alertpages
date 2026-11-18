// Offline support: app shell is cache-first, data is network-first with cache fallback.
const CACHE = "alertpages-{{VERSION}}";
const SHELL = ["./", "index.html", "app.js", "style.css", "i18n.json", "icon.svg", "manifest.webmanifest"];
const DATA = ["alerts.json", "feed.xml"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL.concat(DATA))).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  const isData = DATA.some((d) => url.pathname.endsWith("/" + d));
  if (isData) {
    e.respondWith(fetch(e.request, { cache: "no-store" }).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(e.request, copy));
      return res;
    }).catch(() => caches.match(e.request, { ignoreSearch: true }).then((hit) => {
      if (!hit) return Response.error();
      const headers = new Headers(hit.headers);
      headers.set("x-from-cache", "1"); // lets the page show its offline banner
      return new Response(hit.body, { status: 200, headers });
    })));
  } else {
    e.respondWith(caches.match(e.request, { ignoreSearch: true }).then((hit) => hit || fetch(e.request)));
  }
});
