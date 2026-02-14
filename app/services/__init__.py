import os
import json
import time
import requests
from datetime import datetime, timedelta
import pytz
from app.extensions import db, cache
from app.models import NamazVakti, DailyContent, Guide
from flask import request, session
from .ramadan_service import RamadanService

# Varsayılan değerler
DEFAULT_COUNTRY = 'TR'
DEFAULT_CITY = 'Istanbul'
DEFAULT_TZ = 'Europe/Istanbul'

# Uygulama kök dizinini al
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

# Bellek içi singleton veriler
_CITY_TIMEZONE_MAPPING_CACHE = None

def get_timezone_for_city(sehir, country_code='TR'):
    """
    Şehir ve ülke koduna göre timezone döndürür.
    """
    global _CITY_TIMEZONE_MAPPING_CACHE
    if _CITY_TIMEZONE_MAPPING_CACHE is None:
        _CITY_TIMEZONE_MAPPING_CACHE = {
            # Turkey
            ('istanbul', 'tr'): 'Europe/Istanbul',
            ('ankara', 'tr'): 'Europe/Istanbul',
            ('izmir', 'tr'): 'Europe/Istanbul',
            # International - North America
            ('washington', 'us'): 'America/New_York',
            ('new-york', 'us'): 'America/New_York',
            ('los-angeles', 'us'): 'America/Los_Angeles',
            ('ottawa', 'ca'): 'America/Toronto',
            ('toronto', 'ca'): 'America/Toronto',
            ('mexico-city', 'mx'): 'America/Mexico_City',
            ('havana', 'cu'): 'America/Havana',
            # South America
            ('brasilia', 'br'): 'America/Sao_Paulo',
            ('sao-paulo', 'br'): 'America/Sao_Paulo',
            ('rio-de-janeiro', 'br'): 'America/Sao_Paulo',
            ('buenos-aires', 'ar'): 'America/Argentina/Buenos_Aires',
            ('santiago', 'cl'): 'America/Santiago',
            ('bogota', 'co'): 'America/Bogota',
            ('lima', 'pe'): 'America/Lima',
            ('caracas', 've'): 'America/Caracas',
            # Europe
            ('london', 'gb'): 'Europe/London',
            ('paris', 'fr'): 'Europe/Paris',
            ('berlin', 'de'): 'Europe/Berlin',
            ('rome', 'it'): 'Europe/Rome',
            ('madrid', 'es'): 'Europe/Madrid',
            ('amsterdam', 'nl'): 'Europe/Amsterdam',
            ('brussels', 'be'): 'Europe/Brussels',
            ('vienna', 'at'): 'Europe/Vienna',
            ('bern', 'ch'): 'Europe/Zurich',
            ('lisbon', 'pt'): 'Europe/Lisbon',
            ('athens', 'gr'): 'Europe/Athens',
            ('dublin', 'ie'): 'Europe/Dublin',
            ('stockholm', 'se'): 'Europe/Stockholm',
            ('oslo', 'no'): 'Europe/Oslo',
            ('copenhagen', 'dk'): 'Europe/Copenhagen',
            ('helsinki', 'fi'): 'Europe/Helsinki',
            ('reykjavik', 'is'): 'Atlantic/Reykjavik',
            ('moscow', 'ru'): 'Europe/Moscow',
            ('kiev', 'ua'): 'Europe/Kiev',
            ('warsaw', 'pl'): 'Europe/Warsaw',
            ('prague', 'cz'): 'Europe/Prague',
            ('budapest', 'hu'): 'Europe/Budapest',
            ('bucharest', 'ro'): 'Europe/Bucharest',
            ('sofia', 'bg'): 'Europe/Sofia',
            ('belgrade', 'rs'): 'Europe/Belgrade',
            ('sarajevo', 'ba'): 'Europe/Sarajevo',
            ('skopje', 'mk'): 'Europe/Skopje',
            ('tirana', 'al'): 'Europe/Tirane',
            ('pristina', 'xk'): 'Europe/Belgrade',
            ('zagreb', 'hr'): 'Europe/Zagreb',
            # Middle East
            ('mecca', 'sa'): 'Asia/Riyadh',
            ('medina', 'sa'): 'Asia/Riyadh',
            ('riyadh', 'sa'): 'Asia/Riyadh',
            ('baku', 'az'): 'Asia/Baku',
            ('tbilisi', 'ge'): 'Asia/Tbilisi',
            ('yerevan', 'am'): 'Asia/Yerevan',
            ('baghdad', 'iq'): 'Asia/Baghdad',
            ('tehran', 'ir'): 'Asia/Tehran',
            ('damascus', 'sy'): 'Asia/Damascus',
            ('beirut', 'lb'): 'Asia/Beirut',
            ('amman', 'jo'): 'Asia/Amman',
            ('jerusalem', 'il'): 'Asia/Jerusalem',
            ('palestine', 'ps'): 'Asia/Gaza',
            ('dubai', 'ae'): 'Asia/Dubai',
            ('kuwait', 'kw'): 'Asia/Kuwait',
            ('doha', 'qa'): 'Asia/Qatar',
            ('muscat', 'om'): 'Asia/Muscat',
            ('manama', 'bh'): 'Asia/Bahrain',
            ('sanaa', 'ye'): 'Asia/Aden',
            ('nicosia', 'cy'): 'Asia/Nicosia',
            # Asia
            ('nur-sultan', 'kz'): 'Asia/Almaty',
            ('almaty', 'kz'): 'Asia/Almaty',
            ('tashkent', 'uz'): 'Asia/Tashkent',
            ('ashgabat', 'tm'): 'Asia/Ashgabat',
            ('bishkek', 'kg'): 'Asia/Bishkek',
            ('dushanbe', 'tj'): 'Asia/Dushanbe',
            ('kabul', 'af'): 'Asia/Kabul',
            ('islamabad', 'pk'): 'Asia/Karachi',
            ('new-delhi', 'in'): 'Asia/Kolkata',
            ('tokyo', 'jp'): 'Asia/Tokyo',
            ('seoul', 'kr'): 'Asia/Seoul',
            ('beijing', 'cn'): 'Asia/Shanghai',
            ('jakarta', 'id'): 'Asia/Jakarta',
            ('singapore', 'sg'): 'Asia/Singapore',
            ('kuala-lumpur', 'my'): 'Asia/Kuala_Lumpur',
            ('bangkok', 'th'): 'Asia/Bangkok',
            ('manila', 'ph'): 'Asia/Manila',
            ('hanoi', 'vn'): 'Asia/Ho_Chi_Minh',
            # Oceania
            ('sydney', 'au'): 'Australia/Sydney',
            ('melbourne', 'au'): 'Australia/Melbourne',
            ('perth', 'au'): 'Australia/Perth',
            ('auckland', 'nz'): 'Pacific/Auckland',
            # Africa
            ('cairo', 'eg'): 'Africa/Cairo',
            ('tripoli', 'ly'): 'Africa/Tripoli',
            ('tunis', 'tn'): 'Africa/Tunis',
            ('algiers', 'dz'): 'Africa/Algiers',
            ('rabat', 'ma'): 'Africa/Casablanca',
            ('khartoum', 'sd'): 'Africa/Khartoum',
            ('abuja', 'ng'): 'Africa/Lagos',
            ('dakar', 'sn'): 'Africa/Dakar',
            ('nairobi', 'ke'): 'Africa/Nairobi',
            ('addis-ababa', 'et'): 'Africa/Addis_Ababa',
            ('pretoria', 'za'): 'Africa/Johannesburg',
            ('cape-town', 'za'): 'Africa/Johannesburg',
            ('kinshasa', 'cd'): 'Africa/Kinshasa',
            ('juba', 'ss'): 'Africa/Juba'
        }
    
    # Doğrudan erişim (O(1))
    return _CITY_TIMEZONE_MAPPING_CACHE.get((sehir.lower(), country_code.lower()), DEFAULT_TZ)

def get_country_for_city(sehir):
    """Şehrin bağlı olduğu ülke kodunu döndürür."""
    mapping = {
        # Türkiye
        'Istanbul': 'TR', 'Ankara': 'TR', 'Izmir': 'TR',
        # North America
        'Washington': 'US', 'New-York': 'US', 'Los-Angeles': 'US',
        'Ottawa': 'CA', 'Toronto': 'CA', 'Mexico-City': 'MX', 'Havana': 'CU',
        # South America
        'Brasilia': 'BR', 'Sao-Paulo': 'BR', 'Rio-de-Janeiro': 'BR',
        'Buenos-Aires': 'AR', 'Santiago': 'CL', 'Bogota': 'CO',
        'Lima': 'PE', 'Caracas': 'VE',
        # Europe
        'London': 'GB', 'Paris': 'FR', 'Berlin': 'DE', 'Rome': 'IT',
        'Madrid': 'ES', 'Amsterdam': 'NL', 'Brussels': 'BE', 'Vienna': 'AT',
        'Bern': 'CH', 'Lisbon': 'PT', 'Athens': 'GR', 'Dublin': 'IE',
        'Stockholm': 'SE', 'Oslo': 'NO', 'Copenhagen': 'DK', 'Helsinki': 'FI',
        'Reykjavik': 'IS', 'Moscow': 'RU', 'Kiev': 'UA', 'Warsaw': 'PL',
        'Prague': 'CZ', 'Budapest': 'HU', 'Bucharest': 'RO', 'Sofia': 'BG',
        'Belgrade': 'RS', 'Sarajevo': 'BA', 'Skopje': 'MK', 'Tirana': 'AL',
        'Pristina': 'XK', 'Zagreb': 'HR',
        # Middle East
        'Mecca': 'SA', 'Medina': 'SA', 'Riyadh': 'SA', 'Baku': 'AZ',
        'Tbilisi': 'GE', 'Yerevan': 'AM', 'Baghdad': 'IQ', 'Tehran': 'IR',
        'Damascus': 'SY', 'Beirut': 'LB', 'Amman': 'JO', 'Jerusalem': 'IL',
        'Palestine': 'PS', 'Dubai': 'AE', 'Kuwait': 'KW', 'Doha': 'QA',
        'Muscat': 'OM', 'Manama': 'BH', 'Sanaa': 'YE', 'Nicosia': 'CY',
        # Asia
        'Nur-Sultan': 'KZ', 'Almaty': 'KZ', 'Tashkent': 'UZ', 'Ashgabat': 'TM',
        'Bishkek': 'KG', 'Dushanbe': 'TJ', 'Kabul': 'AF', 'Islamabad': 'PK',
        'New-Delhi': 'IN', 'Tokyo': 'JP', 'Seoul': 'KR', 'Beijing': 'CN',
        'Jakarta': 'ID', 'Singapore': 'SG', 'Kuala-Lumpur': 'MY',
        'Bangkok': 'TH', 'Manila': 'PH', 'Hanoi': 'VN',
        # Oceania
        'Sydney': 'AU', 'Melbourne': 'AU', 'Perth': 'AU', 'Auckland': 'NZ',
        # Africa
        'Cairo': 'EG', 'Tripoli': 'LY', 'Tunis': 'TN', 'Algiers': 'DZ',
        'Rabat': 'MA', 'Khartoum': 'SD', 'Abuja': 'NG', 'Dakar': 'SN',
        'Nairobi': 'KE', 'Addis-Ababa': 'ET', 'Pretoria': 'ZA', 'Cape-Town': 'ZA',
        'Kinshasa': 'CD', 'Juba': 'SS'
    }
    return mapping.get(sehir, 'TR')

def get_current_date(timezone_str=DEFAULT_TZ):
    """Verilen timezone'a göre yerel saati döndürür."""
    tz = pytz.timezone(timezone_str)
    return datetime.now(tz)

class UserService:
    @staticmethod
    def get_current_user_preferences(db_session=None):
        """Kullanıcının tercih ettiği şehir ve ülkeyi döndürür. (Session > Default)"""
        # Session Kontrolü
        try:
            if 'sehir' in session:
                return {
                    'sehir': session.get('sehir'),
                    'country_code': session.get('country_code', DEFAULT_COUNTRY)
                }
        except RuntimeError:
            pass
        
        # Varsayılan
        return {'sehir': DEFAULT_CITY, 'country_code': DEFAULT_COUNTRY}

    @staticmethod
    def save_user_preferences(sehir, country_code=DEFAULT_COUNTRY, db_session=None):
        try:
            session['sehir'] = sehir
            session['country_code'] = country_code
        except RuntimeError:
            pass

    @staticmethod
    def get_sehirler(country_code=DEFAULT_COUNTRY):
        # Ülkeye göre şehir listesi
        if country_code == 'TR':
            return [
                "Adana", "Adiyaman", "Afyonkarahisar", "Agri", "Aksaray", "Amasya", "Ankara", "Antalya", "Ardahan", "Artvin",
                "Aydin", "Balikesir", "Bartin", "Batman", "Bayburt", "Bilecik", "Bingol", "Bitlis", "Bolu", "Burdur", "Bursa",
                "Canakkale", "Cankiri", "Corum", "Denizli", "Diyarbakir", "Duzce", "Edirne", "Elazig", "Erzincan", "Erzurum",
                "Eskisehir", "Gaziantep", "Giresun", "Gumushane", "Hakkari", "Hatay", "Igdir", "Isparta", "Istanbul", "Izmir",
                "Kahramanmaras", "Karabuk", "Karaman", "Kars", "Kastamonu", "Kayseri", "Kirikkale", "Kirklareli", "Kirsehir",
                "Kilis", "Kocaeli", "Konya", "Kutahya", "Malatya", "Manisa", "Mardin", "Mersin", "Mugla", "Mus", "Nevsehir",
                "Nigde", "Ordu", "Osmaniye", "Rize", "Sakarya", "Samsun", "Sanliurfa", "Siirt", "Sinop", "Sirnak", "Sivas",
                "Tekirdag", "Tokat", "Trabzon", "Tunceli", "Usak", "Van", "Yalova", "Yozgat", "Zonguldak"
            ]
        elif country_code == 'INT':
            return [
                "Washington", "New-York", "Los-Angeles", "Ottawa", "Toronto", "Mexico-City", "Havana",
                "Brasilia", "Sao-Paulo", "Rio-de-Janeiro", "Buenos-Aires", "Santiago", "Bogota", "Lima", "Caracas",
                "London", "Paris", "Berlin", "Rome", "Madrid", "Amsterdam", "Brussels", "Vienna", "Bern", "Lisbon",
                "Athens", "Dublin", "Stockholm", "Oslo", "Copenhagen", "Helsinki", "Reykjavik", "Moscow", "Kiev",
                "Warsaw", "Prague", "Budapest", "Bucharest", "Sofia", "Belgrade", "Sarajevo", "Skopje", "Tirana",
                "Pristina", "Zagreb", "Mecca", "Medina", "Riyadh", "Baku", "Tbilisi", "Yerevan", "Baghdad", "Tehran",
                "Damascus", "Beirut", "Amman", "Jerusalem", "Palestine", "Dubai", "Kuwait", "Doha", "Muscat", "Manama",
                "Sanaa", "Nicosia", "Nur-Sultan", "Almaty", "Tashkent", "Ashgabat", "Bishkek", "Dushanbe", "Kabul",
                "Islamabad", "New-Delhi", "Tokyo", "Seoul", "Beijing", "Jakarta", "Singapore", "Kuala-Lumpur",
                "Bangkok", "Manila", "Hanoi", "Sydney", "Melbourne", "Perth", "Auckland", "Cairo", "Tripoli",
                "Tunis", "Algiers", "Rabat", "Khartoum", "Abuja", "Dakar", "Nairobi", "Addis-Ababa", "Pretoria",
                "Cape-Town", "Kinshasa", "Juba"
            ]
        elif country_code == 'ALL':
            return UserService.get_sehirler('TR') + UserService.get_sehirler('INT')
        return [DEFAULT_CITY]

class PrayerService:
    _CACHE_TTL = 3600  # Varsayılan 1 saat

    @staticmethod
    def _calculate_dynamic_ttl(tz_str):
        """
        Gece yarısına kadar olan süreyi saniye cinsinden hesaplar.
        En az 3600 saniye (1 saat) döner.
        """
        try:
            tz = pytz.timezone(tz_str)
            now = datetime.now(tz)
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            ttl = int((tomorrow - now).total_seconds())
            return max(ttl, 3600)
        except Exception:
            return 3600

    @staticmethod
    def get_vakitler(sehir, country_code=None, tarih_dt=None, db_session=None):
        """
        Merkezi vakit alma servisi. Timezone-aware çalışır.
        Sıralama: Cache -> DB -> API
        """
        if db_session is None:
            db_session = db.session

        # Eğer country_code verilmemişse veya 'TR' ise ama şehir uluslararası listedeyse düzelt
        if country_code is None or country_code == 'TR':
            detected_country = get_country_for_city(sehir)
            country_code = detected_country
        
        timezone_str = get_timezone_for_city(sehir, country_code)
        tz = pytz.timezone(timezone_str)

        # Eğer tarih verilmemişse o timezone'un "bugün"ünü al
        if tarih_dt is None:
            tarih_dt = datetime.now(tz)
        elif isinstance(tarih_dt, str):
            tarih_dt = datetime.strptime(tarih_dt, "%Y-%m-%d")
        
        # Tarihi timezone-aware yap
        if tarih_dt.tzinfo is None:
            tarih_dt = tz.localize(tarih_dt)
            
        tarih_str = tarih_dt.strftime("%Y-%m-%d")
        
        # 1. Flask-Caching Kontrolü
        cache_key = f"vakitler_{country_code}_{sehir}_{tarih_str}_{timezone_str}"
        cached_data = cache.get(cache_key)
        if cached_data:
            from flask import current_app
            current_app.logger.info(f"Cache Hit: {cache_key}")
            return cached_data
        
        from flask import current_app
        current_app.logger.info(f"Cache Miss: {cache_key}")
        
        # 2. DB Kontrolü
        try:
            vakit = db_session.query(NamazVakti).filter_by(
                sehir=sehir, country_code=country_code, tarih=tarih_dt.date()
            ).first()
            if vakit:
                res = {
                    "imsak": vakit.imsak, "gunes": vakit.gunes, "ogle": vakit.ogle,
                    "ikindi": vakit.ikindi, "aksam": vakit.aksam, "yatsi": vakit.yatsi,
                    "timezone": vakit.timezone
                }
                # Cache'e ekle
                cache.set(cache_key, res, timeout=PrayerService._CACHE_TTL)
                return res
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"DB query error for {sehir}: {e}")
        
        # 3. API Fallback
        if country_code == 'TR':
            diyanet_vakit = PrayerService._get_from_diyanet(sehir, tarih_dt)
            if diyanet_vakit:
                PrayerService._save_to_db(sehir, country_code, timezone_str, tarih_dt.date(), diyanet_vakit, db_session)
                res = {**diyanet_vakit, "timezone": timezone_str}
                # Dinamik TTL hesapla (Gece yarısına kadar)
                dynamic_ttl = PrayerService._calculate_dynamic_ttl(timezone_str)
                cache.set(cache_key, res, timeout=dynamic_ttl)
                return res
        else:
            # Uluslararası şehirler için Aladhan API
            aladhan_vakit = PrayerService._get_from_aladhan(sehir, country_code, tarih_dt)
            if aladhan_vakit:
                PrayerService._save_to_db(sehir, country_code, timezone_str, tarih_dt.date(), aladhan_vakit, db_session)
                res = {**aladhan_vakit, "timezone": timezone_str}
                # Dinamik TTL hesapla (Gece yarısına kadar)
                dynamic_ttl = PrayerService._calculate_dynamic_ttl(timezone_str)
                cache.set(cache_key, res, timeout=dynamic_ttl)
                return res

        # Son çare: Boş veri döndür
        return {
            "imsak": "--:--", "gunes": "--:--", "ogle": "--:--",
            "ikindi": "--:--", "aksam": "--:--", "yatsi": "--:--",
            "timezone": timezone_str
        }

    @staticmethod
    def get_next_vakit(sehir, country_code=DEFAULT_COUNTRY, simdi=None):
        """
        Bir sonraki namaz vaktini ve kalan süreyi hesaplar.
        Gece yarısı ve timezone farklarını gözetir.
        """
        timezone_str = get_timezone_for_city(sehir, country_code)
        tz = pytz.timezone(timezone_str)

        if simdi is None:
            simdi = datetime.now(tz)
        elif simdi.tzinfo is None:
            simdi = tz.localize(simdi)
            
        bugun = simdi.date()
        vakitler = PrayerService.get_vakitler(sehir, country_code, simdi)
        
        yarin = simdi + timedelta(days=1)
        yarin_vakitler = PrayerService.get_vakitler(sehir, country_code, yarin)
        
        vakit_sirasi = ["imsak", "gunes", "ogle", "ikindi", "aksam", "yatsi"]
        
        # Bugünün kalan vakitlerini kontrol et
        for vakit_adi in vakit_sirasi:
            vakit_saati_str = vakitler.get(vakit_adi)
            if not vakit_saati_str or vakit_saati_str in ["null", "--:--"]:
                continue
                
            try:
                # Vakit saatini o günün tarihiyle birleştir ve timezone-aware yap
                vakit_zamani = tz.localize(datetime.strptime(f"{bugun.strftime('%Y-%m-%d')} {vakit_saati_str}", "%Y-%m-%d %H:%M"))
                
                if vakit_zamani > simdi:
                    return {
                        "sonraki_vakit": vakit_adi,
                        "vakit": vakit_saati_str,
                        "kalan_sure": int((vakit_zamani - simdi).total_seconds()),
                        "timezone": timezone_str
                    }
            except ValueError:
                continue
        
        # Eğer bugün bittiyse yarının ilk vaktini (imsak) döndür
        yarin_imsak_str = yarin_vakitler.get("imsak")
        if yarin_imsak_str and yarin_imsak_str not in ["null", "--:--"]:
            try:
                vakit_zamani = tz.localize(datetime.strptime(f"{yarin.strftime('%Y-%m-%d')} {yarin_imsak_str}", "%Y-%m-%d %H:%M"))
                return {
                    "sonraki_vakit": "imsak",
                    "vakit": yarin_imsak_str,
                    "kalan_sure": int((vakit_zamani - simdi).total_seconds()),
                    "timezone": timezone_str
                }
            except ValueError:
                pass
                
        return None

    @staticmethod
    def get_vakitler_range(sehir, country_code, start_date, end_date, db_session=None):
        """
        Belirli bir tarih aralığındaki vakitleri döner.
        """
        if db_session is None:
            db_session = db.session
            
        try:
            vakitler = db_session.query(NamazVakti).filter(
                NamazVakti.sehir == sehir,
                NamazVakti.country_code == country_code,
                NamazVakti.tarih >= start_date,
                NamazVakti.tarih <= end_date
            ).order_by(NamazVakti.tarih).all()
            
            return [{
                "tarih": v.tarih.strftime("%Y-%m-%d"),
                "imsak": v.imsak, "gunes": v.gunes, "ogle": v.ogle,
                "ikindi": v.ikindi, "aksam": v.aksam, "yatsi": v.yatsi
            } for v in vakitler]
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"DB range query error for {sehir}: {e}")
            return []

    @staticmethod
    def _save_to_db(sehir, country_code, timezone_str, tarih_date, vakitler, db_session=None):
        if db_session is None:
            db_session = db.session
            
        try:
            # Varsa eskiyi sil (Upsert)
            db_session.query(NamazVakti).filter_by(
                sehir=sehir, country_code=country_code, tarih=tarih_date
            ).delete()

            yeni_vakit = NamazVakti(
                sehir=sehir, country_code=country_code, timezone=timezone_str, tarih=tarih_date,
                imsak=vakitler['imsak'], gunes=vakitler['gunes'],
                ogle=vakitler['ogle'], ikindi=vakitler['ikindi'],
                aksam=vakitler['aksam'], yatsi=vakitler['yatsi']
            )
            db_session.add(yeni_vakit)
            db_session.commit()
        except Exception as e:
            db_session.rollback()
            from flask import current_app
            current_app.logger.error(f"DB save error for {sehir}: {e}")

    @staticmethod
    def _get_from_aladhan(sehir, country_code, tarih_dt):
        """Aladhan API'den vakitleri çeker."""
        try:
            tarih_str = tarih_dt.strftime("%d-%m-%Y")
            # Aladhan API URL (Method 13 = Diyanet)
            # Not: Bazı şehirler için ülke kodu zorunludur.
            url = f"http://api.aladhan.com/v1/timingsByCity/{tarih_str}"
            params = {
                "city": sehir,
                "country": country_code,
                "method": 13
            }
            # Debug için log eklenebilir
            # print(f"Aladhan API Request: {url} params: {params}")
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                timings = data.get("data", {}).get("timings", {})
                if timings:
                    return {
                        "imsak": timings.get("Fajr"),
                        "gunes": timings.get("Sunrise"),
                        "ogle": timings.get("Dhuhr"),
                        "ikindi": timings.get("Asr"),
                        "aksam": timings.get("Maghrib"),
                        "yatsi": timings.get("Isha")
                    }
            else:
                from flask import current_app
                current_app.logger.error(f"Aladhan API Error for {sehir}: {response.status_code} - {response.text}")
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Aladhan API exception for {sehir}: {e}")
        return None

    @staticmethod
    def _get_from_diyanet(sehir, tarih_dt):
        """Diyanet API simülasyonu."""
        return None


@cache.cached(timeout=86400, key_prefix='daily_content')
def get_daily_content():
    """Günün içeriğini döndürür (Rastgele ve Tekrarsız)."""
    try:
        # 1. Hiç gösterilmemiş olanları getir
        content = DailyContent.query.filter_by(category='daily', is_active=True, last_shown=None).order_by(db.func.random()).first()
        
        # 2. Eğer hepsi gösterildiyse (elimizdekiler bittiyse), en eski gösterileni getir (sıfırla)
        if not content:
            content = DailyContent.query.filter_by(category='daily', is_active=True).order_by(DailyContent.last_shown.asc(), db.func.random()).first()
        
        if content:
            # Gösterilme tarihini güncelle
            content.last_shown = datetime.now().date()
            db.session.commit()
            return content.to_dict()
        
        # Yedek içerik
        return {
            "type": "hadis",
            "text": "Cennet'in sekiz kapısından biri 'Reyyan' adını taşır ki, buradan ancak oruçlular girer.",
            "source": "Buhârî, Savm, 4"
        }
    except Exception as e:
        db.session.rollback()
        from flask import current_app
        current_app.logger.error(f"Daily content error: {e}")
        return {
            "type": "hadis",
            "text": "Cennet'in sekiz kapısından biri 'Reyyan' adını taşır ki, buradan ancak oruçlular girer.",
            "source": "Buhârî, Savm, 4"
        }

def get_guides():
    """Tüm bilgi köşesi yazılarını veritabanından döndürür."""
    try:
        guides = Guide.query.filter_by(is_active=True).order_by(Guide.last_updated.desc()).all()
        return [guide.to_dict() for guide in guides]
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Get guides error: {e}")
    return []

def get_guide_by_slug(slug):
    """Slug'a göre tek bir bilgi köşesi yazısı veritabanından döndürür."""
    try:
        guide = Guide.query.filter_by(slug=slug, is_active=True).first()
        if guide:
            return guide.to_dict()
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Get guide by slug error: {e}")
    return None
