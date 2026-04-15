# tests/test_emission_calculator.py
"""
Unit tests for EmissionCalculator.
"""
import pytest
from models.emission_calculator import EmissionCalculator

calc = EmissionCalculator()


class TestCalculate:
    """Test calculate() for all 7 vehicle profiles at 10 km."""

    EXPECTED = {
        # vehicle_key: expected co2_kg for 10 km (grams/km × 10 / 1000)
        'car_petrol':   round(171 * 10 / 1000, 3),   # 1.71
        'car_diesel':   round(145 * 10 / 1000, 3),   # 1.45
        'car_cng':      round(96  * 10 / 1000, 3),   # 0.96
        'car_electric': 0.0,
        'bike_petrol':  round(83  * 10 / 1000, 3),   # 0.83
        'bicycle':      0.0,
        'public_bus':   round(14  * 10 / 1000, 3),   # 0.14
    }

    @pytest.mark.parametrize('vehicle,expected_co2', EXPECTED.items())
    def test_co2_kg_for_10km(self, vehicle, expected_co2):
        result = calc.calculate(10, vehicle)
        assert result['co2_kg'] == expected_co2, (
            f"{vehicle}: expected {expected_co2}, got {result['co2_kg']}")

    def test_electric_co2_is_zero(self):
        result = calc.calculate(10, 'car_electric')
        assert result['co2_kg'] == 0.0

    def test_bicycle_co2_is_zero(self):
        result = calc.calculate(10, 'bicycle')
        assert result['co2_kg'] == 0.0

    def test_green_score_100_for_zero_emission(self):
        for key in ('car_electric', 'bicycle'):
            result = calc.calculate(100, key)
            assert result['green_score'] == 100, (
                f"{key} should have green_score=100, got {result['green_score']}")

    def test_fuel_cost_is_non_negative(self):
        for key in calc.VEHICLE_PROFILES:
            result = calc.calculate(50, key)
            assert result['fuel_cost_inr'] >= 0

    def test_co2_saved_is_non_negative(self):
        # Baseline is petrol car; petrol car itself should have 0 savings
        result = calc.calculate(100, 'car_petrol')
        assert result['co2_saved_kg'] >= 0

    def test_result_contains_required_keys(self):
        result = calc.calculate(100, 'car_petrol')
        for k in ('vehicle', 'co2_kg', 'fuel_cost_inr',
                  'co2_saved_kg', 'green_score', 'trees_equivalent'):
            assert k in result


class TestCompareAll:
    def test_returns_seven_entries(self):
        results = calc.compare_all(100)
        assert len(results) == 7

    def test_sorted_ascending_by_co2_kg(self):
        results = calc.compare_all(100)
        co2_vals = [r['co2_kg'] for r in results]
        assert co2_vals == sorted(co2_vals)

    def test_zero_emission_vehicles_first(self):
        results = calc.compare_all(100)
        # First two should be 0 (electric + bicycle)
        assert results[0]['co2_kg'] == 0
        assert results[1]['co2_kg'] == 0
