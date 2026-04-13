# models/emission_calculator.py
# CO2 emission factors in grams per km (sourced from ICCT & EEA data)

class EmissionCalculator:

    VEHICLE_PROFILES = {
        'car_petrol': {
            'label': 'Petrol Car',
            'icon': '🚗',
            'co2_per_km': 171,       # grams
            'fuel_cost_per_km': 6.5, # INR approx
            'color': '#ef4444'
        },
        'car_diesel': {
            'label': 'Diesel Car',
            'icon': '🚙',
            'co2_per_km': 145,
            'fuel_cost_per_km': 5.8,
            'color': '#f97316'
        },
        'car_cng': {
            'label': 'CNG Car',
            'icon': '🚘',
            'co2_per_km': 96,
            'fuel_cost_per_km': 3.2,
            'color': '#eab308'
        },
        'car_electric': {
            'label': 'Electric Car',
            'icon': '⚡',
            'co2_per_km': 0,
            'fuel_cost_per_km': 1.2,
            'color': '#22c55e'
        },
        'bike_petrol': {
            'label': 'Petrol Bike',
            'icon': '🏍️',
            'co2_per_km': 83,
            'fuel_cost_per_km': 3.0,
            'color': '#a855f7'
        },
        'bicycle': {
            'label': 'Bicycle',
            'icon': '🚲',
            'co2_per_km': 0,
            'fuel_cost_per_km': 0,
            'color': '#14b8a6'
        },
        'public_bus': {
            'label': 'Public Bus',
            'icon': '🚌',
            'co2_per_km': 14,  # per passenger
            'fuel_cost_per_km': 0.8,
            'color': '#3b82f6'
        },
    }

    # Baseline reference: average petrol car (171g/km)
    BASELINE_VEHICLE = 'car_petrol'

    def calculate(self, distance_km: float, vehicle_key: str) -> dict:
        profile = self.VEHICLE_PROFILES.get(vehicle_key, self.VEHICLE_PROFILES['car_petrol'])
        baseline = self.VEHICLE_PROFILES[self.BASELINE_VEHICLE]

        co2_grams = profile['co2_per_km'] * distance_km
        co2_kg    = round(co2_grams / 1000, 3)
        fuel_cost = round(profile['fuel_cost_per_km'] * distance_km, 2)

        # Savings compared to baseline petrol car
        baseline_co2_kg = round(baseline['co2_per_km'] * distance_km / 1000, 3)
        co2_saved_kg    = round(baseline_co2_kg - co2_kg, 3)

        # Trees equivalent (1 tree absorbs ~21 kg CO2/year)
        trees_equivalent = round(co2_saved_kg / 21, 2)

        # Green score 0-100 (inverse of emission ratio)
        max_co2 = baseline['co2_per_km']
        green_score = int(100 * (1 - profile['co2_per_km'] / max_co2)) if max_co2 > 0 else 100

        return {
            'vehicle': vehicle_key,
            'vehicle_label': profile['label'],
            'distance_km': round(distance_km, 2),
            'co2_kg': co2_kg,
            'fuel_cost_inr': fuel_cost,
            'co2_saved_kg': max(0, co2_saved_kg),
            'trees_equivalent': max(0, trees_equivalent),
            'green_score': green_score,
            'color': profile['color'],
        }

    def compare_all(self, distance_km: float) -> list:
        results = []
        for key in self.VEHICLE_PROFILES:
            r = self.calculate(distance_km, key)
            results.append(r)
        return sorted(results, key=lambda x: x['co2_kg'])

    def get_vehicle_profiles(self) -> dict:
        return self.VEHICLE_PROFILES