# models/achievements.py
"""
Achievement / badge engine for SROS.
"""
from datetime import datetime, timedelta
from extensions import db
from models.db_models import Achievement, Trip


# ── Badge definitions ─────────────────────────────────────────────────────

BADGES = [
    {
        'badge_name':  'First Step',
        'badge_icon':  '🌱',
        'description': 'Completed your very first trip.',
    },
    {
        'badge_name':  'Green Commuter',
        'badge_icon':  '🚲',
        'description': 'Took 5 trips using bicycle or public bus.',
    },
    {
        'badge_name':  'Carbon Saver',
        'badge_icon':  '💚',
        'description': 'Saved 10 kg CO₂ in total.',
    },
    {
        'badge_name':  'Eco Champion',
        'badge_icon':  '🏆',
        'description': 'Saved 100 kg CO₂ in total.',
    },
    {
        'badge_name':  'Electric Pioneer',
        'badge_icon':  '⚡',
        'description': 'Completed 3 trips with an electric vehicle.',
    },
    {
        'badge_name':  'Century Tripper',
        'badge_icon':  '🗺️',
        'description': 'Completed 100 total trips.',
    },
    {
        'badge_name':  'Perfect Week',
        'badge_icon':  '📅',
        'description': 'Logged at least one trip every day for 7 consecutive days.',
    },
]

BADGE_MAP = {b['badge_name']: b for b in BADGES}


# ── Core engine ───────────────────────────────────────────────────────────

def check_and_award_achievements(user_id: int) -> list:
    """
    Evaluate all badge rules for user_id.
    Inserts newly earned achievements into the DB.
    Returns list of newly-earned badge dicts.
    """
    # Load active trips (non-deleted)
    trips = (Trip.query
             .filter_by(user_id=user_id)
             .filter(Trip.deleted_at.is_(None))
             .all())

    # Stats
    total_trips   = len(trips)
    total_co2_saved = sum(t.co2_saved_kg or 0 for t in trips)
    green_commuter_count = sum(
        1 for t in trips if t.vehicle_type in ('bicycle', 'public_bus')
    )
    ev_count = sum(1 for t in trips if t.vehicle_type == 'car_electric')

    # Perfect Week: any 7 consecutive days with at least 1 trip
    perfect_week = _check_perfect_week(trips)

    # Already-earned badge names
    earned_names = {
        a.badge_name
        for a in Achievement.query.filter_by(user_id=user_id).all()
    }

    newly_earned = []

    def _award(badge_name: str):
        if badge_name in earned_names:
            return
        info = BADGE_MAP[badge_name]
        ach  = Achievement(
            user_id    = user_id,
            badge_name = badge_name,
            badge_icon = info['badge_icon'],
            description= info['description'],
        )
        db.session.add(ach)
        newly_earned.append({
            'badge_name':  badge_name,
            'badge_icon':  info['badge_icon'],
            'description': info['description'],
        })

    # Evaluate rules
    if total_trips >= 1:
        _award('First Step')
    if green_commuter_count >= 5:
        _award('Green Commuter')
    if total_co2_saved >= 10:
        _award('Carbon Saver')
    if total_co2_saved >= 100:
        _award('Eco Champion')
    if ev_count >= 3:
        _award('Electric Pioneer')
    if total_trips >= 100:
        _award('Century Tripper')
    if perfect_week:
        _award('Perfect Week')

    if newly_earned:
        db.session.commit()

    return newly_earned


def _check_perfect_week(trips: list) -> bool:
    """Return True if the user has ≥1 trip on each of 7 consecutive days."""
    if not trips:
        return False
    trip_dates = sorted({t.created_at.date() for t in trips})
    max_streak = 1
    current    = 1
    for i in range(1, len(trip_dates)):
        diff = (trip_dates[i] - trip_dates[i - 1]).days
        if diff == 1:
            current += 1
            max_streak = max(max_streak, current)
        elif diff > 1:
            current = 1
    return max_streak >= 7


def get_all_badges_for_user(user_id: int) -> list:
    """Return all badge definitions with earned status."""
    earned = {
        a.badge_name: a.earned_at
        for a in Achievement.query.filter_by(user_id=user_id).all()
    }
    result = []
    for b in BADGES:
        name = b['badge_name']
        result.append({
            'badge_name':  name,
            'badge_icon':  b['badge_icon'],
            'description': b['description'],
            'earned':      name in earned,
            'earned_at':   earned[name].isoformat() if name in earned else None,
        })
    return result
