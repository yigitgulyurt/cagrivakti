from datetime import datetime, date, timedelta
import pytz
from app.extensions import cache


class MilliGunlerService:
    """Milli günleri ve özel günleri yöneten servis."""

    @classmethod
    def get_milli_gunler(cls, current_date=None):
        if current_date is None:
            tz = pytz.timezone('Europe/Istanbul')
            current_date = datetime.now(tz).date()

        cache_key = f"milli_gunler_{current_date.strftime('%Y-%m-%d')}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        gunler = []
        current_year = current_date.year

        # Türkiye'nin Milli ve Özel Günleri
        milli_gun_listesi = [
            {
                "ad": "Yılbaşı",
                "gun": 1,
                "ay": 1,
                "tur": "milli",
                "aciklama": "Yeni yılın ilk günü"
            },
            {
                "ad": "8 Mart Dünya Kadınlar Günü",
                "gun": 8,
                "ay": 3,
                "tur": "milli",
                "aciklama": "Dünya Kadınlar Günü"
            },
            {
                "ad": "23 Nisan Ulusal Egemenlik ve Çocuk Bayramı",
                "gun": 23,
                "ay": 4,
                "tur": "bayram",
                "aciklama": "TBMM'nin kuruluş yıldönümü ve çocuk bayramı"
            },
            {
                "ad": "1 Mayıs Emek ve Dayanışma Günü",
                "gun": 1,
                "ay": 5,
                "tur": "milli",
                "aciklama": "Dünya Emek ve Dayanışma Günü"
            },
            {
                "ad": "3 Mayıs Basın Bayramı",
                "gun": 3,
                "ay": 5,
                "tur": "milli",
                "aciklama": "Türkiye Basın Bayramı"
            },
            {
                "ad": "19 Mayıs Atatürk'ü Anma, Gençlik ve Spor Bayramı",
                "gun": 19,
                "ay": 5,
                "tur": "bayram",
                "aciklama": "Samsun'a çıkış yıldönümü ve gençlik bayramı"
            },
            {
                "ad": "15 Temmuz Demokrasi ve Milli Birlik Günü",
                "gun": 15,
                "ay": 7,
                "tur": "milli",
                "aciklama": "15 Temmuz Demokrasi ve Milli Birlik Günü"
            },
            {
                "ad": "30 Ağustos Zafer Bayramı",
                "gun": 30,
                "ay": 8,
                "tur": "bayram",
                "aciklama": "Büyük Zafer'in yıldönümü"
            },
            {
                "ad": "9 Eylül İzmir'in Kurtuluşu",
                "gun": 9,
                "ay": 9,
                "tur": "milli",
                "aciklama": "İzmir'in Kurtuluş Yıldönümü"
            },
            {
                "ad": "5 Ekim Dünya Öğretmenler Günü",
                "gun": 5,
                "ay": 10,
                "tur": "milli",
                "aciklama": "Dünya Öğretmenler Günü"
            },
            {
                "ad": "29 Ekim Cumhuriyet Bayramı",
                "gun": 29,
                "ay": 10,
                "tur": "bayram",
                "aciklama": "Türkiye Cumhuriyeti'nin kuruluş yıldönümü"
            },
            {
                "ad": "10 Kasım Atatürk'ü Anma Günü",
                "gun": 10,
                "ay": 11,
                "tur": "milli",
                "aciklama": "Gazi Mustafa Kemal Atatürk'ün ölüm yıldönümü"
            },
            {
                "ad": "10 Aralık İnsan Hakları Günü",
                "gun": 10,
                "ay": 12,
                "tur": "milli",
                "aciklama": "Dünya İnsan Hakları Günü"
            },
        ]

        for gun in milli_gun_listesi:
            # Mevcut yıl ve gelecek yıl için tarihler oluştur
            for yil in [current_year, current_year + 1]:
                try:
                    gun_tarihi = date(yil, gun["ay"], gun["gun"])
                    kalan_gun = (gun_tarihi - current_date).days

                    # Geçmiş günleri ekleme ama sadece bir kez
                    if kalan_gun >= -10:
                        gunler.append({
                            "ad": gun["ad"],
                            "tarih": gun_tarihi,
                            "tur": gun["tur"],
                            "aciklama": gun["aciklama"],
                            "kalan_gun": kalan_gun
                        })
                except:
                    pass

        # Tarihe göre sırala
        gunler_sirali = sorted(gunler, key=lambda x: x["tarih"])
        cache.set(cache_key, gunler_sirali, timeout=3600)
        return gunler_sirali

    @classmethod
    def format_turkish_date(cls, dt):
        TURKISH_MONTHS = [
            '', 'Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
            'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'
        ]
        TURKISH_DAYS = [
            'Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar'
        ]
        day = dt.day
        month = TURKISH_MONTHS[dt.month]
        year = dt.year
        weekday = TURKISH_DAYS[dt.weekday()]
        return f"{day} {month} {year} {weekday}"
