# models/db_models.py
"""
SQLAlchemy database models for SROS.
"""
from datetime import datetime
from extensions import db


class User(db.Model):
    __tablename__ = 'users'

    id           = db.Column(db.Integer, primary_key=True)
    email        = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name         = db.Column(db.String(150), nullable=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_active    = db.Column(db.Boolean, default=True, nullable=False)

    # Relationships
    trips        = db.relationship('Trip', backref='user', lazy='dynamic',
                                   foreign_keys='Trip.user_id')
    achievements = db.relationship('Achievement', backref='user', lazy='dynamic',
                                   cascade='all, delete-orphan')
    stats        = db.relationship('UserStats', backref='user', uselist=False,
                                   cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id':         self.id,
            'email':      self.email,
            'name':       self.name,
            'created_at': self.created_at.isoformat(),
            'is_active':  self.is_active,
        }

    def __repr__(self):
        return f'<User {self.email}>'


class Trip(db.Model):
    __tablename__ = 'trips'

    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    origin        = db.Column(db.String(255), nullable=False)
    destination   = db.Column(db.String(255), nullable=False)
    origin_lat    = db.Column(db.Float)
    origin_lng    = db.Column(db.Float)
    dest_lat      = db.Column(db.Float)
    dest_lng      = db.Column(db.Float)

    vehicle_type  = db.Column(db.String(50), nullable=False)
    route_type    = db.Column(db.String(50), nullable=False)   # fastest / balanced / greenest

    distance_km   = db.Column(db.Float)
    time_min      = db.Column(db.Float)
    co2_kg        = db.Column(db.Float)
    fuel_cost_inr = db.Column(db.Float)
    co2_saved_kg  = db.Column(db.Float)
    green_score   = db.Column(db.Integer)

    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    deleted_at    = db.Column(db.DateTime, nullable=True)          # soft-delete
    share_token   = db.Column(db.String(64), unique=True, nullable=True, index=True)

    def to_dict(self):
        return {
            'id':            self.id,
            'user_id':       self.user_id,
            'origin':        self.origin,
            'destination':   self.destination,
            'origin_lat':    self.origin_lat,
            'origin_lng':    self.origin_lng,
            'dest_lat':      self.dest_lat,
            'dest_lng':      self.dest_lng,
            'vehicle_type':  self.vehicle_type,
            'route_type':    self.route_type,
            'distance_km':   self.distance_km,
            'time_min':      self.time_min,
            'co2_kg':        self.co2_kg,
            'fuel_cost_inr': self.fuel_cost_inr,
            'co2_saved_kg':  self.co2_saved_kg,
            'green_score':   self.green_score,
            'created_at':    self.created_at.isoformat(),
            'share_token':   self.share_token,
        }

    def __repr__(self):
        return f'<Trip {self.origin}→{self.destination}>'


class Achievement(db.Model):
    __tablename__ = 'achievements'

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    badge_name  = db.Column(db.String(100), nullable=False)
    badge_icon  = db.Column(db.String(10),  nullable=False)
    earned_at   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    description = db.Column(db.String(255))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'badge_name', name='uq_user_badge'),
    )

    def to_dict(self):
        return {
            'id':          self.id,
            'badge_name':  self.badge_name,
            'badge_icon':  self.badge_icon,
            'earned_at':   self.earned_at.isoformat(),
            'description': self.description,
        }

    def __repr__(self):
        return f'<Achievement {self.badge_name} user={self.user_id}>'


class UserStats(db.Model):
    __tablename__ = 'user_stats'

    id                  = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    total_trips         = db.Column(db.Integer, default=0)
    total_co2_saved_kg  = db.Column(db.Float, default=0.0)
    total_distance_km   = db.Column(db.Float, default=0.0)
    total_fuel_saved_inr = db.Column(db.Float, default=0.0)
    streak_days         = db.Column(db.Integer, default=0)
    last_trip_at        = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'total_trips':          self.total_trips,
            'total_co2_saved_kg':   round(self.total_co2_saved_kg, 2),
            'total_distance_km':    round(self.total_distance_km, 2),
            'total_fuel_saved_inr': round(self.total_fuel_saved_inr, 2),
            'streak_days':          self.streak_days,
            'last_trip_at':         self.last_trip_at.isoformat() if self.last_trip_at else None,
        }
