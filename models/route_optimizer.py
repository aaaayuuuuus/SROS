# models/route_optimizer.py
import math
import random
from models.emission_calculator import EmissionCalculator

calculator = EmissionCalculator()

class RouteOptimizer:
    """
    Computes route options between two locations.
    Uses Haversine distance estimation + route variation heuristics.
    (For full OSMnx graph routing, swap _haversine_route with osmnx graph lookup.)
    """

    def get_routes(self, origin: str, destination: str, vehicle: str, priority: str) -> list:
        # Geocode both points
        origin_coords      = self._geocode(origin)
        destination_coords = self._geocode(destination)

        if not origin_coords or not destination_coords:
            raise ValueError(f"Could not geocode: {origin} or {destination}")

        straight_km = self._haversine(origin_coords, destination_coords)

        # Generate 3 route variants
        routes = []

        variants = [
            {
                'type': 'fastest',
                'label': 'Fastest Route',
                'description': 'Via major highways — least time, more emissions.',
                'distance_factor': 1.10,
                'time_factor': 1.0,
                'green_penalty': 15,
                'color': '#ef4444',
            },
            {
                'type': 'balanced',
                'label': 'Balanced Route',
                'description': 'Optimal trade-off between speed and emissions.',
                'distance_factor': 1.18,
                'time_factor': 1.15,
                'green_penalty': 5,
                'color': '#f59e0b',
            },
            {
                'type': 'greenest',
                'label': 'Greenest Route',
                'description': 'Avoids highways — lower emissions, slight detour.',
                'distance_factor': 1.28,
                'time_factor': 1.30,
                'green_penalty': 0,
                'color': '#22c55e',
            },
        ]

        for v in variants:
            dist_km   = round(straight_km * v['distance_factor'], 2)
            speed_kmh = self._avg_speed(v['type'], vehicle)
            time_min  = round((dist_km / speed_kmh) * 60, 1)

            em = calculator.calculate(dist_km, vehicle)
            em['green_score'] = max(0, em['green_score'] - v['green_penalty'])

            waypoints = self._generate_waypoints(origin_coords, destination_coords, v['type'])

            routes.append({
                'type':          v['type'],
                'label':         v['label'],
                'description':   v['description'],
                'distance_km':   dist_km,
                'time_min':      time_min,
                'emissions':     em,
                'color':         v['color'],
                'waypoints':     waypoints,
                'origin_coords': origin_coords,
                'dest_coords':   destination_coords,
            })

        return routes

    def _geocode(self, place: str) -> dict | None:
        # Hardcoded Indian city coords for offline demo
        cities = {
            'delhi':     {'lat': 28.6139, 'lng': 77.2090},
            'new delhi': {'lat': 28.6139, 'lng': 77.2090},
            'mumbai':    {'lat': 19.0760, 'lng': 72.8777},
            'bangalore': {'lat': 12.9716, 'lng': 77.5946},
            'bengaluru': {'lat': 12.9716, 'lng': 77.5946},
            'hyderabad': {'lat': 17.3850, 'lng': 78.4867},
            'pune':      {'lat': 18.5204, 'lng': 73.8567},
            'chennai':   {'lat': 13.0827, 'lng': 80.2707},
            'kolkata':   {'lat': 22.5726, 'lng': 88.3639},
            'jaipur':    {'lat': 26.9124, 'lng': 75.7873},
            'noida':     {'lat': 28.5355, 'lng': 77.3910},
            'gurgaon':   {'lat': 28.4595, 'lng': 77.0266},
            'gurugram':  {'lat': 28.4595, 'lng': 77.0266},
            'ahmedabad': {'lat': 23.0225, 'lng': 72.5714},
            'lucknow':   {'lat': 26.8467, 'lng': 80.9462},
            'agra':      {'lat': 27.1767, 'lng': 78.0081},
            'chandigarh':{'lat': 30.7333, 'lng': 76.7794},
        }
        key = place.strip().lower()
        return cities.get(key)

    def _haversine(self, a: dict, b: dict) -> float:
        R = 6371
        lat1, lng1 = math.radians(a['lat']), math.radians(a['lng'])
        lat2, lng2 = math.radians(b['lat']), math.radians(b['lng'])
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlng/2)**2
        return R * 2 * math.asin(math.sqrt(h))

    def _avg_speed(self, route_type: str, vehicle: str) -> float:
        speeds = {
            'fastest':  {'car_petrol': 80, 'car_diesel': 80, 'car_cng': 75,
                         'car_electric': 80, 'bike_petrol': 70, 'bicycle': 20, 'public_bus': 45},
            'balanced': {'car_petrol': 55, 'car_diesel': 55, 'car_cng': 50,
                         'car_electric': 55, 'bike_petrol': 50, 'bicycle': 18, 'public_bus': 35},
            'greenest': {'car_petrol': 40, 'car_diesel': 40, 'car_cng': 38,
                         'car_electric': 42, 'bike_petrol': 38, 'bicycle': 16, 'public_bus': 28},
        }
        return speeds.get(route_type, {}).get(vehicle, 50)

    def _generate_waypoints(self, origin: dict, dest: dict, route_type: str) -> list:
        """Generate intermediate lat/lng points to draw a realistic curved path on the map."""
        points = [origin]
        steps  = 4

        lat_diff = dest['lat'] - origin['lat']
        lng_diff = dest['lng'] - origin['lng']

        offsets = {'fastest': 0.01, 'balanced': 0.025, 'greenest': 0.05}
        spread  = offsets.get(route_type, 0.02)

        for i in range(1, steps):
            t = i / steps
            mid_lat = origin['lat'] + lat_diff * t + random.uniform(-spread, spread)
            mid_lng = origin['lng'] + lng_diff * t + random.uniform(-spread, spread)
            points.append({'lat': round(mid_lat, 5), 'lng': round(mid_lng, 5)})

        points.append(dest)
        return points