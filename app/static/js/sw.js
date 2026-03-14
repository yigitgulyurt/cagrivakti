// Service Worker - Ezan Vakitleri
const CACHE_NAME = `ezan-vakitleri-V${VERSION}`;

// API istekleri için Cache-First, sonra Network (Offline için)
const API_CACHE_NAME = `api-cache-V${VERSION}`;

// Önbelleğe alınacak statik dosyalar ve sayfalar
const PRECACHE_ASSETS = [
    '/',
    '/indir',
    '/sehir',
    '/offline',
    '/ramazan',
    '/iletisim',
    '/imsakiye',
    '/konum-bul',
    '/neden-biz',
    '/asal-sayi',
    '/qr-okuyucu',
    '/ilkelerimiz',
    '/bilgi-kosesi',
    '/kible-pusulasi',
    '/Mustafa-Kemal-Ataturk',
    '/static/js/city-data.js',
    '/static/icons/favicon.ico',
    '/static/icons/ios/180.png',
    '/static/js/html5-qrcode.min.js',
    '/static/js/jquery-cagrivakti.js',
    '/static/icons/android/android-launchericon-192-192.png',
    '/static/icons/android/android-launchericon-512-512.png',
    '/static/icons/windows11/Square150x150Logo.scale-100.png',
];

// SW tarafından hiç önbelleğe alınmayacak sayfalar
const NO_CACHE_PAGES = [
    '/oyunlar/under-the-red-sky',
];

// Yükleme (Install) - Kritik dosyaları önbelleğe al
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[SW] Pre-caching critical assets');
            return cache.addAll(PRECACHE_ASSETS);
        }).then(() => self.skipWaiting())
    );
});

// Aktifleştirme (Activate) - Eski önbellekleri temizle
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME && cacheName !== API_CACHE_NAME) {
                        console.log('[SW] Removing old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// İstekleri Yakalama (Fetch)
self.addEventListener('fetch', (event) => {
    // Sadece GET isteklerini işle
    if (event.request.method !== 'GET') return;

    const url = new URL(event.request.url);

    // Font ve stream bypass
    if (
        url.hostname === 'fonts.googleapis.com' ||
        url.hostname === 'fonts.gstatic.com' ||
        url.hostname === 'fonts.cagrivakti.com.tr' ||
        url.pathname.startsWith('/canli-kaynak/') ||
        url.pathname === '/stream/status'
    ) {
        return;
    }

    // Oyun dosyaları bypass
    if (
        url.pathname.startsWith('/oyun') ||
        url.pathname === '/workermain.js' ||
        url.pathname.startsWith('/scripts/jobworker') ||
        url.pathname.startsWith('/scripts/dispatchworker')
    ) {
        return;
    }

    // Önbelleğe alınmayacak sayfalar — her zaman ağdan getir
    if (NO_CACHE_PAGES.some(p => url.pathname === p || url.pathname.startsWith(p + '/'))) {
        event.respondWith(fetch(event.request));
        return;
    }

    // API istekleri (Vakitler vb.) - Network-First, ama Cache'e kaydet ve hata durumunda Cache'den getir
    if (url.hostname === 'api.cagrivakti.com.tr' && (url.pathname.startsWith('/ezan_vakitleri') || url.pathname.startsWith('/vakitler/'))) {
        event.respondWith(
            fetch(event.request)
                .then((response) => {
                    if (response.ok) {
                        const responseClone = response.clone();
                        caches.open(API_CACHE_NAME).then((cache) => {
                            cache.put(event.request, responseClone);
                        });
                    }
                    return response;
                })
                .catch(async () => {
                    const cachedResponse = await caches.match(event.request);
                    if (cachedResponse) return cachedResponse;
                    return new Response(JSON.stringify({
                        durum: "hata",
                        mesaj: "İnternet bağlantısı yok ve veri henüz önbelleğe alınmamış."
                    }), {
                        status: 503,
                        headers: { 'Content-Type': 'application/json' }
                    });
                })
        );
        return;
    }

    // HTML sayfaları için Network-First, hata durumunda önce Cache'e bak, yoksa Offline sayfası
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request)
                .then((response) => {
                    if (response.ok && response.status === 200 && 
                        !response.url.includes('/offline') && 
                        !response.url.includes('/kaynak/') &&
                        !response.url.includes('/canli-kaynak/')) { 
                        const responseClone = response.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(event.request, responseClone);
                        });
                    }
                    return response;
                })
                .catch(async () => {
                        const cachedResponse = await caches.match(event.request);
                        if (cachedResponse) return cachedResponse;
                        
                        const url = new URL(event.request.url);
                        const cleanResponse = await caches.match(url.pathname, { ignoreSearch: true });
                        if (cleanResponse) return cleanResponse;

                        if (url.pathname.startsWith('/sehir/')) {
                            const sehirResponse = await caches.match('/sehir');
                            if (sehirResponse) return sehirResponse;
                        }
                        
                        if (url.pathname.startsWith('/imsakiye/')) {
                            const imsakiyeResponse = await caches.match('/imsakiye');
                            if (imsakiyeResponse) return imsakiyeResponse;
                        }

                        return caches.match('/offline');
                    })
        );
        return;
    }

    // Statik dosyalar için Stale-While-Revalidate stratejisi
    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            const fetchPromise = fetch(event.request)
                .then((networkResponse) => {
                    if (networkResponse && networkResponse.status === 200) {
                        const responseToCache = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(event.request, responseToCache);
                        });
                    }
                    return networkResponse;
                })
                .catch((err) => {
                    if (cachedResponse) {
                        console.warn('[SW] Background fetch failed for ' + event.request.url);
                        return;
                    }
                    throw err;
                });

            return cachedResponse || fetchPromise;
        })
    );
});