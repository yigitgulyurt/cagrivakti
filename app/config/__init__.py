import os
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

class Config:
    APP_VERSION = "2.33"
    # Tek versiyon kaynağı: APP_VERSION
    SEND_FILE_MAX_AGE_DEFAULT = 31536000 # Flask static dosya cache süresi (1 Yıl)
    SERVER_NAME = os.environ.get('SERVER_NAME')
    # Subdomainler arası session paylaşımı için
    if SERVER_NAME:
        SESSION_COOKIE_DOMAIN = '.' + SERVER_NAME
    
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    LOG_FILE = os.path.join(LOG_DIR, 'cagrivakti-web.log')
    API_LOG_FILE = os.path.join(LOG_DIR, 'cagrivakti-api.log')
    TELEGRAM_LOG_FILE = os.path.join(LOG_DIR, 'cagrivakti-bot.log')
    SECURITY_LOG_FILE = os.path.join(LOG_DIR, 'security.log')
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    API_LOG_JSON = os.environ.get('API_LOG_JSON', 'true').lower() in ('1', 'true', 'yes')
    LOG_RETENTION_DAYS = int(os.environ.get('LOG_RETENTION_DAYS', '30'))
    
    LOGGED_PAGES = {
        '/sehir',
        '/sehir/',
        '/ulke/',
        '/ilkelerimiz',
        '/Mustafa-Kemal-Ataturk',
        '/api-dokuman'
    }
    
    # Bot Tokens
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
    DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
    ADMIN_TELEGRAM_ID = os.environ.get('ADMIN_TELEGRAM_ID')
    ADMIN_DISCORD_WEBHOOK = os.environ.get('ADMIN_DISCORD_WEBHOOK')

    # API Settings
    VIP_API_KEYS = os.environ.get('VIP_API_KEYS', 'cagrivakti_admin_key_2026').split(',')
    
    # Admin Authentication
    ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
    ADMIN_PASS = os.environ.get('ADMIN_PASS', 'cagrivakti2026')
    
    # Cache Settings
    CACHE_TYPE = os.environ.get('CACHE_TYPE', 'RedisCache' if os.environ.get('REDIS_URL') else 'SimpleCache')
    CACHE_REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_DEFAULT_TIMEOUT = 3600

    # Canlı Yayın Secret key
    STREAM_SECRET = os.environ.get('STREAM_SECRET', 'okulcanli2025')
    STREAM_KEY = os.environ.get('STREAM_KEY', 'yayin')
    SHOW_LIVE_SECTION = os.environ.get('SHOW_LIVE_SECTION', 'false').lower() in ('1', 'true', 'yes')
