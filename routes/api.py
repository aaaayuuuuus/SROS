from flask import Blueprint, request, jsonify
from models.route_optimizer import RouteOptimizer
from models.emission_calculator import EmissionCalculator

api_bp = Blueprint('api', __name__)
optimizer = RouteOptimizer()
calculator = EmissionCalculator()

@api_bp.route('/optimize', methods=['POST'])
def optimize():
    data = request.get_json()
    origin = data.get('origin')
    destination = data.get('destination')
    vehicle = data.get('vehicle', 'car_petrol')
    priority = data.get('priority', 'balanced')
    if not origin or not destination:
        return jsonify({'error': 'Origin and destination required'}), 400
    try:
        results = optimizer.get_routes(origin, destination, vehicle, priority)
        return jsonify({'success': True, 'routes': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/emissions', methods=['POST'])
def emissions():
    data = request.get_json()
    distance_km = data.get('distance_km', 0)
    vehicle = data.get('vehicle', 'car_petrol')
    result = calculator.calculate(distance_km, vehicle)
    return jsonify(result)

@api_bp.route('/vehicles', methods=['GET'])
def vehicles():
    return jsonify(calculator.get_vehicle_profiles())

@api_bp.route('/leaderboard', methods=['GET'])
def leaderboard():
    data = [
        {'rank': 1, 'user': 'Arjun S.', 'savings_kg': 142.3, 'trips': 89},
        {'rank': 2, 'user': 'Priya M.', 'savings_kg': 128.7, 'trips': 74},
        {'rank': 3, 'user': 'Rahul K.', 'savings_kg': 115.2, 'trips': 91},
        {'rank': 4, 'user': 'Sneha P.', 'savings_kg': 98.4,  'trips': 63},
        {'rank': 5, 'user': 'Dev R.',   'savings_kg': 87.1,  'trips': 58},
    ]
    return jsonify(data)