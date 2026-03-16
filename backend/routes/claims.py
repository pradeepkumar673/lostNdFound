"""
backend/routes/claims.py
Claim lifecycle endpoints.

Changes v2:
  • Rate limiting on POST /claims
  • bleach sanitise on message / proof fields
  • Type hints + flasgger docstrings
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import bleach
from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import limiter
from config.database import get_db
from config.settings import Config
from services.notification_service import create_notification
from utils.helpers import serialize_doc

logger = logging.getLogger(__name__)
claims_bp = Blueprint("claims", __name__)


def _clean(v: str, n: int = 1000) -> str:
    return bleach.clean(str(v).strip(), tags=[], strip=True)[:n]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─── Create Claim ─────────────────────────────────────────────────────────────
@claims_bp.route("/", methods=["POST"])
@jwt_required()
@limiter.limit(Config.RATELIMIT_CLAIM)
def create_claim():
    """
    Submit a claim on a found item.
    ---
    tags: [Claims]
    security: [{Bearer: []}]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          required: [item_id, message]
          properties:
            item_id:       {type: string}
            message:       {type: string, description: "Why you believe this is yours (≥20 chars)"}
            proof_details: {type: string}
    responses:
      201:
        description: Claim submitted
      400:
        description: Validation error
      409:
        description: Duplicate claim
    """
    db          = get_db()
    claimant_id = get_jwt_identity()
    data        = request.get_json(silent=True) or {}

    item_id = data.get("item_id", "").strip()
    message = _clean(data.get("message", ""), 2000)

    if not item_id:
        return jsonify({"error": "item_id is required"}), 400
    if not message or len(message) < 20:
        return jsonify({"error": "Please provide a detailed message (≥20 chars)"}), 400

    try:
        oid = ObjectId(item_id)
    except InvalidId:
        return jsonify({"error": "Invalid item ID"}), 400

    item = db.items.find_one({"_id": oid})
    if not item:
        return jsonify({"error": "Item not found"}), 404
    if item["user_id"] == claimant_id:
        return jsonify({"error": "Cannot claim your own item"}), 400
    if item["status"] != "active":
        return jsonify({"error": "Item is no longer available"}), 400

    existing = db.claims.find_one({
        "item_id":     item_id,
        "claimant_id": claimant_id,
        "status":      {"$in": ["pending", "accepted"]},
    })
    if existing:
        return jsonify({"error": "You already have an active claim on this item"}), 409

    claimant = db.users.find_one({"_id": ObjectId(claimant_id)}, {"name": 1, "email": 1})
    now      = _utcnow()

    claim_doc = {
        "item_id":       item_id,
        "item_title":    item["title"],
        "item_type":     item["type"],
        "poster_id":     item["user_id"],
        "claimant_id":   claimant_id,
        "claimant_name": claimant["name"] if claimant else "Unknown",
        "message":       message,
        "proof_details": _clean(data.get("proof_details", ""), 1000) or None,
        "status":        "pending",
        "created_at":    now,
        "updated_at":    now,
        "resolved_at":   None,
        "poster_note":   None,
    }

    result   = db.claims.insert_one(claim_doc)
    claim_id = str(result.inserted_id)

    db.items.update_one({"_id": oid}, {"$inc": {"claim_count": 1}})

    create_notification(
        db         = db,
        user_id    = item["user_id"],
        notif_type = "new_claim",
        title      = "New Claim Request",
        message    = f"{claimant['name']} claimed your item: {item['title']}",
        data       = {"item_id": item_id, "claim_id": claim_id},
    )

    logger.info("claim_created", extra={"claim_id": claim_id, "item_id": item_id})
    return jsonify({"message": "Claim submitted", "claim_id": claim_id}), 201


# ─── Get Claims for Item ──────────────────────────────────────────────────────
@claims_bp.route("/item/<item_id>", methods=["GET"])
@jwt_required()
def get_item_claims(item_id: str):
    """
    Get all claims on an item (poster only).
    ---
    tags: [Claims]
    security: [{Bearer: []}]
    """
    db      = get_db()
    user_id = get_jwt_identity()

    item = db.items.find_one({"_id": ObjectId(item_id)})
    if not item:
        return jsonify({"error": "Item not found"}), 404
    if item["user_id"] != user_id:
        return jsonify({"error": "Not authorised"}), 403

    claims = list(db.claims.find({"item_id": item_id}).sort("created_at", -1))
    result = []
    for claim in claims:
        doc = serialize_doc(claim)
        claimant = db.users.find_one(
            {"_id": ObjectId(claim["claimant_id"])},
            {"name": 1, "email": 1, "roll_number": 1, "department": 1, "avatar_url": 1},
        )
        if claimant:
            doc["claimant_profile"] = {
                "name":        claimant["name"],
                "email":       claimant["email"],
                "roll_number": claimant.get("roll_number"),
                "department":  claimant.get("department"),
                "avatar_url":  claimant.get("avatar_url"),
            }
        result.append(doc)

    return jsonify({"claims": result, "count": len(result)}), 200


# ─── My Claims ────────────────────────────────────────────────────────────────
@claims_bp.route("/my", methods=["GET"])
@jwt_required()
def get_my_claims():
    """
    Get claims submitted by the current user.
    ---
    tags: [Claims]
    security: [{Bearer: []}]
    """
    db      = get_db()
    user_id = get_jwt_identity()

    status = request.args.get("status")
    q: dict = {"claimant_id": user_id}
    if status:
        q["status"] = status

    claims = list(db.claims.find(q).sort("created_at", -1))
    result = []
    for claim in claims:
        doc  = serialize_doc(claim)
        item = db.items.find_one(
            {"_id": ObjectId(claim["item_id"])},
            {"title": 1, "images": 1, "status": 1, "category": 1},
        )
        if item:
            doc["item_preview"] = {
                "title":     item["title"],
                "status":    item["status"],
                "category":  item["category"],
                "thumbnail": item["images"][0]["url"] if item.get("images") else None,
            }
        result.append(doc)

    return jsonify({"claims": result, "count": len(result)}), 200


# ─── Accept / Decline ─────────────────────────────────────────────────────────
@claims_bp.route("/<claim_id>", methods=["PUT"])
@jwt_required()
def respond_to_claim(claim_id: str):
    """
    Accept or decline a claim (poster only).
    ---
    tags: [Claims]
    security: [{Bearer: []}]
    parameters:
      - in: body
        name: body
        schema:
          required: [action]
          properties:
            action:      {type: string, enum: [accept, decline]}
            poster_note: {type: string}
    responses:
      200:
        description: Claim updated
    """
    db      = get_db()
    user_id = get_jwt_identity()

    try:
        oid = ObjectId(claim_id)
    except InvalidId:
        return jsonify({"error": "Invalid claim ID"}), 400

    claim = db.claims.find_one({"_id": oid})
    if not claim:
        return jsonify({"error": "Claim not found"}), 404
    if claim["poster_id"] != user_id:
        return jsonify({"error": "Not authorised"}), 403
    if claim["status"] != "pending":
        return jsonify({"error": f"Claim is already {claim['status']}"}), 400

    data   = request.get_json(silent=True) or {}
    action = data.get("action")
    if action not in ("accept", "decline"):
        return jsonify({"error": "action must be 'accept' or 'decline'"}), 400

    new_status = "accepted" if action == "accept" else "declined"
    note       = _clean(data.get("poster_note", ""), 500) or None
    now        = _utcnow()

    db.claims.update_one(
        {"_id": oid},
        {"$set": {"status": new_status, "poster_note": note, "resolved_at": now, "updated_at": now}},
    )

    if action == "accept":
        db.items.update_one(
            {"_id": ObjectId(claim["item_id"])},
            {"$set": {"status": "claimed", "updated_at": now}},
        )
        # Decline all other pending claims
        db.claims.update_many(
            {"item_id": claim["item_id"], "status": "pending", "_id": {"$ne": oid}},
            {"$set": {"status": "declined", "updated_at": now}},
        )
        db.users.update_one({"_id": ObjectId(user_id)},         {"$inc": {"points": Config.POINTS_CLAIM_ACCEPT}})
        db.users.update_one({"_id": ObjectId(claim["claimant_id"])}, {"$inc": {"points": Config.POINTS_CLAIM_MAKE}})

    notif_msg = (
        f"Your claim for '{claim['item_title']}' was accepted! Contact the finder."
        if action == "accept"
        else f"Your claim for '{claim['item_title']}' was not accepted."
    )
    if note:
        notif_msg += f" Note: {note}"

    create_notification(
        db         = db,
        user_id    = claim["claimant_id"],
        notif_type = f"claim_{new_status}",
        title      = "Claim Accepted! 🎉" if action == "accept" else "Claim Update",
        message    = notif_msg,
        data       = {"item_id": claim["item_id"], "claim_id": claim_id},
    )

    logger.info("claim_responded", extra={"claim_id": claim_id, "action": action})
    return jsonify({"message": f"Claim {new_status}"}), 200


# ─── Withdraw ─────────────────────────────────────────────────────────────────
@claims_bp.route("/<claim_id>", methods=["DELETE"])
@jwt_required()
def withdraw_claim(claim_id: str):
    """
    Withdraw a pending claim (claimant only).
    ---
    tags: [Claims]
    security: [{Bearer: []}]
    """
    db      = get_db()
    user_id = get_jwt_identity()

    try:
        oid = ObjectId(claim_id)
    except InvalidId:
        return jsonify({"error": "Invalid claim ID"}), 400

    claim = db.claims.find_one({"_id": oid})
    if not claim:
        return jsonify({"error": "Claim not found"}), 404
    if claim["claimant_id"] != user_id:
        return jsonify({"error": "Not authorised"}), 403
    if claim["status"] != "pending":
        return jsonify({"error": "Can only withdraw pending claims"}), 400

    db.claims.update_one(
        {"_id": oid},
        {"$set": {"status": "withdrawn", "updated_at": _utcnow()}},
    )
    return jsonify({"message": "Claim withdrawn"}), 200
