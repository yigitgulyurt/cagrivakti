from flask import Flask, request, g, current_app
from flask_cors import CORS
# from flask_compress import Compress
from flask_minify import Minify
import os
import uuid
from dotenv import load_dotenv
from datetime import datetime

from app.extensions import db, migrate, cache, csrf, limiter, assets
from app.config import Config
from app.error_handlers import register_error_handlers
from app.middleware import setup_middleware
from app.logging_config import setup_logging, setup_api_logging, setup_security_logging

def create_app(config_class=Config):
    # .env dosyasını yükle
    load_dotenv()
    
    # Set instance_path to the root directory's instance folder
    root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    instance_path = os.path.join(root_path, 'instance')
    
    app = Flask(__name__, instance_path=instance_path)
    app.config.from_object(config_class)
    
    # JSON sorting ayarı (Yeni Flask versiyonları için)
    app.json.sort_keys = False

    # Extensions
    CORS(app, resources={
        r"/api/*": {
            "origins": [
                "https://cagrivakti.com.tr",
                "https://www.cagrivakti.com.tr",
                "http://localhost:*",
                "http://127.0.0.1:*",
            ]
        },
        r"/vakitler*": {
            "origins": [
                "https://cagrivakti.com.tr",
                "https://www.cagrivakti.com.tr",
                "http://localhost:*",
                "http://127.0.0.1:*"
            ]
        },
        r"/api/cagri_vakitleri": {
            "origins": [
                "https://cagrivakti.com.tr",
                "https://www.cagrivakti.com.tr",
                "http://localhost:*",
                "http://127.0.0.1:*",
            ]
        },
        r"/sonraki_vakit": {
            "origins": [
                "https://cagrivakti.com.tr",
                "https://www.cagrivakti.com.tr",
                "http://localhost:*",
                "http://127.0.0.1:*"
            ]
        },
        r"/daily_content": {
            "origins": [
                "https://cagrivakti.com.tr",
                "https://www.cagrivakti.com.tr",
                "http://localhost:*",
                "http://127.0.0.1:*"
            ]
        }
    })
    
    assets.init_app(app)

    # css_bundle = Bundle('css/main.css', filters='cssmin', output='css/main.min.css')
    # assets.register('css_main', css_bundle)

    # js_bundle = Bundle(
    #     'js/jquery-cagrivakti.js',
    #     'js/inappredirect-cagrivakti.js',
    #     filters='rjsmin',
    #     output='js/main.min.js'
    # )
    # assets.register('js_main', js_bundle)

    app.jinja_env.add_extension('webassets.ext.jinja2.AssetsExtension')
    app.jinja_env.assets_environment = assets                          
    db.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    Minify(app=app, html=False, js=False, cssless=True)

    setup_logging(app)

    @app.before_request
    def ensure_uid():
        try:
            g.user_uid = '-'
            uid = request.cookies.get('cv_uid')
            if uid and all(c in '0123456789abcdefABCDEF' for c in uid):
                g.user_uid = uid
            else:
                # Yeni uid oluştur ama çerezi after_request'te ayarlayacağız
                g.user_uid = uuid.uuid4().hex[:16]
        except Exception:
            g.user_uid = '-'

    setup_middleware(app)
    register_error_handlers(app)

    from app.routes.views import views_bp
    from app.routes.api import api_bp
    from app.routes.og import og_bp
    
    # API'yi sadece /api yolundan erişilebilir yap
    app.register_blueprint(api_bp, url_prefix='/api')  # cagrivakti.com.tr/api/...
    
    # Diğer blueprint'leri kaydet
    app.register_blueprint(og_bp)
    app.register_blueprint(views_bp)

    setup_api_logging(app)
    setup_security_logging(app)
    
    @app.after_request
    def add_header(response):
        try:
            # Çerezi her zaman kontrol et ve yenile/güncelle
            current_uid_in_cookie = request.cookies.get('cv_uid')
            current_uid_in_g = getattr(g, 'user_uid', '-')
            
            # Eğer cookie yoksa veya geçersizse, yenisini ayarla
            if (not current_uid_in_cookie or 
                current_uid_in_cookie != current_uid_in_g or
                not all(c in '0123456789abcdefABCDEF' for c in current_uid_in_g)):
                
                if current_uid_in_g and current_uid_in_g != '-':
                    uid_to_set = current_uid_in_g
                else:
                    uid_to_set = uuid.uuid4().hex[:16]
                
                response.set_cookie(
                    'cv_uid',
                    uid_to_set,
                    max_age=60*60*24*365*2,  # 2 yıl
                    samesite='Lax',
                    path='/',
                    secure=not current_app.debug,  # Debug modunda secure=False
                    httponly=True
                )
        except Exception:
            pass
        
        if request.endpoint == 'static' or request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
            from datetime import datetime, timedelta
            expires = datetime.now() + timedelta(days=365)
            response.headers['Expires'] = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
            response.headers['Vary'] = 'Accept-Encoding'
            response.headers['Access-Control-Allow-Origin'] = '*'
        elif 'Cache-Control' not in response.headers:
             response.headers['Cache-Control'] = 'no-cache'
        return response

    @app.url_defaults
    def hashed_url_for_static_file(endpoint, values):
        if 'static' == endpoint or endpoint.endswith('.static'):
            filename = values.get('filename')
            if filename:
                if '.' in filename:
                    version = app.config.get('APP_VERSION') or '1.0'
                    param_name = 'v'
                    while param_name in values:
                        param_name = '_' + param_name
                    values[param_name] = version

    from app.services.ramadan_service import RamadanService
    from app.services import CITY_DISPLAY_NAME_MAPPING
    
    @app.context_processor
    def inject_global_data():
        def get_display_name(city_name):
            if not city_name: return ""
            return CITY_DISPLAY_NAME_MAPPING.get(city_name, city_name)

        return dict(
            ramadan_info=RamadanService.get_ramadan_info(),
            current_year=datetime.now().year,
            app_version=app.config.get('APP_VERSION', '1.0'),
            get_display_name=get_display_name,
            CITY_DISPLAY_NAME_MAPPING=CITY_DISPLAY_NAME_MAPPING
        )

    # ── Versiyon değişince Flask cache'ini otomatik temizle ──
    with app.app_context():
        _clear_cache_on_version_change(app)

    return app


def _clear_cache_on_version_change(app):
    """Redis'e kaydedilen son versiyonla mevcut versiyonu karşılaştırır.
    Farklıysa Flask cache'ini temizler ve yeni versiyonu kaydeder."""
    try:
        import redis as redis_lib
        r = redis_lib.from_url(
            os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
            decode_responses=True
        )
        current_version = app.config.get('APP_VERSION', '')
        stored_version = r.get('app:deployed_version')
        if stored_version != current_version:
            cache.clear()
            r.set('app:deployed_version', current_version)
            app.logger.info(
                f'[version] {stored_version} → {current_version} — Flask cache temizlendi.'
            )
    except Exception as e:
        app.logger.warning(f'[version] Cache temizleme kontrolü başarısız: {e}')


