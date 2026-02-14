# 🌙 Çağrı Vakti - Modern Namaz Vakitleri Ekosistemi

**Çağrı Vakti**, modern web teknolojileri ve yapay zeka destekli geliştirme süreçleriyle inşa edilmiş, çok platformlu bir ibadet asistanı ekosistemidir. Bu proje, estetik tasarımı güçlü bir teknik altyapıyla birleştirerek kullanıcılara en hızlı ve doğru vakit bilgilerini sunmayı hedefler.

---

## 💎 Temel Özellikler

### 🛰️ Akıllı Konum Servisleri
*   **Hassas Tespit:** Tarayıcı tabanlı konum servisleri ve gelişmiş reverse geocoding ile kullanıcının bulunduğu şehri anında belirler.
*   **Akıllı Hafıza:** Tercihleri yerel depolamada saklayarak her girişte akıcı ve kesintisiz bir deneyim sunar.

### 📱 Modern Kullanıcı Deneyimi
*   **PWA Desteği:** Yerleşik uygulama konforu; masaüstü ve mobilde yüklenebilir yapı ve çevrimdışı kullanım kabiliyeti.
*   **Ultra-Modern Arayüz:** Göz yormayan dinamik temalar, akıcı animasyonlar ve her cihaza tam uyumlu (Responsive) tasarım.

### 🤖 Bot Entegrasyonları
*   **Telegram & Discord:** Merkezi veri motorundan beslenen, anlık sorgulama ve topluluk bilgilendirme botları ile her platformda erişilebilirlik.

---

## 🧠 Geliştirme Vizyonu

Bu sistem, **AI-Pair Programming** metodolojisiyle hayata geçirilmiştir. Yapay zeka desteği sayesinde:
*   Karmaşık veri algoritmaları en verimli şekilde optimize edilmiştir.
*   Hata payı minimize edilmiş, yüksek performanslı ve sürdürülebilir bir kod mimarisi kurulmuştur.

---

## 🛠️ Teknik Altyapı

*   **Backend:** Python (Flask) - Modüler App Factory mimarisi.
*   **Frontend:** HTML5, CSS3 (Modern Variables), Native JavaScript.
*   **Veri Yönetimi:** SQLAlchemy ORM.
*   **Performans:** Flask-Compress ve Gelişmiş Önbellekleme (Caching) sistemleri.

---

## ⚙️ Sistem Bileşenleri ve Amaçları

Proje, birbirine entegre ancak bağımsız çalışan üç ana Python tabanlı alt sistemden oluşur:

### 1. Merkezi Web Sistemi (Flask)
Sistemin kalbidir. Kullanıcıların web üzerinden vakitlere erişmesini, konum tabanlı şehir tespitini ve REST API uç noktalarını yönetir.
*   **Amacı:** Yüksek performanslı bir kullanıcı arayüzü sunmak ve tüm ekosisteme veri servis etmek.

### 2. Bot Mikro-servisleri (Telegram & Discord)
Mesajlaşma platformları üzerinden çalışan bağımsız Python süreçleridir.
*   **Amacı:** Kullanıcıların web sitesine girmesine gerek kalmadan, bulundukları platformda anlık vakit sorgusu yapmalarını ve otomatik hatırlatmalar almalarını sağlamak.

### 3. Veri ve İşlem Otomasyonu (Scripts)
Arka planda çalışan yardımcı Python betikleridir.
*   **Amacı:** Diyanet tabanlı verileri işlemek, yıllık imsakiye dosyalarını sisteme aktarmak ve günlük içerikleri (hadis, dua vb.) organize etmek.

---

## 📂 Sistem Yapısı

```text
├── app/                  # Uygulama çekirdeği (Routes, Services, Templates)
├── bots/                 # Çoklu platform bot servisleri
├── scripts/              # Veri otomasyon betikleri
└── static/               # PWA Assets ve optimize edilmiş bileşenler
```

---

## 📄 Lisans
Bu proje **Yiğit Gülyurt** tarafından geliştirilmiştir. Tüm hakları saklıdır. Kod yapısı ve tasarım öğeleri şahsi portfolyomun bir parçasıdır; izinsiz kullanımı yasaktır.

---
**[Canlı Önizleme](https://cagrivakti.com.tr)**
