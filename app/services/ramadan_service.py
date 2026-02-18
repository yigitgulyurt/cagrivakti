from datetime import datetime, date, timedelta
import pytz
import requests
from app.extensions import cache
from app.models import DailyContent

class RamadanService:
    @classmethod
    def get_ramadan_info(cls, current_date=None):
        if current_date is None:
            # Türkiye saatine göre bugün
            tz = pytz.timezone('Europe/Istanbul')
            current_date = datetime.now(tz).date()
        
        # Cache anahtarı: ramadan_info_v2_YYYY-MM-DD
        cache_key = f"ramadan_info_v2_{current_date.strftime('%Y-%m-%d')}"
        cached_info = cache.get(cache_key)
        if cached_info:
            return cached_info

        # 1. Bugünün Hijri tarihini öğren
        hijri_date = cls._get_hijri_date(current_date)
        if not hijri_date:
            # API hatası durumunda fallback (boş döndür)
            return {"is_ramadan": False, "status": "error"}
            
        h_year = int(hijri_date['year'])
        
        # 2. Bu Hijri yılın Ramazan başlangıç ve bitişini bul
        dates = cls._get_ramadan_dates_for_hijri_year(h_year)
        
        if not dates:
             return {"is_ramadan": False, "status": "error"}

        start_date = dates['start']
        end_date = dates['end']
        laylat_al_qadr = dates['laylat_al_qadr']
        
        res = {"is_ramadan": False, "status": "none"}

        # Ramazan Öncesi (Geri Sayım)
        if current_date < start_date:
            days_left = (start_date - current_date).days
            res = {
                "is_ramadan": False,
                "status": "upcoming",
                "days_to_start": days_left,
                "start_date": start_date
            }
        
        # Ramazan Sırası
        elif start_date <= current_date <= end_date:
            current_day = (current_date - start_date).days + 1
            days_remaining = (end_date - current_date).days
            is_laylat_al_qadr = (current_date == laylat_al_qadr)
            
            res = {
                "is_ramadan": True,
                "status": "active",
                "current_day": current_day,
                "days_remaining": days_remaining,
                "is_laylat_al_qadr": is_laylat_al_qadr,
                "end_date": end_date,
                "ramadan_content": cls.get_ramadan_content(current_day)
            }
        
        # Ramazan Sonrası
        else:
            res = {
                "is_ramadan": False,
                "status": "finished"
            }
            
        # Sonucu cache'e kaydet (1 saat)
        cache.set(cache_key, res, timeout=3600)
        return res

    @staticmethod
    def _get_hijri_date(g_date):
        """Verilen Gregorian tarihinin Hijri karşılığını API'den çeker."""
        try:
            date_str = g_date.strftime("%d-%m-%Y")
            url = f"http://api.aladhan.com/v1/gToH?date={date_str}"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                return r.json()['data']['hijri']
        except Exception as e:
            print(f"Hijri date error: {e}")
        return None

    @classmethod
    def get_ramadan_dates_by_year(cls, year):
        """
        Verilen Gregorian yıl için Ramazan tarihlerini döndürür.
        Önce o yıla denk gelen Hijri yılı tahmin eder, sonra API'den kesin tarihleri alır.
        """
        # Hijri yıl tahmini (Yaklaşık)
        h_year_est = int((year - 622) * 33 / 32)
        
        # Olası Hijri yılları kontrol et (Önceki, Mevcut, Sonraki)
        # Çünkü Ramazan yılı 11 gün geri kayar, bazen yıl atlayabilir veya aynı yıla 2 ramazan düşebilir
        for h in [h_year_est, h_year_est - 1, h_year_est + 1]:
            dates = cls._get_ramadan_dates_for_hijri_year(h)
            if dates:
                # Eğer Ramazan başlangıcı bu yıl içindeyse
                if dates['start'].year == year:
                    return dates
                # Veya bitişi bu yıl içindeyse (Ocak ayında biten Ramazan)
                elif dates['end'].year == year:
                     # Ama biz genellikle o yılın Ramazan'ı deyince o yıl başlayan veya büyük kısmı o yılda olanı kastederiz.
                     # API mantığına göre 'start' o yıl olmalı.
                     pass
        
        # Bulamazsa None
        return None

    @classmethod
    def _get_ramadan_dates_for_hijri_year(cls, h_year):
        """Verilen Hijri yıl için Ramazan başlangıç, bitiş ve Kadir gecesi tarihlerini bulur."""
        cache_key = f"ramadan_dates_h_{h_year}"
        cached = cache.get(cache_key)
        if cached:
            return cached
            
        try:
            # 1 Ramazan (Başlangıç)
            start_g = cls._get_gregorian_from_hijri(1, 9, h_year)
            
            # 1 Şevval (Bitişin ertesi günü - Bayram)
            eid_g = cls._get_gregorian_from_hijri(1, 10, h_year)
            
            # 27 Ramazan (Kadir Gecesi)
            qadr_g = cls._get_gregorian_from_hijri(27, 9, h_year)
            
            if start_g and eid_g and qadr_g:
                end_g = eid_g - timedelta(days=1)
                
                res = {
                    "start": start_g,
                    "end": end_g,
                    "laylat_al_qadr": qadr_g
                }
                # Bu tarihleri uzun süre cacheleyebiliriz (30 gün)
                cache.set(cache_key, res, timeout=86400 * 30)
                return res
        except Exception as e:
            print(f"Ramadan calculation error: {e}")
            
        return None

    @staticmethod
    def _get_gregorian_from_hijri(day, month, year):
        """Hijri tarihi Gregorian tarihe çevirir."""
        try:
            url = f"http://api.aladhan.com/v1/hToG?date={day}-{month}-{year}"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                d_str = r.json()['data']['gregorian']['date']
                return datetime.strptime(d_str, "%d-%m-%Y").date()
        except Exception:
            pass
        return None

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
