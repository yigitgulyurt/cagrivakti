// Service Worker - Namaz Vakitleri
const CACHE_NAME = 'namaz-vakitleri-v2.8'; // Versiyon güncellendi (PWA Shortcut ve Şehir Eşleme)

// API istekleri için Cache-First, sonra Network (Offline için)
const API_CACHE_NAME = 'api-cache-v1';

// Önbelleğe alınacak statik dosyalar ve sayfalar
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
    '/static/icons/favicon.ico',
    '/static/icons/icon-48-48.webp',
    '/static/icons/icon-72-72.webp',
    '/static/icons/icon-96-96.webp',
    '/static/icons/icon-144-144.webp',
    '/static/icons/icon-152-152.webp',
    '/static/icons/icon-192-192.webp',
    '/static/icons/icon-512-512.webp',
    '/static/icons/og-image.webp',
    '/manifest.json',
    'https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Amiri&display=swap'
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

    // API istekleri (Vakitler vb.) - Network-First, ama Cache'e kaydet ve hata durumunda Cache'den getir
    if (url.pathname.startsWith('/api/namaz_vakitleri') || url.pathname.startsWith('/api/vakitler/')) {
        event.respondWith(
            fetch(event.request)
                .then((response) => {
                    // Sadece başarılı yanıtları önbelleğe al
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
                    
                    // Eğer cache'de de yoksa, anlamlı bir hata dön (undefined dönmemeli)
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
                    // Sadece başarılı ve geçerli yanıtları önbelleğe al
                    // Offline sayfasını veya hata sayfalarını dinamik olarak ana URL'lere kaydetme
                    if (response.ok && response.status === 200 && !response.url.includes('/offline')) {
                        const responseClone = response.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(event.request, responseClone);
                        });
                    }
                    return response;
                })
                .catch(async () => {
                        // Çevrimdışı durumunda:
                        // 1. Önce tam URL ile cache'e bak (Query params dahil)
                        const cachedResponse = await caches.match(event.request);
                        if (cachedResponse) return cachedResponse;
                        
                        // 2. Query params olmadan bak (Örn: /sehir/Istanbul?country=TR -> /sehir/Istanbul)
                        const url = new URL(event.request.url);
                        const cleanResponse = await caches.match(url.pathname, { ignoreSearch: true });
                        if (cleanResponse) return cleanResponse;

                        // 3. Eğer bir alt sayfa ise (Örn: /sehir/Istanbul), ana route'u dene (/sehir)
                        if (url.pathname.startsWith('/sehir/')) {
                            const sehirResponse = await caches.match('/sehir');
                            if (sehirResponse) return sehirResponse;
                        }
                        
                        if (url.pathname.startsWith('/imsakiye/')) {
                            const imsakiyeResponse = await caches.match('/imsakiye');
                            if (imsakiyeResponse) return imsakiyeResponse;
                        }

                        // 4. Hiçbiri yoksa offline fallback
                        return caches.match('/offline');
                    })
        );
        return;
    }

    // Statik dosyalar için Stale-While-Revalidate stratejisi
    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            const fetchPromise = fetch(event.request).then((networkResponse) => {
                // Geçerli bir yanıt aldığımızda önbelleği güncelle
                if (networkResponse && networkResponse.status === 200) {
                    const responseToCache = networkResponse.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseToCache);
                    });
                }
                return networkResponse;
            });

            // Önbellekte varsa hemen döndür, yoksa ağı bekle
            return cachedResponse || fetchPromise;
        })
    );
});
