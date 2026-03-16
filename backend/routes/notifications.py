
"""
CampusLostFound - Notifications Routes
GET  /api/notifications         - Get user notifications (paginated)
PUT  /api/notifications/read-all - Mark all as read
PUT  /api/notifications/<id>    - Mark single notification as read
DELETE /api/notifications/<id>  - Delete notification
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
from datetime import datetime
import logging

from config.database import get_db
from utils.helpers import serialize_doc

logger = logging.getLogger(__name__)
notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/", methods=["GET"])
@jwt_required()
def get_notifications():
    db      = get_db()
    user_id = get_jwt_identity()

    page  = max(1, int(request.args.get("page",  1)))
    limit = min(50, int(request.args.get("limit", 20)))
    skip  = (page - 1) * limit

    query = {"user_id": user_id}
    unread_filter = request.args.get("unread_only")
    if unread_filter == "true":
        query["read"] = False

    total = db.notifications.count_documents(query)
    notifs = list(db.notifications.find(query).sort("created_at", -1).skip(skip).limit(limit))
    unread_count = db.notifications.count_documents({"user_id": user_id, "read": False})

    return jsonify({
        "notifications": [serialize_doc(n) for n in notifs],
        "unread_count":  unread_count,
        "pagination": {
            "total": total, "page": page, "limit": limit,
            "total_pages": (total + limit - 1) // limit,
        }
    }), 200


@notifications_bp.route("/read-all", methods=["PUT"])
@jwt_required()
def mark_all_read():
    db      = get_db()
    user_id = get_jwt_identity()
    db.notifications.update_many(
        {"user_id": user_id, "read": False},
        {"$set": {"read": True, "read_at": datetime.utcnow()}}
    )
    return jsonify({"message": "All notifications marked as read"}), 200


@notifications_bp.route("/<notif_id>", methods=["PUT"])
@jwt_required()
def mark_read(notif_id):
    db      = get_db()
    user_id = get_jwt_identity()
    db.notifications.update_one(
        {"_id": ObjectId(notif_id), "user_id": user_id},
        {"$set": {"read": True, "read_at": datetime.utcnow()}}
    )
    return jsonify({"message": "Marked as read"}), 200


@notifications_bp.route("/<notif_id>", methods=["DELETE"])
@jwt_required()
def delete_notification(notif_id):
    db      = get_db()
    user_id = get_jwt_identity()
    db.notifications.delete_one({"_id": ObjectId(notif_id), "user_id": user_id})
    return jsonify({"message": "Notification deleted"}), 200
