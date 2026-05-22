// Service Worker - Ezan Vakitleri (Basit Versiyon)
/* global VERSION */

const STATIC_CACHE = 'cv-static-v' + VERSION;
const API_CACHE = 'cv-api-v' + VERSION;
const JS_CACHE = 'cv-js-v' + VERSION;
const CSS_CACHE = 'cv-css-v' + VERSION;

console.log('[SW] Yukleniyor, VERSION:', VERSION);

self.addEventListener('install', function(event) {
    console.log('[SW] Kuruluyor...');
    self.skipWaiting();
});

self.addEventListener('activate', function(event) {
    console.log('[SW] Aktiflesiyor...');
    event.waitUntil(
        caches.keys().then(function(cacheNames) {
            console.log('[SW] Mevcut cacheler:', cacheNames);
            return Promise.all(
                cacheNames.map(function(cacheName) {
                    if (cacheName !== STATIC_CACHE && 
                        cacheName !== API_CACHE && 
                        cacheName !== JS_CACHE && 
                        cacheName !== CSS_CACHE) {
                        console.log('[SW] Eski cache siliniyor:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(function() {
            console.log('[SW] Aktiflestirme tamamlaniyor');
            return self.clients.claim();
        })
    );
});

self.addEventListener('fetch', function(event) {
    event.respondWith(
        fetch(event.request).catch(function() {
            return caches.match(event.request);
        })
    );
});
