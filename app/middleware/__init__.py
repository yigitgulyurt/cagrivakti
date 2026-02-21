from flask import request, render_template, current_app
import time

# Son loglanan IP ve yolları tutmak için basit bir cache (IP, Path) -> Timestamp
# _log_cache = {}
# _CACHE_TIMEOUT = 300  # 5 dakika (saniye cinsinden)

def setup_middleware(app):
    @app.before_request
    def log_request_info():
        path = request.path
        logged_pages = app.config.get('LOGGED_PAGES', set())
        
        # Sadece belirlenen sayfaları ve kök dizini logla
        if path != '/' and not any(path.startswith(page) for page in logged_pages):
            return
            
        # API ve Static dosyaları loglama
        if request.blueprint == 'api' or (request.host and request.host.startswith('api.')) or '/static/' in path or path.endswith(('.ico', '.json', '.txt')):
            return
            
        try:
            # IP adresini al
            if request.headers.get('X-Forwarded-For'):
                ip = request.headers.get('X-Forwarded-For').split(',')[0]
            else:
                ip = request.remote_addr
            
            # Her isteği kaydet (Deduplication kaldırıldı)
            app.logger.info(f'{ip} ziyaret: {path}')
                    
        except Exception as e:
            app.logger.error(f"Loglama hatası: {str(e)}")

    @app.before_request
    def check_instagram_browser():
        user_agent = request.headers.get('User-Agent', '').lower()
        if 'instagram' in user_agent and ('fbav' in user_agent or 'instagram' in user_agent):
            return render_template('open_in_browser.html')

    @app.after_request
    def set_security_headers(response):
        """Güvenlik başlıklarını (Security Headers) ekle."""
        
        # Embed sayfaları için özel izinler
        if request.path.startswith('/embed/'):
            # Embed edilebilir sayfalar için frame-ancestors * (her yere izin ver)
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://code.jquery.com https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: https:; "
                "connect-src 'self' https://nominatim.openstreetmap.org https://api.cagrivakti.com.tr; "
                "frame-ancestors *; "
                "base-uri 'self'; "
                "form-action 'self';"
            )
            response.headers['Content-Security-Policy'] = csp
            # X-Frame-Options header'ını kaldır (varsa)
            response.headers.pop('X-Frame-Options', None)
            
        else:
            # Standart sayfalar için sıkı güvenlik
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://code.jquery.com https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: https:; "
                "connect-src 'self' https://nominatim.openstreetmap.org https://api.cagrivakti.com.tr; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self';"
            )
            response.headers['Content-Security-Policy'] = csp
            # Clickjacking koruması
            response.headers['X-Frame-Options'] = 'DENY'
        
        # MIME tipi koklamayı engelle
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # XSS koruması (Modern tarayıcılar için CSP olsa da eklenir)
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer politikasını belirle
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # HSTS (Sadece HTTPS üzerinden erişim zorunlu kılar)
        # Sadece üretim ortamında aktifleştirilmesi önerilir, ancak projede SSL olduğu varsayımıyla ekliyoruz
        if not current_app.debug:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
            
        return response
