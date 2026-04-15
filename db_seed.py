# db_seed.py
"""
Seed the database with 10 realistic Indian user records + sample trips.
Run with:  flask shell < db_seed.py   OR   python db_seed.py
"""
import os, sys

# Allow running directly (not only via flask shell)
if __name__ == '__main__':
    os.environ.setdefault('FLASK_ENV', 'development')
    sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
import random
import bcrypt

from app import create_app
from extensions import db
from models.db_models import User, Trip, UserStats, Achievement

app = create_app('development')

USERS = [
    {'name': 'Arjun Sharma',    'email': 'arjun@example.in'},
    {'name': 'Priya Mehta',     'email': 'priya@example.in'},
    {'name': 'Rahul Kumar',     'email': 'rahul@example.in'},
    {'name': 'Sneha Patel',     'email': 'sneha@example.in'},
    {'name': 'Dev Rajan',       'email': 'dev@example.in'},
    {'name': 'Anita Nair',      'email': 'anita@example.in'},
    {'name': 'Vikram Singh',    'email': 'vikram@example.in'},
    {'name': 'Deepika Iyer',    'email': 'deepika@example.in'},
    {'name': 'Saurabh Gupta',   'email': 'saurabh@example.in'},
    {'name': 'Kavya Reddy',     'email': 'kavya@example.in'},
]

ROUTES = [
    ('Delhi',     'Agra',       28.6139, 77.2090, 27.1767, 78.0081),
    ('Mumbai',    'Pune',       19.0760, 72.8777, 18.5204, 73.8567),
    ('Bangalore', 'Hyderabad',  12.9716, 77.5946, 17.3850, 78.4867),
    ('Noida',     'Jaipur',     28.5355, 77.3910, 26.9124, 75.7873),
    ('Chennai',   'Bengaluru',  13.0827, 80.2707, 12.9716, 77.5946),
    ('Ahmedabad', 'Mumbai',     23.0225, 72.5714, 19.0760, 72.8777),
    ('Kolkata',   'Dhanbad',    22.5726, 88.3639, 23.7957, 86.4304),
    ('Lucknow',   'Kanpur',     26.8467, 80.9462, 26.4499, 80.3319),
    ('Delhi',     'Chandigarh', 28.6139, 77.2090, 30.7333, 76.7794),
    ('Hyderabad', 'Pune',       17.3850, 78.4867, 18.5204, 73.8567),
]

VEHICLES    = ['car_petrol', 'car_diesel', 'car_cng', 'car_electric',
               'bike_petrol', 'bicycle', 'public_bus']
ROUTE_TYPES = ['fastest', 'balanced', 'greenest']
CO2_MAP     = {'car_petrol': 171, 'car_diesel': 145, 'car_cng': 96,
               'car_electric': 0, 'bike_petrol': 83, 'bicycle': 0,
               'public_bus': 14}
FUEL_MAP    = {'car_petrol': 6.5, 'car_diesel': 5.8, 'car_cng': 3.2,
               'car_electric': 1.2, 'bike_petrol': 3.0, 'bicycle': 0,
               'public_bus': 0.8}

DEFAULT_PW  = bcrypt.hashpw(b'Password123!', bcrypt.gensalt()).decode()


def seed():
    with app.app_context():
        db.create_all()

        # Clear existing seed data
        for email in [u['email'] for u in USERS]:
            u = User.query.filter_by(email=email).first()
            if u:
                Achievement.query.filter_by(user_id=u.id).delete()
                Trip.query.filter_by(user_id=u.id).delete()
                UserStats.query.filter_by(id=u.id).delete()
                db.session.delete(u)
        db.session.commit()

        print('Seeding users & trips…')
        for u_data in USERS:
            user = User(
                name          = u_data['name'],
                email         = u_data['email'],
                password_hash = DEFAULT_PW,
                is_active     = True,
                created_at    = datetime.utcnow() - timedelta(days=random.randint(30, 180)),
            )
            db.session.add(user)
            db.session.flush()

            total_co2_saved  = 0.0
            total_distance   = 0.0
            total_fuel_saved = 0.0
            num_trips        = random.randint(5, 25)

            for i in range(num_trips):
                rt           = random.choice(ROUTE_TYPES)
                vt           = random.choice(VEHICLES)
                route        = random.choice(ROUTES)
                base_dist    = random.uniform(50, 600)
                factor       = {'fastest': 0.92, 'balanced': 1.0, 'greenest': 1.12}[rt]
                dist_km      = round(base_dist * factor, 2)

                co2_per_km   = CO2_MAP[vt]
                fuel_per_km  = FUEL_MAP[vt]
                co2_kg       = round(co2_per_km * dist_km / 1000, 3)
                fuel_cost    = round(fuel_per_km * dist_km, 2)
                baseline_co2 = round(171 * dist_km / 1000, 3)
                co2_saved    = round(max(0, baseline_co2 - co2_kg), 3)
                green_score  = int(100 * (1 - co2_per_km / 171)) if 171 > 0 else 100

                trip = Trip(
                    user_id       = user.id,
                    origin        = route[0],
                    destination   = route[1],
                    origin_lat    = route[2],
                    origin_lng    = route[3],
                    dest_lat      = route[4],
                    dest_lng      = route[5],
                    vehicle_type  = vt,
                    route_type    = rt,
                    distance_km   = dist_km,
                    time_min      = round((dist_km / 60) * 60, 1),
                    co2_kg        = co2_kg,
                    fuel_cost_inr = fuel_cost,
                    co2_saved_kg  = co2_saved,
                    green_score   = green_score,
                    created_at    = datetime.utcnow() - timedelta(days=random.randint(0, 60)),
                )
                db.session.add(trip)
                total_co2_saved  += co2_saved
                total_distance   += dist_km
                total_fuel_saved += fuel_cost

            stats = UserStats(
                id                   = user.id,
                total_trips          = num_trips,
                total_co2_saved_kg   = round(total_co2_saved, 2),
                total_distance_km    = round(total_distance, 2),
                total_fuel_saved_inr = round(total_fuel_saved, 2),
                streak_days          = random.randint(1, 14),
                last_trip_at         = datetime.utcnow() - timedelta(days=random.randint(0, 5)),
            )
            db.session.add(stats)

        db.session.commit()
        print(f'[OK] Seeded {len(USERS)} users with trips & stats.')


if __name__ == '__main__':
    seed()
