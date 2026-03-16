"""
CampusLostFound - Socket.IO Service
Real-time chat and live notifications via Flask-SocketIO.
"""

import logging
from datetime import datetime
from flask import request
from flask_jwt_extended import decode_token
from jwt.exceptions import InvalidTokenError

logger = logging.getLogger(__name__)

# Global socketio reference
_socketio = None

# Map user_id → set of socket session IDs
_user_sessions = {}


def register_socket_events(socketio):
    """Attach all SocketIO event handlers"""
    global _socketio
    _socketio = socketio

    # ─── Connection ───────────────────────────────────────────────────────────
    @socketio.on("connect")
    def on_connect():
        token = request.args.get("token") or (request.headers.get("Authorization", "").replace("Bearer ", ""))
        if not token:
            logger.warning("Socket connection rejected — no token")
            return False  # Reject connection

        try:
            decoded = decode_token(token)
            user_id = decoded["sub"]
            sid     = request.sid

            if user_id not in _user_sessions:
                _user_sessions[user_id] = set()
            _user_sessions[user_id].add(sid)

            # Store user_id in session
            from flask import session
            session["user_id"] = user_id

            socketio.emit("connected", {"message": "Connected to CampusLostFound", "user_id": user_id}, to=sid)
            logger.info(f"Socket connected: user={user_id} sid={sid}")

        except (InvalidTokenError, KeyError, Exception) as e:
            logger.warning(f"Socket auth failed: {e}")
            return False

    # ─── Disconnection ────────────────────────────────────────────────────────
    @socketio.on("disconnect")
    def on_disconnect():
        sid = request.sid
        for user_id, sessions in list(_user_sessions.items()):
            if sid in sessions:
                sessions.discard(sid)
                if not sessions:
                    del _user_sessions[user_id]
                logger.info(f"Socket disconnected: sid={sid}")
                break

    # ─── Join Item Chat Room ──────────────────────────────────────────────────
    @socketio.on("join_room")
    def on_join_room(data):
        """
        Client joins a chat room for a specific item.
        Payload: { item_id: "..." }
        """
        from flask import session
        user_id = session.get("user_id")
        item_id = data.get("item_id")

        if not user_id or not item_id:
            return

        # Verify user is authorized for this room
        from config.database import get_db
        from bson import ObjectId
        db = get_db()

        item = db.items.find_one({"_id": ObjectId(item_id)})
        if not item:
            return

        is_poster   = item["user_id"] == user_id
        is_claimant = db.claims.find_one({"item_id": item_id, "claimant_id": user_id})

        if not is_poster and not is_claimant:
            socketio.emit("error", {"message": "Not authorized for this room"}, to=request.sid)
            return

        room_name = f"item_{item_id}"
        socketio.server.enter_room(request.sid, room_name)
        socketio.emit("room_joined", {"room": room_name, "item_id": item_id}, to=request.sid)
        logger.info(f"User {user_id} joined room {room_name}")

    # ─── Leave Room ───────────────────────────────────────────────────────────
    @socketio.on("leave_room")
    def on_leave_room(data):
        item_id   = data.get("item_id")
        room_name = f"item_{item_id}"
        socketio.server.leave_room(request.sid, room_name)

    # ─── Send Message ─────────────────────────────────────────────────────────
    @socketio.on("send_message")
    def on_send_message(data):
        """
        Receive a chat message and broadcast to room.
        Payload: { item_id: "...", text: "..." }
        """
        from flask import session
        user_id = session.get("user_id")
        item_id = data.get("item_id", "").strip()
        text    = data.get("text", "").strip()

        if not user_id or not item_id or not text:
            return

        if len(text) > 1000:
            socketio.emit("error", {"message": "Message too long"}, to=request.sid)
            return

        from config.database import get_db
        from bson import ObjectId
        db = get_db()

        # Get sender info
        sender = db.users.find_one({"_id": ObjectId(user_id)}, {"name": 1, "avatar_url": 1})

        # Save to database
        msg_doc = {
            "item_id":     item_id,
            "sender_id":   user_id,
            "sender_name": sender["name"] if sender else "Unknown",
            "text":        text,
            "read":        False,
            "created_at":  datetime.utcnow(),
        }
        result      = db.messages.insert_one(msg_doc)
        msg_doc["_id"] = str(result.inserted_id)
        msg_doc["created_at"] = msg_doc["created_at"].isoformat()

        # Emit to all in the room
        room_name = f"item_{item_id}"
        payload = {
            "id":          str(result.inserted_id),
            "item_id":     item_id,
            "sender_id":   user_id,
            "sender_name": sender["name"] if sender else "Unknown",
            "sender_avatar": sender.get("avatar_url") if sender else None,
            "text":        text,
            "created_at":  msg_doc["created_at"],
            "is_mine":     False,  # Client updates this based on own user_id
        }
        socketio.emit("new_message", payload, to=room_name)
        logger.info(f"Message sent in room {room_name} by {user_id}")

    # ─── Typing Indicator ─────────────────────────────────────────────────────
    @socketio.on("typing")
    def on_typing(data):
        from flask import session
        user_id   = session.get("user_id")
        item_id   = data.get("item_id")
        is_typing = data.get("is_typing", False)

        if user_id and item_id:
            room_name = f"item_{item_id}"
            socketio.emit("user_typing", {
                "user_id":   user_id,
                "is_typing": is_typing,
            }, to=room_name, skip_sid=request.sid)

    # ─── Mark Messages Read ───────────────────────────────────────────────────
    @socketio.on("mark_read")
    def on_mark_read(data):
        from flask import session
        user_id = session.get("user_id")
        item_id = data.get("item_id")

        if user_id and item_id:
            from config.database import get_db
            db = get_db()
            db.messages.update_many(
                {"item_id": item_id, "sender_id": {"$ne": user_id}, "read": False},
                {"$set": {"read": True}}
            )

    logger.info("✅ Socket.IO events registered")


def emit_notification(user_id, notification_data):
    """
    Push a notification to all socket sessions of a user.
    Called from notification_service.py
    """
    if _socketio is None:
        return

    sessions = _user_sessions.get(str(user_id), set())
    for sid in sessions:
        try:
            _socketio.emit("notification", notification_data, to=sid)
        except Exception as e:
            logger.warning(f"Failed to emit notification to {sid}: {e}")


def emit_match_found(user_id, match_data):
    """Notify user that a potential match was found for their item"""
    if _socketio is None:
        return

    sessions = _user_sessions.get(str(user_id), set())
    for sid in sessions:
        try:
            _socketio.emit("match_found", match_data, to=sid)
        except Exception as e:
            logger.warning(f"Failed to emit match to {sid}: {e}")
