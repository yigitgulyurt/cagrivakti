from flask import Flask
from flask_cors import CORS
from flask_compress import Compress
import logging
from logging.handlers import RotatingFileHandler
import os
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

    # Context Processors
    from app.services.ramadan_service import RamadanService
    from datetime import datetime
    
    # Şehir isimlerini Türkçe karakterli göstermek için eşleme
    CITY_DISPLAY_NAME_MAPPING = {
        # Türkiye
        "Adiyaman": "Adıyaman", "Agri": "Ağrı", "Aydin": "Aydın", "Balikesir": "Balıkesir", "Bingol": "Bingöl",
        "Bitlis": "Bitlis", "Cankiri": "Çankırı", "Corum": "Çorum", "Diyarbakir": "Diyarbakır", "Duzce": "Düzce",
        "Elazig": "Elazığ", "Gumushane": "Gümüşhane", "Igdir": "Iğdır", "Istanbul": "İstanbul", "Izmir": "İzmir",
        "Kahramanmaras": "Kahramanmaraş", "Karabuk": "Karabük", "Kirikkale": "Kırıkkale", "Kirklareli": "Kırklareli",
        "Kirsehir": "Kırşehir", "Kutahya": "Kütahya", "Mus": "Muş", "Nigde": "Niğde", "Sanliurfa": "Şanlıurfa",
        "Sirnak": "Şırnak", "Tekirdag": "Tekirdağ", "Usak": "Uşak",
        # Uluslararası
        "New-York": "New York", "Los-Angeles": "Los Angeles", "Mexico-City": "Mexico City", "San-Salvador": "San Salvador",
        "Guatemala-City": "Guatemala City", "Tegucigalpa": "Tegucigalpa", "Panama-City": "Panama City", 
        "Santo-Domingo": "Santo Domingo", "Port-au-Prince": "Port-au-Prince", "Saint-Johns": "Saint John's",
        "Saint-Georges": "Saint George's", "Port-of-Spain": "Port of Spain", "Rio-de-Janeiro": "Rio de Janeiro",
        "Buenos-Aires": "Buenos Aires", "Andorra-la-Vella": "Andorra la Vella", "St.-Petersburg": "St. Petersburg",
        "Nur-Sultan": "Nur-Sultan", "New-Delhi": "New Delhi", "Hong-Kong": "Hong Kong", "Kuala-Lumpur": "Kuala Lumpur",
        "Phnom-Penh": "Phnom Penh", "Bandar-Seri-Begawan": "Bandar Seri Begawan", "Port-Moresby": "Port Moresby",
        "N-Djamena": "N'Djamena", "Addis-Ababa": "Addis Ababa", "Cape-Town": "Cape Town", "Sao-Tome": "São Tomé",
        "Saint-Denis": "Saint-Denis", "Mecca": "Mekke", "Medina": "Medine", "Jerusalem": "Kudüs"
    }

    @app.context_processor
    def inject_global_data():
        def get_display_name(city_name):
            if not city_name: return ""
            return CITY_DISPLAY_NAME_MAPPING.get(city_name, city_name)

        return dict(
            ramadan_info=RamadanService.get_ramadan_info(),
                current_year=datetime.now().year,
                get_display_name=get_display_name,
                CITY_DISPLAY_NAME_MAPPING=CITY_DISPLAY_NAME_MAPPING
            )

    return app

def setup_logging(app):
    """
    Genel uygulama loglarını özet rapor formatına dönüştürür.
    IP bazlı ziyaret ve hata özetlerini tutar.
    """
    log_file = app.config['LOG_FILE']
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    import datetime
    from flask import request

    # Özet veriler
    app_stats = {
        'visits': {}, # {ip: {path: count, last_seen: time}}
        'errors': {}  # {message: {count: count, last_seen: time}}
    }

    def save_app_report():
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"--- UYGULAMA GENEL RAPORU (Son Güncelleme: {now}) ---\n\n")
                
                f.write(" [ Hatalar ]\n")
                if not app_stats['errors']:
                    f.write(" Temiz. Hiç hata yok.\n")
                else:
                    sorted_errors = sorted(app_stats['errors'].items(), key=lambda x: x[1]['count'], reverse=True)
                    for msg, data in sorted_errors:
                        f.write(f" Sayı: {data['count']:<5} | Son: {data['last_seen']} | Mesaj: {msg}\n")
                
                f.write("\n [ Ziyaretçi Özeti ]\n")
                sorted_visits = sorted(app_stats['visits'].items(), key=lambda x: sum(p['count'] for p in x[1].values() if isinstance(p, dict)), reverse=True)
                for ip, paths in sorted_visits:
                    total_ip_visits = sum(p['count'] for p in paths.values() if isinstance(p, dict))
                    last_ip_seen = max(p['last_seen'] for p in paths.values() if isinstance(p, dict))
                    f.write(f" IP: {ip:<15} | Toplam: {total_ip_visits:<5} | Son: {last_ip_seen}\n")
                    for path, data in paths.items():
                        f.write(f"   - {path:<20} : {data['count']} kez\n")
        except Exception as e:
            # Kritik hata durumunda konsola yaz
            print(f"Log yazma hatası: {str(e)}")

    # Standart logger'ı devre dışı bırakıp kendi raporlama mantığımızı ekliyoruz
    # Flask logger'ını override et
    class ReportHandler(logging.Handler):
        def emit(self, record):
            if record.levelno >= logging.ERROR:
                msg = record.getMessage()
                now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                if msg not in app_stats['errors']:
                    app_stats['errors'][msg] = {'count': 0, 'last_seen': now}
                app_stats['errors'][msg]['count'] += 1
                app_stats['errors'][msg]['last_seen'] = now
                save_app_report()

    app.logger.handlers = [ReportHandler()]
    app.logger.setLevel(logging.INFO)

    @app.before_request
    def log_visit():
        if not request.path.startswith('/static') and not request.path.startswith('/api'):
            ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            path = request.path
            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if ip not in app_stats['visits']:
                app_stats['visits'][ip] = {}
            if path not in app_stats['visits'][ip]:
                app_stats['visits'][ip][path] = {'count': 0, 'last_seen': now}
            
            app_stats['visits'][ip][path]['count'] += 1
            app_stats['visits'][ip][path]['last_seen'] = now
            save_app_report()

    # Werkzeug loglarını sessize al
    logging.getLogger('werkzeug').setLevel(logging.ERROR)

    # Log Rotasyonu ekle (Hatalar için)
    error_log_file = os.path.join(os.path.dirname(log_file), 'error_details.log')
    error_handler = RotatingFileHandler(error_log_file, maxBytes=1000000, backupCount=5, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    ))
    app.logger.addHandler(error_handler)

    # Genel uygulama logları (INFO seviyesi, rotasyonlu)
    info_log_file = os.path.join(os.path.dirname(log_file), 'app_info.log')
    info_handler = RotatingFileHandler(info_log_file, maxBytes=2000000, backupCount=10, encoding='utf-8')
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    app.logger.addHandler(info_handler)

def setup_api_logging(app):
    """
    API kullanımı için özel loglama sistemini kurar.
    Her IP için sadece en son durumu tutar, böylece log dosyası şişmez.
    """
    api_log_file = app.config['API_LOG_FILE']
    os.makedirs(os.path.dirname(api_log_file), exist_ok=True)

    from flask import request
    import datetime
    import json

    # IP bazlı veri (Bellekte tutulur, uygulama restartında sıfırlanır)
    # Daha kalıcı olması için dosyadan yüklenebilir
    api_usage_data = {}

    def save_api_usage():
        try:
            with open(api_log_file, 'w', encoding='utf-8') as f:
                f.write(f"--- API KULLANIM RAPORU (Son Güncelleme: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---\n")
                # İstek sayısına göre sırala (en çok istek atan üstte)
                sorted_ips = sorted(api_usage_data.items(), key=lambda x: x[1]['count'], reverse=True)
                for ip, data in sorted_ips:
                    f.write(f"IP: {ip:<15} | İstek: {data['count']:<6} | Son İstek: {data['last_seen']}\n")
        except Exception as e:
            app.logger.error(f"API log yazma hatası: {str(e)}")

    @app.before_request
    def log_api_request():
        if request.path.startswith('/api'):
            ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if ip not in api_usage_data:
                api_usage_data[ip] = {'count': 0, 'last_seen': now}
            
            api_usage_data[ip]['count'] += 1
            api_usage_data[ip]['last_seen'] = now
            
            # Her istekte dosyayı güncelle (IP bazlı tek satır)
            save_api_usage()
