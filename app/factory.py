from flask import Flask, request, g, current_app
from flask_cors import CORS
# from flask_compress import Compress
from flask_minify import Minify
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import os
import gzip
import shutil
import pytz
from datetime import datetime
from dotenv import load_dotenv

import json
import time
import uuid

from app.extensions import db, migrate, cache, csrf, limiter, assets
from app.config import Config
from app.error_handlers import register_error_handlers
from app.middleware import setup_middleware

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
        r"/ezan_vakitleri-V2*": {
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
    Minify(app=app, html=True, js=True, cssless=True)

    setup_logging(app)

    @app.before_request
    def ensure_uid():
        try:
            uid = request.cookies.get('cv_uid')
            if not uid:
                uid = uuid.uuid4().hex[:16]
                g._set_uid_cookie = uid
            g.user_uid = uid
        except Exception:
            g.user_uid = '-'

    setup_middleware(app)
    register_error_handlers(app)

    from app.routes.views import views_bp
    from app.routes.api import api_bp
    from app.routes.og import og_bp
    
    app.register_blueprint(views_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(og_bp)

    setup_api_logging(app)
    setup_security_logging(app)
    
    @app.after_request
    def add_header(response):
        try:
            if getattr(g, '_set_uid_cookie', None):
                response.set_cookie(
                    'cv_uid',
                    g._set_uid_cookie,
                    max_age=60*60*24*365,
                    samesite='Lax',
                    path='/',
                    secure=True,
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


class IstanbulFormatter(logging.Formatter):
    def converter(self, timestamp):
        dt = datetime.fromtimestamp(timestamp, pytz.utc)
        return dt.astimezone(pytz.timezone('Europe/Istanbul'))

    def formatTime(self, record, datefmt=None):
        dt = self.converter(record.created)
        if datefmt:
            s = dt.strftime(datefmt)
        else:
            try:
                s = dt.isoformat(timespec='milliseconds')
            except TypeError:
                s = dt.isoformat()
        return s

def compress_rotator(source, dest):
    with open(source, 'rb') as f_in:
        with gzip.open(dest + '.gz', 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    os.remove(source)

class RequestContextFilter(logging.Filter):
    def filter(self, record):
        try:
            record.request_id = getattr(g, 'request_id', '-')
        except Exception:
            record.request_id = '-'
        return True

class APIRequestContextFilter(logging.Filter):
    def filter(self, record):
        try:
            record.request_id = getattr(g, 'request_id', '-')
            record.user_id = getattr(g, 'user_uid', '-')
        except Exception:
            record.request_id = '-'
            record.user_id = '-'
        if not hasattr(record, 'status'):
            record.status = '-'
        if not hasattr(record, 'duration_ms'):
            record.duration_ms = 0
        return True

class SecurityContextFilter(logging.Filter):
    def filter(self, record):
        try:
            record.remote_addr = getattr(g, 'remote_addr', '-')
            record.method = getattr(g, 'request_method', '-')
            record.path = getattr(g, 'request_path', '-')
        except Exception:
            record.remote_addr = '-'
            record.method = '-'
            record.path = '-'
        return True

class JSONFormatter(IstanbulFormatter):
    def format(self, record):
        log_record = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'module': record.module,
            'message': record.getMessage(),
            'request_id': getattr(record, 'request_id', '-')
        }
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)
        return json.dumps(log_record, ensure_ascii=False)

class APILogFormatter(IstanbulFormatter):
    def format(self, record):
        dt = self.converter(record.created)
        asctime = dt.strftime('%Y-%m-%d %H:%M:%S')
        remote_addr = getattr(record, 'remote_addr', '-')
        method = getattr(record, 'method', '-')
        path = getattr(record, 'path', '-')
        status = getattr(record, 'status', '-')
        duration_ms = getattr(record, 'duration_ms', 0)
        request_id = getattr(record, 'request_id', '-')
        user_id = getattr(record, 'user_id', '-')
        
        return (f'[{asctime}] {remote_addr:<18} - {method} {path:<52} '
                f'{status:3} {duration_ms:4}ms rid={request_id} uid={user_id}')

def setup_logging(app):
    log_file = app.config['LOG_FILE']
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    app.logger.handlers = []
    level_name = app.config.get('LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, level_name, logging.INFO)
    app.logger.setLevel(log_level)
    
    default_formatter = IstanbulFormatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    clean_formatter = IstanbulFormatter(
        '[%(asctime)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    json_formatter = JSONFormatter()
    
    ctx_filter = RequestContextFilter()
    
    file_handler = TimedRotatingFileHandler(
        log_file, when='midnight', interval=1, backupCount=30, encoding='utf-8'
    )
    file_handler.rotator = compress_rotator
    file_handler.setFormatter(json_formatter if app.config.get('APP_LOG_JSON') else clean_formatter)
    file_handler.setLevel(logging.INFO)
    file_handler.addFilter(ctx_filter)
    app.logger.addHandler(file_handler)
    
    if app.config.get('APP_LOG_JSON'):
        json_file = log_file.replace('.log', '.jsonl')
        json_file_handler = TimedRotatingFileHandler(
            json_file, when='midnight', interval=1, backupCount=30, encoding='utf-8'
        )
        json_file_handler.rotator = compress_rotator
        json_file_handler.setFormatter(json_formatter)
        json_file_handler.setLevel(logging.INFO)
        json_file_handler.addFilter(ctx_filter)
        app.logger.addHandler(json_file_handler)
    
    error_log_file = os.path.join(os.path.dirname(log_file), 'error.log')
    error_handler = RotatingFileHandler(
        error_log_file, maxBytes=10*1024*1024, backupCount=10, encoding='utf-8'
    )
    error_handler.setFormatter(default_formatter)
    error_handler.addFilter(ctx_filter)
    error_handler.setLevel(logging.ERROR)
    app.logger.addHandler(error_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(default_formatter)
    console_handler.setLevel(log_level)
    console_handler.addFilter(ctx_filter)
    app.logger.addHandler(console_handler)
    
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.ERROR)
    werkzeug_logger.addHandler(error_handler)
    werkzeug_logger.addHandler(console_handler)

def setup_api_logging(app):
    api_log_file = app.config['API_LOG_FILE']
    os.makedirs(os.path.dirname(api_log_file), exist_ok=True)
    api_logger = logging.getLogger('api_logger')
    level_name = app.config.get('LOG_LEVEL', 'INFO').upper()
    api_logger.setLevel(getattr(logging, level_name, logging.INFO))
    api_logger.propagate = False
    formatter = APILogFormatter(
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler = TimedRotatingFileHandler(
        api_log_file, when='midnight', interval=1, backupCount=app.config.get('LOG_RETENTION_DAYS', 30), encoding='utf-8'
    )
    handler.rotator = compress_rotator
    handler.setFormatter(formatter)

    api_ctx_filter = APIRequestContextFilter()

    handler.addFilter(api_ctx_filter)
    api_logger.addHandler(handler)
    if app.config.get('API_LOG_JSON', True):
        json_file = api_log_file.replace('.log', '.jsonl')
        json_handler = TimedRotatingFileHandler(
            json_file, when='midnight', interval=1, backupCount=app.config.get('LOG_RETENTION_DAYS', 30), encoding='utf-8'
        )
        json_handler.rotator = compress_rotator
        json_handler.setLevel(getattr(logging, level_name, logging.INFO))
        json_logger = logging.getLogger('api_logger.json')
        json_logger.setLevel(getattr(logging, level_name, logging.INFO))
        json_logger.propagate = False
        json_logger.addHandler(json_handler)
        json_handler.addFilter(api_ctx_filter)
        json_handler.setFormatter(logging.Formatter('%(message)s'))

    @app.before_request
    def _api_log_start():
        g._log_start = time.time()
        g.request_id = uuid.uuid4().hex[:12]

    @app.after_request
    def _api_log_end(response):
        try:
            if request.blueprint == 'api' or (request.host and request.host.startswith('api.')):
                if request.headers.get('X-Forwarded-For'):
                    ip = request.headers.get('X-Forwarded-For').split(',')[0]
                else:
                    ip = request.remote_addr
                duration_ms = int((time.time() - getattr(g, '_log_start', time.time())) * 1000)
                ua = request.headers.get('User-Agent', '')[:200]
                referer = request.headers.get('Referer', '')[:200]
                path = request.full_path
                status = response.status_code
                extra = {
                    'remote_addr': ip,
                    'method': request.method,
                    'path': path,
                    'status': status,
                    'duration_ms': duration_ms,
                    'user_id': getattr(g, 'user_uid', '-')
                }
                api_logger.info('', extra=extra)
                if app.config.get('API_LOG_JSON', True):
                    payload = {
                        'ts': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                        'rid': getattr(g, 'request_id', '-'),
                        'uid': getattr(g, 'user_uid', '-'),
                        'ip': ip,
                        'method': request.method,
                        'path': path,
                        'status': status,
                        'duration_ms': duration_ms,
                        'ua': ua,
                        'referer': referer
                    }
                    logging.getLogger('api_logger.json').info(json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass
        return response

def setup_security_logging(app):
    sec_log_file = app.config.get('SECURITY_LOG_FILE')
    os.makedirs(os.path.dirname(sec_log_file), exist_ok=True)
    logger = logging.getLogger('security_logger')
    level_name = app.config.get('LOG_LEVEL', 'INFO').upper()
    logger.setLevel(getattr(logging, level_name, logging.INFO))
    logger.propagate = False
    handler = TimedRotatingFileHandler(
        sec_log_file, when='midnight', interval=1, backupCount=app.config.get('LOG_RETENTION_DAYS', 30), encoding='utf-8'
    )
    handler.rotator = compress_rotator
    handler.setFormatter(IstanbulFormatter('[%(asctime)s] %(levelname)s | ip=%(remote_addr)s | method=%(method)s | path=%(path)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    
    sec_ctx_filter = SecurityContextFilter()
    
    handler.addFilter(sec_ctx_filter)
    logger.addHandler(handler)
    
    @app.before_request
    def capture_security_context():
        try:
            g.remote_addr = request.remote_addr
            g.request_method = request.method
            g.request_path = request.full_path
        except Exception:
            pass