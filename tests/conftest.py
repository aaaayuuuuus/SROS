# tests/conftest.py
"""
Shared pytest fixtures for SROS test suite.
Uses a file-based test SQLite so the conftest session and Flask request handlers
use genuinely separate connections (avoids SQLAlchemy identity-map conflicts
that occur when StaticPool + same thread share one session object).
"""
import os
import pytest
from app import create_app
from extensions import db as _db
from models.db_models import User, Trip, UserStats, Achievement

# Path to the test DB file (created fresh each test session)
_TEST_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'instance', 'test_sros.db'
)


@pytest.fixture(scope='session')
def app():
    """Session-wide test application backed by a file-based test SQLite."""
    application = create_app('testing')

    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()

    # Clean up the test DB file after the session
    for path in (
        _TEST_DB_PATH,
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'test_sros.db'),
    ):
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


@pytest.fixture(scope='function')
def client(app):
    return app.test_client()


# ── Clean-up helper ───────────────────────────────────────────────────────────

def _wipe_test_user(app):
    """Remove test@sros.in and all its child rows using raw SQL."""
    with app.app_context():
        try:
            row = _db.session.execute(
                _db.text("SELECT id FROM users WHERE email = 'test@sros.in'")
            ).fetchone()
            if row:
                uid = row[0]
                for sql in [
                    f"DELETE FROM achievements WHERE user_id = {uid}",
                    f"DELETE FROM trips WHERE user_id = {uid}",
                    f"DELETE FROM user_stats WHERE id = {uid}",
                    f"DELETE FROM users WHERE id = {uid}",
                ]:
                    _db.session.execute(_db.text(sql))
                _db.session.commit()
        except Exception:
            _db.session.rollback()
        finally:
            _db.session.remove()   # expire all cached objects


# ── auth_headers fixture ──────────────────────────────────────────────────────

@pytest.fixture(scope='function')
def auth_headers(client, app):
    """Register a fresh test user each test, yield bearer headers, then clean up."""
    _wipe_test_user(app)

    res = client.post('/auth/register', json={
        'name':     'Test User',
        'email':    'test@sros.in',
        'password': 'TestPass123!',
    })
    assert res.status_code == 201, f"Register failed: {res.get_json()}"

    token = res.get_json()['data']['access_token']
    yield {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

    _wipe_test_user(app)


# ── test_user fixture ─────────────────────────────────────────────────────────

@pytest.fixture(scope='function')
def test_user(app, auth_headers):
    with app.app_context():
        _db.session.remove()
        return User.query.filter_by(email='test@sros.in').first()


# ── sample_trip fixture ───────────────────────────────────────────────────────

@pytest.fixture(scope='function')
def sample_trip(app, auth_headers):
    """Create a Trip for the test user; yields the integer trip id."""
    with app.app_context():
        _db.session.remove()
        u = User.query.filter_by(email='test@sros.in').first()
        if not u:
            pytest.skip('Test user not found')

        t = Trip(
            user_id       = u.id,
            origin        = 'Delhi',
            destination   = 'Agra',
            origin_lat    = 28.6139,
            origin_lng    = 77.2090,
            dest_lat      = 27.1767,
            dest_lng      = 78.0081,
            vehicle_type  = 'car_petrol',
            route_type    = 'balanced',
            distance_km   = 210.5,
            time_min      = 180.0,
            co2_kg        = 36.0,
            fuel_cost_inr = 1368.25,
            co2_saved_kg  = 0.0,
            green_score   = 50,
        )
        _db.session.add(t)
        _db.session.commit()
        trip_id = t.id
        _db.session.remove()

    yield trip_id
