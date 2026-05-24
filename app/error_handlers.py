from flask import render_template, request, flash, redirect, url_for, jsonify, g
from flask_wtf.csrf import CSRFError
from flask_limiter.errors import RateLimitExceeded
import logging

def is_api_subdomain():
    """API subdomain'inde olup olmadığımızı kontrol eder"""
    return request.host.startswith('api.')

def get_log_prefix():
    try:
        rid = getattr(g, 'request_id', '-')
        uid = getattr(g, 'user_uid', '-')
        return f'rid={rid} uid={uid}'
    except Exception:
        return 'rid=- uid=-'

def register_error_handlers(app):
    """
    Flask uygulamasına hata yöneticilerini kaydeder.
    """
    
    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit_error(e):
        prefix = get_log_prefix()
        app.logger.warning(f'Rate limit exceeded: {request.remote_addr} - {request.method} {request.full_path} {prefix}')
        if is_api_subdomain():
            return jsonify({'error': 'Too many requests'}), 429
        if request.endpoint == 'views.iletisim' and request.method == 'POST':
            flash('Çok fazla mesaj gönderdiniz. Lütfen bir süre bekleyip tekrar deneyin.', 'error')
            return redirect(url_for('views.iletisim'))
        return render_template('errors/429.html'), 429

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        sec_logger = logging.getLogger('security_logger')
        prefix = get_log_prefix()
        sec_logger.warning(f'CSRF error: {request.remote_addr} - {request.method} {request.full_path} {prefix}')
        if is_api_subdomain():
            return jsonify({'error': 'CSRF token validation failed'}), 400
        return render_template('errors/400.html', reason="CSRF token validation failed"), 400
    
    @app.errorhandler(400)
    def bad_request(e):
        prefix = get_log_prefix()
        app.logger.info(f'Bad request: {request.remote_addr} - {request.method} {request.full_path} {prefix}')
        if is_api_subdomain():
            return jsonify({'error': 'Bad request'}), 400
        return render_template('errors/400.html'), 400
    
    @app.errorhandler(401)
    def unauthorized(e):
        sec_logger = logging.getLogger('security_logger')
        prefix = get_log_prefix()
        sec_logger.info(f'Unauthorized: {request.remote_addr} - {request.method} {request.full_path} {prefix}')
        if is_api_subdomain():
            return jsonify({'error': 'Unauthorized'}), 401
        return render_template('errors/401.html'), 401
    
    @app.errorhandler(403)
    def forbidden(e):
        sec_logger = logging.getLogger('security_logger')
        prefix = get_log_prefix()
        sec_logger.warning(f'Forbidden: {request.remote_addr} - {request.method} {request.full_path} {prefix}')
        if is_api_subdomain():
            return jsonify({'error': 'Forbidden'}), 403
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def page_not_found(e):
        prefix = get_log_prefix()
        app.logger.info(f'Page not found: {request.remote_addr} - {request.method} {request.full_path} {prefix}')
        if is_api_subdomain():
            return jsonify({'error': 'Not found'}), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(405)
    def method_not_allowed(e):
        prefix = get_log_prefix()
        app.logger.info(f'Method not allowed: {request.remote_addr} - {request.method} {request.full_path} {prefix}')
        if is_api_subdomain():
            return jsonify({'error': 'Method not allowed'}), 405
        return render_template('errors/405.html'), 405
    
    @app.errorhandler(429)
    def too_many_requests(e):
        prefix = get_log_prefix()
        app.logger.warning(f'Too many requests: {request.remote_addr} - {request.method} {request.full_path} {prefix}')
        if is_api_subdomain():
            return jsonify({'error': 'Too many requests'}), 429
        return render_template('errors/429.html'), 429
    
    @app.errorhandler(500)
    def internal_server_error(e):
        prefix = get_log_prefix()
        app.logger.error(f'Internal server error: {request.remote_addr} - {request.method} {request.full_path} {prefix}', exc_info=True)
        if is_api_subdomain():
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(502)
    def bad_gateway(e):
        prefix = get_log_prefix()
        app.logger.error(f'Bad gateway: {request.remote_addr} - {request.method} {request.full_path} {prefix}', exc_info=True)
        if is_api_subdomain():
            return jsonify({'error': 'Bad gateway'}), 502
        return render_template('errors/502.html'), 502
    
    @app.errorhandler(503)
    def service_unavailable(e):
        prefix = get_log_prefix()
        app.logger.error(f'Service unavailable: {request.remote_addr} - {request.method} {request.full_path} {prefix}', exc_info=True)
        if is_api_subdomain():
            return jsonify({'error': 'Service unavailable'}), 503
        return render_template('errors/503.html'), 503