# 🌙 Çağrı Vakti

**[cagrivakti.com.tr](https://cagrivakti.com.tr)** — Namaz vakitleri, imsakiye ve dini içerikler için modern, ücretsiz Türkçe platform.

---

## Ne Sunuyor?

- **Namaz vakitleri** — Türkiye'nin 81 ili ve 200'den fazla ülke için T.C. Diyanet İşleri Başkanlığı kaynaklı resmi veriler
- **Otomatik konum tespiti** — "Konumumu Bul" ile şehri otomatik belirle; tercihler tarayıcıda saklanır
- **Geri sayım** — Bir sonraki vakite saniyelik canlı geri sayım
- **2026 İmsakiye** — Sahur ve iftar vakitleri dahil güncel Ramazan imsakiyesi
- **Kıble pusulası** — Harita tabanlı anlık kıble yönü tespiti
- **Bilgi Köşesi** — Abdest, zekat, itikaf gibi konularda rehber içerikler
- **PWA desteği** — Ana ekrana ekle, uygulama gibi kullan, çevrimdışı çalışır
- **Telegram botu** — [@cagrivaktibot](https://t.me/cagrivaktibot) üzerinden vakit sorgulama ve bildirim
- **Windows widget** — Rainmeter ile masaüstünde namaz vakti takibi (`.rmskin` paketi dahil)
- **Site widget'ı** — Kendi web sitenize entegre edebileceğiniz ücretsiz vakit bileşeni

---

## Hızlı Erişim

| Özellik | Bağlantı |
|---|---|
| Ana Sayfa | [cagrivakti.com.tr](https://cagrivakti.com.tr) |
| Şehir Seçimi | [/sehir](https://cagrivakti.com.tr/sehir) |
| İmsakiye | [/imsakiye](https://cagrivakti.com.tr/imsakiye) |
| Kıble Pusulası | [/kible-pusulasi](https://cagrivakti.com.tr/kible-pusulasi) |
| Bilgi Köşesi | [/bilgi-kosesi](https://cagrivakti.com.tr/bilgi-kosesi) |
| Telegram Bot | [@cagrivaktibot](https://t.me/cagrivaktibot) |
| Rainmeter Widget | [/rainmeter-rehber](https://cagrivakti.com.tr/rainmeter-rehber) |

---

## Teknik

Python (Flask) tabanlı, Gunicorn + Nginx üzerinde çalışan üretim ortamına sahip bir web uygulaması. Telegram ve Discord bot entegrasyonları bağımsız süreçler olarak çalışmakta; veri işleme ve imsakiye aktarımı betikler aracılığıyla otomatize edilmektedir.

---

## Lisans

Bu proje **Yiğit Gülyurt** tarafından geliştirilmiştir. Tüm hakları saklıdır. İzinsiz kullanım yasaktır.