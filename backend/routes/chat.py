
"""
CampusLostFound - Chat Routes
GET  /api/chat/<item_id>/messages  - Get message history for an item
POST /api/chat/<item_id>/messages  - Send a message (REST fallback)
GET  /api/chat/rooms               - Get all chat rooms for current user
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
from datetime import datetime
import logging

from config.database import get_db
from utils.helpers import serialize_doc

logger = logging.getLogger(__name__)
chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/<item_id>/messages", methods=["GET"])
@jwt_required()
def get_messages(item_id):
    """Get chat history for a specific item"""
    db      = get_db()
    user_id = get_jwt_identity()

    # Verify item exists and user is involved (poster or claimant)
    item = db.items.find_one({"_id": ObjectId(item_id)})
    if not item:
        return jsonify({"error": "Item not found"}), 404

    is_poster   = item["user_id"] == user_id
    is_claimant = db.claims.find_one({"item_id": item_id, "claimant_id": user_id})

    if not is_poster and not is_claimant:
        return jsonify({"error": "Not authorized to view this chat"}), 403

    limit = min(100, int(request.args.get("limit", 50)))
    before_id = request.args.get("before_id")

    query = {"item_id": item_id}
    if before_id:
        query["_id"] = {"$lt": ObjectId(before_id)}

    messages = list(
        db.messages.find(query)
        .sort("created_at", -1)
        .limit(limit)
    )
    messages.reverse()  # Oldest first for display

    # Enrich with sender info
    result = []
    for msg in messages:
        doc = serialize_doc(msg)
        sender = db.users.find_one(
            {"_id": ObjectId(msg["sender_id"])},
            {"name": 1, "avatar_url": 1}
        )
        doc["sender"] = {
            "id":         msg["sender_id"],
            "name":       sender["name"] if sender else "Unknown",
            "avatar_url": sender.get("avatar_url") if sender else None,
            "is_me":      msg["sender_id"] == user_id,
        }
        result.append(doc)

    return jsonify({
        "messages":   result,
        "item_title": item["title"],
        "count":      len(result),
    }), 200


@chat_bp.route("/<item_id>/messages", methods=["POST"])
@jwt_required()
def send_message(item_id):
    """
    Send a message via REST (SocketIO is primary, this is fallback)
    Body: { text: "message content" }
    """
    db      = get_db()
    user_id = get_jwt_identity()
    data    = request.get_json() or {}

    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Message text required"}), 400
    if len(text) > 1000:
        return jsonify({"error": "Message too long (max 1000 chars)"}), 400

    item = db.items.find_one({"_id": ObjectId(item_id)})
    if not item:
        return jsonify({"error": "Item not found"}), 404

    # Authorization check
    is_poster   = item["user_id"] == user_id
    is_claimant = db.claims.find_one({"item_id": item_id, "claimant_id": user_id})
    if not is_poster and not is_claimant:
        return jsonify({"error": "Not authorized"}), 403

    sender = db.users.find_one({"_id": ObjectId(user_id)}, {"name": 1})

    msg_doc = {
        "item_id":    item_id,
        "sender_id":  user_id,
        "sender_name": sender["name"] if sender else "Unknown",
        "text":       text,
        "read":       False,
        "created_at": datetime.utcnow(),
    }
    result = db.messages.insert_one(msg_doc)
    msg_doc["_id"] = str(result.inserted_id)

    return jsonify({"message": serialize_doc(msg_doc)}), 201


@chat_bp.route("/rooms", methods=["GET"])
@jwt_required()
def get_chat_rooms():
    """Get all chat rooms the current user is part of"""
    db      = get_db()
    user_id = get_jwt_identity()

    # Items where user is poster
    my_items = list(db.items.find(
        {"user_id": user_id},
        {"title": 1, "images": 1, "type": 1, "status": 1}
    ))
    my_item_ids = [str(i["_id"]) for i in my_items]

    # Items where user has accepted claims
    my_claims = list(db.claims.find(
        {"claimant_id": user_id, "status": "accepted"},
        {"item_id": 1}
    ))
    claimed_item_ids = [c["item_id"] for c in my_claims]

    all_item_ids = list(set(my_item_ids + claimed_item_ids))

    rooms = []
    for item_id in all_item_ids:
        item = db.items.find_one({"_id": ObjectId(item_id)})
        if not item:
            continue

        # Last message
        last_msg = db.messages.find_one(
            {"item_id": item_id},
            sort=[("created_at", -1)]
        )
        unread = db.messages.count_documents({
            "item_id":   item_id,
            "sender_id": {"$ne": user_id},
            "read":      False,
        })

        rooms.append({
            "item_id":     item_id,
            "item_title":  item["title"],
            "item_type":   item["type"],
            "thumbnail":   item["images"][0]["url"] if item.get("images") else None,
            "last_message": {
                "text":       last_msg["text"] if last_msg else None,
                "created_at": last_msg["created_at"].isoformat() if last_msg else None,
            },
            "unread_count": unread,
        })

    # Sort by last message time
    rooms.sort(key=lambda r: r["last_message"]["created_at"] or "", reverse=True)
    return jsonify({"rooms": rooms, "count": len(rooms)}), 200
