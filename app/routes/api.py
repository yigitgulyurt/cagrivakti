from flask import Blueprint, jsonify, request, current_app, abort
import logging

from app.services import UserService, PrayerService, get_daily_content, get_country_for_city, get_timezone_for_city, CITY_DISPLAY_NAME_MAPPING, COUNTRY_NAME_MAPPING
from app.extensions import cache, limiter, db, csrf
from datetime import datetime, date, timedelta
from functools import wraps
import re

api_bp = Blueprint('api', __name__)

@api_bp.route('/')
def api_anasayfa():
    return jsonify({
        'uygulama': 'Çağrı Vakti API',
        'surum': '1.0',
        'uygun_uc_noktalar': [
            {
                'yol': '/',
                'aciklama': 'API ana sayfası',
                'durum': 'Erişime Açık'
            },
            {
                'yol': '/sehirler',
                'aciklama': 'Belirli bir ülkenin şehirlerini listeler (varsayılan: TR)',
                'durum': 'Erişime Açık'
            },
            {
                'yol': '/sehirler/uluslararasi',
                'aciklama': 'Tüm ulusuz uluslararası şehirleri listeler',
                'durum': 'Erişime Açık'
            },
            {
                'yol': '/sehirler/tumu',
                'aciklama': 'Tüm şehirleri (Türkiye ve 160+ + uluslararası) listeler',
                'durum': 'Erişime Açık'
            },
            {
                'yol': '/sehirler/ara',
                'aciklama': 'Şehir adı ile arama yapar (parametre: q)',
                'durum': 'Erişime Kapalı'
            },
            {
                'yol': '/sehir/detay',
                'aciklama': 'Belirli bir şehrin detaylarını verir (parametre: sehir)',
                'durum': 'Erişime Kapalı'
            },
            {
                'yol': '/sehir/suanki_zaman',
                'aciklama': 'Belirli bir şehrin o anki zamanını verir (parametre: sehir)',
                'durum': 'Erişime Kapalı'
            },
            {
                'yol': '/sehir_kaydet',
                'aciklama': 'Şehir tercihini kaydeder (POST, parametreler: sehir, country_code)',
                'durum': 'Erişime Kapalı'
            },
            {
                'yol': '/ulkeler',
                'aciklama': 'Tüm ülkeleri listeler',
                'durum': 'Erişime Kapalı'
            },
            {
                'yol': '/ulke/detay',
                'aciklama': 'Belirli bir ülkenin detaylarını verir (parametre: kod)',
                'durum': 'Erişime Kapalı'
            },
            {
                'yol': '/cagri_vakitleri',
                'aciklama': 'Genel API v1 uç noktası',
                'durum': 'Erişime Kapalı'
            },
            {
                'yol': '/sonraki_vakit',
                'aciklama': 'Bir sonraki ezan vaktini verir',
                'durum': 'Erişime Kapalı'
            },
            {
                'yol': '/daily_content',
                'aciklama': 'Günlük içeriği verir',
                'durum': 'Erişime Kapalı'
            },

            {
                'yol': '/status',
                'aciklama': 'Sağlık kontrolü',
                'durum': 'Erişime Açık'
            }
        ]
    })

def is_latin_only(text):
    """Metnin yalnızca Latin karakterler, sayılar ve izin verilen sembollerden oluştuğunu kontrol eder."""
    if not text:
        return True
    return bool(re.match(r'^[A-Za-z0-9\-\_\s\.]+$', text))

def restrict_to_main_domain(f):
    """
    API isteklerini sadece cagrivakti.com.tr üzerinden gelenlerle kısıtlar.
    Geliştirme ortamında (localhost) ve VIP API anahtarı ile gelen isteklere izin verir.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. VIP API Anahtarı Kontrolü
        api_key = request.headers.get('X-API-Key') or request.args.get('key')
        vip_keys = current_app.config.get('VIP_API_KEYS', [])
        if api_key and api_key in vip_keys:
            return f(*args, **kwargs)

        # 2. Geliştirme Ortamı Kontrolü
        if current_app.debug or request.host.startswith('localhost') or request.host.startswith('127.0.0.1'):
            return f(*args, **kwargs)

        # 3. Referer / Origin Kontrolü
        referer = request.headers.get('Referer', '')
        origin = request.headers.get('Origin', '')
        
        allowed_domains = ['cagrivakti.com.tr', 'www.cagrivakti.com.tr']
        
        def is_allowed(url):
            if not url: return False
            return any(domain in url for domain in allowed_domains)

        if is_allowed(referer) or is_allowed(origin):
            return f(*args, **kwargs)
            
        # Eğer hiçbir şart sağlanmazsa erişimi engelle
        sec = logging.getLogger('security_logger')
        sec.warning(f"Unauthorized API access blocked | ip={request.remote_addr} path={request.full_path} referer={referer} origin={origin}")
        return jsonify({"error": "Unauthorized access. This API is restricted to cagrivakti.com.tr"}), 403
        
    return decorated_function

@api_bp.route('/sehirler')
#@restrict_to_main_domain
@cache.cached(timeout=86400, query_string=True)
def sehirleri_getir():
    country_code = request.args.get('country', 'TR')
    if not is_latin_only(country_code):
        abort(400, description="Gecersiz karakter iceren ulke kodu.")
    return jsonify(UserService.get_sehirler(country_code))

@api_bp.route('/sehirler/uluslararasi')
#@restrict_to_main_domain
@cache.cached(timeout=86400)
def uluslararasi_sehirleri_getir():
    return jsonify(UserService.get_sehirler('INT'))

@api_bp.route('/sehirler/tumu')
#@restrict_to_main_domain
@cache.cached(timeout=86400)
def tum_sehirleri_getir():
    return jsonify(UserService.get_sehirler('ALL'))

@api_bp.route('/sehirler/ara')
@restrict_to_main_domain
@cache.cached(timeout=3600, query_string=True)
def sehirleri_ara():
    arama = request.args.get('q', '').strip().lower()
    if not arama or not is_latin_only(arama):
        return jsonify([])
    tum_sehirler = UserService.get_sehirler('ALL')
    sonuclar = []
    for sehir in tum_sehirler:
        sehir_lower = sehir.lower()
        gorunen_adi = CITY_DISPLAY_NAME_MAPPING.get(sehir, sehir.replace('-', ' ').title()).lower()
        if arama in sehir_lower or arama in gorunen_adi:
            sonuclar.append(sehir)
    return jsonify(sonuclar)

@api_bp.route('/sehir/suanki_zaman')
@restrict_to_main_domain
@cache.cached(timeout=60, query_string=True)
def sehir_suanki_zaman():
    sehir = request.args.get('sehir')
    if not sehir:
        return jsonify({'error': 'Sehir bilgisi gerekli'}), 400
    if not is_latin_only(sehir):
        return jsonify({'error': 'Gecersiz karakter iceren sehir ismi'}), 400
    country_code = get_country_for_city(sehir)
    timezone = get_timezone_for_city(sehir, country_code)
    from pytz import timezone as pytz_timezone
    tz = pytz_timezone(timezone)
    suanki = datetime.now(tz)
    return jsonify({
        'sehir': sehir,
        'ulke_kodu': country_code,
        'timezone': timezone,
        'suanki_zaman': suanki.isoformat(),
        'tarih': suanki.strftime('%Y-%m-%d'),
        'saat': suanki.strftime('%H:%M:%S')
    })

@api_bp.route('/ulkeler')
@restrict_to_main_domain
@cache.cached(timeout=86400)
def ulkeleri_getir():
    tum_sehirler = UserService.get_sehirler('ALL')
    ulke_kodlari = set()
    for sehir in tum_sehirler:
        ulke_kodlari.add(get_country_for_city(sehir))
    ulkeler = []
    for kod in sorted(ulke_kodlari):
        ulkeler.append({
            'kod': kod,
            'adi': COUNTRY_NAME_MAPPING.get(kod, kod)
        })
    return jsonify(ulkeler)

@api_bp.route('/ulke/detay')
@restrict_to_main_domain
@cache.cached(timeout=86400, query_string=True)
def ulke_detay():
    ulke_kodu = request.args.get('kod')
    if not ulke_kodu or not is_latin_only(ulke_kodu):
        return jsonify({'error': 'Gecerli ulke kodu gerekli'}), 400
    ulke_adi = COUNTRY_NAME_MAPPING.get(ulke_kodu, ulke_kodu)
    sehirler = UserService.get_sehirler(ulke_kodu)
    return jsonify({
        'kod': ulke_kodu,
        'adi': ulke_adi,
        'sehirler': sehirler
    })

@api_bp.route('/sehir/detay')
@restrict_to_main_domain
@cache.cached(timeout=86400, query_string=True)
def sehir_detay():
    sehir = request.args.get('sehir')
    if not sehir:
        return jsonify({'error': 'Sehir bilgisi gerekli'}), 400
    if not is_latin_only(sehir):
        return jsonify({'error': 'Gecersiz karakter iceren sehir ismi'}), 400
    country_code = get_country_for_city(sehir)
    timezone = get_timezone_for_city(sehir, country_code)
    display_name = CITY_DISPLAY_NAME_MAPPING.get(sehir, sehir.replace('-', ' ').title())
    return jsonify({
        'sehir': sehir,
        'ulke_kodu': country_code,
        'timezone': timezone,
        'gorunen_adi': display_name
    })

@api_bp.route('/sehir_kaydet', methods=['POST'])
@restrict_to_main_domain
def sehir_kaydet():
    data = request.get_json()
    sehir = data.get('sehir')
    country_code = data.get('country_code')
    
    if not sehir:
        return jsonify({'error': 'Sehir bilgisi gerekli'}), 400
        
    if not is_latin_only(sehir) or (country_code and not is_latin_only(country_code)):
        return jsonify({'error': 'Gecersiz karakter iceren sehir veya ulke kodu'}), 400
    
    if not country_code:
        country_code = get_country_for_city(sehir)
        
    UserService.save_user_preferences(sehir, country_code)
    return jsonify({'redirect': f'/sehir/{sehir}?country={country_code}'})



@api_bp.route('/sonraki_vakit')
@restrict_to_main_domain
def sonraki_vakti_getir():
    sehir = request.args.get('sehir')
    country_code = request.args.get('country', 'TR')
    if not sehir:
        return jsonify({"error": "Sehir gerekli"}), 400
    if not is_latin_only(sehir) or not is_latin_only(country_code):
        return jsonify({"error": "Gecersiz karakter iceren sehir veya ulke kodu"}), 400
    result = PrayerService.get_next_vakit(sehir, country_code)
    return jsonify(result)

@api_bp.route('/daily_content')
@restrict_to_main_domain
@cache.cached(timeout=86400)
def daily_content():
    return jsonify(get_daily_content())

# Public API v1
@api_bp.route('/cagri_vakitleri')
@restrict_to_main_domain
def public_api_vakitler():
    sehir = request.args.get('sehir')
    country_code = request.args.get('ulke', 'TR').upper()
    tarih = request.args.get('tarih')
    ay = request.args.get('ay')
    yil = request.args.get('yil', datetime.now().year)
    tip_param = request.args.get('tip')
    is_ramadan_request = request.args.get('ramazan') == 'true'

    if not sehir:
        return jsonify({'durum': 'hata', 'mesaj': 'sehir parametresi zorunludur.', 'yardim': '/api-dokuman'}), 400

    if not is_latin_only(sehir) or not is_latin_only(country_code) or (tarih and not is_latin_only(tarih)) or (ay and not is_latin_only(str(ay))) or (yil and not is_latin_only(str(yil))) or (tip_param and not is_latin_only(tip_param)):
        return jsonify({'durum': 'hata', 'mesaj': 'Gecersiz karakter iceren parametre.'}), 400

    try:
        # Timezone bilgisini al
        from app.services import get_timezone_for_city
        timezone_str = get_timezone_for_city(sehir, country_code)

        if is_ramadan_request:
            from app.services.ramadan_service import RamadanService
            # İstenen yıl için örnek bir tarih oluştur (Ramazan genellikle yılın ortalarında olur ama garanti olsun diye yılın ortası)
            # Ancak get_ramadan_info o anki tarihi baz alıyor.
            # Bizim belirli bir yılın Ramazan'ını bulmamız lazım.
            
            target_year = int(yil)
            
            # Bu yılın Ramazan başlangıcını bulmak için basit bir döngü veya tahmin yapabiliriz.
            # Hicri takvim her yıl 11 gün geriye gelir.
            # 2025: 1 Mart
            # 2026: 18 Şubat
            # ...
            
            # RamadanService'e yeni bir metod eklemek en doğrusu olurdu ama şimdilik burada çözelim.
            # RamadanService.gregorian_to_hijri statik metodunu kullanabiliriz.
            
            # Hedef yılın ortasından başlayıp Ramazan ayını (9. ay) arayalım.
            # Veya daha basit: O yılın her ayının 1'ine bakıp Hicri 9. ayı bulana kadar tarayalım.
            
            start_date = None
            end_date = None
            
            # O yılın her gününü taramak pahalı olabilir. Ay başlarına bakalım.
            # Hicri aylar Gregoryen aylarla örtüşmez ama başlangıcı yakalamak için yeterli olabilir.
            # Daha iyi yöntem: O yılın 1 Ocak'ından itibaren Hicri 9. aya denk gelen ilk günü bulmak.
            
            # Hızlı çözüm: O yılın 1. ayından 12. ayına kadar 1. ve 15. günleri kontrol et.
            # Hicri 9. ayı bulduğumuzda, o ayın 1. gününü (start) ve son gününü (end) hesaplayalım.
            
            found = False
            # 1 Ocak'tan başla
            curr = date(target_year, 1, 1)
            # Bir sonraki yıla kadar
            while curr.year == target_year:
                h_y, h_m, h_d = RamadanService.gregorian_to_hijri(curr)
                if h_m == 9:
                    # Ramazan ayı içindeyiz!
                    # Başlangıç tarihini bulmak için:
                    # Şu anki günden (h_d - 1) gün geriye git
                    start_date = curr - timedelta(days=h_d - 1)
                    
                    # Bitiş tarihini bulmak için:
                    # Hicri aylar 29 veya 30 çeker. Tabular takvimde 9. ay 30 çeker.
                    # Start date'e 29 gün ekle (toplam 30 gün)
                    end_date = start_date + timedelta(days=29)
                    
                    found = True
                    break
                
                # 15 gün atla (Ramazan'ı kaçırmamak için 29 günden az atlamalıyız)
                curr += timedelta(days=15)
            
            if found and start_date and end_date:
                vakitler_list = PrayerService.get_vakitler_range(sehir, country_code, start_date, end_date)
                return jsonify({
                    'durum': 'basarili', 
                    'tip': 'ramazan', 
                    'data': {
                        'sehir': sehir, 
                        'ulke': country_code, 
                        'yil': yil, 
                        'vakitler': vakitler_list,
                        'timezone': timezone_str,
                        'start_date': start_date.strftime("%Y-%m-%d"),
                        'end_date': end_date.strftime("%Y-%m-%d")
                    }
                })
            else:
                return jsonify({'durum': 'hata', 'mesaj': f'{yil} yılı için Ramazan tarihleri bulunamadı.'}), 404

        if ay or tip_param == 'aylik':
            ay = int(ay) if ay else datetime.now().month
            yil = int(yil)
            start_date = date(yil, ay, 1)
            end_date = (date(yil + 1, 1, 1) if ay == 12 else date(yil, ay + 1, 1)) - timedelta(days=1)
            vakitler_list = PrayerService.get_vakitler_range(sehir, country_code, start_date, end_date)
            return jsonify({
                'durum': 'basarili', 
                'tip': 'aylik', 
                'data': {
                    'sehir': sehir, 
                    'ulke': country_code, 
                    'ay': ay, 
                    'yil': yil, 
                    'vakitler': vakitler_list,
                    'timezone': timezone_str
                }
            })

        full_year = request.args.get('tam_yil') == 'true' or tip_param == 'yillik'
        
        if full_year:
            yil = int(yil)
            vakitler_list = PrayerService.get_vakitler_range(sehir, country_code, date(yil, 1, 1), date(yil, 12, 31))
            return jsonify({
                'durum': 'basarili', 
                'tip': 'yillik', 
                'data': {
                    'sehir': sehir, 
                    'ulke': country_code, 
                    'yil': yil, 
                    'vakitler': vakitler_list,
                    'timezone': timezone_str
                }
            })

        vakitler = PrayerService.get_vakitler(sehir, country_code, tarih)
        if vakitler and vakitler.get('imsak') != "--:--":
            # Timezone'u vakitlerden ayır
            tz_info = vakitler.pop('timezone', 'Europe/Istanbul')
            
            # Vakitleri kronolojik sıraya göre düzenle
            sirali_vakitler = {}
            vakit_sirasi = ["imsak", "gunes", "ogle", "ikindi", "aksam", "yatsi"]
            for v in vakit_sirasi:
                if v in vakitler:
                    sirali_vakitler[v] = vakitler[v]
            
            # Yarının imsak vaktini de al
            yarin_tarih = None
            if tarih:
                try:
                    tarih_obj = datetime.strptime(tarih, '%Y-%m-%d')
                    yarin_tarih = (tarih_obj + timedelta(days=1)).strftime('%Y-%m-%d')
                except:
                    pass
            else:
                yarin_tarih = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            
            yarin_vakitler = PrayerService.get_vakitler(sehir, country_code, yarin_tarih)
            yarin_imsak = yarin_vakitler.get('imsak') if yarin_vakitler else None

            return jsonify({
                'durum': 'basarili', 
                'tip': 'gunluk', 
                'data': {
                    'sehir': sehir, 
                    'ulke': country_code, 
                    'tarih': tarih or datetime.now().strftime('%Y-%m-%d'), 
                    'vakitler': sirali_vakitler,
                    'timezone': tz_info,
                    'yarin': {'imsak': yarin_imsak} if yarin_imsak else None
                }
            })
        return jsonify({'durum': 'hata', 'mesaj': 'Vakit bulunamadı.'}), 404
    except Exception as e:
        return jsonify({'durum': 'hata', 'mesaj': str(e)}), 500

@api_bp.route('/status')
def health_check():
    """
    Uptime Kuma ve benzeri monitoring servisleri için gelişmiş health check endpoint'i.
    restrict_to_main_domain kasıtlı olarak uygulanmıyor — harici checker'ların
    Referer/Origin başlığı göndermediği için 403 alırlardı.
    """
    import time
    start_time = time.time()
    
    checks = {}
    http_status = 200
    critical_failure = False

    # 1. Veritabanı bağlantısı
    try:
        db_start = time.time()
        db.session.execute(db.text('SELECT 1'))
        db.session.commit()
        db_time = round((time.time() - db_start) * 1000, 2)
        checks['database'] = {
            'db_status': 'ok',
            'response_time_ms': db_time
        }
    except Exception as e:
        checks['database'] = {
            'db_status': 'error',
            'message': str(e)
        }
        critical_failure = True
        http_status = 503

    # 2. Cache bağlantısı (Redis/SimpleCache vs.)
    try:
        cache_start = time.time()
        cache.set('__healthcheck__', '1', timeout=5)
        val = cache.get('__healthcheck__')
        cache_time = round((time.time() - cache_start) * 1000, 2)
        checks['cache'] = {
            'cache_status': 'ok' if val == '1' else 'miss',
            'response_time_ms': cache_time
        }
    except Exception as e:
        checks['cache'] = {
            'cache_status': 'error',
            'message': str(e)
        }
        # Cache hatası kritik değil, servisi durdurmuyoruz

    # 3. Genel uygulama durumu ve metadata
    checks['app'] = {
        'app_status': 'ok',
        'version': current_app.config.get('APP_VERSION', '1.0'),
        'environment': 'production' if not current_app.debug else 'development'
    }

    # 4. Toplam yanıt süresi
    total_time = round((time.time() - start_time) * 1000, 2)

    # Sonuç
    return jsonify({
        'app_status': 'ok' if not critical_failure else 'degraded',
        'checks': checks,
        'total_response_time_ms': total_time,
        'timestamp': datetime.now().isoformat() + 'Z'
    }), http_status