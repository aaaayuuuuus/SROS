from flask import Flask
from flask_cors import CORS
from routes.api import api_bp
from routes.pages import pages_bp

app = Flask(__name__)
CORS(app)

app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(pages_bp)

if __name__ == '__main__':
    app.run(debug=True, port=5000)