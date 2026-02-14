from flask import render_template, request, flash, redirect, url_for
from flask_wtf.csrf import CSRFError
from flask_limiter.errors import RateLimitExceeded

def register_error_handlers(app):
    """
    Flask uygulamasına hata yöneticilerini kaydeder.
    """
    
    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit_error(e):
        if request.endpoint == 'views.iletisim' and request.method == 'POST':
            flash('Çok fazla mesaj gönderdiniz. Lütfen bir süre bekleyip tekrar deneyin.', 'error')
            return redirect(url_for('views.iletisim'))
        return render_template('errors/429.html'), 429

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        return render_template('errors/400.html', reason="CSRF token validation failed"), 400
    
    @app.errorhandler(400)
    def bad_request(e):
        return render_template('errors/400.html'), 400
    
    @app.errorhandler(401)
    def unauthorized(e):
        return render_template('errors/401.html'), 401
    
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(405)
    def method_not_allowed(e):
        return render_template('errors/405.html'), 405
    
    @app.errorhandler(429)
    def too_many_requests(e):
        return render_template('errors/429.html'), 429
    
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(502)
    def bad_gateway(e):
        return render_template('errors/502.html'), 502
    
    @app.errorhandler(503)
    def service_unavailable(e):
        return render_template('errors/503.html'), 503