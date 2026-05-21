from datetime import datetime, date, timedelta
import pytz
from app.extensions import cache
from app.services.ramadan_service import RamadanService


class DiniGunlerService:
    """Dini günleri ve kandilleri yöneten servis."""
    
    @classmethod
    def get_dini_gunler(cls, current_date=None):
        """Yaklaşan ve bu yılki tüm dini günleri döndürür."""
        if current_date is None:
            tz = pytz.timezone('Europe/Istanbul')
            current_date = datetime.now(tz).date()
        
        cache_key = f"dini_gunler_{current_date.strftime('%Y-%m-%d')}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        h_year, h_month, h_day = RamadanService.gregorian_to_hijri(current_date)
        
        gunler = []
        
        # Kandiller (Hicri ay ve gün olarak)
        kandiller = [
            {"ad": "Regaip Kandili", "h_ay": 1, "h_gun": 27},
            {"ad": "Miraç Kandili", "h_ay": 2, "h_gun": 27},
            {"ad": "Berat Kandili", "h_ay": 8, "h_gun": 15},
            {"ad": "Kadir Gecesi", "h_ay": 9, "h_gun": 27},
        ]
        
        # Bayramlar
        bayramlar = [
            {"ad": "Ramazan Bayramı", "h_ay": 10, "h_gun": 1, "gun_sayisi": 3},
            {"ad": "Kurban Bayramı", "h_ay": 12, "h_gun": 10, "gun_sayisi": 4},
        ]
        
        # Kandilleri hesapla
        for kandil in kandiller:
            try:
                # Bu yılki
                g_date = RamadanService.hijri_to_gregorian(h_year, kandil["h_ay"], kandil["h_gun"])
                gunler.append({
                    "ad": kandil["ad"],
                    "tarih": g_date,
                    "tur": "kandil",
                    "kalan_gun": (g_date - current_date).days
                })
            except:
                pass
        
        # Ramazan başlangıcı
        try:
            ramazan_baslangic = RamadanService.hijri_to_gregorian(h_year, 9, 1)
            gunler.append({
                "ad": "Ramazan Başlangıcı",
                "tarih": ramazan_baslangic,
                "tur": "ramazan",
                "kalan_gun": (ramazan_baslangic - current_date).days
            })
        except:
            pass
        
        # Bayramları hesapla
        for bayram in bayramlar:
            try:
                g_date = RamadanService.hijri_to_gregorian(h_year, bayram["h_ay"], bayram["h_gun"])
                gunler.append({
                    "ad": bayram["ad"],
                    "tarih": g_date,
                    "tur": "bayram",
                    "kalan_gun": (g_date - current_date).days,
                    "gun_sayisi": bayram["gun_sayisi"]
                })
            except:
                pass
        
        # Tarihe göre sırala
        gunler_sirali = sorted(gunler, key=lambda x: x["tarih"])
        
        # Sonucu cache'e kaydet (1 saat)
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

