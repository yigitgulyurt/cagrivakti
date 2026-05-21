from datetime import datetime, date, timedelta
import pytz
from app.extensions import cache
from app.services.ramadan_service import RamadanService


class DiniGunlerService:
    """Dini günleri ve kandilleri yöneten servis."""
    
@classmethod
def get_dini_gunler(cls, current_date=None):
    if current_date is None:
        tz = pytz.timezone('Europe/Istanbul')
        current_date = datetime.now(tz).date()

    cache_key = f"dini_gunler_{current_date.strftime('%Y-%m-%d')}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    h_year, h_month, h_day = RamadanService.gregorian_to_hijri(current_date)

    def en_yakin_tarih(h_ay, h_gun, offset_gun=0):
        """
        Verilen Hicri ay/gün için h_year ve h_year+1'i dener,
        current_date'e en yakın ve henüz çok geçmemiş olanı seçer.
        offset_gun: algoritma kayması düzeltmesi (-1 kandiller için)
        """
        candidates = []
        for yil in [h_year - 1, h_year, h_year + 1]:
            try:
                g = RamadanService.hijri_to_gregorian(yil, h_ay, h_gun)
                g = g + timedelta(days=offset_gun)
                candidates.append(g)
            except:
                pass
        if not candidates:
            return None
        # current_date'e en yakın, tercihen geçmemiş olanı bul
        gelecek = [c for c in candidates if c >= current_date]
        gecmis  = [c for c in candidates if c < current_date]
        if gelecek:
            return min(gelecek)
        return max(gecmis)  # hepsi geçtiyse en son geçeni döndür

    gunler = []

    # Regaip Kandili: Recep 1'den sonraki ilk Cuma
    for yil in [h_year - 1, h_year, h_year + 1]:
        try:
            recep_1 = RamadanService.hijri_to_gregorian(yil, 7, 1)
            ilk_cuma = recep_1
            while ilk_cuma.weekday() != 4:
                ilk_cuma += timedelta(days=1)
            # Algoritma offset'i burada da uygula
            ilk_cuma -= timedelta(days=1)
            if ilk_cuma >= current_date:
                gunler.append({
                    "ad": "Regaip Kandili",
                    "tarih": ilk_cuma,
                    "tur": "kandil",
                    "kalan_gun": (ilk_cuma - current_date).days
                })
                break
        except:
            pass

    # Kandiller: algoritma 1 gün ileri hesaplıyor, -1 offset uygula
    kandiller = [
        {"ad": "Aşure Günü",     "h_ay": 1, "h_gun": 10, "offset": 0},
        {"ad": "Mevlid Kandili", "h_ay": 3, "h_gun": 12, "offset": 0},
        {"ad": "Miraç Kandili",  "h_ay": 7, "h_gun": 27, "offset": -1},
        {"ad": "Berat Kandili",  "h_ay": 8, "h_gun": 15, "offset": -1},
        {"ad": "Kadir Gecesi",   "h_ay": 9, "h_gun": 27, "offset":  0},
    ]

    for k in kandiller:
        g_date = en_yakin_tarih(k["h_ay"], k["h_gun"], k["offset"])
        if g_date:
            gunler.append({
                "ad": k["ad"],
                "tarih": g_date,
                "tur": "kandil",
                "kalan_gun": (g_date - current_date).days
            })

    # Özel günler
    ozel_gunler = [
        {"ad": "Hicri Yılbaşı",         "h_ay": 1,  "h_gun": 1,  "offset": 0},
        {"ad": "Üç Ayların Başlangıcı", "h_ay": 7,  "h_gun": 1,  "offset": 0},
        {"ad": "Ramazan Başlangıcı",    "h_ay": 9,  "h_gun": 1,  "offset": -1},
        {"ad": "Arefe (Kurban)",        "h_ay": 12, "h_gun": 9,  "offset": 0},
    ]

    for gun in ozel_gunler:
        g_date = en_yakin_tarih(gun["h_ay"], gun["h_gun"], gun["offset"])
        if g_date:
            gunler.append({
                "ad": gun["ad"],
                "tarih": g_date,
                "tur": "ozel",
                "kalan_gun": (g_date - current_date).days
            })

    # Bayramlar
    bayramlar = [
        {"ad": "Ramazan Bayramı", "h_ay": 10, "h_gun": 1,  "gun_sayisi": 3, "offset": 0},
        {"ad": "Kurban Bayramı",  "h_ay": 12, "h_gun": 10, "gun_sayisi": 4, "offset": 0},
    ]

    for b in bayramlar:
        g_date = en_yakin_tarih(b["h_ay"], b["h_gun"], b["offset"])
        if g_date:
            gunler.append({
                "ad": b["ad"],
                "tarih": g_date,
                "tur": "bayram",
                "kalan_gun": (g_date - current_date).days,
                "gun_sayisi": b["gun_sayisi"]
            })

    gunler_sirali = sorted(gunler, key=lambda x: x["tarih"])
    cache.set(cache_key, gunler_sirali, timeout=3600)
    return gunler_sirali
    
    @classmethod
    def format_turkish_date(cls, dt):
        """Tarihi Türkçe formatta döndürür."""
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

