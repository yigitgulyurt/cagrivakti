import os
from dotenv import load_dotenv

    # .env dosyasını yükle
load_dotenv()
    

class Config:
    APP_VERSION = "2.8"
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    LOG_FILE = os.path.join(LOG_DIR, 'cagrivakti-web.log')
    API_LOG_FILE = os.path.join(LOG_DIR, 'cagrivakti-api.log')
    TELEGRAM_LOG_FILE = os.path.join(LOG_DIR, 'cagrivakti-bot.log')
    
    LOGGED_PAGES = {
        '/sehir',
        '/sehir/',
        '/ulke/',
        '/ilkelerimiz',
        '/MUSTAFA-KEMAL-ATATÜRK',
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
