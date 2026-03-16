"""
backend/routes/chat.py
Per-item chat REST endpoints.

Changes v2:
  • bleach sanitisation on every message
  • Rate limiting (Config.RATELIMIT_CHAT)
  • Max message length from Config
  • Type hints + flasgger docstrings
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import bleach
from bson import ObjectId
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import limiter
from config.database import get_db
from config.settings import Config
from utils.helpers import serialize_doc

logger = logging.getLogger(__name__)
chat_bp = Blueprint("chat", __name__)


def _sanitize_msg(text: str) -> str:
    """Strip all HTML from a chat message."""
    return bleach.clean(text.strip(), tags=[], strip=True)[: Config.CHAT_MAX_MESSAGE_LEN]


def _is_authorized(db, item, user_id: str) -> bool:
    """Return True if user is the item poster or has an accepted claim."""
    if item["user_id"] == user_id:
        return True
    return bool(db.claims.find_one({"item_id": str(item["_id"]), "claimant_id": user_id}))


# ─── Get Messages ─────────────────────────────────────────────────────────────
@chat_bp.route("/<item_id>/messages", methods=["GET"])
@jwt_required()
def get_messages(item_id: str):
    """
    Retrieve chat history for a specific item.
    ---
    tags: [Chat]
    security: [{Bearer: []}]
    parameters:
      - {name: item_id, in: path,  type: string, required: true}
      - {name: limit,   in: query, type: integer, default: 50}
      - {name: before_id, in: query, type: string, description: "cursor for pagination"}
    responses:
      200:
        description: Message list (oldest-first)
      403:
        description: Not authorised — must be poster or accepted claimant
    """
    db      = get_db()
    user_id = get_jwt_identity()

    item = db.items.find_one({"_id": ObjectId(item_id)})
    if not item:
        return jsonify({"error": "Item not found"}), 404

    if not _is_authorized(db, item, user_id):
        return jsonify({"error": "Not authorised to view this chat"}), 403

    limit     = min(100, int(request.args.get("limit", 50)))
    before_id = request.args.get("before_id")

    query: dict = {"item_id": item_id}
    if before_id:
        try:
            query["_id"] = {"$lt": ObjectId(before_id)}
        except Exception:
            pass

    messages = list(db.messages.find(query).sort("created_at", -1).limit(limit))
    messages.reverse()

    result = []
    sender_cache: dict = {}
    for msg in messages:
        doc = serialize_doc(msg)
        sid = msg["sender_id"]
        if sid not in sender_cache:
            s = db.users.find_one({"_id": ObjectId(sid)}, {"name": 1, "avatar_url": 1})
            sender_cache[sid] = s or {}
        s = sender_cache[sid]
        doc["sender"] = {
            "id":         sid,
            "name":       s.get("name", "Unknown"),
            "avatar_url": s.get("avatar_url"),
            "is_me":      sid == user_id,
        }
        result.append(doc)

    return jsonify({"messages": result, "item_title": item["title"], "count": len(result)}), 200


# ─── Send Message (REST fallback) ─────────────────────────────────────────────
@chat_bp.route("/<item_id>/messages", methods=["POST"])
@jwt_required()
@limiter.limit(Config.RATELIMIT_CHAT)
def send_message(item_id: str):
    """
    Send a chat message via REST (SocketIO is primary; this is the fallback).
    ---
    tags: [Chat]
    security: [{Bearer: []}]
    parameters:
      - {name: item_id, in: path, type: string, required: true}
      - in: body
        name: body
        schema:
          required: [text]
          properties:
            text: {type: string}
    responses:
      201:
        description: Message sent
      400:
        description: Validation error
    """
    db      = get_db()
    user_id = get_jwt_identity()
    data    = request.get_json(silent=True) or {}

    text = _sanitize_msg(data.get("text", ""))
    if not text:
        return jsonify({"error": "Message text required"}), 400

    item = db.items.find_one({"_id": ObjectId(item_id)})
    if not item:
        return jsonify({"error": "Item not found"}), 404

    if not _is_authorized(db, item, user_id):
        return jsonify({"error": "Not authorised"}), 403

    sender = db.users.find_one({"_id": ObjectId(user_id)}, {"name": 1})
    now    = datetime.now(timezone.utc)

    msg_doc = {
        "item_id":     item_id,
        "sender_id":   user_id,
        "sender_name": sender["name"] if sender else "Unknown",
        "text":        text,
        "read":        False,
        "created_at":  now,
    }
    result          = db.messages.insert_one(msg_doc)
    msg_doc["_id"]  = str(result.inserted_id)
    msg_doc["created_at"] = now.isoformat()

    return jsonify({"message": serialize_doc(msg_doc)}), 201


# ─── List Chat Rooms ──────────────────────────────────────────────────────────
@chat_bp.route("/rooms", methods=["GET"])
@jwt_required()
def get_chat_rooms():
    """
    All chat rooms the current user participates in.
    ---
    tags: [Chat]
    security: [{Bearer: []}]
    responses:
      200:
        description: List of room summaries
    """
    db      = get_db()
    user_id = get_jwt_identity()

    my_item_ids = [
        str(i["_id"])
        for i in db.items.find({"user_id": user_id}, {"_id": 1})
    ]
    claimed_ids = [
        c["item_id"]
        for c in db.claims.find({"claimant_id": user_id, "status": "accepted"}, {"item_id": 1})
    ]

    all_ids = list(set(my_item_ids + claimed_ids))
    rooms   = []

    for item_id in all_ids:
        item = db.items.find_one({"_id": ObjectId(item_id)})
        if not item:
            continue

        last_msg = db.messages.find_one({"item_id": item_id}, sort=[("created_at", -1)])
        unread   = db.messages.count_documents({
            "item_id":   item_id,
            "sender_id": {"$ne": user_id},
            "read":      False,
        })

        rooms.append({
            "item_id":    item_id,
            "item_title": item["title"],
            "item_type":  item["type"],
            "thumbnail":  item["images"][0]["url"] if item.get("images") else None,
            "last_message": {
                "text":       last_msg["text"] if last_msg else None,
                "created_at": last_msg["created_at"].isoformat() if last_msg else None,
            },
            "unread_count": unread,
        })

    rooms.sort(key=lambda r: r["last_message"]["created_at"] or "", reverse=True)
    return jsonify({"rooms": rooms, "count": len(rooms)}), 200
