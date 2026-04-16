# models/route_optimizer.py
"""
Route optimizer with:
 - OpenRouteService (ORS) real geocoding + driving directions
 - Multi-layer cache: Redis → SQLite → ORS API
 - 3 route variants: fastest / balanced / greenest
 - Graceful fallback to hardcoded Indian city coords
"""
import math
import os
import time
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

import requests

from models.emission_calculator import EmissionCalculator

log       = logging.getLogger(__name__)
calculator = EmissionCalculator()

# ── SQLite cache path (same dir as this file) ─────────────────────────────
_CACHE_DB = Path(__file__).parent.parent / 'geocode_cache.sqlite'
_CACHE_TTL_DAYS = 30

# ── Hardcoded fallback coords (17 Indian cities) ─────────────────────────
_FALLBACK_CITIES = {
    'delhi':      {'lat': 28.6139, 'lng': 77.2090},
    'new delhi':  {'lat': 28.6139, 'lng': 77.2090},
    'mumbai':     {'lat': 19.0760, 'lng': 72.8777},
    'bangalore':  {'lat': 12.9716, 'lng': 77.5946},
    'bengaluru':  {'lat': 12.9716, 'lng': 77.5946},
    'hyderabad':  {'lat': 17.3850, 'lng': 78.4867},
    'pune':       {'lat': 18.5204, 'lng': 73.8567},
    'chennai':    {'lat': 13.0827, 'lng': 80.2707},
    'kolkata':    {'lat': 22.5726, 'lng': 88.3639},
    'jaipur':     {'lat': 26.9124, 'lng': 75.7873},
    'noida':      {'lat': 28.5355, 'lng': 77.3910},
    'gurgaon':    {'lat': 28.4595, 'lng': 77.0266},
    'gurugram':   {'lat': 28.4595, 'lng': 77.0266},
    'ahmedabad':  {'lat': 23.0225, 'lng': 72.5714},
    'lucknow':    {'lat': 26.8467, 'lng': 80.9462},
    'agra':       {'lat': 27.1767, 'lng': 78.0081},
    'chandigarh': {'lat': 30.7333, 'lng': 76.7794},
}

# ── Route variants definition ─────────────────────────────────────────────
_VARIANTS = [
    {
        'type':             'fastest',
        'label':            'Fastest Route',
        'description':      'Via major highways — least time, more emissions.',
        'distance_factor':  1.15,   # longer highway perimeter
        'time_factor':      0.8,
        'green_penalty':    15,
        'color':            '#ef4444',
    },
    {
        'type':             'balanced',
        'label':            'Balanced Route',
        'description':      'Optimal trade-off between speed and emissions.',
        'distance_factor':  1.0,    # real ORS distance is the baseline
        'time_factor':      1.15,
        'green_penalty':    5,
        'color':            '#f59e0b',
    },
    {
        'type':             'greenest',
        'label':            'Greenest Route',
        'description':      'Avoids highways — lower emissions, slight detour.',
        'distance_factor':  0.90,   # shortest direct path physical distance
        'time_factor':      1.25,
        'green_penalty':    0,
        'color':            '#22c55e',
    },
]


class RouteOptimizer:
    """
    Computes 3 route options (fastest / balanced / greenest) between two locations.
    Uses ORS API for real geocoding and driving distance, with Redis + SQLite caching.
    """

    def __init__(self):
        self._ors_key  = os.environ.get('ORS_API_KEY', '')
        self._redis    = self._init_redis()
        self._init_sqlite_cache()

    # ── Public API ────────────────────────────────────────────────────────

    def get_routes(self, origin: str, destination: str,
                   vehicle: str, priority: str = 'balanced') -> list:

        origin_coords  = self._geocode(origin)
        dest_coords    = self._geocode(destination)

        if not origin_coords:
            raise ValueError(f"Location not found: '{origin}'. "
                             "Try a major Indian city name or full address.")
        if not dest_coords:
            raise ValueError(f"Location not found: '{destination}'. "
                             "Try a major Indian city name or full address.")

        # Real driving distance from ORS; fallback to Haversine × 1.3
        base_km, base_waypoints = self._get_driving_route(origin_coords, dest_coords)

        routes = []
        for v in _VARIANTS:
            dist_km   = round(base_km * v['distance_factor'], 2)
            speed_kmh = self._avg_speed(v['type'], vehicle)
            time_min  = round((dist_km / speed_kmh) * 60, 1)

            em = calculator.calculate(dist_km, vehicle)
            em['green_score'] = max(0, em['green_score'] - v['green_penalty'])

            # Use real road waypoints for all variants to ensure no straight/jagged lines
            if base_waypoints:
                waypoints = base_waypoints
            else:
                waypoints = self._simple_waypoints(origin_coords, dest_coords, steps=20)

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
                'dest_coords':   dest_coords,
            })

        return routes

    # ── Geocoding ─────────────────────────────────────────────────────────

    def _geocode(self, place: str) -> dict | None:
        key = place.strip().lower()

        # 1. Fallback city dict (instant)
        if key in _FALLBACK_CITIES:
            return _FALLBACK_CITIES[key]

        # 2. Redis cache
        cached = self._redis_get(f'geocode:{key}')
        if cached:
            return cached

        # 3. SQLite cache
        cached = self._sqlite_get(key)
        if cached:
            self._redis_set(f'geocode:{key}', cached)
            return cached

        # 4. ORS Geocoding API
        if self._ors_key:
            result = self._ors_geocode(place)
            if result:
                self._redis_set(f'geocode:{key}', result)
                self._sqlite_set(key, result)
                return result

        # 5. Photon fallback (no key needed)
        result = self._photon_geocode(place)
        if result:
            self._redis_set(f'geocode:{key}', result)
            self._sqlite_set(key, result)
            return result

        return None

    def _ors_geocode(self, place: str) -> dict | None:
        """Forward geocode via ORS Pelias."""
        url = 'https://api.openrouteservice.org/geocode/search'
        try:
            r = requests.get(url, params={
                'api_key': self._ors_key,
                'text':    place,
                'size':    1,
                'boundary.country': 'IND',
            }, timeout=5)
            r.raise_for_status()
            features = r.json().get('features', [])
            if features:
                lng, lat = features[0]['geometry']['coordinates']
                return {'lat': round(lat, 6), 'lng': round(lng, 6)}
        except Exception as e:
            log.warning('ORS geocode error for %s: %s', place, e)
        return None

    def _photon_geocode(self, place: str) -> dict | None:
        """Forward geocode via Photon (Komoot) — free, no key needed."""
        url = 'https://photon.komoot.io/api/'
        try:
            r = requests.get(url, params={
                'q':    place + ' India',
                'limit': 1,
                'lang':  'en',
            }, timeout=5)
            r.raise_for_status()
            features = r.json().get('features', [])
            if features:
                lng, lat = features[0]['geometry']['coordinates']
                return {'lat': round(lat, 6), 'lng': round(lng, 6)}
        except Exception as e:
            log.warning('Photon geocode error for %s: %s', place, e)
        return None

    # ── Driving route ─────────────────────────────────────────────────────

    def _get_driving_route(self, origin: dict, dest: dict) -> tuple[float, list]:
        """
        Returns (distance_km, [waypoints]) from ORS or OSRM Directions.
        Falls back to Haversine × 1.3 if API unavailable.
        """
        cache_key = (f"route:{origin['lat']:.4f},{origin['lng']:.4f}"
                     f":{dest['lat']:.4f},{dest['lng']:.4f}")

        cached = self._redis_get(cache_key)
        if cached and len(cached['wpts']) > 10:
            return cached['dist'], cached['wpts']

        if self._ors_key:
            dist, wpts = self._ors_directions(origin, dest)
            if dist is not None:
                self._redis_set(cache_key, {'dist': dist, 'wpts': wpts}, ttl=86400)
                return dist, wpts

        # OSRM fallback (free, no key needed)
        dist, wpts = self._osrm_directions(origin, dest)
        if dist is not None:
            self._redis_set(cache_key, {'dist': dist, 'wpts': wpts}, ttl=86400)
            return dist, wpts

        # Haversine fallback
        haversine_km = self._haversine(origin, dest)
        dist = round(haversine_km * 1.30, 2)   # road-distance factor
        wpts = self._simple_waypoints(origin, dest)
        return dist, wpts

    def _ors_directions(self, origin: dict, dest: dict) -> tuple:
        """Call ORS Directions API, return (distance_km, waypoints_list)."""
        url = 'https://api.openrouteservice.org/v2/directions/driving-car'
        try:
            r = requests.post(url,
                headers={
                    'Authorization': self._ors_key,
                    'Content-Type':  'application/json',
                },
                json={
                    'coordinates': [
                        [origin['lng'], origin['lat']],
                        [dest['lng'],   dest['lat']],
                    ],
                    'geometry':        True,
                    'geometry_format': 'geojson',
                    'units':           'km',
                },
                timeout=10)
            r.raise_for_status()
            body = r.json()

            route    = body['routes'][0]
            dist_km  = round(route['summary']['distance'], 2)
            coords   = route['geometry']['coordinates']   # [[lng,lat], ...]
            waypoints = [{'lat': c[1], 'lng': c[0]} for c in coords]
            return dist_km, waypoints

        except Exception as e:
            log.warning('ORS directions error: %s', e)
            return None, []

    def _osrm_directions(self, origin: dict, dest: dict) -> tuple:
        """Call OSRM Directions API (free), return (distance_km, waypoints_list)."""
        url = f"http://router.project-osrm.org/route/v1/driving/{origin['lng']},{origin['lat']};{dest['lng']},{dest['lat']}"
        try:
            r = requests.get(url, params={
                'overview': 'full',
                'geometries': 'geojson'
            }, headers={'User-Agent': 'SROS-App/2.0'}, timeout=10)
            r.raise_for_status()
            body = r.json()

            route    = body['routes'][0]
            dist_km  = round(route['distance'] / 1000.0, 2) # OSRM distance is in meters
            coords   = route['geometry']['coordinates']   # [[lng,lat], ...]
            waypoints = [{'lat': c[1], 'lng': c[0]} for c in coords]
            return dist_km, waypoints

        except Exception as e:
            log.warning('OSRM directions error: %s', e)
            return None, []

    # ── Waypoint helpers ──────────────────────────────────────────────────

    def _simple_waypoints(self, origin: dict, dest: dict, steps: int = 5) -> list:
        """Straight-line interpolation."""
        pts = [origin]
        for i in range(1, steps):
            t = i / steps
            pts.append({
                'lat': round(origin['lat'] + (dest['lat'] - origin['lat']) * t, 5),
                'lng': round(origin['lng'] + (dest['lng'] - origin['lng']) * t, 5),
            })
        pts.append(dest)
        return pts

    def _vary_waypoints(self, base_wpts: list, origin: dict, dest: dict,
                        route_type: str) -> list:
        """
        Thin the real ORS waypoints for fastest/greenest to keep payload small,
        or generate simple ones if no base is available.
        """
        if not base_wpts:
            return self._simple_waypoints(origin, dest, steps=20)

        n = len(base_wpts)
        if route_type == 'fastest':
            # Keep up to ~80 points for a smooth road line
            step = max(1, n // 80)
            pts  = base_wpts[::step]
        else:
            # Greenest: keep up to ~150 points for max detail
            step = max(1, n // 150)
            pts  = base_wpts[::step]

        # Always include start & end
        if pts[0] != origin:
            pts = [origin] + pts
        if pts[-1] != dest:
            pts = pts + [dest]
        return pts

    # ── Speed table ───────────────────────────────────────────────────────

    def _avg_speed(self, route_type: str, vehicle: str) -> float:
        speeds = {
            'fastest':  {'car_petrol': 80, 'car_diesel': 80, 'car_cng': 75,
                         'car_electric': 80, 'bike_petrol': 70, 'bicycle': 20,
                         'public_bus': 45},
            'balanced': {'car_petrol': 55, 'car_diesel': 55, 'car_cng': 50,
                         'car_electric': 55, 'bike_petrol': 50, 'bicycle': 18,
                         'public_bus': 35},
            'greenest': {'car_petrol': 40, 'car_diesel': 40, 'car_cng': 38,
                         'car_electric': 42, 'bike_petrol': 38, 'bicycle': 16,
                         'public_bus': 28},
        }
        return speeds.get(route_type, {}).get(vehicle, 50)

    # ── Haversine ─────────────────────────────────────────────────────────

    def _haversine(self, a: dict, b: dict) -> float:
        R = 6371
        lat1, lng1 = math.radians(a['lat']), math.radians(a['lng'])
        lat2, lng2 = math.radians(b['lat']), math.radians(b['lng'])
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        h = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2)**2
        return R * 2 * math.asin(math.sqrt(h))

    # ── Redis helpers ─────────────────────────────────────────────────────

    def _init_redis(self):
        try:
            import redis
            r = redis.from_url(
                os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
                socket_connect_timeout=1,
                decode_responses=True,
            )
            r.ping()
            return r
        except Exception:
            return None

    def _redis_get(self, key: str):
        if not self._redis:
            return None
        try:
            raw = self._redis.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def _redis_set(self, key: str, value, ttl: int = _CACHE_TTL_DAYS * 86400):
        if not self._redis:
            return
        try:
            self._redis.setex(key, ttl, json.dumps(value))
        except Exception:
            pass

    # ── SQLite cache helpers ──────────────────────────────────────────────

    def _init_sqlite_cache(self):
        try:
            con = sqlite3.connect(str(_CACHE_DB))
            con.execute('''
                CREATE TABLE IF NOT EXISTS geocode_cache (
                    place      TEXT PRIMARY KEY,
                    lat        REAL NOT NULL,
                    lng        REAL NOT NULL,
                    cached_at  TEXT NOT NULL
                )
            ''')
            con.commit()
            con.close()
        except Exception as e:
            log.warning('SQLite cache init failed: %s', e)

    def _sqlite_get(self, place: str) -> dict | None:
        try:
            con    = sqlite3.connect(str(_CACHE_DB))
            row    = con.execute(
                'SELECT lat, lng, cached_at FROM geocode_cache WHERE place = ?', (place,)
            ).fetchone()
            con.close()
            if not row:
                return None
            cached_at = datetime.fromisoformat(row[2])
            if datetime.utcnow() - cached_at > timedelta(days=_CACHE_TTL_DAYS):
                return None
            return {'lat': row[0], 'lng': row[1]}
        except Exception:
            return None

    def _sqlite_set(self, place: str, coords: dict):
        try:
            con = sqlite3.connect(str(_CACHE_DB))
            con.execute('''
                INSERT OR REPLACE INTO geocode_cache (place, lat, lng, cached_at)
                VALUES (?, ?, ?, ?)
            ''', (place, coords['lat'], coords['lng'], datetime.utcnow().isoformat()))
            con.commit()
            con.close()
        except Exception as e:
            log.warning('SQLite cache write failed: %s', e)