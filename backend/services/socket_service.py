"""
backend/services/socket_service.py
Flask-SocketIO real-time service.

Changes v2:
  • Socket auth survives token refresh: client can send new token via
    "refresh_token" event without reconnecting
  • bleach sanitisation on all incoming message text
  • Rate-guard on send_message (max 30 msgs/min per user, tracked in Redis)
  • Structured logging
  • Type hints
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import bleach
from flask import request
from flask_jwt_extended import decode_token
from jwt.exceptions import InvalidTokenError

from config.settings import Config

logger = logging.getLogger(__name__)

_socketio    = None
_user_sessions: dict[str, set[str]] = {}   # user_id → {sid, …}


# ─── Registration ─────────────────────────────────────────────────────────────
def register_socket_events(socketio) -> None:
    """Attach all SocketIO event handlers to the given SocketIO instance."""
    global _socketio
    _socketio = socketio

    # ── connect ───────────────────────────────────────────────────────────────
    @socketio.on("connect")
    def on_connect():
        token = (
            request.args.get("token")
            or request.headers.get("Authorization", "").replace("Bearer ", "")
        )
        if not _authenticate_socket(token, request.sid):
            return False   # Reject connection

    # ── disconnect ────────────────────────────────────────────────────────────
    @socketio.on("disconnect")
    def on_disconnect():
        sid = request.sid
        for uid, sessions in list(_user_sessions.items()):
            if sid in sessions:
                sessions.discard(sid)
                if not sessions:
                    del _user_sessions[uid]
                logger.info("socket_disconnected", extra={"sid": sid, "user_id": uid})
                break

    # ── refresh_token — survive access-token rotation ─────────────────────────
    @socketio.on("refresh_token")
    def on_refresh_token(data: dict):
        """
        Client sends a new access token after refresh.
        Payload: { token: "<new_access_token>" }
        """
        new_token = (data or {}).get("token", "")
        sid       = request.sid
        # Remove old mapping
        for uid, sessions in list(_user_sessions.items()):
            if sid in sessions:
                sessions.discard(sid)
        # Re-authenticate with new token
        if not _authenticate_socket(new_token, sid):
            socketio.emit("auth_error", {"message": "Token refresh failed"}, to=sid)

    # ── join_room ─────────────────────────────────────────────────────────────
    @socketio.on("join_room")
    def on_join_room(data: dict):
        from flask import session
        user_id = session.get("user_id")
        item_id = (data or {}).get("item_id", "").strip()
        if not user_id or not item_id:
            return

        if not _is_room_authorized(user_id, item_id):
            socketio.emit("error", {"message": "Not authorised for this room"}, to=request.sid)
            return

        room = f"item_{item_id}"
        socketio.server.enter_room(request.sid, room)
        socketio.emit("room_joined", {"room": room, "item_id": item_id}, to=request.sid)
        logger.info("room_joined", extra={"user_id": user_id, "room": room})

    # ── leave_room ────────────────────────────────────────────────────────────
    @socketio.on("leave_room")
    def on_leave_room(data: dict):
        item_id = (data or {}).get("item_id", "")
        socketio.server.leave_room(request.sid, f"item_{item_id}")

    # ── send_message ──────────────────────────────────────────────────────────
    @socketio.on("send_message")
    def on_send_message(data: dict):
        from flask import session
        from config.database import get_db
        from bson import ObjectId

        user_id = session.get("user_id")
        item_id = (data or {}).get("item_id", "").strip()
        raw_text = (data or {}).get("text", "")

        if not user_id or not item_id or not raw_text:
            return

        # Sanitise
        text = bleach.clean(raw_text.strip(), tags=[], strip=True)[: Config.CHAT_MAX_MESSAGE_LEN]
        if not text:
            return

        # Simple per-user rate guard via Redis
        if not _check_chat_rate(user_id):
            socketio.emit("error", {"message": "Sending too fast — slow down"}, to=request.sid)
            return

        db   = get_db()
        item = db.items.find_one({"_id": ObjectId(item_id)})
        if not item:
            return

        if not _is_room_authorized(user_id, item_id):
            socketio.emit("error", {"message": "Not authorised"}, to=request.sid)
            return

        sender = db.users.find_one({"_id": ObjectId(user_id)}, {"name": 1, "avatar_url": 1})
        now    = datetime.now(timezone.utc)

        msg = {
            "item_id":     item_id,
            "sender_id":   user_id,
            "sender_name": sender["name"] if sender else "Unknown",
            "text":        text,
            "read":        False,
            "created_at":  now,
        }
        result  = db.messages.insert_one(msg)
        msg_id  = str(result.inserted_id)

        payload = {
            "id":            msg_id,
            "item_id":       item_id,
            "sender_id":     user_id,
            "sender_name":   sender["name"] if sender else "Unknown",
            "sender_avatar": sender.get("avatar_url") if sender else None,
            "text":          text,
            "created_at":    now.isoformat(),
            "is_mine":       False,
        }
        socketio.emit("new_message", payload, to=f"item_{item_id}")
        logger.info("socket_message_sent", extra={"item_id": item_id, "user_id": user_id})

    # ── typing ────────────────────────────────────────────────────────────────
    @socketio.on("typing")
    def on_typing(data: dict):
        from flask import session
        user_id   = session.get("user_id")
        item_id   = (data or {}).get("item_id")
        is_typing = bool((data or {}).get("is_typing", False))
        if user_id and item_id:
            socketio.emit(
                "user_typing",
                {"user_id": user_id, "is_typing": is_typing},
                to=f"item_{item_id}",
                skip_sid=request.sid,
            )

    # ── mark_read ─────────────────────────────────────────────────────────────
    @socketio.on("mark_read")
    def on_mark_read(data: dict):
        from flask import session
        from config.database import get_db

        user_id = session.get("user_id")
        item_id = (data or {}).get("item_id")
        if user_id and item_id:
            db = get_db()
            db.messages.update_many(
                {"item_id": item_id, "sender_id": {"$ne": user_id}, "read": False},
                {"$set": {"read": True}},
            )

    logger.info("socket_events_registered")


# ─── Emit helpers ─────────────────────────────────────────────────────────────
def emit_notification(user_id: str, notification_data: dict) -> None:
    """Push a notification to all active socket sessions of a user."""
    if _socketio is None:
        return
    for sid in _user_sessions.get(str(user_id), set()):
        try:
            _socketio.emit("notification", notification_data, to=sid)
        except Exception as e:
            logger.warning("emit_notification_failed", extra={"sid": sid, "error": str(e)})


def emit_match_found(user_id: str, match_data: dict) -> None:
    """Push a match-found event to a user."""
    if _socketio is None:
        return
    for sid in _user_sessions.get(str(user_id), set()):
        try:
            _socketio.emit("match_found", match_data, to=sid)
        except Exception as e:
            logger.warning("emit_match_failed", extra={"sid": sid, "error": str(e)})


# ─── Private helpers ──────────────────────────────────────────────────────────
def _authenticate_socket(token: str, sid: str) -> bool:
    """
    Decode JWT, store user_id in Flask session, register sid.
    Returns True on success, False on failure.
    """
    if not token:
        logger.warning("socket_auth_no_token", extra={"sid": sid})
        return False
    try:
        decoded = decode_token(token)
        user_id = decoded["sub"]
        from flask import session
        session["user_id"] = user_id

        _user_sessions.setdefault(user_id, set()).add(sid)
        if _socketio:
            _socketio.emit(
                "connected",
                {"message": "Connected", "user_id": user_id},
                to=sid,
            )
        logger.info("socket_auth_ok", extra={"user_id": user_id, "sid": sid})
        return True
    except (InvalidTokenError, KeyError, Exception) as exc:
        logger.warning("socket_auth_failed", extra={"sid": sid, "error": str(exc)})
        return False


def _is_room_authorized(user_id: str, item_id: str) -> bool:
    """Check if user is poster or accepted claimant for item_id."""
    from config.database import get_db
    from bson import ObjectId

    try:
        db   = get_db()
        item = db.items.find_one({"_id": ObjectId(item_id)}, {"user_id": 1})
        if not item:
            return False
        if item["user_id"] == user_id:
            return True
        return bool(db.claims.find_one({"item_id": item_id, "claimant_id": user_id}))
    except Exception:
        return False


def _check_chat_rate(user_id: str, limit: int = 30, window: int = 60) -> bool:
    """
    Redis-backed per-user rate check for chat messages.
    Returns True if under limit, False if exceeded.
    """
    try:
        import redis
        r   = redis.from_url(Config.REDIS_URL, decode_responses=True)
        key = f"chat_rate:{user_id}"
        cur = r.incr(key)
        if cur == 1:
            r.expire(key, window)
        return int(cur) <= limit
    except Exception:
        return True   # fail open if Redis unavailable
