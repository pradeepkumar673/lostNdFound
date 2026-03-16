"""
CampusLostFound - Main Flask Application
Entry point for the backend server
"""

from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from config.settings import Config
from config.database import init_db
from routes.auth import auth_bp
from routes.items import items_bp
from routes.claims import claims_bp
from routes.notifications import notifications_bp
from routes.chat import chat_bp
from routes.dashboard import dashboard_bp
from routes.ai import ai_bp
from services.socket_service import register_socket_events
import logging

# ─── Logging Setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ─── App Factory ──────────────────────────────────────────────────────────────
def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Extensions
    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
    JWTManager(app)
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode="threading",
        logger=False,
        engineio_logger=False
    )

    # Database
    init_db(app)

    # Register blueprints
    app.register_blueprint(auth_bp,          url_prefix="/api/auth")
    app.register_blueprint(items_bp,         url_prefix="/api/items")
    app.register_blueprint(claims_bp,        url_prefix="/api/claims")
    app.register_blueprint(notifications_bp, url_prefix="/api/notifications")
    app.register_blueprint(chat_bp,          url_prefix="/api/chat")
    app.register_blueprint(dashboard_bp,     url_prefix="/api/dashboard")
    app.register_blueprint(ai_bp,            url_prefix="/api/ai")

    # Socket events
    register_socket_events(socketio)

    @app.route("/api/health")
    def health():
        return {"status": "ok", "message": "CampusLostFound API running"}, 200

    logger.info("✅ CampusLostFound app created successfully")
    return app, socketio


app, socketio = create_app()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
