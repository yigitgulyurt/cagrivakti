# 🌙 Çağrı Vakti — Proje Genel Bakış / Project Overview

Bu belge, **Çağrı Vakti** projesinin amacını, teknik yapısını ve sunduğu özellikleri genel bir bakış açısıyla sunar.

- [🇹🇷 Türkçe](https://github.com/yigitgulyurt/cagrivakti#-t%C3%BCrk%C3%A7e)
- [🇺🇸 English](https://github.com/yigitgulyurt/cagrivakti#-english)
---

## 🇹🇷 Türkçe

### 🎯 Amaç ve Motivasyon
Çağrı Vakti, günümüzün dijital ihtiyaçlarına cevap veren; modern, hızlı ve tamamen ücretsiz bir dini rehber platformudur. Projenin temel vizyonu, karmaşık ve reklamlarla dolu alternatiflerin aksine, kullanıcıya en saf ve işlevsel deneyimi sunmaktır. T.C. Diyanet İşleri Başkanlığı'ndan alınan resmi verileri, kullanıcı dostu bir arayüz ve yenilikçi araçlarla harmanlayarak her an her yerden erişilebilir bir "dijital asistan" olmayı hedefler.

### ⚙️ Teknik Mimari
Proje, yüksek performans ve sürdürülebilirlik odaklı modern bir teknoloji yığını üzerine inşa edilmiştir:
- **Arka Yüz (Backend):** Güçlü ve esnek Python (Flask) çatısı ile geliştirilmiştir.
- **Sunucu Yönetimi:** Üretim ortamında yüksek trafik yüklerini karşılamak için Nginx ve Gunicorn ikilisi kullanılmaktadır.
- **Veri ve Önbellek:** Verilerin hızlı sunulması için akıllı önbellekleme (Caching) mekanizmaları devrededir.
- **Platformlar Arası Erişim:** 
    - **PWA (Progressive Web App):** Web sitesi, bir uygulama gibi telefona yüklenebilir ve çevrimdışı çalışma desteği sunar.
    - **Bot Entegrasyonları:** Telegram ve Discord botları sayesinde vakit bilgileri sosyal platformlara taşınır.
    - **Masaüstü:** Rainmeter entegrasyonu ile Windows masaüstünde canlı vakit takibi sağlanır.

### ✨ Özellikler ve Sayfalar
- **Canlı Namaz Vakitleri:** 81 il ve dünya genelindeki şehirler için anlık güncellenen vakitler ve bir sonraki vakte kalan süreyi gösteren canlı geri sayım.
- **Otomatik Konum:** Tarayıcı üzerinden tek tıkla konum tespiti yaparak şehre özel vakitlerin anında yüklenmesi.
- **2026 İmsakiye:** Ramazan ayına özel kapsamlı sahur ve iftar vakitleri çizelgesi.
- **Kıble Pusulası:** Harita destekli, hassas ve görsel kıble yönü tespit aracı.
- **Bilgi Köşesi:** Temel dini bilgiler, ibadet rehberleri ve günlük içeriklerin yer aldığı zengin kütüphane.
- **Web Bileşeni (Widget):** Diğer web sitesi sahiplerinin kendi sitelerine ekleyebileceği özelleştirilebilir vakit kartı.
- **Ekstra Araçlar:** QR kod okuyucu, asal sayı kontrolü gibi günlük yardımcı araçlar ve "Under the Red Sky" adlı mini oyun deneyimi.
- **Atatürk Sayfası:** Milli değerlerimize saygı duruşu niteliğinde özel bir bölüm.

### 🚀 Gelecek Planları
- **İçerik Genişletme:** Bilgi Köşesi'ndeki rehberlerin ve makalelerin sayısını artırarak daha kapsamlı bir ansiklopedi haline gelmek.
- **Gelişmiş Bildirimler:** Tarayıcı ve botlar üzerinden kişiselleştirilebilir ezan vakti hatırlatıcıları.
- **Mobil Deneyim:** PWA deneyimini daha da ileri taşıyarak yerel uygulama akıcılığında yeni özellikler eklemek.
- **Topluluk Araçları:** Kullanıcıların interaktif olarak katılabileceği etkinlik ve paylaşım bölümleri.

---

## 🇺🇸 English

### 🎯 Purpose & Motivation
Çağrı Vakti is a modern, fast, and completely free religious guide platform designed to meet today's digital needs. The core vision of the project is to provide users with the purest and most functional experience, unlike alternatives that are often cluttered with ads. By blending official data from the Presidency of Religious Affairs (Diyanet) with a user-friendly interface and innovative tools, it aims to be a "digital assistant" accessible anytime, anywhere.

### ⚙️ Technical Architecture
The project is built on a modern technology stack focused on high performance and sustainability:
- **Backend:** Developed using the powerful and flexible Python (Flask) framework.
- **Server Management:** Nginx and Gunicorn are utilized in the production environment to handle high traffic loads efficiently.
- **Data & Caching:** Smart caching mechanisms are in place to ensure rapid data delivery.
- **Cross-Platform Access:**
    - **PWA (Progressive Web App):** The website can be installed on mobile devices like a native app and offers offline support.
    - **Bot Integrations:** Prayer time information is extended to social platforms via Telegram and Discord bots.
    - **Desktop:** Live prayer time tracking is available on Windows desktops through Rainmeter integration.

### ✨ Features & Pages
- **Live Prayer Times:** Instant updates for 81 provinces and cities worldwide, featuring a live countdown to the next prayer time.
- **Automatic Location:** One-click location detection via the browser to instantly load city-specific times.
- **2026 Ramadan Schedule:** A comprehensive sahur and iftar timetable specifically for the month of Ramadan.
- **Qibla Compass:** A map-supported, precise, and visual tool for determining the direction of the Qibla.
- **Info Corner:** A rich library containing basic religious information, worship guides, and daily spiritual content.
- **Web Widget:** A customizable prayer time card that other website owners can easily embed into their own sites.
- **Extra Tools:** Daily utility tools such as a QR code reader, prime number checker, and a mini-game experience titled "Under the Red Sky."
- **Ataturk Memorial:** A special section dedicated to honoring national values.

### 🚀 Future Plans
- **Content Expansion:** Increasing the number of guides and articles in the Info Corner to transform it into a more comprehensive encyclopedia.
- **Advanced Notifications:** Customizable prayer time reminders via browsers and social bots.
- **Mobile Experience:** Further enhancing the PWA experience to add new features with the smoothness of a native application.
- **Community Tools:** Developing interactive sections where users can participate in events and sharing.
