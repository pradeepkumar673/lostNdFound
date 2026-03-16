
"""
CampusLostFound - Claims Routes
POST   /api/claims                  - Send a claim request
GET    /api/claims/item/<item_id>   - Get all claims for an item
GET    /api/claims/my               - Get current user's claims
PUT    /api/claims/<claim_id>       - Accept or decline a claim
DELETE /api/claims/<claim_id>       - Withdraw a claim
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime
import logging

from config.database import get_db
from services.notification_service import create_notification
from utils.helpers import serialize_doc

logger = logging.getLogger(__name__)
claims_bp = Blueprint("claims", __name__)


# ─── Send Claim Request ───────────────────────────────────────────────────────
@claims_bp.route("/", methods=["POST"])
@jwt_required()
def create_claim():
    """
    Send a claim request on a found item.
    Body: {
        item_id      : the found item you are claiming
        message      : why you believe this is yours
        proof_details: any identifying details (serial number, etc.)
    }
    """
    db         = get_db()
    claimant_id = get_jwt_identity()
    data        = request.get_json() or {}

    item_id = data.get("item_id", "").strip()
    message = data.get("message", "").strip()

    if not item_id:
        return jsonify({"error": "item_id is required"}), 400
    if not message:
        return jsonify({"error": "Please provide a message explaining your claim"}), 400
    if len(message) < 20:
        return jsonify({"error": "Message too short — please provide more details"}), 400

    # Validate item exists
    try:
        oid = ObjectId(item_id)
    except InvalidId:
        return jsonify({"error": "Invalid item ID"}), 400

    item = db.items.find_one({"_id": oid})
    if not item:
        return jsonify({"error": "Item not found"}), 404

    # Can't claim your own item
    if item["user_id"] == claimant_id:
        return jsonify({"error": "You cannot claim your own post"}), 400

    # Item must be active
    if item["status"] != "active":
        return jsonify({"error": "This item is no longer available for claims"}), 400

    # Check for duplicate claim
    existing = db.claims.find_one({
        "item_id":     item_id,
        "claimant_id": claimant_id,
        "status":      {"$in": ["pending", "accepted"]}
    })
    if existing:
        return jsonify({"error": "You have already submitted a claim for this item"}), 409

    # Get claimant info
    claimant = db.users.find_one({"_id": ObjectId(claimant_id)}, {"name": 1, "email": 1})

    # Build claim document
    claim_doc = {
        "item_id":       item_id,
        "item_title":    item["title"],
        "item_type":     item["type"],
        "poster_id":     item["user_id"],       # the person who posted the found item
        "claimant_id":   claimant_id,
        "claimant_name": claimant["name"] if claimant else "Unknown",
        "message":       message,
        "proof_details": data.get("proof_details", "").strip() or None,
        "status":        "pending",              # pending | accepted | declined | withdrawn
        "created_at":    datetime.utcnow(),
        "updated_at":    datetime.utcnow(),
        "resolved_at":   None,
        "poster_note":   None,                   # note from poster when accepting/declining
    }

    result   = db.claims.insert_one(claim_doc)
    claim_id = str(result.inserted_id)

    # Update item's claim count
    db.items.update_one({"_id": oid}, {"$inc": {"claim_count": 1}})

    # Notify the item poster
    create_notification(
        db         = db,
        user_id    = item["user_id"],
        notif_type = "new_claim",
        title      = "New Claim Request",
        message    = f"{claimant['name']} has submitted a claim for your item: {item['title']}",
        data       = {
            "item_id":   item_id,
            "claim_id":  claim_id,
            "claimant":  claimant["name"],
        }
    )

    logger.info(f"Claim {claim_id} submitted by {claimant_id} on item {item_id}")

    return jsonify({
        "message":  "Claim submitted successfully",
        "claim_id": claim_id,
    }), 201


# ─── Get Claims for an Item ───────────────────────────────────────────────────
@claims_bp.route("/item/<item_id>", methods=["GET"])
@jwt_required()
def get_item_claims(item_id):
    """Get all claims on a specific item (poster only)"""
    db      = get_db()
    user_id = get_jwt_identity()

    item = db.items.find_one({"_id": ObjectId(item_id)})
    if not item:
        return jsonify({"error": "Item not found"}), 404

    if item["user_id"] != user_id:
        return jsonify({"error": "Not authorized — only the item poster can view claims"}), 403

    claims = list(db.claims.find({"item_id": item_id}).sort("created_at", -1))

    result = []
    for claim in claims:
        doc = serialize_doc(claim)
        # Attach claimant profile
        claimant = db.users.find_one(
            {"_id": ObjectId(claim["claimant_id"])},
            {"name": 1, "email": 1, "roll_number": 1, "department": 1, "avatar_url": 1}
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


# ─── Get My Claims ────────────────────────────────────────────────────────────
@claims_bp.route("/my", methods=["GET"])
@jwt_required()
def get_my_claims():
    """Get all claims submitted by the current user"""
    db      = get_db()
    user_id = get_jwt_identity()

    status = request.args.get("status")
    query  = {"claimant_id": user_id}
    if status:
        query["status"] = status

    claims = list(db.claims.find(query).sort("created_at", -1))

    result = []
    for claim in claims:
        doc = serialize_doc(claim)
        # Attach item thumbnail
        item = db.items.find_one(
            {"_id": ObjectId(claim["item_id"])},
            {"title": 1, "images": 1, "status": 1, "category": 1}
        )
        if item:
            doc["item_preview"] = {
                "title":      item["title"],
                "status":     item["status"],
                "category":   item["category"],
                "thumbnail":  item["images"][0]["url"] if item.get("images") else None,
            }
        result.append(doc)

    return jsonify({"claims": result, "count": len(result)}), 200


# ─── Accept or Decline a Claim ────────────────────────────────────────────────
@claims_bp.route("/<claim_id>", methods=["PUT"])
@jwt_required()
def respond_to_claim(claim_id):
    """
    Accept or decline a claim (poster only)
    Body: {
        action      : "accept" | "decline"
        poster_note : optional message to claimant
    }
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

    # Only the item poster can accept/decline
    if claim["poster_id"] != user_id:
        return jsonify({"error": "Not authorized"}), 403

    if claim["status"] != "pending":
        return jsonify({"error": f"Claim is already {claim['status']}"}), 400

    data   = request.get_json() or {}
    action = data.get("action")
    note   = data.get("poster_note", "").strip() or None

    if action not in ("accept", "decline"):
        return jsonify({"error": "action must be 'accept' or 'decline'"}), 400

    new_status = "accepted" if action == "accept" else "declined"

    db.claims.update_one(
        {"_id": oid},
        {"$set": {
            "status":      new_status,
            "poster_note": note,
            "resolved_at": datetime.utcnow(),
            "updated_at":  datetime.utcnow(),
        }}
    )

    # Update item status if accepted
    if action == "accept":
        db.items.update_one(
            {"_id": ObjectId(claim["item_id"])},
            {"$set": {"status": "claimed", "updated_at": datetime.utcnow()}}
        )
        # Decline all other pending claims for this item
        db.claims.update_many(
            {
                "item_id": claim["item_id"],
                "status":  "pending",
                "_id":     {"$ne": oid}
            },
            {"$set": {"status": "declined", "updated_at": datetime.utcnow()}}
        )
        # Award points to poster for helping
        db.users.update_one({"_id": ObjectId(user_id)},         {"$inc": {"points": 15}})
        db.users.update_one({"_id": ObjectId(claim["claimant_id"])}, {"$inc": {"points": 10}})

    # Notify claimant
    notif_title = "Claim Accepted! 🎉" if action == "accept" else "Claim Update"
    notif_msg   = (
        f"Your claim for '{claim['item_title']}' was accepted! Contact the finder to arrange pickup."
        if action == "accept"
        else f"Your claim for '{claim['item_title']}' was not accepted."
    )
    if note:
        notif_msg += f" Note: {note}"

    create_notification(
        db         = db,
        user_id    = claim["claimant_id"],
        notif_type = f"claim_{new_status}",
        title      = notif_title,
        message    = notif_msg,
        data       = {
            "item_id":  claim["item_id"],
            "claim_id": claim_id,
        }
    )

    logger.info(f"Claim {claim_id} {new_status} by {user_id}")
    return jsonify({"message": f"Claim {new_status} successfully"}), 200


# ─── Withdraw a Claim ─────────────────────────────────────────────────────────
@claims_bp.route("/<claim_id>", methods=["DELETE"])
@jwt_required()
def withdraw_claim(claim_id):
    """Claimant withdraws their own pending claim"""
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
        return jsonify({"error": "Not authorized"}), 403

    if claim["status"] != "pending":
        return jsonify({"error": "Can only withdraw pending claims"}), 400

    db.claims.update_one(
        {"_id": oid},
        {"$set": {"status": "withdrawn", "updated_at": datetime.utcnow()}}
    )

    return jsonify({"message": "Claim withdrawn"}), 200
