"""
CampusLostFound - Dashboard Routes
GET /api/dashboard/stats    - User stats + badges + activity
GET /api/dashboard/activity - Recent activity feed
GET /api/dashboard/leaderboard - Top helpers on campus
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
from datetime import datetime, timedelta
import logging

from config.database import get_db
from config.settings import Config
from utils.helpers import serialize_doc

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/stats", methods=["GET"])
@jwt_required()
def get_stats():
    db      = get_db()
    user_id = get_jwt_identity()

    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({"error": "User not found"}), 404

    # ── Item Stats ────────────────────────────────────────────────────────
    total_lost   = db.items.count_documents({"user_id": user_id, "type": "lost"})
    total_found  = db.items.count_documents({"user_id": user_id, "type": "found"})
    active_items = db.items.count_documents({"user_id": user_id, "status": "active"})
    resolved     = db.items.count_documents({"user_id": user_id, "status": "resolved"})

    # ── Claims Stats ──────────────────────────────────────────────────────
    claims_sent     = db.claims.count_documents({"claimant_id": user_id})
    claims_accepted = db.claims.count_documents({"claimant_id": user_id, "status": "accepted"})
    claims_received = db.claims.count_documents({"poster_id":   user_id})

    # ── Points & Badges ───────────────────────────────────────────────────
    points  = user.get("points", 0)
    badges  = user.get("badges", [])

    # Next badge threshold
    next_badge = None
    for badge_id, badge in Config.BADGES.items():
        if points < badge["points"]:
            next_badge = {
                "id":     badge_id,
                "label":  badge["label"],
                "icon":   badge["icon"],
                "needed": badge["points"] - points,
                "target": badge["points"],
            }
            break

    # ── Recent Items ──────────────────────────────────────────────────────
    recent_items = list(
        db.items.find({"user_id": user_id})
        .sort("created_at", -1)
        .limit(5)
    )

    # ── Category breakdown ────────────────────────────────────────────────
    cat_pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    category_breakdown = list(db.items.aggregate(cat_pipeline))

    # ── Weekly Activity (last 7 days) ─────────────────────────────────────
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    weekly_pipeline = [
        {"$match": {"user_id": user_id, "created_at": {"$gte": seven_days_ago}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    weekly_activity = list(db.items.aggregate(weekly_pipeline))

    return jsonify({
        "user": {
            "id":          user_id,
            "name":        user["name"],
            "email":       user["email"],
            "avatar_url":  user.get("avatar_url"),
            "points":      points,
            "badges":      badges,
            "next_badge":  next_badge,
            "member_since": user["created_at"].isoformat(),
        },
        "stats": {
            "total_posts":      total_lost + total_found,
            "lost_reported":    total_lost,
            "found_reported":   total_found,
            "active_items":     active_items,
            "items_resolved":   resolved,
            "claims_sent":      claims_sent,
            "claims_accepted":  claims_accepted,
            "claims_received":  claims_received,
        },
        "category_breakdown": category_breakdown,
        "recent_items":       [serialize_doc(i) for i in recent_items],
        "weekly_activity":    weekly_activity,
    }), 200


@dashboard_bp.route("/activity", methods=["GET"])
@jwt_required()
def get_activity():
    """Recent activity feed for the current user"""
    db      = get_db()
    user_id = get_jwt_identity()
    limit   = min(20, int(request.args.get("limit", 10)))

    activities = []

    # Recent items posted
    items = list(db.items.find({"user_id": user_id}).sort("created_at", -1).limit(5))
    for item in items:
        activities.append({
            "type":       "item_posted",
            "title":      f"You posted: {item['title']}",
            "item_id":    str(item["_id"]),
            "item_type":  item["type"],
            "created_at": item["created_at"].isoformat(),
        })

    # Recent claims received
    claims = list(db.claims.find({"poster_id": user_id}).sort("created_at", -1).limit(5))
    for claim in claims:
        activities.append({
            "type":       "claim_received",
            "title":      f"{claim['claimant_name']} claimed your item",
            "item_id":    claim["item_id"],
            "claim_id":   str(claim["_id"]),
            "status":     claim["status"],
            "created_at": claim["created_at"].isoformat(),
        })

    # Recent claims made
    my_claims = list(db.claims.find({"claimant_id": user_id}).sort("created_at", -1).limit(5))
    for claim in my_claims:
        activities.append({
            "type":       "claim_made",
            "title":      f"Your claim on '{claim['item_title']}' is {claim['status']}",
            "item_id":    claim["item_id"],
            "status":     claim["status"],
            "created_at": claim["updated_at"].isoformat() if claim.get("updated_at") else claim["created_at"].isoformat(),
        })

    # Sort all by date
    activities.sort(key=lambda x: x["created_at"], reverse=True)
    return jsonify({"activity": activities[:limit]}), 200


@dashboard_bp.route("/leaderboard", methods=["GET"])
def get_leaderboard():
    """Top campus helpers by points"""
    db    = get_db()
    limit = min(20, int(request.args.get("limit", 10)))

    top_users = list(
        db.users.find(
            {"is_active": True},
            {"name": 1, "points": 1, "badges": 1, "avatar_url": 1, "department": 1}
        )
        .sort("points", -1)
        .limit(limit)
    )

    result = []
    for i, user in enumerate(top_users):
        resolved = db.items.count_documents({"user_id": str(user["_id"]), "status": "resolved"})
        result.append({
            "rank":       i + 1,
            "user_id":    str(user["_id"]),
            "name":       user["name"],
            "department": user.get("department"),
            "avatar_url": user.get("avatar_url"),
            "points":     user.get("points", 0),
            "badges":     user.get("badges", []),
            "resolved":   resolved,
        })

    return jsonify({"leaderboard": result}), 200
