from flask import Flask, request
from flask_cors import CORS
from flask_compress import Compress
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import os
import gzip
import shutil
import pytz
from datetime import datetime
from dotenv import load_dotenv

from app.extensions import db, migrate, cache, csrf, limiter
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
    CORS(app)
    Compress(app)
    db.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # Logging
    setup_logging(app)

    # Middleware
    setup_middleware(app)

    # Error Handlers
    register_error_handlers(app)

    # Blueprints
    from app.routes.views import views_bp
    from app.routes.api import api_bp
    
    app.register_blueprint(views_bp)
    app.register_blueprint(api_bp)

    # API Kullanım Loglaması
    setup_api_logging(app)
    
    # Statik Dosyalar İçin Cache-Control (1 Yıl)
    @app.after_request
    def add_header(response):
        if 'Cache-Control' not in response.headers:
            # Statik dosyalar için uzun süreli cache
            if request.path.startswith('/static/'):
                # 1 Yıl = 31536000 saniye
                response.headers['Cache-Control'] = 'public, max-age=31536000'
        return response

    # Cache Busting (Versiyonlama)
    @app.url_defaults
    def hashed_url_for_static_file(endpoint, values):
        if 'static' == endpoint or endpoint.endswith('.static'):
            filename = values.get('filename')
            if filename:
                if '.' in filename:
                    # Global versiyon numarasını kullan
                    # Config'den STATIC_VERSION'ı al, yoksa APP_VERSION, o da yoksa 1.0
                    version = app.config.get('STATIC_VERSION') or app.config.get('APP_VERSION') or '1.0'
                    
                    param_name = 'v'
                    while param_name in values:
                        param_name = '_' + param_name
                    
                    values[param_name] = version

    # Context Processors
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

    return app

class IstanbulFormatter(logging.Formatter):
    """
    Log zaman damgalarını Europe/Istanbul saat dilimine dönüştüren formatter.
    """
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
    """Log dosyası rotasyona girdiğinde gzip ile sıkıştır."""
    with open(source, 'rb') as f_in:
        with gzip.open(dest + '.gz', 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    os.remove(source)

def setup_logging(app):
    """
    Uygulama loglama yapılandırması.
    TimedRotatingFileHandler (Günlük) ve Istanbul timezone kullanılır.
    """
    log_file = app.config['LOG_FILE']
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # Mevcut handlerları temizle
    app.logger.handlers = []
    
    # Log seviyesini ayarla
    app.logger.setLevel(logging.INFO)
    
    # Formatter oluştur
    default_formatter = IstanbulFormatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    clean_formatter = IstanbulFormatter(
        '[%(asctime)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Ana log dosyası (INFO ve üzeri) - Günlük Rotasyonlu
    # when='midnight': Gece yarısı döndür
    # interval=1: Her 1 günde bir
    # backupCount=30: 30 günlük yedek sakla
    file_handler = TimedRotatingFileHandler(
        log_file, when='midnight', interval=1, backupCount=30, encoding='utf-8'
    )
    file_handler.setFormatter(clean_formatter)
    file_handler.setLevel(logging.INFO)
    
    # Sıkıştırma fonksiyonunu ata
    file_handler.rotator = compress_rotator
    # Sıkıştırılmış dosya isimlendirmesi (log.2023-01-01.gz gibi olması için namer gerekebilir ama varsayılan + .gz yeterli)
    
    app.logger.addHandler(file_handler)
    
    # Hata log dosyası (Sadece ERROR)
    error_log_file = os.path.join(os.path.dirname(log_file), 'error.log')
    error_handler = RotatingFileHandler(
        error_log_file, maxBytes=10*1024*1024, backupCount=10, encoding='utf-8'
    )
    error_handler.setFormatter(default_formatter)
    error_handler.setLevel(logging.ERROR)
    app.logger.addHandler(error_handler)
    
    # Werkzeug loglarını sessize al (veya dosyaya yönlendir)
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.ERROR)
    werkzeug_logger.addHandler(error_handler)

def setup_api_logging(app):
    """
    API istekleri için ayrı loglama yapılandırması.
    """
    api_log_file = app.config['API_LOG_FILE']
    os.makedirs(os.path.dirname(api_log_file), exist_ok=True)
    
    # API logger oluştur
    api_logger = logging.getLogger('api_logger')
    api_logger.setLevel(logging.INFO)
    api_logger.propagate = False  # Ana loga düşmesini engelle
    
    formatter = IstanbulFormatter(
        '[%(asctime)s] %(remote_addr)s - %(method)s %(path)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # API Logları da günlük rotasyonlu olsun
    handler = TimedRotatingFileHandler(
        api_log_file, when='midnight', interval=1, backupCount=30, encoding='utf-8'
    )
    handler.rotator = compress_rotator
    handler.setFormatter(formatter)
    api_logger.addHandler(handler)
    
    @app.before_request
    def log_api_request():
        if request.blueprint == 'api' or (request.host and request.host.startswith('api.')):
            # IP adresini al
            if request.headers.get('X-Forwarded-For'):
                ip = request.headers.get('X-Forwarded-For').split(',')[0]
            else:
                ip = request.remote_addr
                
            api_logger.info('', extra={
                'remote_addr': ip,
                'method': request.method,
                'path': request.full_path
            })
