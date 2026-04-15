# app.py
"""
SROS — Application factory.
"""
import os
from flask import Flask, jsonify
from config import config_map
from extensions import db, migrate, jwt, cors, limiter, JWT_DENYLIST


def create_app(config_name: str = None) -> Flask:
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config_map.get(config_name, config_map['default']))

    # Disable template caching in development
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.jinja_env.auto_reload = True

    # Prevent browser from caching HTML responses
    @app.after_request
    def add_no_cache_headers(response):
        if 'text/html' in response.content_type:
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

    # ── Extensions ──────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)
    cors.init_app(app,
                  origins=app.config.get('ALLOWED_ORIGINS', '*'),
                  supports_credentials=True)

    # ── JWT denylist check ───────────────────────────────────
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        jti = jwt_payload.get('jti')
        # Try Redis first
        try:
            import redis
            r = redis.from_url(app.config['REDIS_URL'])
            return r.get(f'blacklist:{jti}') is not None
        except Exception:
            return jti in JWT_DENYLIST

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({'success': False, 'error': 'Token has been revoked'}), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({'success': False, 'error': 'Token has expired'}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({'success': False, 'error': 'Invalid token'}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    # ── Blueprints ───────────────────────────────────────────
    from routes.api   import api_bp
    from routes.pages import pages_bp
    from routes.auth  import auth_bp
    from routes.ai_services import ai_bp

    app.register_blueprint(api_bp,   url_prefix='/api')
    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp,  url_prefix='/auth')
    app.register_blueprint(ai_bp,    url_prefix='/api')

    # ── Health check ─────────────────────────────────────────
    @app.route('/health')
    def health():
        db_ok    = False
        redis_ok = False

        try:
            db.session.execute(db.text('SELECT 1'))
            db_ok = True
        except Exception:
            pass

        try:
            import redis
            r = redis.from_url(app.config['REDIS_URL'], socket_connect_timeout=1)
            r.ping()
            redis_ok = True
        except Exception:
            pass

        status = 'ok' if db_ok else 'degraded'
        code   = 200 if db_ok else 503
        return jsonify({'status': status, 'db': db_ok, 'redis': redis_ok}), code

    # ── Shell context ─────────────────────────────────────────
    @app.shell_context_processor
    def make_shell_context():
        from models.db_models import User, Trip, Achievement, UserStats
        return {'db': db, 'User': User, 'Trip': Trip,
                'Achievement': Achievement, 'UserStats': UserStats}

    return app


# ── Entry point ───────────────────────────────────────────────
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)