"""
Supernaut Take Home Task
Nojus Adomaitis, 2025
"""
from flask import Flask
from config import Config
from models import db
from routes import api_bp

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

app.register_blueprint(api_bp)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)
