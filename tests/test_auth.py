# tests/test_auth.py
"""
Tests for authentication endpoints.
"""
import pytest


class TestRegister:
    def test_successful_register_returns_201(self, client, app):
        with app.app_context():
            from extensions import db
            from models.db_models import User
            User.query.filter_by(email='new@sros.in').delete()
            db.session.commit()

        res = client.post('/auth/register', json={
            'name':     'New User',
            'email':    'new@sros.in',
            'password': 'StrongPass1!',
        })
        assert res.status_code == 201
        data = res.get_json()
        assert data['success'] is True
        assert 'access_token' in data['data']
        assert 'refresh_token' in data['data']

    def test_duplicate_email_returns_409(self, client, auth_headers):
        res = client.post('/auth/register', json={
            'name':     'Dup User',
            'email':    'test@sros.in',
            'password': 'StrongPass1!',
        })
        assert res.status_code == 409
        assert res.get_json()['success'] is False

    def test_invalid_email_returns_400(self, client):
        res = client.post('/auth/register', json={
            'name':     'Bad User',
            'email':    'not-an-email',
            'password': 'StrongPass1!',
        })
        assert res.status_code == 400

    def test_short_password_returns_400(self, client):
        res = client.post('/auth/register', json={
            'name':     'Short User',
            'email':    'short@sros.in',
            'password': '123',
        })
        assert res.status_code == 400

    def test_missing_name_returns_400(self, client):
        res = client.post('/auth/register', json={
            'email':    'noname@sros.in',
            'password': 'StrongPass1!',
        })
        assert res.status_code == 400


class TestLogin:
    def test_successful_login(self, client, auth_headers):
        res = client.post('/auth/login', json={
            'email':    'test@sros.in',
            'password': 'TestPass123!',
        })
        assert res.status_code == 200
        assert res.get_json()['data']['access_token']

    def test_wrong_password_returns_401(self, client, auth_headers):
        res = client.post('/auth/login', json={
            'email':    'test@sros.in',
            'password': 'wrong-password',
        })
        assert res.status_code == 401

    def test_unknown_email_returns_401(self, client):
        res = client.post('/auth/login', json={
            'email':    'nobody@sros.in',
            'password': 'SomePass1!',
        })
        assert res.status_code == 401

    def test_missing_fields_returns_400(self, client):
        res = client.post('/auth/login', json={})
        assert res.status_code == 400


class TestMe:
    def test_me_returns_user_with_valid_token(self, client, auth_headers):
        res = client.get('/auth/me', headers=auth_headers)
        assert res.status_code == 200
        data = res.get_json()
        assert data['success'] is True
        assert data['data']['email'] == 'test@sros.in'

    def test_me_returns_401_with_no_token(self, client):
        res = client.get('/auth/me')
        assert res.status_code == 401

    def test_me_returns_401_with_bad_token(self, client):
        res = client.get('/auth/me', headers={'Authorization': 'Bearer bad.token.here'})
        assert res.status_code == 401


class TestRefresh:
    def test_refresh_returns_new_access_token(self, client, app):
        with app.app_context():
            from extensions import db
            from models.db_models import User
            User.query.filter_by(email='refresh@sros.in').delete()
            db.session.commit()

        reg = client.post('/auth/register', json={
            'name': 'Refresh User', 'email': 'refresh@sros.in', 'password': 'TestPass123!'
        })
        refresh_token = reg.get_json()['data']['refresh_token']

        res = client.post('/auth/refresh',
                          headers={'Authorization': f'Bearer {refresh_token}'})
        assert res.status_code == 200
        assert 'access_token' in res.get_json()['data']
