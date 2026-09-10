/* GiziLens — service worker.
   Aturan penting: halaman utama (index.html) diambil dari INTERNET DULU (network-first),
   supaya setiap pembaruan aplikasi langsung terlihat setelah refresh — bukan nyangkut
   di versi lama yang tersimpan di cache. Berkas lain (logo, manifest) pakai cache untuk
   mempercepat & tetap bisa dibuka offline. */
const CACHE = "gizilens-v2";
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
  if (req.method !== "GET") return;
  let sameOrigin = true;
  try { sameOrigin = new URL(req.url).origin === location.origin; } catch (err) { sameOrigin = false; }

  // 1) Halaman aplikasi: coba internet dulu, baru cache (biar update selalu masuk).
  if (req.mode === "navigate" || req.destination === "document") {
    e.respondWith(
      fetch(req).then(function (resp) {
        const salinan = resp.clone();
        caches.open(CACHE).then(function (c) { c.put(req, salinan).catch(function () {}); });
        return resp;
      }).catch(function () {
        return caches.match(req).then(function (ada) { return ada || caches.match("./index.html"); });
      })
    );
    return;
  }

  // 2) Berkas statis di domain yang sama: ambil dari cache, lalu segarkan di belakang.
  if (!sameOrigin) return;
  e.respondWith(
    caches.match(req).then(function (ada) {
      const dariInternet = fetch(req).then(function (resp) {
        const salinan = resp.clone();
        caches.open(CACHE).then(function (c) { c.put(req, salinan).catch(function () {}); });
        return resp;
      }).catch(function () { return ada; });
      return ada || dariInternet;
    })
  );
});
