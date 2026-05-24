from flask import request, render_template, current_app, g
import time
import uuid

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