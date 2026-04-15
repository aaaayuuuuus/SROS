# routes/auth.py
"""
Authentication blueprint: register, login, logout, me, refresh.

NOTE: PyJWT 2.12+ requires the JWT `sub` claim to be a STRING.
All identity values are stored as str(user.id) and cast back with int().
"""
from datetime import datetime, timedelta
import bcrypt
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt,
    verify_jwt_in_request
)
from email_validator import validate_email, EmailNotValidError

from extensions import db, JWT_DENYLIST
from models.db_models import User, UserStats

auth_bp = Blueprint('auth', __name__)

# ── helpers ────────────────────────────────────────────────────────────────

def _ok(data=None, code=200):
    return jsonify({'success': True, 'data': data, 'error': None}), code

def _err(msg, code=400):
    return jsonify({'success': False, 'data': None, 'error': msg}), code

def _blacklist_jti(jti: str):
    """Add JTI to the Redis denylist or fallback in-memory set."""
    try:
        import redis, flask
        r = redis.from_url(flask.current_app.config['REDIS_URL'])
        r.setex(f'blacklist:{jti}', int(timedelta(days=31).total_seconds()), '1')
    except Exception:
        JWT_DENYLIST.add(jti)


# ── decorators ─────────────────────────────────────────────────────────────

def login_required(fn):
    """Require a valid JWT. Returns 401 JSON on failure."""
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request(locations=['headers', 'cookies'])
            # identity is stored as str(user.id); cast back to int for DB lookup
            user_id = int(get_jwt_identity())
            g.current_user = User.query.get(user_id)
            if not g.current_user or not g.current_user.is_active:
                return _err('Account not found or inactive', 401)
        except Exception as e:
            return _err(str(e) or 'Authentication required', 401)
        return fn(*args, **kwargs)
    return wrapper


def optional_auth(fn):
    """Populate g.current_user if a valid token exists; never blocks."""
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        g.current_user = None
        try:
            verify_jwt_in_request(locations=['headers', 'cookies'], optional=True)
            uid = get_jwt_identity()
            if uid:
                g.current_user = User.query.get(int(uid))
        except Exception:
            pass
        return fn(*args, **kwargs)
    return wrapper


# ── POST /auth/register ────────────────────────────────────────────────────

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}

    name     = (data.get('name') or '').strip()
    email    = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not name:
        return _err('Name is required')
    if len(password) < 8:
        return _err('Password must be at least 8 characters')

    # Validate email
    try:
        valid = validate_email(email, check_deliverability=False)
        email = valid.email
    except EmailNotValidError as e:
        return _err(str(e))

    # Duplicate check
    if User.query.filter_by(email=email).first():
        return _err('An account with this email already exists', 409)

    # Hash password
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    user = User(name=name, email=email, password_hash=pw_hash)
    db.session.add(user)
    db.session.flush()  # get user.id before commit

    # Create empty stats row
    stats = UserStats(id=user.id)
    db.session.add(stats)
    db.session.commit()

    # identity MUST be a string for PyJWT 2.12+
    access_token  = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return _ok({
        'user':          user.to_dict(),
        'access_token':  access_token,
        'refresh_token': refresh_token,
    }, 201)


# ── POST /auth/login ───────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}

    email    = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return _err('Email and password required')

    user = User.query.filter_by(email=email).first()
    if not user or not user.is_active:
        return _err('Invalid credentials', 401)

    if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        return _err('Invalid credentials', 401)

    # identity MUST be a string for PyJWT 2.12+
    access_token  = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return _ok({
        'user':          user.to_dict(),
        'access_token':  access_token,
        'refresh_token': refresh_token,
    })


# ── POST /auth/logout ──────────────────────────────────────────────────────

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    jti = get_jwt().get('jti')
    _blacklist_jti(jti)
    return _ok({'message': 'Logged out successfully'})


# ── GET /auth/me ───────────────────────────────────────────────────────────

@auth_bp.route('/me', methods=['GET'])
@login_required
def me():
    return _ok(g.current_user.to_dict())


# ── POST /auth/refresh ─────────────────────────────────────────────────────

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    user_id      = get_jwt_identity()          # already a str
    access_token = create_access_token(identity=user_id)
    return _ok({'access_token': access_token})
