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
    '/static/icons/ios/180.png',
    'https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Amiri&display=swap'
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
        return cache.addAll([...PRECACHE_ASSETS, offlineFallbackPage]);
      })
  );
});

if (workbox.navigationPreload.isSupported()) {
  workbox.navigationPreload.enable();
}

// Tüm istekler için Stale-While-Revalidate stratejisi
workbox.routing.registerRoute(
  new RegExp('/*'),
  new workbox.strategies.StaleWhileRevalidate({
    cacheName: CACHE,
    plugins: [
      new workbox.expiration.ExpirationPlugin({
        maxEntries: 200,
        maxAgeSeconds: 30 * 24 * 60 * 60, // 30 gün
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
