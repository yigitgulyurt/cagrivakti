import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import os
import gzip
import shutil
import pytz
from datetime import datetime
import json
import time
import uuid
from flask import request, g

# API için iç ağ IP'lerini tek bir kez loglamak için cache
_api_internal_ip_cache = set()

def compress_rotator(source, dest):
    with open(source, 'rb') as f_in:
        with gzip.open(dest + '.gz', 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    os.remove(source)


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
            # User_id'yi temiz al, üzerinde ekstra bir şey olmasın
            user_id = getattr(g, 'user_uid', '-')
            # Eğer user_id içinde 'uid=' varsa, temizle
            if 'uid=' in str(user_id):
                user_id = '-'
            record.user_id = user_id
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
        
        path_padding = 52 - len(method)
        return (f'[{asctime}] {remote_addr:<15} - {method} {path:<{path_padding}} '
                f'{status:3} {duration_ms:4}ms rid={request_id} uid={user_id}')


def setup_logging(app):
    log_file = app.config['APP_LOG_FILE']
    error_log_file = app.config['ERROR_LOG_FILE']
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
    
    retention_days = app.config.get('LOG_RETENTION_DAYS', 7)
    file_handler = TimedRotatingFileHandler(
        log_file, when='midnight', interval=1, backupCount=retention_days, encoding='utf-8'
    )
    file_handler.rotator = compress_rotator
    file_handler.setFormatter(json_formatter if app.config.get('APP_LOG_JSON') else clean_formatter)
    file_handler.setLevel(logging.ERROR)
    file_handler.addFilter(ctx_filter)
    app.logger.addHandler(file_handler)
    
    if app.config.get('APP_LOG_JSON'):
        json_file = log_file.replace('.log', '.jsonl')
        json_file_handler = TimedRotatingFileHandler(
            json_file, when='midnight', interval=1, backupCount=retention_days, encoding='utf-8'
        )
        json_file_handler.rotator = compress_rotator
        json_file_handler.setFormatter(json_formatter)
        json_file_handler.setLevel(logging.ERROR)
        json_file_handler.addFilter(ctx_filter)
        app.logger.addHandler(json_file_handler)
    
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
                
                # İç ağ IP'si mi kontrol et
                is_internal_ip = False
                display_ip = ip
                if (
                    ip.startswith('10.') or 
                    (ip.startswith('172.') and 16 <= int(ip.split('.')[1]) <= 31) or 
                    ip.startswith('192.168.') or
                    ip.startswith('127.') or 
                    ip == '::1'
                ):
                    is_internal_ip = True
                
                # Health check User-Agent'lerini kontrol et
                user_agent = request.headers.get('User-Agent', '').lower()
                health_check_keywords = ['health', 'check', 'kube-probe', 'docker', 'uptime', 'ping']
                is_health_check = any(keyword in user_agent for keyword in health_check_keywords)
                
                if is_health_check:
                    is_internal_ip = True
                
                # İç ağ IP'si ise cache kontrolü
                if is_internal_ip:
                    cache_key = f"{ip}-{request.path}"
                    if cache_key in _api_internal_ip_cache:
                        return response  # Zaten loglandı, tekrar loglama
                    else:
                        _api_internal_ip_cache.add(cache_key)
                        # Cache temizliği (her 1000 istekte bir)
                        if len(_api_internal_ip_cache) > 1000:
                            _api_internal_ip_cache.clear()
                
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


def setup_all_requests_logging(app):
    all_requests_log_file = app.config['ALL_REQUESTS_LOG_FILE']
    os.makedirs(os.path.dirname(all_requests_log_file), exist_ok=True)
    all_requests_logger = logging.getLogger('all_requests_logger')
    level_name = app.config.get('LOG_LEVEL', 'INFO').upper()
    all_requests_logger.setLevel(getattr(logging, level_name, logging.INFO))
    all_requests_logger.propagate = False
    formatter = APILogFormatter(
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler = TimedRotatingFileHandler(
        all_requests_log_file, when='midnight', interval=1, backupCount=app.config.get('LOG_RETENTION_DAYS', 30), encoding='utf-8'
    )
    handler.rotator = compress_rotator
    handler.setFormatter(formatter)

    api_ctx_filter = APIRequestContextFilter()

    handler.addFilter(api_ctx_filter)
    all_requests_logger.addHandler(handler)
    if app.config.get('API_LOG_JSON', True):
        json_file = all_requests_log_file.replace('.log', '.jsonl')
        json_handler = TimedRotatingFileHandler(
            json_file, when='midnight', interval=1, backupCount=app.config.get('LOG_RETENTION_DAYS', 30), encoding='utf-8'
        )
        json_handler.rotator = compress_rotator
        json_handler.setLevel(getattr(logging, level_name, logging.INFO))
        json_logger = logging.getLogger('all_requests_logger.json')
        json_logger.setLevel(getattr(logging, level_name, logging.INFO))
        json_logger.propagate = False
        json_logger.addHandler(json_handler)
        json_handler.addFilter(api_ctx_filter)
        json_handler.setFormatter(logging.Formatter('%(message)s'))

    @app.before_request
    def _all_requests_log_start():
        g._all_requests_log_start = time.time()

    @app.after_request
    def _all_requests_log_end(response):
        try:
            # Admin log sayfası isteklerini kaydetme
            if request.path.startswith('/admin/logs'):
                return response
                
            if request.headers.get('X-Forwarded-For'):
                ip = request.headers.get('X-Forwarded-For').split(',')[0]
            else:
                ip = request.remote_addr
            
            duration_ms = int((time.time() - getattr(g, '_all_requests_log_start', time.time())) * 1000)
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
            all_requests_logger.info('', extra=extra)
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
                logging.getLogger('all_requests_logger.json').info(json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass
        return response


def log_web_visit(ip, path, uid):
    return f'{ip:<18} ziyaret: {path} uid={uid}'
