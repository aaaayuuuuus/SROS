# tests/test_api.py
"""
Tests for API endpoints: optimize, stats, trips, leaderboard.
"""
import pytest
from unittest.mock import patch


# ── /api/optimize ──────────────────────────────────────────────────────────

class TestOptimize:
    def test_optional_auth_returns_routes(self, client):
        res = client.post('/api/optimize', json={
            'origin': 'Delhi', 'destination': 'Mumbai', 'vehicle': 'car_petrol', 'priority': 'balanced'
        })
        assert res.status_code == 200
        assert len(res.get_json()['data']['routes']) == 3

    def test_valid_request_returns_three_routes(self, client, auth_headers):
        res = client.post('/api/optimize',
                          headers=auth_headers,
                          json={
                              'origin':      'Delhi',
                              'destination': 'Mumbai',
                              'vehicle':     'car_petrol',
                              'priority':    'balanced',
                          })
        assert res.status_code == 200
        data = res.get_json()
        assert data['success'] is True
        routes = data['data']['routes']
        assert len(routes) == 3

    def test_route_types_present(self, client, auth_headers):
        res = client.post('/api/optimize',
                          headers=auth_headers,
                          json={'origin': 'Delhi', 'destination': 'Agra',
                                'vehicle': 'car_electric'})
        assert res.status_code == 200
        types = [r['type'] for r in res.get_json()['data']['routes']]
        assert set(types) == {'fastest', 'balanced', 'greenest'}

    def test_missing_fields_returns_400(self, client, auth_headers):
        res = client.post('/api/optimize',
                          headers=auth_headers,
                          json={'origin': 'Delhi'})
        assert res.status_code == 400

    def test_unknown_city_returns_404(self, client, auth_headers):
        res = client.post('/api/optimize',
                          headers=auth_headers,
                          json={'origin': 'ZZZUnknown999',
                                'destination': 'Mumbai',
                                'vehicle': 'car_petrol'})
        assert res.status_code == 404

    def test_response_includes_new_achievements_key(self, client, auth_headers):
        res = client.post('/api/optimize',
                          headers=auth_headers,
                          json={'origin': 'Delhi', 'destination': 'Agra',
                                'vehicle': 'car_petrol'})
        assert res.status_code == 200
        assert 'new_achievements' in res.get_json()['data']


# ── /api/stats ─────────────────────────────────────────────────────────────

class TestStats:
    def test_requires_auth(self, client):
        assert client.get('/api/stats').status_code == 401

    def test_returns_correct_structure(self, client, auth_headers):
        res = client.get('/api/stats', headers=auth_headers)
        assert res.status_code == 200
        d = res.get_json()['data']
        for key in ('total_trips', 'total_co2_saved_kg', 'total_distance_km',
                    'total_fuel_saved_inr', 'streak_days', 'monthly_co2',
                    'best_green_score', 'favorite_vehicle', 'most_used_route_type'):
            assert key in d, f"Missing key: {key}"

    def test_monthly_co2_has_six_entries(self, client, auth_headers):
        res = client.get('/api/stats', headers=auth_headers)
        monthly = res.get_json()['data']['monthly_co2']
        assert len(monthly) == 6

    def test_monthly_co2_structure(self, client, auth_headers):
        res = client.get('/api/stats', headers=auth_headers)
        for m in res.get_json()['data']['monthly_co2']:
            assert 'month' in m and 'co2_kg' in m and 'trips' in m


# ── /api/trips ─────────────────────────────────────────────────────────────

class TestTrips:
    def test_requires_auth(self, client):
        assert client.get('/api/trips').status_code == 401

    def test_returns_paginated_list(self, client, auth_headers, sample_trip):
        res = client.get('/api/trips', headers=auth_headers)
        assert res.status_code == 200
        d = res.get_json()['data']
        assert 'trips' in d
        assert 'total_count' in d
        assert 'pages' in d
        assert 'current_page' in d

    def test_pagination_params(self, client, auth_headers, sample_trip):
        res = client.get('/api/trips?page=1&per_page=5', headers=auth_headers)
        assert res.status_code == 200

    def test_single_trip_detail(self, client, auth_headers, sample_trip):
        # sample_trip fixture now yields the integer trip id
        tid = sample_trip
        res = client.get(f'/api/trips/{tid}', headers=auth_headers)
        assert res.status_code == 200
        assert res.get_json()['data']['id'] == tid

    def test_404_for_other_users_trip(self, client, auth_headers):
        res = client.get('/api/trips/999999', headers=auth_headers)
        assert res.status_code == 404


# ── /api/leaderboard ───────────────────────────────────────────────────────

class TestLeaderboard:
    def test_returns_list(self, client):
        res = client.get('/api/leaderboard')
        assert res.status_code == 200
        data = res.get_json()
        assert data['success'] is True
        assert isinstance(data['data'], list)

    def test_max_ten_entries(self, client):
        res = client.get('/api/leaderboard')
        assert len(res.get_json()['data']) <= 10

    def test_entry_has_required_fields(self, client, auth_headers):
        # Ensure at least one user in the DB
        client.post('/api/optimize',
                    headers=auth_headers,
                    json={'origin': 'Delhi', 'destination': 'Agra',
                          'vehicle': 'car_petrol'})
        res = client.get('/api/leaderboard')
        entries = res.get_json()['data']
        if entries:
            for key in ('rank', 'name', 'savings_kg', 'trips', 'green_badge'):
                assert key in entries[0]


# ── /api/achievements ──────────────────────────────────────────────────────

class TestAchievements:
    def test_requires_auth(self, client):
        assert client.get('/api/achievements').status_code == 401

    def test_returns_seven_badges(self, client, auth_headers):
        res = client.get('/api/achievements', headers=auth_headers)
        assert res.status_code == 200
        badges = res.get_json()['data']
        assert len(badges) == 7

    def test_badge_structure(self, client, auth_headers):
        res = client.get('/api/achievements', headers=auth_headers)
        for b in res.get_json()['data']:
            for key in ('badge_name', 'badge_icon', 'description', 'earned', 'earned_at'):
                assert key in b
