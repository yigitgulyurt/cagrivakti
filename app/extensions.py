from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_caching import Cache
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import request, current_app

db = SQLAlchemy()
migrate = Migrate()
cache = Cache()
csrf = CSRFProtect()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per day", "200 per hour"],
    storage_uri="memory://",
)

@limiter.request_filter
def vip_request_filter():
    """
    VIP API anahtarına sahip veya yerel geliştirme isteklerini rate limit'ten muaf tutar.
    """
    # Yerel geliştirme muafiyeti
    if request.remote_addr in ['127.0.0.1', '::1']:
        return True

    # VIP API Key muafiyeti
    api_key = request.headers.get('X-API-Key')
    if api_key and api_key in current_app.config.get('VIP_API_KEYS', []):
        return True
    return False
