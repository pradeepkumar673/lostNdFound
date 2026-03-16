"""
backend/app.py
CampusLostFound – Application factory.

Improvements over v1:
  • Flask-Limiter rate limiting (Redis-backed)
  • Structured JSON logging via structlog
  • Flasgger OpenAPI / Swagger UI at /api/docs
  • Detailed /api/health endpoint (Mongo, Redis, Celery, Gemini, CLIP)
  • Graceful SIGTERM / SIGINT shutdown
  • JWT blacklist wired to Redis
  • Global error handlers (404, 405, 429, 500)
"""

from __future__ import annotations

import logging
import os
import signal
import sys

from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO
from flasgger import Swagger

from config.settings import Config
from config.database import init_db
from config.logging_config import configure_logging
from routes.auth import auth_bp
from routes.items import items_bp
from routes.claims import claims_bp
from routes.notifications import notifications_bp
from routes.chat import chat_bp
from routes.dashboard import dashboard_bp
from routes.ai import ai_bp
from services.socket_service import register_socket_events

# ─── Logging ──────────────────────────────────────────────────────────────────
configure_logging()
logger = logging.getLogger(__name__)

# ─── Extensions (module-level so tasks/services can import them) ──────────────
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[Config.RATELIMIT_DEFAULT],
    storage_uri=Config.RATELIMIT_STORAGE_URL,
    strategy="fixed-window",
)

jwt = JWTManager()


# ─── App Factory ──────────────────────────────────────────────────────────────
def create_app(config_class: type = Config) -> tuple[Flask, SocketIO]:
    """
    Create and fully configure the Flask application.

    Returns:
        (app, socketio) tuple — both are needed by run.py / WSGI.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ── Extensions ────────────────────────────────────────────────────────────
    CORS(
        app,
        resources={r"/api/*": {"origins": os.getenv("ALLOWED_ORIGINS", "*")}},
        supports_credentials=True,
    )

    jwt.init_app(app)
    limiter.init_app(app)

    socketio = SocketIO(
        app,
        cors_allowed_origins=os.getenv("ALLOWED_ORIGINS", "*"),
        async_mode="threading",
        logger=False,
        engineio_logger=False,
        ping_timeout=60,
        ping_interval=25,
    )

    # ── Swagger / OpenAPI ─────────────────────────────────────────────────────
    Swagger(
        app,
        config={
            "headers": [],
            "specs": [
                {
                    "endpoint": "apispec",
                    "route": "/api/apispec.json",
                    "rule_filter": lambda rule: True,
                    "model_filter": lambda tag: True,
                }
            ],
            "static_url_path": "/flasgger_static",
            "swagger_ui": True,
            "specs_route": "/api/docs",
        },
        template={
            "info": {
                "title": "CampusLostFound API",
                "description": "Campus Lost & Found with AI matching",
                "version": "2.0.0",
            },
            "securityDefinitions": {
                "Bearer": {
                    "type": "apiKey",
                    "name": "Authorization",
                    "in": "header",
                    "description": "JWT token: Bearer <token>",
                }
            },
        },
    )

    # ── Database ──────────────────────────────────────────────────────────────
    init_db(app)

    # ── JWT Redis Blacklist ───────────────────────────────────────────────────
    _setup_jwt_redis_blacklist(app)

    # ── Blueprints ────────────────────────────────────────────────────────────
    app.register_blueprint(auth_bp,          url_prefix="/api/auth")
    app.register_blueprint(items_bp,         url_prefix="/api/items")
    app.register_blueprint(claims_bp,        url_prefix="/api/claims")
    app.register_blueprint(notifications_bp, url_prefix="/api/notifications")
    app.register_blueprint(chat_bp,          url_prefix="/api/chat")
    app.register_blueprint(dashboard_bp,     url_prefix="/api/dashboard")
    app.register_blueprint(ai_bp,            url_prefix="/api/ai")

    # ── Socket Events ─────────────────────────────────────────────────────────
    register_socket_events(socketio)

    # ── Routes ────────────────────────────────────────────────────────────────
    _register_utility_routes(app)

    # ── Error Handlers ────────────────────────────────────────────────────────
    _register_error_handlers(app)

    # ── Graceful Shutdown ─────────────────────────────────────────────────────
    _register_shutdown_handler(socketio)

    logger.info("✅ CampusLostFound app created (v2)")
    return app, socketio


# ─── JWT Redis Blacklist ──────────────────────────────────────────────────────
def _setup_jwt_redis_blacklist(app: Flask) -> None:
    """
    Store revoked JWT JTIs in Redis with TTL equal to the token expiry.
    Falls back to an in-process set if Redis is unreachable.
    """
    import redis as redis_lib
    from flask_jwt_extended import decode_token

    _fallback_blacklist: set[str] = set()

    try:
        _redis = redis_lib.from_url(app.config["REDIS_URL"], decode_responses=True)
        _redis.ping()
        use_redis = True
        logger.info("✅ JWT blacklist → Redis")
    except Exception as exc:
        use_redis = False
        logger.warning("⚠️  JWT blacklist → in-memory fallback (%s)", exc)

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header: dict, jwt_payload: dict) -> bool:  # noqa: ANN001
        jti = jwt_payload["jti"]
        if use_redis:
            return bool(_redis.get(f"jwt_blacklist:{jti}"))
        return jti in _fallback_blacklist

    # Store reference so routes can call it
    app.extensions["jwt_redis"] = _redis if use_redis else None
    app.extensions["jwt_fallback_blacklist"] = _fallback_blacklist


def blacklist_token(app: Flask, jti: str, expires_in: int = 86400) -> None:
    """
    Add a JTI to the blacklist.  Called from auth.logout().

    Args:
        app:        Flask application instance.
        jti:        JWT ID to revoke.
        expires_in: Seconds until the token would have expired (used as Redis TTL).
    """
    r = app.extensions.get("jwt_redis")
    if r:
        r.setex(f"jwt_blacklist:{jti}", expires_in, "1")
    else:
        app.extensions["jwt_fallback_blacklist"].add(jti)


# ─── Utility Routes ───────────────────────────────────────────────────────────
def _register_utility_routes(app: Flask) -> None:

    @app.route("/api/health", methods=["GET"])
    def health():
        """
        Detailed health check.
        ---
        tags: [Utility]
        responses:
          200:
            description: All systems healthy
          503:
            description: One or more dependencies unhealthy
        """
        from config.database import get_db
        import redis as redis_lib

        checks: dict[str, dict] = {}
        overall = "ok"

        # ── MongoDB ───────────────────────────────────────────────────────────
        try:
            db = get_db()
            db.command("ping")
            checks["mongodb"] = {"status": "ok"}
        except Exception as exc:
            checks["mongodb"] = {"status": "error", "detail": str(exc)}
            overall = "degraded"

        # ── Redis ─────────────────────────────────────────────────────────────
        try:
            r = redis_lib.from_url(app.config["REDIS_URL"])
            r.ping()
            checks["redis"] = {"status": "ok"}
        except Exception as exc:
            checks["redis"] = {"status": "error", "detail": str(exc)}
            overall = "degraded"

        # ── Celery ────────────────────────────────────────────────────────────
        try:
            from tasks.match_tasks import celery_app
            inspect = celery_app.control.inspect(timeout=1.5)
            active  = inspect.active()
            checks["celery"] = {
                "status":  "ok" if active is not None else "no_workers",
                "workers": list(active.keys()) if active else [],
            }
        except Exception as exc:
            checks["celery"] = {"status": "error", "detail": str(exc)}

        # ── Gemini ────────────────────────────────────────────────────────────
        gemini_key = app.config.get("GEMINI_API_KEY", "")
        checks["gemini"] = {
            "status":     "configured" if gemini_key else "missing_key",
            "model":      app.config.get("GEMINI_MODEL"),
        }

        # ── CLIP ──────────────────────────────────────────────────────────────
        from services.match_service import _clip_model
        checks["clip"] = {"status": "loaded" if _clip_model is not None else "not_loaded"}

        status_code = 200 if overall == "ok" else 503
        return jsonify({"status": overall, "checks": checks}), status_code


# ─── Error Handlers ───────────────────────────────────────────────────────────
def _register_error_handlers(app: Flask) -> None:

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "detail": str(e)}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": "Unauthorized"}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": "Forbidden"}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        return jsonify({"error": "Too many requests", "retry_after": str(e.description)}), 429

    @app.errorhandler(500)
    def internal_error(e):
        logger.exception("Unhandled 500 error")
        return jsonify({"error": "Internal server error"}), 500


# ─── Graceful Shutdown ────────────────────────────────────────────────────────
def _register_shutdown_handler(socketio: SocketIO) -> None:

    def _shutdown(signum, frame):  # noqa: ANN001
        logger.info("Received signal %s — shutting down gracefully…", signum)
        try:
            socketio.stop()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT,  _shutdown)


# ─── Module-level instance (for run.py / WSGI) ───────────────────────────────
app, socketio = create_app()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=Config.DEBUG)
