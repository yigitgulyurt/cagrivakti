// Basit Service Worker - Test için
const CACHE_VERSION = '6.08';
const STATIC_CACHE = `cv-static-v${CACHE_VERSION}`;
const API_CACHE    = `cv-api-v${CACHE_VERSION}`;

console.log('[SW] Starting...');

// Yükleme (Install)
self.addEventListener('install', (event) => {
    console.log('[SW] Install event triggered');
    event.waitUntil(
        Promise.all([
            caches.open(STATIC_CACHE).then((cache) => {
                console.log('[SW] Static cache opened');
                return cache;
            }),
            caches.open(API_CACHE).then((cache) => {
                console.log('[SW] API cache opened');
                return cache;
            })
        ]).then(() => {
            console.log('[SW] Install completed, skipping waiting');
            return self.skipWaiting();
        })
    );
});

// Aktifleştirme (Activate)
self.addEventListener('activate', (event) => {
    console.log('[SW] Activate event triggered');
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            console.log('[SW] Found caches:', cacheNames);
            const allowedCaches = [STATIC_CACHE, API_CACHE];
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (!allowedCaches.includes(cacheName)) {
                        console.log('[SW] Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => {
            console.log('[SW] Activate completed, claiming clients');
            return self.clients.claim();
        })
    );
});

// İstekleri Yakalama (Fetch)
self.addEventListener('fetch', (event) => {
    console.log('[SW] Fetch event for:', event.request.url);
    // Basitçe ağdan getir
    event.respondWith(fetch(event.request));
});

console.log('[SW] Script loaded successfully');