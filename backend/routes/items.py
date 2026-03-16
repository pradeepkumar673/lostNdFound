"""
backend/routes/items.py
Item CRUD with automatic AI pipeline on creation.

Changes v2:
  • Auto-triggers categorize + OCR + Gemini after image upload (inline for small
    payloads; Celery for heavier background work)
  • bleach sanitisation on title / description / features / brand
  • Rate limiting on write endpoints
  • POST /items/<id>/analyze – manual re-analysis trigger
  • Type hints + flasgger docstrings
  • Heatmap data endpoint
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import bleach
from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import limiter
from config.database import get_db
from config.settings import Config
from services.cloudinary_service import delete_image, upload_images
from services.match_service import find_matches_for_item
from services.notification_service import create_notification
from utils.helpers import serialize_doc
from utils.validators import validate_item_data

logger = logging.getLogger(__name__)
items_bp = Blueprint("items", __name__)


def _clean(value: str, max_len: int = 500) -> str:
    """Strip HTML tags and trim to max_len."""
    return bleach.clean(str(value).strip(), tags=[], strip=True)[:max_len]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─── List / Search ────────────────────────────────────────────────────────────
@items_bp.route("/", methods=["GET"])
@jwt_required(optional=True)
def list_items():
    """
    Paginated item feed with filtering.
    ---
    tags: [Items]
    parameters:
      - {name: type,     in: query, type: string,  description: "lost|found|all"}
      - {name: category, in: query, type: string}
      - {name: status,   in: query, type: string,  description: "active|claimed|resolved|all"}
      - {name: location, in: query, type: string}
      - {name: search,   in: query, type: string,  description: "full-text search"}
      - {name: page,     in: query, type: integer, default: 1}
      - {name: limit,    in: query, type: integer, default: 12}
      - {name: sort,     in: query, type: string,  description: "newest|oldest|most_matched"}
      - {name: my_posts, in: query, type: boolean}
    responses:
      200:
        description: Paginated item list
    """
    db      = get_db()
    user_id = get_jwt_identity()

    query: dict[str, Any] = {}

    item_type = request.args.get("type", "all")
    if item_type in ("lost", "found"):
        query["type"] = item_type

    category = request.args.get("category")
    if category:
        query["category"] = category

    status = request.args.get("status", "active")
    if status != "all":
        query["status"] = status

    location = request.args.get("location")
    if location:
        query["location_id"] = location

    search = request.args.get("search", "").strip()
    if search:
        query["$text"] = {"$search": bleach.clean(search, tags=[], strip=True)[:200]}

    if request.args.get("my_posts") == "true" and user_id:
        query["user_id"] = user_id

    page  = max(1, int(request.args.get("page",  1)))
    limit = min(Config.MAX_PAGE_SIZE, int(request.args.get("limit", Config.ITEMS_PER_PAGE)))
    skip  = (page - 1) * limit

    sort_map = {
        "newest":       [("created_at", -1)],
        "oldest":       [("created_at",  1)],
        "most_matched": [("match_count", -1), ("created_at", -1)],
    }
    sort = sort_map.get(request.args.get("sort", "newest"), sort_map["newest"])

    total = db.items.count_documents(query)
    items = list(db.items.find(query).sort(sort).skip(skip).limit(limit))

    serialized = []
    for item in items:
        doc = serialize_doc(item)
        poster = db.users.find_one(
            {"_id": ObjectId(item["user_id"])},
            {"name": 1, "avatar_url": 1},
        )
        doc["poster"] = {
            "name":       poster["name"] if poster else "Unknown",
            "avatar_url": poster.get("avatar_url") if poster else None,
        }
        doc["is_mine"] = user_id == item["user_id"]
        serialized.append(doc)

    return jsonify({
        "items": serialized,
        "pagination": {
            "total":       total,
            "page":        page,
            "limit":       limit,
            "total_pages": max(1, (total + limit - 1) // limit),
            "has_next":    (page * limit) < total,
            "has_prev":    page > 1,
        },
    }), 200


# ─── Create Item ──────────────────────────────────────────────────────────────
@items_bp.route("/", methods=["POST"])
@jwt_required()
@limiter.limit(Config.RATELIMIT_ITEMS_WRITE)
def create_item():
    """
    Post a new lost or found item.
    Accepts multipart/form-data OR JSON.
    After creation, automatically runs AI pipeline (Gemini + OCR + category)
    in a Celery background task.
    ---
    tags: [Items]
    security: [{Bearer: []}]
    consumes: [multipart/form-data, application/json]
    parameters:
      - {name: type,        in: formData, type: string,  required: true}
      - {name: title,       in: formData, type: string,  required: true}
      - {name: description, in: formData, type: string,  required: true}
      - {name: category,    in: formData, type: string}
      - {name: location_id, in: formData, type: string}
      - {name: color,       in: formData, type: string}
      - {name: brand,       in: formData, type: string}
      - {name: tags,        in: formData, type: string,  description: "comma-separated"}
      - {name: features,    in: formData, type: string}
      - {name: images,      in: formData, type: file}
    responses:
      201:
        description: Item created, AI analysis queued
    """
    db      = get_db()
    user_id = get_jwt_identity()

    # ── Parse body (form-data or JSON) ────────────────────────────────────────
    if request.content_type and "multipart" in request.content_type:
        data: dict = request.form.to_dict()
    else:
        data = request.get_json(silent=True) or {}

    # ── Validate ──────────────────────────────────────────────────────────────
    errors = validate_item_data(data)
    if errors:
        return jsonify({"error": errors[0], "errors": errors}), 400

    # ── Sanitize free-text fields ─────────────────────────────────────────────
    title       = _clean(data["title"],       Config.ITEM_TITLE_MAX_LEN)
    description = _clean(data["description"], Config.ITEM_DESC_MAX_LEN)
    brand       = _clean(data.get("brand",    ""), 80)
    features    = _clean(data.get("features", ""), 500)

    tags_raw = data.get("tags", "")
    tags: list[str] = (
        [_clean(t, 40) for t in tags_raw.split(",") if t.strip()]
        if isinstance(tags_raw, str) else
        [_clean(t, 40) for t in tags_raw]
    )

    # ── Location ──────────────────────────────────────────────────────────────
    location_id   = data.get("location_id", "other")
    location_info = next(
        (l for l in Config.CAMPUS_LOCATIONS if l["id"] == location_id),
        Config.CAMPUS_LOCATIONS[-1],
    )

    # ── Date ──────────────────────────────────────────────────────────────────
    date_str = data.get("date_occurred")
    try:
        date_occurred = datetime.fromisoformat(date_str) if date_str else _utcnow()
    except (ValueError, TypeError):
        date_occurred = _utcnow()

    # ── AI analysis from form (if user accepted Gemini suggestions already) ───
    ai_analysis: dict | None = None
    ai_raw = data.get("ai_analysis")
    if ai_raw:
        try:
            ai_analysis = json.loads(ai_raw) if isinstance(ai_raw, str) else ai_raw
        except Exception:
            pass

    # ── Build document ────────────────────────────────────────────────────────
    now = _utcnow()
    item_doc: dict[str, Any] = {
        "type":          data["type"],
        "title":         title,
        "description":   description,
        "category":      data.get("category", "other"),
        "location_id":   location_id,
        "location_name": data.get("location_name", location_info["name"]),
        "location":      {"lat": location_info["lat"], "lng": location_info["lng"]},
        "floor":         _clean(data.get("floor", ""), 80) or None,
        "date_occurred": date_occurred,
        "color":         _clean(data.get("color", ""), 40) or None,
        "brand":         brand or None,
        "tags":          tags,
        "features":      features or None,
        "images":        [],
        "ai_analysis":   ai_analysis,
        "ocr_text":      data.get("ocr_text") or None,
        "ocr_fields":    None,
        "status":        "active",
        "user_id":       user_id,
        "match_count":   0,
        "view_count":    0,
        "ai_processed":  False,    # flag — set True once background pipeline completes
        "created_at":    now,
        "updated_at":    now,
    }

    # ── Upload images ─────────────────────────────────────────────────────────
    uploaded_images: list[dict] = []
    if request.files:
        files = request.files.getlist("images")
        if len(files) > Config.MAX_IMAGES_PER_ITEM:
            return jsonify({"error": f"Max {Config.MAX_IMAGES_PER_ITEM} images allowed"}), 400

        valid_files = [
            f for f in files
            if f and f.filename and
            f.filename.rsplit(".", 1)[-1].lower() in Config.ALLOWED_EXTENSIONS
        ]
        if valid_files:
            uploaded_images = upload_images(valid_files, folder=f"items/{user_id}")

    item_doc["images"] = uploaded_images

    # ── Persist ───────────────────────────────────────────────────────────────
    result  = db.items.insert_one(item_doc)
    item_id = str(result.inserted_id)

    # ── Points ────────────────────────────────────────────────────────────────
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$inc": {"points": Config.POINTS_POST_ITEM}},
    )

    # ── Background AI pipeline ────────────────────────────────────────────────
    # Always queue — even if images not yet uploaded (OCR + category still run
    # on description text; Gemini skipped if no images).
    _queue_ai_pipeline(item_id, uploaded_images)

    logger.info("item_created", extra={"item_id": item_id, "user_id": user_id, "type": data["type"]})

    return jsonify({
        "message":       "Item posted successfully — AI analysis queued",
        "item_id":       item_id,
        "ai_processing": True,
        "item":          {**serialize_doc(item_doc), "_id": item_id, "id": item_id},
    }), 201


# ─── Get Single Item ──────────────────────────────────────────────────────────
@items_bp.route("/<item_id>", methods=["GET"])
@jwt_required(optional=True)
def get_item(item_id: str):
    """
    Full item detail page including AI matches and claims.
    ---
    tags: [Items]
    parameters:
      - {name: item_id, in: path, type: string, required: true}
    responses:
      200:
        description: Item detail
      404:
        description: Not found
    """
    db      = get_db()
    user_id = get_jwt_identity()

    try:
        oid = ObjectId(item_id)
    except InvalidId:
        return jsonify({"error": "Invalid item ID"}), 400

    item = db.items.find_one({"_id": oid})
    if not item:
        return jsonify({"error": "Item not found"}), 404

    db.items.update_one({"_id": oid}, {"$inc": {"view_count": 1}})

    doc = serialize_doc(item)

    poster = db.users.find_one(
        {"_id": ObjectId(item["user_id"])},
        {"name": 1, "email": 1, "avatar_url": 1, "department": 1},
    )
    doc["poster"] = {
        "id":         item["user_id"],
        "name":       poster["name"] if poster else "Unknown",
        "email":      poster["email"] if poster else None,
        "avatar_url": poster.get("avatar_url") if poster else None,
        "department": poster.get("department") if poster else None,
    }
    doc["is_mine"] = user_id == item["user_id"]

    # Matches
    matches = list(
        db.matches.find(
            {"$or": [{"lost_item_id": item_id}, {"found_item_id": item_id}]}
        ).sort("score", -1).limit(10)
    )
    serialized_matches = []
    for m in matches:
        other_id   = m["found_item_id"] if m["lost_item_id"] == item_id else m["lost_item_id"]
        other_item = db.items.find_one({"_id": ObjectId(other_id)})
        if other_item:
            o = serialize_doc(other_item)
            op = db.users.find_one({"_id": ObjectId(other_item["user_id"])}, {"name": 1})
            o["poster_name"] = op["name"] if op else "Unknown"
            serialized_matches.append({
                "match_id":   str(m["_id"]),
                "score":      m.get("score", 0),
                "score_pct":  round(m.get("score", 0) * 100),
                "highlights": m.get("highlights", {}),
                "item":       o,
                "created_at": m["created_at"].isoformat() if m.get("created_at") else None,
            })
    doc["matches"] = serialized_matches

    # Claims
    claims = list(db.claims.find({"item_id": item_id}).sort("created_at", -1))
    doc["claims"]       = [serialize_doc(c) for c in claims]
    doc["claims_count"] = len(claims)

    doc["location_detail"] = next(
        (loc for loc in Config.CAMPUS_LOCATIONS if loc["id"] == item.get("location_id")), None
    )

    return jsonify(doc), 200


# ─── Update Item ──────────────────────────────────────────────────────────────
@items_bp.route("/<item_id>", methods=["PUT"])
@jwt_required()
@limiter.limit(Config.RATELIMIT_ITEMS_WRITE)
def update_item(item_id: str):
    """
    Update item details (owner only).
    ---
    tags: [Items]
    security: [{Bearer: []}]
    """
    db      = get_db()
    user_id = get_jwt_identity()

    try:
        oid = ObjectId(item_id)
    except InvalidId:
        return jsonify({"error": "Invalid item ID"}), 400

    item = db.items.find_one({"_id": oid})
    if not item:
        return jsonify({"error": "Item not found"}), 404
    if item["user_id"] != user_id:
        return jsonify({"error": "Not authorized"}), 403

    data    = request.get_json(silent=True) or {}
    allowed = ["title", "description", "category", "location_id", "location_name",
               "floor", "color", "brand", "tags", "features", "date_occurred"]
    updates: dict = {}

    for field in allowed:
        if field not in data:
            continue
        if field in ("title", "description", "brand", "features", "floor", "color"):
            max_len = {
                "title": Config.ITEM_TITLE_MAX_LEN,
                "description": Config.ITEM_DESC_MAX_LEN,
            }.get(field, 500)
            updates[field] = _clean(data[field], max_len)
        elif field == "tags":
            raw = data[field]
            updates[field] = (
                [_clean(t, 40) for t in raw.split(",") if t.strip()]
                if isinstance(raw, str) else
                [_clean(t, 40) for t in raw]
            )
        else:
            updates[field] = data[field]

    if "location_id" in updates:
        loc = next((l for l in Config.CAMPUS_LOCATIONS if l["id"] == updates["location_id"]), None)
        if loc:
            updates["location"] = {"lat": loc["lat"], "lng": loc["lng"]}

    updates["updated_at"] = _utcnow()
    db.items.update_one({"_id": oid}, {"$set": updates})
    return jsonify({"message": "Item updated"}), 200


# ─── Delete Item ──────────────────────────────────────────────────────────────
@items_bp.route("/<item_id>", methods=["DELETE"])
@jwt_required()
def delete_item(item_id: str):
    """
    Delete an item and its Cloudinary images (owner only).
    ---
    tags: [Items]
    security: [{Bearer: []}]
    """
    db      = get_db()
    user_id = get_jwt_identity()

    try:
        oid = ObjectId(item_id)
    except InvalidId:
        return jsonify({"error": "Invalid item ID"}), 400

    item = db.items.find_one({"_id": oid})
    if not item:
        return jsonify({"error": "Item not found"}), 404
    if item["user_id"] != user_id:
        return jsonify({"error": "Not authorized"}), 403

    for img in item.get("images", []):
        if img.get("public_id"):
            try:
                delete_image(img["public_id"])
            except Exception as e:
                logger.warning("cloudinary_delete_failed", extra={"error": str(e)})

    db.items.delete_one({"_id": oid})
    db.claims.delete_many({"item_id": item_id})
    db.matches.delete_many({"$or": [{"lost_item_id": item_id}, {"found_item_id": item_id}]})
    db.messages.delete_many({"item_id": item_id})

    logger.info("item_deleted", extra={"item_id": item_id})
    return jsonify({"message": "Item deleted"}), 200


# ─── Upload Images ────────────────────────────────────────────────────────────
@items_bp.route("/<item_id>/images", methods=["POST"])
@jwt_required()
@limiter.limit(Config.RATELIMIT_ITEMS_WRITE)
def upload_item_images(item_id: str):
    """
    Add images to an existing item.
    Re-triggers AI pipeline after upload.
    ---
    tags: [Items]
    security: [{Bearer: []}]
    """
    db      = get_db()
    user_id = get_jwt_identity()

    try:
        oid = ObjectId(item_id)
    except InvalidId:
        return jsonify({"error": "Invalid item ID"}), 400

    item = db.items.find_one({"_id": oid})
    if not item:
        return jsonify({"error": "Item not found"}), 404
    if item["user_id"] != user_id:
        return jsonify({"error": "Not authorized"}), 403

    current_count = len(item.get("images", []))
    if current_count >= Config.MAX_IMAGES_PER_ITEM:
        return jsonify({"error": f"Max {Config.MAX_IMAGES_PER_ITEM} images already uploaded"}), 400

    files = request.files.getlist("images")
    max_new = Config.MAX_IMAGES_PER_ITEM - current_count

    valid_files = [
        f for f in files[:max_new]
        if f and f.filename and
        f.filename.rsplit(".", 1)[-1].lower() in Config.ALLOWED_EXTENSIONS
    ]
    if not valid_files:
        return jsonify({"error": "No valid images"}), 400

    uploaded = upload_images(valid_files, folder=f"items/{user_id}")
    db.items.update_one(
        {"_id": oid},
        {
            "$push": {"images": {"$each": uploaded}},
            "$set":  {"updated_at": _utcnow(), "ai_processed": False},
        },
    )

    # Re-trigger AI pipeline with new images
    all_images = item.get("images", []) + uploaded
    _queue_ai_pipeline(item_id, all_images)

    return jsonify({"message": "Images uploaded — AI analysis queued", "uploaded": uploaded}), 200


# ─── Manual AI Analysis Trigger ───────────────────────────────────────────────
@items_bp.route("/<item_id>/analyze", methods=["POST"])
@jwt_required()
@limiter.limit(Config.RATELIMIT_AI)
def trigger_analysis(item_id: str):
    """
    Manually (re-)trigger the full AI pipeline for an item.
    ---
    tags: [Items]
    security: [{Bearer: []}]
    responses:
      202:
        description: Analysis queued
    """
    db      = get_db()
    user_id = get_jwt_identity()

    try:
        oid = ObjectId(item_id)
    except InvalidId:
        return jsonify({"error": "Invalid item ID"}), 400

    item = db.items.find_one({"_id": oid})
    if not item:
        return jsonify({"error": "Item not found"}), 404
    if item["user_id"] != user_id:
        return jsonify({"error": "Not authorized"}), 403

    db.items.update_one({"_id": oid}, {"$set": {"ai_processed": False}})
    _queue_ai_pipeline(item_id, item.get("images", []))

    return jsonify({"message": "AI analysis queued", "item_id": item_id}), 202


# ─── Status Update ────────────────────────────────────────────────────────────
@items_bp.route("/<item_id>/status", methods=["PUT"])
@jwt_required()
def update_status(item_id: str):
    """
    Update item status (owner only).
    ---
    tags: [Items]
    security: [{Bearer: []}]
    """
    db      = get_db()
    user_id = get_jwt_identity()

    try:
        oid = ObjectId(item_id)
    except InvalidId:
        return jsonify({"error": "Invalid item ID"}), 400

    item = db.items.find_one({"_id": oid})
    if not item:
        return jsonify({"error": "Item not found"}), 404
    if item["user_id"] != user_id:
        return jsonify({"error": "Not authorized"}), 403

    new_status = (request.get_json(silent=True) or {}).get("status")
    if new_status not in ("active", "claimed", "resolved"):
        return jsonify({"error": "status must be active|claimed|resolved"}), 400

    db.items.update_one({"_id": oid}, {"$set": {"status": new_status, "updated_at": _utcnow()}})

    if new_status == "resolved":
        db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$inc": {"points": Config.POINTS_RESOLVE}},
        )
        _check_and_award_badges(db, user_id)

    return jsonify({"message": f"Status updated to {new_status}"}), 200


# ─── Get Matches ──────────────────────────────────────────────────────────────
@items_bp.route("/<item_id>/matches", methods=["GET"])
@jwt_required()
def get_matches(item_id: str):
    """
    Return pre-computed matches for an item.
    ---
    tags: [Items]
    security: [{Bearer: []}]
    """
    db = get_db()
    try:
        ObjectId(item_id)
    except InvalidId:
        return jsonify({"error": "Invalid item ID"}), 400

    item = db.items.find_one({"_id": ObjectId(item_id)})
    if not item:
        return jsonify({"error": "Item not found"}), 404

    matches = find_matches_for_item(item_id)
    return jsonify({"matches": matches, "count": len(matches)}), 200


# ─── Heatmap ──────────────────────────────────────────────────────────────────
@items_bp.route("/heatmap/data", methods=["GET"])
def get_heatmap():
    """
    Aggregated location data for the campus loss heatmap.
    ---
    tags: [Items]
    responses:
      200:
        description: Heatmap data array
    """
    db = get_db()
    pipeline = [
        {"$match": {"status": {"$in": ["active", "claimed"]}}},
        {"$group": {
            "_id":           "$location_id",
            "count":         {"$sum": 1},
            "lost":          {"$sum": {"$cond": [{"$eq": ["$type", "lost"]},  1, 0]}},
            "found":         {"$sum": {"$cond": [{"$eq": ["$type", "found"]}, 1, 0]}},
            "lat":           {"$first": "$location.lat"},
            "lng":           {"$first": "$location.lng"},
            "location_name": {"$first": "$location_name"},
        }},
        {"$sort": {"count": -1}},
    ]
    return jsonify({"heatmap": list(db.items.aggregate(pipeline))}), 200


# ─── Private helpers ──────────────────────────────────────────────────────────
def _queue_ai_pipeline(item_id: str, images: list[dict]) -> None:
    """
    Enqueue the full AI pipeline (Celery).
    If Celery is not available, runs inline (blocking) as fallback.
    """
    try:
        from tasks.match_tasks import run_ai_pipeline, find_and_notify_matches
        run_ai_pipeline.delay(item_id)
        find_and_notify_matches.delay(item_id)
        logger.info("ai_pipeline_queued", extra={"item_id": item_id})
    except Exception as e:
        logger.warning(
            "celery_unavailable_running_inline",
            extra={"item_id": item_id, "error": str(e)},
        )
        # Inline fallback — run synchronously (slower but functional)
        try:
            from tasks.match_tasks import _run_ai_pipeline_sync
            _run_ai_pipeline_sync(item_id)
        except Exception as ie:
            logger.error("inline_ai_pipeline_failed", extra={"item_id": item_id, "error": str(ie)})


def _check_and_award_badges(db: Any, user_id: str) -> None:
    """Award badges based on current point total."""
    user = db.users.find_one({"_id": ObjectId(user_id)}, {"points": 1, "badges": 1})
    if not user:
        return

    points         = user.get("points", 0)
    current_badges = {b["id"] for b in user.get("badges", [])}
    new_badges     = []

    for badge_id, badge in Config.BADGES.items():
        if points >= badge["points"] and badge_id not in current_badges:
            new_badges.append({
                "id":         badge_id,
                "label":      badge["label"],
                "icon":       badge["icon"],
                "awarded_at": datetime.now(timezone.utc).isoformat(),
            })

    if new_badges:
        db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$push": {"badges": {"$each": new_badges}}},
        )
        logger.info("badges_awarded", extra={"user_id": user_id, "badges": [b["id"] for b in new_badges]})
