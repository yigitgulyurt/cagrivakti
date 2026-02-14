from datetime import datetime, date, timedelta
import pytz
from app.extensions import cache
from app.models import DailyContent

class RamadanService:
    # Ramazan Tarihleri (Merkezi Yönetim)
    # Not: Bu tarihler her yıl için güncellenmelidir ya da bir API'den çekilebilir.
    # 2026 için yaklaşık tarihler:
    RAMADAN_DATES = {
        2025: {"start": date(2025, 3, 1), "end": date(2025, 3, 29), "laylat_al_qadr": date(2025, 3, 26)},
        2026: {"start": date(2026, 2, 18), "end": date(2026, 3, 19), "laylat_al_qadr": date(2026, 3, 15)},
        2027: {"start": date(2027, 2, 8), "end": date(2027, 3, 9), "laylat_al_qadr": date(2027, 3, 5)}
    }

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

        year = current_date.year
        dates = cls.RAMADAN_DATES.get(year)
        
        res = {"is_ramadan": False, "status": "none"}
        
        if dates:
            start_date = dates["start"]
            end_date = dates["end"]
            laylat_al_qadr = dates["laylat_al_qadr"]

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
