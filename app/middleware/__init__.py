from flask import request, render_template, current_app, g, session
import time
import uuid
from app.models import UtmVisit
from app.extensions import db

# İç ağ IP'lerini tek bir kez loglamak için cache
_internal_ip_cache = set()
_internal_ip_cache_timeout = 3600  # 1 saat (saniye)

def setup_middleware(app):
    @app.before_request
    def set_request_context():
        g.request_id = uuid.uuid4().hex[:12]

    @app.before_request
    def check_instagram_browser():
        user_agent = request.headers.get('User-Agent', '').lower()
        if 'instagram' in user_agent and ('fbav' in user_agent or 'instagram' in user_agent):
            return render_template('utils/open_in_browser.html')

    @app.before_request
    def capture_utm_params():
        # UTM parametrelerini kontrol et
        utm_params = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content']
        has_utm = any(request.args.get(param) for param in utm_params)
        
        # Eğer UTM parametreleri varsa ve zaten session'da saklanmamışsa
        if has_utm and 'utm_data' not in session:
            session['utm_data'] = {
                'utm_source': request.args.get('utm_source'),
                'utm_medium': request.args.get('utm_medium'),
                'utm_campaign': request.args.get('utm_campaign'),
                'utm_term': request.args.get('utm_term'),
                'utm_content': request.args.get('utm_content'),
                'initial_path': request.path,
                'initial_referrer': request.headers.get('Referer')
            }
            # Session'ı kalıcı yap
            session.permanent = True
        
        # Eğer session'da UTM verisi varsa veya şu anda UTM parametreleri varsa, kaydet
        if has_utm or 'utm_data' in session:
            try:
                # Kullanıcı verilerini al
                user_uid = getattr(g, 'user_uid', '-')
                ip_address = request.remote_addr
                user_agent = request.headers.get('User-Agent', '')[:500]
                referrer = request.headers.get('Referer', '')[:255]
                
                # UTM verilerini al (ya yeni ya session'dan)
                utm_data = session.get('utm_data', {}) if not has_utm else {
                    'utm_source': request.args.get('utm_source'),
                    'utm_medium': request.args.get('utm_medium'),
                    'utm_campaign': request.args.get('utm_campaign'),
                    'utm_term': request.args.get('utm_term'),
                    'utm_content': request.args.get('utm_content')
                }
                
                # Veritabanına kaydet
                visit = UtmVisit(
                    user_uid=user_uid,
                    ip_address=ip_address,
                    path=request.path,
                    referrer=referrer,
                    user_agent=user_agent,
                    utm_source=utm_data.get('utm_source'),
                    utm_medium=utm_data.get('utm_medium'),
                    utm_campaign=utm_data.get('utm_campaign'),
                    utm_term=utm_data.get('utm_term'),
                    utm_content=utm_data.get('utm_content')
                )
                db.session.add(visit)
                db.session.commit()
            except Exception as e:
                current_app.logger.error(f"UTM kaydetme hatası: {e}")

    @app.after_request
    def set_security_headers(response):
        """Güvenlik başlıklarını (Security Headers) ekle."""

        # Embed sayfaları için özel izinler
        if request.path.startswith('/embed/'):
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://code.jquery.com https://cdn.jsdelivr.net https://unpkg.com/html5-qrcode https://js.yigitgulyurt.net.tr; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://font.yigitgulyurt.net.tr https://css.yigitgulyurt.net.tr; "
                "font-src 'self' https://font.yigitgulyurt.net.tr; "
                "img-src 'self' data: https:; "
                "connect-src 'self' https://nominatim.openstreetmap.org https://api.cagrivakti.com.tr https://js.yigitgulyurt.net.tr https://css.yigitgulyurt.net.tr; "
                "frame-ancestors *; "
                "base-uri 'self'; "
                "form-action 'self';"
            )
            response.headers['Content-Security-Policy'] = csp
            response.headers.pop('X-Frame-Options', None)
            response.headers['Access-Control-Allow-Origin'] = '*'

        elif request.path.startswith('/kaynak/'):
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob: https://cdnjs.cloudflare.com; "
                "style-src 'self' 'unsafe-inline'; "
                "font-src 'self' data:; "
                "img-src 'self' data: blob: https:; "
                "connect-src 'self' blob:; "
                "frame-src 'self'; "
                "frame-ancestors 'self'; "
                "worker-src 'self' blob:; "
                "base-uri 'self'; "
                "form-action 'self';"
            )
            response.headers['Content-Security-Policy'] = csp
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'

        else:
            # Standart sayfalar
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://code.jquery.com https://cdn.jsdelivr.net https://unpkg.com/html5-qrcode https://js.yigitgulyurt.net.tr; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://font.yigitgulyurt.net.tr https://css.yigitgulyurt.net.tr; "
                "font-src 'self' https://font.yigitgulyurt.net.tr; "
                "img-src 'self' data: https:; "
                "connect-src 'self' https://nominatim.openstreetmap.org https://api.cagrivakti.com.tr https://js.yigitgulyurt.net.tr https://css.yigitgulyurt.net.tr; "
                "frame-src 'self' *; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "worker-src 'self' blob:; "
                "media-src 'self' blob:;"
            )
            response.headers['Content-Security-Policy'] = csp
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'

        # MIME tipi koklamayı engelle
        response.headers['X-Content-Type-Options'] = 'nosniff'

        # XSS koruması (Modern tarayıcılar için CSP olsa da eklenir)
        response.headers['X-XSS-Protection'] = '1; mode=block'

        # Referrer politikasını belirle
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # HSTS (Sadece HTTPS üzerinden erişim zorunlu kılar)
        if not current_app.debug:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'

        return response