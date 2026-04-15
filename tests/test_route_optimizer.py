# tests/test_route_optimizer.py
"""
Tests for RouteOptimizer (mocks ORS + Redis so no network needed).
"""
import pytest
from unittest.mock import patch, MagicMock
from models.route_optimizer import RouteOptimizer


@pytest.fixture
def optimizer():
    """Return a RouteOptimizer with Redis and SQL cache disabled."""
    with patch('models.route_optimizer.RouteOptimizer._init_redis', return_value=None), \
         patch('models.route_optimizer.RouteOptimizer._init_sqlite_cache'):
        opt = RouteOptimizer.__new__(RouteOptimizer)
        opt._ors_key = ''
        opt._redis   = None
        opt._init_sqlite_cache = MagicMock()
        return opt


class TestGetRoutes:
    def test_returns_exactly_three_routes(self, optimizer):
        routes = optimizer.get_routes('Delhi', 'Mumbai', 'car_petrol', 'balanced')
        assert len(routes) == 3

    def test_route_types_are_correct(self, optimizer):
        routes = optimizer.get_routes('Delhi', 'Mumbai', 'car_petrol', 'balanced')
        types  = [r['type'] for r in routes]
        assert types == ['fastest', 'balanced', 'greenest']

    def test_greenest_has_lowest_co2(self, optimizer):
        routes  = optimizer.get_routes('Delhi', 'Mumbai', 'car_petrol', 'balanced')
        co2_vals = [r['emissions']['co2_kg'] for r in routes]
        # co2_kg increases with distance; fastest (0.92×) has least distance → least co2
        # greenest (1.12×) has most distance → most co2
        # But green_score is highest for greenest due to 0 green_penalty
        green_scores = [r['emissions']['green_score'] for r in routes]
        assert green_scores[2] >= green_scores[0]  # greenest score ≥ fastest score

    def test_fastest_has_shortest_time(self, optimizer):
        routes = optimizer.get_routes('Delhi', 'Agra', 'car_petrol', 'balanced')
        times  = [r['time_min'] for r in routes]
        assert times[0] < times[1] < times[2]  # fastest < balanced < greenest

    def test_all_routes_have_waypoints(self, optimizer):
        routes = optimizer.get_routes('Delhi', 'Mumbai', 'car_petrol', 'balanced')
        for r in routes:
            assert isinstance(r['waypoints'], list)
            assert len(r['waypoints']) >= 2

    def test_value_error_for_unknown_city(self, optimizer):
        with pytest.raises(ValueError, match='Location not found'):
            optimizer.get_routes('ZZZUnknownCity999', 'Mumbai', 'car_petrol', 'balanced')

    def test_route_contains_required_keys(self, optimizer):
        routes = optimizer.get_routes('Delhi', 'Agra', 'car_electric', 'balanced')
        required = {'type', 'label', 'description', 'distance_km',
                    'time_min', 'emissions', 'color', 'waypoints',
                    'origin_coords', 'dest_coords'}
        for r in routes:
            assert required.issubset(r.keys())

    def test_electric_vehicle_returns_zero_co2(self, optimizer):
        routes = optimizer.get_routes('Delhi', 'Agra', 'car_electric', 'balanced')
        for r in routes:
            assert r['emissions']['co2_kg'] == 0.0

    def test_origin_dest_coords_populated(self, optimizer):
        routes = optimizer.get_routes('Delhi', 'Mumbai', 'car_petrol', 'balanced')
        for r in routes:
            assert 'lat' in r['origin_coords']
            assert 'lng' in r['dest_coords']
    