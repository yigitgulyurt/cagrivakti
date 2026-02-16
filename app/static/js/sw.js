// Service Worker - Namaz Vakitleri (Workbox Powered)
importScripts('https://storage.googleapis.com/workbox-cdn/releases/5.1.2/workbox-sw.js');

const CACHE = "namaz-vakitleri-offline-v3.0";
const offlineFallbackPage = "/offline";

// Önbelleğe alınacak kritik dosyalar (App Shell)
const PRECACHE_ASSETS = [
    '/',
    '/offline',
    '/sehir',
    '/imsakiye',
    '/ramazan',
    '/neden-biz',
    '/indir',
    '/bilgi-kosesi',
    '/konum-bul',
    '/iletisim',
    '/ilkelerimiz',
    '/MUSTAFA-KEMAL-ATATÜRK',
    '/static/js/jquery.min.js',
    '/static/js/city-data.js',
    '/static/css/main.css',
    '/static/icons/favicon.ico',
    '/static/icons/android/android-launchericon-192-192.png',
    '/static/icons/android/android-launchericon-512-512.png',
    '/static/icons/ios/180.png'
];

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

self.addEventListener('install', async (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => {
        console.log('[SW] Caching app shell and offline page');
        return cache.addAll(PRECACHE_ASSETS);
      })
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      // Eski cacheleri temizle (v3.0 olmayanlar)
      const cacheNames = await caches.keys();
      await Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE) {
            console.log('[SW] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
      // Hemen kontrolü ele al
      await self.clients.claim();
    })()
  );
});

if (workbox.navigationPreload.isSupported()) {
  workbox.navigationPreload.enable();
}

// 1. HTML Sayfaları (Navigation) -> NetworkFirst
// Önce internetten almaya çalış, yoksa cache'e bak, o da yoksa offline sayfası
workbox.routing.registerRoute(
  ({ request }) => request.mode === 'navigate',
  new workbox.strategies.NetworkFirst({
    cacheName: CACHE,
    plugins: [
      new workbox.expiration.ExpirationPlugin({
        maxEntries: 50,
        maxAgeSeconds: 30 * 24 * 60 * 60, // 30 gün
      }),
    ],
  })
);

// 2. Statik Dosyalar (CSS, JS, Images, Fonts) -> StaleWhileRevalidate
// Hızlı açılış için cache, arka planda güncelle
workbox.routing.registerRoute(
  ({ request }) =>
    request.destination === 'style' ||
    request.destination === 'script' ||
    request.destination === 'image' ||
    request.destination === 'font',
  new workbox.strategies.StaleWhileRevalidate({
    cacheName: CACHE,
    plugins: [
      new workbox.expiration.ExpirationPlugin({
        maxEntries: 200,
        maxAgeSeconds: 60 * 24 * 60 * 60, // 60 gün
      }),
    ],
  })
);

// Offline Fallback logic (Workbox Catch Handler)
// Eğer StaleWhileRevalidate hem cache'de bulamaz hem de network'e erişemezse burası çalışır
workbox.routing.setCatchHandler(async ({ event }) => {
  if (event.request.destination === 'document' || event.request.mode === 'navigate') {
    return caches.match(offlineFallbackPage);
  }
  return Response.error();
});
