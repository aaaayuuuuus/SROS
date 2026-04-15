# routes/api.py
"""
API blueprint — route optimization, trip history, stats, leaderboard, achievements.
"""
import uuid
from datetime import datetime, timedelta
from collections import Counter

from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import func, extract

from extensions import db, limiter
from models.route_optimizer import RouteOptimizer
from models.emission_calculator import EmissionCalculator
from models.db_models import User, Trip, UserStats
from models.achievements import check_and_award_achievements, get_all_badges_for_user
from routes.auth import login_required, optional_auth

api_bp     = Blueprint('api', __name__)
optimizer  = RouteOptimizer()
calculator = EmissionCalculator()


# ── Envelope helpers ───────────────────────────────────────────────────────

def ok(data=None, code=200):
    return jsonify({'success': True, 'data': data, 'error': None}), code

def err(msg, code=400):
    return jsonify({'success': False, 'data': None, 'error': msg}), code


# ── POST /api/optimize ─────────────────────────────────────────────────────

@api_bp.route('/optimize', methods=['POST'])
@limiter.limit('10 per minute')
@optional_auth
def optimize():
    data        = request.get_json(silent=True) or {}
    origin      = (data.get('origin') or '').strip()
    destination = (data.get('destination') or '').strip()
    vehicle     = data.get('vehicle', 'car_petrol')
    priority    = data.get('priority', 'balanced')

    if not origin or not destination:
        return err('Origin and destination required')

    try:
        routes = optimizer.get_routes(origin, destination, vehicle, priority)
    except ValueError as e:
        return err(str(e), 404)
    except Exception as e:
        return err(f'Route calculation failed: {e}', 500)

    # ── Save the selected (balanced) route to Trip table ─────────────────
    new_achievements = []
    
    if getattr(g, 'current_user', None):
        try:
            user_id = g.current_user.id
            # Pick the requested priority route; fallback to balanced (index 1)
            chosen = next((r for r in routes if r['type'] == priority), routes[1])

            em = chosen['emissions']
            oc = chosen['origin_coords']
            dc = chosen['dest_coords']

            trip = Trip(
                user_id       = user_id,
                origin        = origin,
                destination   = destination,
                origin_lat    = oc.get('lat'),
                origin_lng    = oc.get('lng'),
                dest_lat      = dc.get('lat'),
                dest_lng      = dc.get('lng'),
                vehicle_type  = vehicle,
                route_type    = chosen['type'],
                distance_km   = chosen['distance_km'],
                time_min      = chosen['time_min'],
                co2_kg        = em.get('co2_kg', 0),
                fuel_cost_inr = em.get('fuel_cost_inr', 0),
                co2_saved_kg  = em.get('co2_saved_kg', 0),
                green_score   = em.get('green_score', 0),
            )
            db.session.add(trip)
            # Update UserStats — register always creates the row; this is a safety net
            stats = UserStats.query.get(user_id)
            if not stats:
                stats = UserStats(id=user_id)
                db.session.add(stats)

            stats.total_trips          = (stats.total_trips or 0) + 1
            stats.total_co2_saved_kg   = round((stats.total_co2_saved_kg or 0) + (em.get('co2_saved_kg') or 0), 3)
            stats.total_distance_km    = round((stats.total_distance_km or 0) + (chosen['distance_km'] or 0), 2)
            stats.total_fuel_saved_inr = round((stats.total_fuel_saved_inr or 0) + max(0, (em.get('fuel_cost_inr') or 0)), 2)

            _update_streak(stats)
            db.session.commit()

            # ── Check achievements ──────────────────────────────────────────
            new_achievements = check_and_award_achievements(user_id)

        except Exception as e:
            db.session.rollback()
            import logging
            logging.getLogger(__name__).error('Trip save failed: %s', e)

    return ok({
        'routes':           routes,
        'new_achievements': new_achievements,
    })


def _update_streak(stats: UserStats):
    now  = datetime.utcnow().date()
    last = stats.last_trip_at.date() if stats.last_trip_at else None
    if last is None:
        stats.streak_days = 1
    elif last == now:
        pass  # already tripped today
    elif (now - last).days == 1:
        stats.streak_days = (stats.streak_days or 0) + 1
    else:
        stats.streak_days = 1
    stats.last_trip_at = datetime.utcnow()


# ── GET /api/emissions ─────────────────────────────────────────────────────

@api_bp.route('/emissions', methods=['POST'])
def emissions():
    data        = request.get_json(silent=True) or {}
    distance_km = data.get('distance_km', 0)
    vehicle     = data.get('vehicle', 'car_petrol')
    return ok(calculator.calculate(distance_km, vehicle))


# ── GET /api/vehicles ──────────────────────────────────────────────────────

@api_bp.route('/vehicles', methods=['GET'])
def vehicles():
    return ok(calculator.get_vehicle_profiles())


# ── GET /api/trips ─────────────────────────────────────────────────────────

@api_bp.route('/trips', methods=['GET'])
@login_required
def list_trips():
    page     = max(1, request.args.get('page', 1, type=int))
    per_page = min(50, request.args.get('per_page', 10, type=int))
    user_id  = g.current_user.id

    q = (Trip.query
         .filter_by(user_id=user_id)
         .filter(Trip.deleted_at.is_(None))
         .order_by(Trip.created_at.desc()))

    total   = q.count()
    trips   = q.offset((page - 1) * per_page).limit(per_page).all()

    return ok({
        'trips':        [t.to_dict() for t in trips],
        'total_count':  total,
        'pages':        math.ceil(total / per_page) if total else 1,
        'current_page': page,
        'per_page':     per_page,
    })


# ── GET /api/trips/<id> ────────────────────────────────────────────────────

@api_bp.route('/trips/<int:trip_id>', methods=['GET'])
@login_required
def get_trip(trip_id):
    trip = Trip.query.filter_by(id=trip_id, user_id=g.current_user.id,
                                deleted_at=None).first()
    if not trip:
        return err('Trip not found', 404)
    return ok(trip.to_dict())


# ── DELETE /api/trips/<id> ─────────────────────────────────────────────────

@api_bp.route('/trips/<int:trip_id>', methods=['DELETE'])
@login_required
def delete_trip(trip_id):
    trip = Trip.query.filter_by(id=trip_id, user_id=g.current_user.id,
                                deleted_at=None).first()
    if not trip:
        return err('Trip not found', 404)
    trip.deleted_at = datetime.utcnow()
    db.session.commit()
    return ok({'message': 'Trip deleted'})


# ── GET /api/stats ─────────────────────────────────────────────────────────

@api_bp.route('/stats', methods=['GET'])
@login_required
def stats():
    user_id = g.current_user.id
    us      = UserStats.query.get(user_id)

    if not us:
        us = UserStats(id=user_id)
        db.session.add(us)
        db.session.commit()

    base = us.to_dict()

    # Active trips
    active_trips = (Trip.query
                    .filter_by(user_id=user_id)
                    .filter(Trip.deleted_at.is_(None))
                    .all())

    # Best green score
    best_green = max((t.green_score or 0 for t in active_trips), default=0)

    # Favourite vehicle
    vc = Counter(t.vehicle_type for t in active_trips)
    favourite_vehicle = vc.most_common(1)[0][0] if vc else None

    # Most-used route type
    rc = Counter(t.route_type for t in active_trips)
    most_used_route = rc.most_common(1)[0][0] if rc else None

    # Monthly CO₂ saved — last 6 months
    now   = datetime.utcnow()
    months = []
    for i in range(5, -1, -1):
        target = now - timedelta(days=30 * i)
        month_trips = [
            t for t in active_trips
            if t.created_at.year == target.year and t.created_at.month == target.month
        ]
        months.append({
            'month':  target.strftime('%b %Y'),
            'co2_kg': round(sum(t.co2_saved_kg or 0 for t in month_trips), 2),
            'trips':  len(month_trips),
        })

    return ok({
        **base,
        'best_green_score':     best_green,
        'favorite_vehicle':     favourite_vehicle,
        'most_used_route_type': most_used_route,
        'monthly_co2':          months,
    })


# ── GET /api/leaderboard ───────────────────────────────────────────────────

@api_bp.route('/leaderboard', methods=['GET'])
def leaderboard():
    rows = (db.session.query(User, UserStats)
            .join(UserStats, User.id == UserStats.id)
            .filter(User.is_active == True)
            .order_by(UserStats.total_co2_saved_kg.desc())
            .limit(10)
            .all())

    result = []
    for rank, (user, us) in enumerate(rows, start=1):
        savings = round(us.total_co2_saved_kg or 0, 2)
        result.append({
            'rank':       rank,
            'name':       user.name,
            'savings_kg': savings,
            'trips':      us.total_trips or 0,
            'green_badge': savings > 100,
        })
    return ok(result)


# ── POST /api/trips/<id>/share ────────────────────────────────────────────

@api_bp.route('/trips/<int:trip_id>/share', methods=['POST'])
@login_required
def share_trip(trip_id):
    trip = Trip.query.filter_by(id=trip_id, user_id=g.current_user.id,
                                deleted_at=None).first()
    if not trip:
        return err('Trip not found', 404)

    if not trip.share_token:
        trip.share_token = uuid.uuid4().hex
        db.session.commit()

    return ok({'share_url': f'/trip/share/{trip.share_token}'})


# ── GET /api/trip/share/<token> ────────────────────────────────────────────

@api_bp.route('/trip/share/<token>', methods=['GET'])
def public_trip(token):
    trip = Trip.query.filter_by(share_token=token, deleted_at=None).first()
    if not trip:
        return err('Shared trip not found', 404)
    data = trip.to_dict()
    # Include owner name
    owner = User.query.get(trip.user_id)
    data['owner_name'] = owner.name if owner else 'Unknown'
    return ok(data)


# ── GET /api/achievements ──────────────────────────────────────────────────

@api_bp.route('/achievements', methods=['GET'])
@login_required
def achievements():
    return ok(get_all_badges_for_user(g.current_user.id))


# ── math import (used in list_trips) ──────────────────────────────────────
import math