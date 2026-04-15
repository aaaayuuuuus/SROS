import os
import requests
import google.generativeai as genai
from flask import Blueprint, request, jsonify

ai_bp = Blueprint('ai', __name__)

# Configure Gemini with environment variable if present
API_KEY = os.environ.get("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)

# ── POST /api/ai_insight ───────────────────────────────────────────────────
@ai_bp.route('/ai_insight', methods=['POST'])
def ai_insight():
    data = request.get_json(silent=True) or {}
    routes = data.get('routes', [])
    weather_desc = data.get('weather', 'Clear')
    temp = data.get('temp', '--')
    
    if not routes or len(routes) < 3:
        return jsonify({"success": False, "error": "Invalid routes data."}), 400

    fastest = routes[0]
    greenest = routes[-1]

    saved_kg = abs(greenest['emissions']['co2_saved_kg'] - fastest['emissions']['co2_saved_kg'])
    time_diff = greenest['time_min'] - fastest['time_min']
    trees = greenest['emissions']['trees_equivalent']

    if API_KEY:
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"""
            You are a highly empathetic, brilliant human travel concierge (do NOT act like an AI, an assistant, or a robot. Be warm and casual).
            Your client is planning a road trip right now. Look at this data:
            - Weather at destination: {weather_desc}, {temp}°C.
            - The highway ("Fastest") route takes {fastest['time_min']} mins.
            - The eco-friendly ("Greenest") route avoids highways, adding just {time_diff} minutes, but saves {saved_kg:.2f} kg of CO2 (equivalent to {trees} trees).
            Write an ultra-short, punchy, text-message style tip (max 2 sentences). Factor in the weather dynamically. Speak casually and encourage the green route. Do *not* use hashtags.
            """
            response = model.generate_content(prompt)
            insight_text = response.text.replace('"', '').strip()
            return jsonify({"success": True, "data": {"insight": insight_text, "source": "gemini"}})
        except Exception as e:
            pass
            
    # Fallback (algorithmic)
    insight_text = f"Taking the green route today adds about {time_diff} mins to your drive, but it's totally worth it—you'll avoid the worst highway stretches and save {saved_kg:.1f} kg of CO₂. Have a safe trip in that {weather_desc.lower()} weather!"
    return jsonify({"success": True, "data": {"insight": insight_text, "source": "algorithmic"}})

# ── GET /api/ai_dashboard_tip ──────────────────────────────────────────────
@ai_bp.route('/ai_dashboard_tip', methods=['GET'])
def ai_dashboard_tip():
    if not API_KEY:
        return jsonify({"success": True, "data": {"insight": "Small shifts matter. Keeping your tires properly inflated can actually reduce your carbon emissions by up to 3% on every trip!"}})
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = "Give me one single, ultra-short, fascinating eco-driving or sustainability tip formatted like a daily fun fact. Tone: smart, human, encouraging. Max 2 sentences."
        response = model.generate_content(prompt)
        return jsonify({"success": True, "data": {"insight": response.text.strip()}})
    except Exception:
        return jsonify({"success": True, "data": {"insight": "Carpooling just once a week reduces your carbon footprint significantly. Small steps, big impact!"}})

# ── POST /api/weather ──────────────────────────────────────────────────────
@ai_bp.route('/weather', methods=['POST'])
def weather():
    data = request.get_json(silent=True) or {}
    lat = data.get('lat')
    lng = data.get('lng')

    if not lat or not lng:
        return jsonify({"success": False, "error": "Missing coordinates"}), 400

    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current_weather=true"
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        weather_data = r.json()
        current = weather_data.get("current_weather", {})
        
        # very simple mapping of WMO codes to descriptions/icons
        wmo_map = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Fog", 48: "Depositing rime fog", 51: "Drizzle", 53: "Drizzle", 55: "Dense drizzle",
            61: "Rain", 63: "Rain", 65: "Heavy rain", 71: "Snow", 73: "Snow", 75: "Heavy snow",
            95: "Thunderstorm"
        }
        
        code = current.get("weathercode", 0)
        desc = wmo_map.get(code, "Variable")
        
        return jsonify({
            "success": True,
            "data": {
                "temperature": current.get("temperature"),
                "description": desc
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
