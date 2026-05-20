from flask import render_template, request, flash, redirect, url_for
from flask_wtf.csrf import CSRFError
from flask_limiter.errors import RateLimitExceeded
import logging

def register_error_handlers(app):
    """
    Flask uygulamasına hata yöneticilerini kaydeder.
    """
    
    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit_error(e):
        app.logger.warning(f'Rate limit exceeded: {request.remote_addr} - {request.method} {request.full_path}')
        if request.endpoint == 'views.iletisim' and request.method == 'POST':
            flash('Çok fazla mesaj gönderdiniz. Lütfen bir süre bekleyip tekrar deneyin.', 'error')
            return redirect(url_for('views.iletisim'))
        return render_template('errors/429.html'), 429

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        sec_logger = logging.getLogger('security_logger')
        sec_logger.warning(f'CSRF error: {request.remote_addr} - {request.method} {request.full_path}')
        return render_template('errors/400.html', reason="CSRF token validation failed"), 400
    
    @app.errorhandler(400)
    def bad_request(e):
        app.logger.info(f'Bad request: {request.remote_addr} - {request.method} {request.full_path}')
        return render_template('errors/400.html'), 400
    
    @app.errorhandler(401)
    def unauthorized(e):
        sec_logger = logging.getLogger('security_logger')
        sec_logger.info(f'Unauthorized: {request.remote_addr} - {request.method} {request.full_path}')
        return render_template('errors/401.html'), 401
    
    @app.errorhandler(403)
    def forbidden(e):
        sec_logger = logging.getLogger('security_logger')
        sec_logger.warning(f'Forbidden: {request.remote_addr} - {request.method} {request.full_path}')
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def page_not_found(e):
        app.logger.info(f'Page not found: {request.remote_addr} - {request.method} {request.full_path}')
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(405)
    def method_not_allowed(e):
        app.logger.info(f'Method not allowed: {request.remote_addr} - {request.method} {request.full_path}')
        return render_template('errors/405.html'), 405
    
    @app.errorhandler(429)
    def too_many_requests(e):
        app.logger.warning(f'Too many requests: {request.remote_addr} - {request.method} {request.full_path}')
        return render_template('errors/429.html'), 429
    
    @app.errorhandler(500)
    def internal_server_error(e):
        app.logger.error(f'Internal server error: {request.remote_addr} - {request.method} {request.full_path}', exc_info=True)
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(502)
    def bad_gateway(e):
        app.logger.error(f'Bad gateway: {request.remote_addr} - {request.method} {request.full_path}', exc_info=True)
        return render_template('errors/502.html'), 502
    
    @app.errorhandler(503)
    def service_unavailable(e):
        app.logger.error(f'Service unavailable: {request.remote_addr} - {request.method} {request.full_path}', exc_info=True)
        return render_template('errors/503.html'), 503