from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_caching import Cache
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_assets import Environment, Bundle
from flask import request, current_app

assets = Environment()
db = SQLAlchemy()
migrate = Migrate()
cache = Cache()
csrf = CSRFProtect()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per day", "200 per hour"],
    storage_uri="memory://",
    enabled=True
)

@limiter.request_filter
def vip_request_filter():
    """
    SADECE sağlık kontrolü endpoint'leri ve iç ağ IP'leri rate limit'ten muaf tutar.
    """
    # SADECE sağlık kontrolü endpoint'lerini muaf tut
    if '/status' in request.path or request.path == '/api/status':
        return True
    
    # Yerel geliştirme ve iç ağ IP'lerini muaf tut
    ip = request.remote_addr
    if (
        ip in ['127.0.0.1', '::1'] or
        ip.startswith('10.') or 
        (ip.startswith('172.') and 16 <= int(ip.split('.')[1]) <= 31) or 
        ip.startswith('192.168.')
    ):
        return True

    # VIP API Key muafiyeti
    api_key = request.headers.get('X-API-Key')
    if api_key and api_key in current_app.config.get('VIP_API_KEYS', []):
        return True
    
    # Kendi domainimizden gelen istekleri muaf tut (sitenin kendi API istekleri için)
    referer = request.headers.get('Referer', '')
    origin = request.headers.get('Origin', '')
    
    allowed_domains = [
        'https://cagrivakti.com.tr',
        'https://www.cagrivakti.com.tr',
        'http://cagrivakti.com.tr',
        'http://www.cagrivakti.com.tr',
        'http://localhost',
        'http://127.0.0.1'
        ]
    
    def is_allowed_domain(url):
        if not url:
            return False
        return any(url.startswith(domain) for domain in allowed_domains)
    
    if is_allowed_domain(referer) or is_allowed_domain(origin):
        return True
    
    return False
