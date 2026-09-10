/* GiziLens — service worker sederhana: simpan berkas inti supaya bisa dibuka offline.
   Catatan: hanya aktif kalau aplikasi dibuka lewat https (mis. GitHub Pages) atau localhost. */
const CACHE = "gizilens-v1";
const INTI = ["./", "./index.html", "./manifest.webmanifest", "./assets/logo_rspal.png"];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(INTI).catch(function () {}); })
    .then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener("fetch", function (e) {
  const req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== location.origin) return;
  e.respondWith(
    caches.match(req).then(function (ada) {
      return ada || fetch(req).then(function (resp) {
        const salinan = resp.clone();
        caches.open(CACHE).then(function (c) { c.put(req, salinan).catch(function () {}); });
        return resp;
      }).catch(function () { return caches.match("./index.html"); });
    })
  );
});
