# extensions.py
"""
Shared Flask extension instances.
Import from here to avoid circular imports.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS

db      = SQLAlchemy()
migrate = Migrate()
jwt     = JWTManager()
cors    = CORS()
limiter = Limiter(key_func=get_remote_address, default_limits=[])

# In-memory JWT denylist (use Redis in production)
JWT_DENYLIST: set = set()
