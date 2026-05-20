import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS

from auth import auth_bp, login_manager
from database import init_db
from routes.ai_routes import ai_bp
from routes.analytics import analytics_bp
from routes.dashboard import dashboard_bp
from routes.exports import exports_bp


load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-retailpulse-change-me")
    app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=7)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    if os.getenv("FLASK_ENV") == "production":
        app.config["SESSION_COOKIE_SECURE"] = True

    CORS(app, supports_credentials=True)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(exports_bp)

    with app.app_context():
        init_db(seed_users=True)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_ENV") != "production")
