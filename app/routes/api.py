from flask import Blueprint, jsonify, request, current_app, abort
from app.services import UserService, PrayerService, get_daily_content
from app.extensions import cache, limiter
from datetime import datetime, date, timedelta
import re

api_bp = Blueprint('api', __name__, url_prefix='/api')

def is_latin_only(text):
    """Metnin yalnızca Latin karakterler, sayılar ve izin verilen sembollerden oluştuğunu kontrol eder."""
    if not text:
        return True
    return bool(re.match(r'^[A-Za-z0-9\-\_\s\.]+$', text))

@api_bp.route('/sehirler')
@cache.cached(timeout=86400, query_string=True)
def sehirleri_getir():
    country_code = request.args.get('country', 'TR')
    if not is_latin_only(country_code):
        abort(400, description="Gecersiz karakter iceren ulke kodu.")
    return jsonify(UserService.get_sehirler(country_code))

@api_bp.route('/sehir_kaydet', methods=['POST'])
def sehir_kaydet():
    data = request.get_json()
    sehir = data.get('sehir')
    country_code = data.get('country_code', 'TR')
    
    if not sehir:
        return jsonify({'error': 'Sehir bilgisi gerekli'}), 400
        
    if not is_latin_only(sehir) or not is_latin_only(country_code):
        return jsonify({'error': 'Gecersiz karakter iceren sehir veya ulke kodu'}), 400
        
    UserService.save_user_preferences(sehir, country_code)
    return jsonify({'redirect': f'/sehir/{sehir}?country={country_code}'})

@api_bp.route('/namaz_vakitleri')
@cache.cached(timeout=3600, query_string=True)
def namaz_vakitlerini_al_api():
    sehir = request.args.get('sehir')
    country_code = request.args.get('country', 'TR')
    tarih = request.args.get('date')
    
    if not sehir:
        return jsonify({'error': 'Sehir bilgisi gerekli'}), 400
        
    if not is_latin_only(sehir) or not is_latin_only(country_code) or (tarih and not is_latin_only(tarih)):
        return jsonify({'error': 'Gecersiz karakter iceren parametre'}), 400
        
    try:
        vakitler = PrayerService.get_vakitler(sehir, country_code, tarih)
        if vakitler:
            # Timezone'u ayır ve vakitleri sırala
            tz_info = vakitler.pop('timezone', 'Europe/Istanbul')
            sirali_vakitler = {}
            for v in ["imsak", "gunes", "ogle", "ikindi", "aksam", "yatsi"]:
                if v in vakitler:
                    sirali_vakitler[v] = vakitler[v]
            
            return jsonify({
                'vakitler': sirali_vakitler,
                'timezone': tz_info
            })
        return jsonify({'error': 'Vakit bulunamadı'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/sonraki_vakit')
def sonraki_vakti_getir():
    sehir = request.args.get('sehir')
    country_code = request.args.get('country', 'TR')
    if not sehir:
        return jsonify({"error": "Sehir gerekli"}), 400
    if not is_latin_only(sehir) or not is_latin_only(country_code):
        return jsonify({"error": "Gecersiz karakter iceren sehir veya ulke kodu"}), 400
    result = PrayerService.get_next_vakit(sehir, country_code)
    return jsonify(result)

@api_bp.route('/update_city', methods=['POST'])
def update_city():
    try:
        data = request.get_json()
        new_city = data.get('sehir')
        if not new_city:
            return jsonify({"success": False, "error": "Sehir gerekli"})
        if not is_latin_only(new_city):
            return jsonify({"success": False, "error": "Gecersiz karakter iceren sehir ismi"})
        UserService.save_user_city(new_city)
        return jsonify({"success": True, "message": f"Sehir {new_city} olarak guncellendi"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@api_bp.route('/daily_content')
@cache.cached(timeout=86400)
def daily_content():
    return jsonify(get_daily_content())

@api_bp.route('/widget-data')
def widget_data():
    """
    PWA Widget'ı için özel veri endpoint'i.
    Cookie'den kullanıcı şehrini okur ve bir sonraki vakit bilgisini döndürür.
    """
    # CORS headers ekleyerek widget'ın erişimini garanti altına al
    response_headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
    }

    sehir = request.cookies.get('user_city')
    if not sehir:
        # Cookie yoksa varsayılan
        sehir = 'istanbul'
    
    # Güvenlik kontrolü
    if not is_latin_only(sehir):
        sehir = 'istanbul'
        
    try:
        # Bir sonraki vakti al
        next_vakit_data = PrayerService.get_next_vakit(sehir, 'TR')
        
        if not next_vakit_data or 'error' in next_vakit_data:
            return jsonify({
                "template": "cagri-vakti-template",
                "data": {
                    "city": sehir.upper(),
                    "next_prayer": "Hata",
                    "remaining_time": "--:--",
                    "next_prayer_time": "--:--"
                }
            }), 200, response_headers

        # Veriyi hazırla
        remaining = next_vakit_data.get('kalan_sure', '')
        # "02:15:30" formatından "02 sa 15 dk" formatına çevir (sadece saat ve dakika)
        if remaining:
            parts = remaining.split(':')
            if len(parts) >= 2:
                remaining = f"{parts[0]} sa {parts[1]} dk"
        
        # Windows Widget formatına uygun JSON yapısı (Düz JSON)
        return jsonify({
            "city": sehir.replace('-', ' ').title(),
            "next_prayer": next_vakit_data.get('sonraki_vakit_ismi', '').title(),
            "remaining_time": remaining,
            "next_prayer_time": next_vakit_data.get('sonraki_vakit_saati', '')
        }), 200, response_headers
    except Exception as e:
        current_app.logger.error(f"Widget Data Error: {str(e)}")
        return jsonify({
            "city": "Hata",
            "next_prayer": "",
            "remaining_time": "",
            "next_prayer_time": ""
        }), 200, response_headers

# Public API v1
@api_bp.route('/vakitler')
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
            ramadan_info = RamadanService.get_ramadan_info()
            
            # RamadanService'den o yıla ait tarihleri al
            dates = RamadanService.RAMADAN_DATES.get(int(yil))
            if dates:
                start_date = dates["start"]
                end_date = dates["end"]
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
                return jsonify({'durum': 'hata', 'mesaj': 'Ramazan tarihleri bulunamadı.'}), 404

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
            
            return jsonify({
                'durum': 'basarili', 
                'tip': 'gunluk', 
                'data': {
                    'sehir': sehir, 
                    'ulke': country_code, 
                    'tarih': tarih or datetime.now().strftime('%Y-%m-%d'), 
                    'vakitler': sirali_vakitler,
                    'timezone': tz_info
                }
            })
        return jsonify({'durum': 'hata', 'mesaj': 'Vakit bulunamadı.'}), 404
    except Exception as e:
        return jsonify({'durum': 'hata', 'mesaj': str(e)}), 500
