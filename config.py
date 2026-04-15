# config.py
import os
from datetime import timedelta


class Config:
    """Base configuration."""
    SECRET_KEY                          = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
    JWT_SECRET_KEY                      = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-change-me')
    JWT_ACCESS_TOKEN_EXPIRES            = timedelta(days=1)
    JWT_REFRESH_TOKEN_EXPIRES           = timedelta(days=30)
    JWT_TOKEN_LOCATION                  = ['headers', 'cookies']
    JWT_COOKIE_SECURE                   = False
    JWT_COOKIE_CSRF_PROTECT             = False

    SQLALCHEMY_TRACK_MODIFICATIONS      = False
    SQLALCHEMY_ECHO                     = False

    # Redis
    REDIS_URL                           = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

    # ORS
    ORS_API_KEY                         = os.environ.get('ORS_API_KEY', '')

    # Rate limiting
    RATELIMIT_DEFAULT                   = '200 per day;50 per hour'
    RATELIMIT_STORAGE_URI               = os.environ.get('REDIS_URL', 'memory://')

    # CORS
    ALLOWED_ORIGINS                     = os.environ.get(
        'ALLOWED_ORIGINS', 'http://localhost:5000,http://127.0.0.1:5000'
    ).split(',')


class DevelopmentConfig(Config):
    DEBUG                               = True
    SQLALCHEMY_DATABASE_URI             = os.environ.get(
        'DATABASE_URL',
        'sqlite:///sros_dev.db'
    )
    SQLALCHEMY_ECHO                     = False


class TestingConfig(Config):
    TESTING                             = True
    DEBUG                               = True
    # File-based SQLite for tests: separate connections see each other's
    # committed data, avoiding the identity-map sharing problem of StaticPool.
    SQLALCHEMY_DATABASE_URI             = 'sqlite:///test_sros.db'
    JWT_SECRET_KEY                      = 'test-jwt-secret-key-at-least-32-chars!!'
    JWT_ACCESS_TOKEN_EXPIRES            = timedelta(minutes=30)
    RATELIMIT_ENABLED                   = False
    WTF_CSRF_ENABLED                    = False


class ProductionConfig(Config):
    DEBUG                               = False
    TESTING                             = False

    # PostgreSQL is required in production
    _db_url = os.environ.get('DATABASE_URL', '')
    # Railway / Render supply postgres:// but SQLAlchemy needs postgresql://
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI             = _db_url

    # Connection pool
    SQLALCHEMY_ENGINE_OPTIONS           = {
        'pool_size':         5,
        'max_overflow':      10,
        'pool_timeout':      30,
        'pool_recycle':      1800,
    }

    # Secure cookies
    JWT_COOKIE_SECURE                   = True
    JWT_COOKIE_CSRF_PROTECT             = True
    SESSION_COOKIE_SECURE               = True
    SESSION_COOKIE_HTTPONLY             = True
    SESSION_COOKIE_SAMESITE             = 'Lax'

    # Rate limit storage via Redis
    RATELIMIT_STORAGE_URI               = os.environ.get('REDIS_URL', 'memory://')


config_map = {
    'development': DevelopmentConfig,
    'testing':     TestingConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}
