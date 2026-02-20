from datetime import datetime, date, timedelta
import pytz
from app.extensions import cache
from app.models import DailyContent

class RamadanService:
    # Otomatik hesaplama için yardımcı metodlar
    @staticmethod
    def _int_part(float_num):
        """Python'un int() fonksiyonu 0'a doğru yuvarlar, bu algoritma için yeterlidir."""
        return int(float_num)

    @staticmethod
    def gregorian_to_hijri(date_obj):
        """
        Gregoryen tarihi Hicri tarihe çevirir.
        Tabular Islamic Calendar (Kuwaiti Algorithm) kullanılır.
        """
        y = date_obj.year
        m = date_obj.month
        d = date_obj.day

        if m < 3:
            y -= 1
            m += 12

        a = RamadanService._int_part(y / 100.0)
        b = 2 - a + RamadanService._int_part(a / 4.0)

        if y < 1583: b = 0
        if y == 1582:
            if m > 10: b = -10
            if m == 10:
                b = 0
                if d > 4: b = -10

        jd = RamadanService._int_part(365.25 * (y + 4716)) + \
             RamadanService._int_part(30.6001 * (m + 1)) + \
             d + b - 1524

        z = jd - 1948440 + 10632
        n = RamadanService._int_part((z - 1) / 10631.0)
        z = z - 10631 * n + 354
        j = (RamadanService._int_part((10985 - z) / 5316.0)) * (RamadanService._int_part((50 * z) / 17719.0)) + \
            (RamadanService._int_part(z / 5670.0)) * (RamadanService._int_part((43 * z) / 15238.0))
        z = z - (RamadanService._int_part((30 - j) / 15.0)) * (RamadanService._int_part((17719 * j) / 50.0)) - \
            (RamadanService._int_part(j / 16.0)) * (RamadanService._int_part((15238 * j) / 43.0)) + 29
        
        m = RamadanService._int_part((24 * z) / 709.0)
        d = z - RamadanService._int_part((709 * m) / 24.0)
        y = 30 * n + j - 30

        return y, m, d

    @staticmethod
    def hijri_to_gregorian(year, month, day):
        """
        Hicri tarihi Gregoryen tarihe çevirir.
        """
        jd = RamadanService._int_part((11 * year + 3) / 30.0) + \
             354 * year + \
             30 * month - \
             RamadanService._int_part((month - 1) / 2.0) + \
             day + 1948440 - 385

        if jd > 2299160:
            l = jd + 68569
            n = RamadanService._int_part((4 * l) / 146097.0)
            l = l - RamadanService._int_part((146097 * n + 3) / 4.0)
            i = RamadanService._int_part((4000 * (l + 1)) / 1461001.0)
            l = l - RamadanService._int_part((1461 * i) / 4.0) + 31
            j = RamadanService._int_part((80 * l) / 2447.0)
            d = l - RamadanService._int_part((2447 * j) / 80.0)
            l = RamadanService._int_part(j / 11.0)
            m = j + 2 - 12 * l
            y = 100 * (n - 49) + i + l
        else:
            j = jd + 1402
            k = RamadanService._int_part((j - 1) / 1461.0)
            l = j - 1461 * k
            n = RamadanService._int_part((l - 1) / 365.0) - RamadanService._int_part(l / 1461.0)
            i = l - 365 * n + 30
            j = RamadanService._int_part((80 * i) / 2447.0)
            d = i - RamadanService._int_part((2447 * j) / 80.0)
            i = RamadanService._int_part(j / 11.0)
            m = j + 2 - 12 * i
            y = 4 * k + n + i - 4716

        return date(y, m, d)

    @classmethod
    def get_ramadan_info(cls, current_date=None):
        if current_date is None:
            # Türkiye saatine göre bugün
            tz = pytz.timezone('Europe/Istanbul')
            current_date = datetime.now(tz).date()
        
        # Cache anahtarı: ramadan_info_YYYY-MM-DD
        cache_key = f"ramadan_info_{current_date.strftime('%Y-%m-%d')}"
        cached_info = cache.get(cache_key)
        if cached_info:
            return cached_info

        # Otomatik Hesaplama
        h_year, h_month, h_day = cls.gregorian_to_hijri(current_date)
        
        res = {"is_ramadan": False, "status": "none"}

        # Ramazan Ayı (9. Ay)
        if h_month == 9:
            # Ramazan'ın başlangıcı (Hicri Yıl, 9, 1)
            start_date = cls.hijri_to_gregorian(h_year, 9, 1)
            # Ramazan'ın bitişi (Hicri Yıl, 9, 30) - Tabular takvimde 9. ay 30 çeker
            end_date = cls.hijri_to_gregorian(h_year, 9, 30)
            # Kadir Gecesi (27. Gece - 26. günün akşamı başlar ama genellikle 27. gün olarak işaretlenir)
            laylat_al_qadr = cls.hijri_to_gregorian(h_year, 9, 27)
            
            current_day = h_day
            days_remaining = 30 - current_day # Basit hesap
            is_laylat_al_qadr = (h_day == 27)

            res = {
                "is_ramadan": True,
                "status": "active",
                "current_day": current_day,
                "days_remaining": days_remaining,
                "is_laylat_al_qadr": is_laylat_al_qadr,
                "end_date": end_date,
                "ramadan_content": cls.get_ramadan_content(current_day)
            }
        
        # Ramazan Öncesi veya Sonrası (Sıradaki Ramazan'ı bul)
        else:
            # Eğer ay 9'dan küçükse bu yılın Ramazan'ı gelecek
            if h_month < 9:
                target_h_year = h_year
            # Eğer ay 9'dan büyükse gelecek yılın Ramazan'ı gelecek
            else:
                target_h_year = h_year + 1
            
            start_date = cls.hijri_to_gregorian(target_h_year, 9, 1)
            days_left = (start_date - current_date).days
            
            # Eğer çok uzaksa (örn. 300+ gün) ve kullanıcı sadece "bu yılki bitti mi"yi merak ediyorsa
            # Ancak "upcoming" her zaman mantıklıdır.
            
            # Geriye dönük uyumluluk: Eğer bu yılın Ramazan'ı bittiyse "finished" dönebiliriz
            # Ama kullanıcı "sürekli döngü" istiyorsa upcoming daha iyidir.
            # Mevcut yapıya sadık kalmak için:
            # Eğer h_month > 9 ise (Ramazan bitti) -> finished
            # Eğer h_month < 9 ise (Ramazan geliyor) -> upcoming
            
            if h_month > 9:
                res = {
                    "is_ramadan": False,
                    "status": "finished",
                    "next_ramadan_date": start_date, # Ekstra bilgi
                    "days_to_next": days_left
                }
            else:
                res = {
                    "is_ramadan": False,
                    "status": "upcoming",
                    "days_to_start": days_left,
                    "start_date": start_date
                }

        # Sonucu cache'e kaydet (24 saat)
        cache.set(cache_key, res, timeout=86400)
        return res

    @classmethod
    def get_ramadan_content(cls, day_number):
        """Ramazan gününe özel içerik döndürür (Rastgele ve Tekrarsız)."""
        from app.extensions import db
        try:
            # 1. Hiç gösterilmemiş ramazan içeriklerini getir
            content = DailyContent.query.filter_by(
                category='ramadan', 
                is_active=True,
                last_shown=None
            ).order_by(db.func.random()).first()
            
            # 2. Hepsi gösterildiyse en eski gösterileni getir (sıfırla)
            if not content:
                content = DailyContent.query.filter_by(
                    category='ramadan', 
                    is_active=True
                ).order_by(DailyContent.last_shown.asc(), db.func.random()).first()
            
            if content:
                # Gösterilme tarihini güncelle
                content.last_shown = datetime.now().date()
                db.session.commit()
                return content.text
                
        except Exception as e:
            db.session.rollback()
            print(f"Ramadan content error: {e}")

        # Fallback
        return "Oruç, sadece aç kalmak değil, ruhu terbiye etmektir."
