
function updateOnlineStatus() {
    // Sadece bağlantı koptuğunda offline sayfasına yönlendirilebilir 
    // ya da uygulama genelinde sessizce yönetilebilir.
    // Kullanıcının bahsettiği "kırmızı kutu" uyarısı burada tetiklenmiyor.
    console.log(navigator.onLine ? "Çevrimiçi" : "Çevrimdışı");
}
window.addEventListener('online', updateOnlineStatus);
window.addEventListener('offline', updateOnlineStatus);
// Manifest URL'ini kullanıcı şehrine göre güncelle (Cache busting ve Parametre)
window.addEventListener('DOMContentLoaded', () => {
    const userCityMatch = document.cookie.match(/user_city=([^;]+)/);
    if (userCityMatch && userCityMatch[1]) {
        const city = userCityMatch[1];
        const manifestLink = document.querySelector('link[rel="manifest"]');
        if (manifestLink) {
            const url = new URL(manifestLink.href, window.location.origin);
            url.searchParams.set('city', city);
            // Tarayıcının cache'ini zorlamak için versiyon ekle
            // url.searchParams.set('v', '2.11'); 
            manifestLink.href = url.toString();
            // console.log('Manifest updated for:', city);
        }
    }
});
// PWA Kurulum Mantığı
window.deferredPrompt = null;
const pwaBanner = document.getElementById('pwaInstallBanner');
const installBtn = document.getElementById('pwaInstallBtn');
const closeBtn = document.getElementById('pwaCloseBtn');
// Şehir eşleştirme ve normalizasyon fonksiyonları (Global Scope'da tanımlı olabilir, kontrol et)
//const CITY_DISPLAY_MAPPING_GLOBAL = JSON.parse('{{ CITY_DISPLAY_NAME_MAPPING | tojson | safe if CITY_DISPLAY_NAME_MAPPING else "{}" }}');
const CITY_DISPLAY_MAPPING_GLOBAL = JSON.parse('{{ CITY_DISPLAY_NAME_MAPPING | tojson | default('{}') | safe }}');
const REVERSE_CITY_MAPPING_GLOBAL = Object.fromEntries(
    Object.entries(CITY_DISPLAY_MAPPING_GLOBAL).map(([latin, turkish]) => [turkish, latin])
);
function getLatinNameGlobal(turkishName) {
     if (REVERSE_CITY_MAPPING_GLOBAL[turkishName]) {
         return REVERSE_CITY_MAPPING_GLOBAL[turkishName];
     }
     const charMap = {
         'ç': 'c', 'Ç': 'C', 'ğ': 'g', 'Ğ': 'G', 'ı': 'i', 'İ': 'I',
         'ö': 'o', 'Ö': 'O', 'ş': 's', 'Ş': 'S', 'ü': 'u', 'Ü': 'U'
     };
     let normalized = turkishName.split('').map(char => charMap[char] || char).join('');
     return normalized.replace(/\s+/g, '-').replace(/[^A-Za-z0-9\-]/g, '');
}
// Banner'ı kapatma fonksiyonu
function closePwaBanner() {
    if (pwaBanner) {
        pwaBanner.classList.remove('active');
        pwaBanner.classList.remove('ready');
        // Bu oturumda tekrar gösterme
        sessionStorage.setItem('pwaBannerDismissed', 'true');
    }
}
window.addEventListener('beforeinstallprompt', (e) => {
    // Masaüstü cihazlarda PWA kurulumunu tamamen engelle
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    if (!isMobile) {
        e.preventDefault();
        console.log('PWA prompt suppressed on desktop');
        return;
    }
    // İndir sayfasında ise native banner'ın çıkmasına izin ver (preventDefault yapma)
    // Diğer sayfalarda otomatik gösterimi engelle
    const isDownloadPage = window.location.pathname.includes('/indir') || window.location.pathname.includes('/uygulamayi-indir');
    
    if (!isDownloadPage) {
        e.preventDefault();
    }
    
    // Olayı sakla ki daha sonra tetikleyebilelim
    window.deferredPrompt = e;
    
    // Eğer indir sayfasındaysak ve kullanıcı bir butona basarsa tetiklemek için hazır olsun
    if (isDownloadPage) {
        console.log('PWA native prompt allowed on download page');
        // İndir sayfasında özel butonları aktif et (varsa)
        const downloadPageBtn = document.getElementById('pwa-install-btn-main');
        if (downloadPageBtn) {
            downloadPageBtn.style.display = 'inline-block';
            downloadPageBtn.addEventListener('click', async () => {
                if (window.deferredPrompt) {
                    window.deferredPrompt.prompt();
                    const { outcome } = await window.deferredPrompt.userChoice;
                    console.log(`User response to the install prompt: ${outcome}`);
                    window.deferredPrompt = null;
                    downloadPageBtn.style.display = 'none';
                }
            });
        }
        return; // Custom banner'ı gösterme
    }
    
    // Eğer reload sonrası ise hemen göster
    if (sessionStorage.getItem('reloadingForPWA')) {
        pwaBanner.classList.add('active');
        pwaBanner.classList.add('ready'); // Büyük ve ortalı görünüm
        
        const pwaText = document.querySelector('.pwa-text p');
        const pwaTitle = document.querySelector('.pwa-text h3');
        const installBtn = document.getElementById('pwaInstallBtn');
        
        if (pwaTitle) pwaTitle.textContent = 'Kuruluma Hazır';
        if (pwaText) pwaText.textContent = 'Her şey hazır, şimdi uygulamayı yükleyebilirsin.';
        if (installBtn) {
            installBtn.innerHTML = '<svg class="icon" style="font-size: 1.2em; margin-right: 8px;"><use xlink:href="#fa-download-solid-full"></use></svg> Uygulamayı Yükle';
            installBtn.classList.add('pulse-animation');
        }
        
        sessionStorage.removeItem('reloadingForPWA');
    } 
    // Eğer kullanıcı daha önce bu oturumda kapatmadıysa banner'ı göster
    else if (!sessionStorage.getItem('pwaBannerDismissed')) {
        setTimeout(() => {
            pwaBanner.classList.add('active');
        }, 1000); // 1 saniye sonra göster
    }
});
// iOS ve Desteklenmeyen Tarayıcılar İçin Fallback Logic
window.addEventListener('load', () => {
     const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
     const isStandalone = window.matchMedia('(display-mode: standalone)').matches;
     const isDismissed = sessionStorage.getItem('pwaBannerDismissed');
     const isDownloadPage = window.location.pathname.includes('/indir') || window.location.pathname.includes('/uygulamayi-indir');
     
     if (isMobile && !isStandalone && !isDismissed && !isDownloadPage) {
         // beforeinstallprompt'un tetiklenip tetiklenmediğini kontrol et (Android için biraz bekle)
         setTimeout(() => {
             if (!window.deferredPrompt) {
                 // Eğer native prompt yoksa, banner'ı yine de göster (Redirect modu)
                 if (pwaBanner) {
                     pwaBanner.classList.add('active');
                     // Buton metnini gerekirse güncelle (Şimdilik "Yükle" kalabilir)
                 }
             }
         }, 3000); // 3 saniye bekle
     }
});
if (installBtn) {
    installBtn.addEventListener('click', async () => {
        if (window.deferredPrompt) {
            // 1. Şehir kontrolü (Cookie)
            const userCity = document.cookie.split('; ').find(row => row.startsWith('user_city='));
            const pwaText = document.querySelector('.pwa-text p');
            
            if (!userCity) {
                // MODAL VE TOAST ELEMENTLERİNİ SEÇ
                const permissionModal = document.getElementById('locationPermissionModal');
                const allowBtn = document.getElementById('allowLocationBtn');
                const denyBtn = document.getElementById('denyLocationBtn');
                const toast = document.getElementById('processToast');
                const toastMsg = document.getElementById('toastMessage');
                // Modalı göster
                if (permissionModal) {
                    permissionModal.classList.add('active');
                    
                    // İzin ver butonuna tıklandığında
                    const handleAllow = async () => {
                        permissionModal.classList.remove('active');
                        
                        // Toast göster
                        if (toast && toastMsg) {
                            toastMsg.textContent = 'Konum uydudan alınıyor...';
                            toast.classList.add('active');
                            toast.classList.remove('success'); // Reset success state
                        }
                        try {
                            // Konum izni iste
                            const position = await new Promise((resolve, reject) => {
                                navigator.geolocation.getCurrentPosition(resolve, reject);
                            });
                            
                            // Konum alındı
                            if (toastMsg) toastMsg.textContent = 'Şehir bilgisi işleniyor...';
                            
                            const lat = position.coords.latitude;
                            const lon = position.coords.longitude;
                            
                            // Reverse Geocoding
                            let originalCityName = null;
                            // 1. Deneme: Nominatim (OpenStreetMap)
                            try {
                                const response = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json&accept-language=tr`);
                                if (response.ok) {
                                    const data = await response.json();
                                    if (data && data.address) {
                                        originalCityName = data.address.province || data.address.city || data.address.town || data.address.state;
                                    }
                                }
                            } catch (err) {
                                console.warn('Nominatim failed, trying fallback...');
                            }
                            // 2. Deneme: BigDataCloud (Fallback)
                            if (!originalCityName) {
                                try {
                                    if (toastMsg) toastMsg.textContent = 'Alternatif servis deneniyor...';
                                    const response = await fetch(`https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${lat}&longitude=${lon}&localityLanguage=tr`);
                                    if (response.ok) {
                                        const data = await response.json();
                                        // BigDataCloud field mapping
                                        originalCityName = data.city || data.locality || data.principalSubdivision;
                                    }
                                } catch (err) {
                                    console.error('Fallback geocoding failed:', err);
                                }
                            }
                            if (originalCityName) {
                                // Başarılı
                                originalCityName = originalCityName.replace(" İli", "").replace(" Province", "").trim();
                                const latinCityName = getLatinNameGlobal(originalCityName);
                                
                                // Cookie ve LocalStorage güncelle
                                document.cookie = `user_city=${latinCityName}; path=/; max-age=31536000; SameSite=Lax`;
                                localStorage.setItem('user_city', latinCityName);
                                
                                if (toastMsg) toastMsg.textContent = `Şehir bulundu: ${originalCityName}`;
                                if (toast) {
                                    toast.classList.add('success');
                                    // Başarı ikonunu göster (spinner gizlenir css ile)
                                    const icon = toast.querySelector('.toast-success-icon use');
                                    if(icon) icon.setAttribute('xlink:href', '#fa-check-circle');
                                }
                                
                                // Biraz bekle sonra yenile
                                setTimeout(() => {
                                    sessionStorage.setItem('reloadingForPWA', 'true');
                                    window.location.reload();
                                }, 1500);
                            } else {
                                // Başarısız - Manuel Seçime Yönlendir
                                console.error('All reverse geocoding attempts failed.');
                                if (toastMsg) toastMsg.textContent = 'Otomatik konum bulunamadı.';
                                if (toast) toast.classList.remove('success'); // Hata durumunda success olmamalı
                                
                                setTimeout(() => {
                                    if (toastMsg) toastMsg.textContent = 'Manuel seçime yönlendiriliyorsunuz...';
                                    // Hata durumunda da yönlendir
                                    window.location.href = "{{ url_for('views.sehir_secimi') }}";
                                }, 1500);
                            }
                        } catch (error) {
                            console.log('Konum hatası:', error);
                            if (toastMsg) toastMsg.textContent = 'Konum izni verilmedi.';
                            setTimeout(() => {
                                if (toast) toast.classList.remove('active');
                            }, 2000);
                        }
                        
                        // Event listener'ı temizle (gerekirse)
                        allowBtn.removeEventListener('click', handleAllow);
                    };
                    allowBtn.onclick = handleAllow; // onclick kullanarak önceki listenerları ezeriz
                    // Vazgeç butonuna tıklandığında
                    denyBtn.onclick = () => {
                        permissionModal.classList.remove('active');
                    };
                    
                    return; // Modal sonucunu bekle
                }
            }
            // 2. Yükleme işlemini başlat (Eğer şehir varsa)
            window.deferredPrompt.prompt();
            
            const { outcome } = await window.deferredPrompt.userChoice;
            console.log(`User response to the install prompt: ${outcome}`);
            
            window.deferredPrompt = null;
            closePwaBanner();
        } else {
            // Fallback: Native prompt yoksa (iOS vb.) indir sayfasına yönlendir
            window.location.href = "{{ url_for('views.indir') }}";
        }
    });
}
if (closeBtn) {
    closeBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        closePwaBanner();
    });
}
// Uygulama yüklendiğinde
window.addEventListener('appinstalled', (evt) => {
    console.log('PWA başarıyla yüklendi');
    pwaBanner.classList.remove('active');
});
// Navbar Toggle
const navToggle = document.getElementById('navToggle');
const navLinks = document.getElementById('navLinks');
if (navToggle && navLinks) {
    navToggle.addEventListener('click', () => {
        navLinks.classList.toggle('active');
        const icon = navToggle.querySelector('use');
        if (navLinks.classList.contains('active')) {
            icon.setAttribute('xlink:href', '#fa-xmark');
            document.body.style.overflow = 'hidden';
        } else {
            icon.setAttribute('xlink:href', '#fa-bars');
            document.body.style.overflow = 'auto';
        }
    });
    // Menü linklerine tıklandığında menüyü kapat
    navLinks.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', () => {
            navLinks.classList.remove('active');
            navToggle.querySelector('use').setAttribute('xlink:href', '#fa-bars');
            document.body.style.overflow = 'auto';
        });
    });
}