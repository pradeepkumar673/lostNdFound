
"""
CampusLostFound - Items Routes
GET    /api/items              - List/search all items (paginated)
POST   /api/items              - Create new item (lost or found)
GET    /api/items/<id>         - Get single item with matches
PUT    /api/items/<id>         - Update item
DELETE /api/items/<id>         - Delete item
POST   /api/items/<id>/images  - Upload images to existing item
GET    /api/items/<id>/matches - Get AI matches for an item
PUT    /api/items/<id>/status  - Update item status
GET    /api/items/heatmap      - Get location data for heatmap
"""

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime
import logging

from config.database import get_db
from config.settings import Config
from services.cloudinary_service import upload_images, delete_image
from services.match_service import find_matches_for_item
from services.notification_service import create_notification
from utils.helpers import serialize_doc, paginate_query
from utils.validators import validate_item_data

logger = logging.getLogger(__name__)
items_bp = Blueprint("items", __name__)


# ─── List / Search Items ──────────────────────────────────────────────────────
@items_bp.route("/", methods=["GET"])
@jwt_required(optional=True)
def list_items():
    """
    Query params:
      type       = lost | found | all
      category   = phone | wallet | ...
      status     = active | claimed | resolved
      location   = location_id
      search     = text search query
      page       = page number (default 1)
      limit      = items per page (default 12)
      my_posts   = true → only current user's posts
      my_matches = true → items that match current user's posts
      sort       = newest | oldest | most_matched
    """
    db      = get_db()
    user_id = get_jwt_identity()

    # ── Build Query Filter ────────────────────────────────────────────────
    query = {}

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

    # Text search
    search = request.args.get("search", "").strip()
    if search:
        query["$text"] = {"$search": search}

    # My posts only
    if request.args.get("my_posts") == "true" and user_id:
        query["user_id"] = user_id

    # ── Pagination ────────────────────────────────────────────────────────
    page  = max(1, int(request.args.get("page",  1)))
    limit = min(50, int(request.args.get("limit", Config.ITEMS_PER_PAGE)))
    skip  = (page - 1) * limit

    # ── Sorting ───────────────────────────────────────────────────────────
    sort_map = {
        "newest":       [("created_at", -1)],
        "oldest":       [("created_at",  1)],
        "most_matched": [("match_count", -1), ("created_at", -1)],
    }
    sort_key = request.args.get("sort", "newest")
    sort     = sort_map.get(sort_key, sort_map["newest"])

    # ── Execute Query ─────────────────────────────────────────────────────
    total = db.items.count_documents(query)
    items = list(db.items.find(query).sort(sort).skip(skip).limit(limit))

    # ── Enrich with user info ─────────────────────────────────────────────
    serialized = []
    for item in items:
        doc = serialize_doc(item)
        # Attach poster's name
        poster = db.users.find_one({"_id": ObjectId(item["user_id"])}, {"name": 1, "avatar_url": 1})
        doc["poster"] = {
            "name":       poster["name"] if poster else "Unknown",
            "avatar_url": poster.get("avatar_url") if poster else None,
        }
        # Is this the current user's item?
        doc["is_mine"] = (user_id == item["user_id"])
        serialized.append(doc)

    return jsonify({
        "items":      serialized,
        "pagination": {
            "total":       total,
            "page":        page,
            "limit":       limit,
            "total_pages": (total + limit - 1) // limit,
            "has_next":    (page * limit) < total,
            "has_prev":    page > 1,
        }
    }), 200


# ─── Create Item ──────────────────────────────────────────────────────────────
@items_bp.route("/", methods=["POST"])
@jwt_required()
def create_item():
    """
    Create a new lost or found item.
    Accepts multipart/form-data OR JSON.

    Fields:
      type*        : lost | found
      title*       : item title
      description* : detailed description
      category*    : phone | wallet | laptop | ...
      location_id* : campus location ID
      location_name: human-readable location
      floor        : floor/area detail
      date_occurred: ISO date string
      color        : main color
      brand        : brand name
      tags         : comma-separated tags
      features     : distinctive features
      images       : up to 5 image files (multipart)
      ai_analysis  : JSON string of Gemini analysis
    """
    db      = get_db()
    user_id = get_jwt_identity()

    # Handle both JSON and form data
    if request.content_type and "multipart" in request.content_type:
        data = request.form.to_dict()
    else:
        data = request.get_json() or {}

    # Validate
    errors = validate_item_data(data)
    if errors:
        return jsonify({"error": errors[0], "errors": errors}), 400

    # Parse tags
    tags_raw = data.get("tags", "")
    if isinstance(tags_raw, str):
        tags = [t.strip().lower() for t in tags_raw.split(",") if t.strip()]
    else:
        tags = tags_raw or []

    # Get location coordinates from config
    location_id = data.get("location_id", "other")
    location_info = next(
        (loc for loc in Config.CAMPUS_LOCATIONS if loc["id"] == location_id),
        Config.CAMPUS_LOCATIONS[-1]
    )

    # Parse date
    date_str = data.get("date_occurred")
    try:
        date_occurred = datetime.fromisoformat(date_str) if date_str else datetime.utcnow()
    except (ValueError, TypeError):
        date_occurred = datetime.utcnow()

    # Parse AI analysis if provided
    import json
    ai_analysis = None
    ai_raw = data.get("ai_analysis")
    if ai_raw:
        try:
            ai_analysis = json.loads(ai_raw) if isinstance(ai_raw, str) else ai_raw
        except Exception:
            pass

    # Build item document
    item_doc = {
        "type":          data["type"],          # lost | found
        "title":         data["title"].strip(),
        "description":   data["description"].strip(),
        "category":      data.get("category", "other"),
        "location_id":   location_id,
        "location_name": data.get("location_name", location_info["name"]),
        "location": {
            "lat": location_info["lat"],
            "lng": location_info["lng"],
        },
        "floor":         data.get("floor", "").strip() or None,
        "date_occurred": date_occurred,
        "color":         data.get("color", "").strip() or None,
        "brand":         data.get("brand", "").strip() or None,
        "tags":          tags,
        "features":      data.get("features", "").strip() or None,
        "images":        [],          # filled after upload
        "ai_analysis":   ai_analysis,
        "ocr_text":      data.get("ocr_text", None),
        "status":        "active",    # active | claimed | resolved
        "user_id":       user_id,
        "match_count":   0,
        "view_count":    0,
        "created_at":    datetime.utcnow(),
        "updated_at":    datetime.utcnow(),
        # Embeddings stored separately in matches collection
    }

    # Handle image uploads (multipart)
    uploaded_images = []
    if request.files:
        files = request.files.getlist("images")
        if len(files) > Config.MAX_IMAGES_PER_ITEM:
            return jsonify({"error": f"Maximum {Config.MAX_IMAGES_PER_ITEM} images allowed"}), 400

        valid_files = [
            f for f in files
            if f and f.filename and
            f.filename.rsplit(".", 1)[-1].lower() in Config.ALLOWED_EXTENSIONS
        ]

        if valid_files:
            upload_results = upload_images(valid_files, folder=f"items/{user_id}")
            uploaded_images = upload_results

    item_doc["images"] = uploaded_images

    # Insert
    result  = db.items.insert_one(item_doc)
    item_id = str(result.inserted_id)

    # Award points for posting
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$inc": {"points": 5}}
    )

    # Trigger async match-finding (Celery task)
    try:
        from tasks.match_tasks import find_and_notify_matches
        find_and_notify_matches.delay(item_id)
    except Exception as e:
        logger.warning(f"Celery task not available: {e}")

    logger.info(f"Item created: {item_id} by user {user_id}")

    return jsonify({
        "message": "Item posted successfully",
        "item_id": item_id,
        "item":    {**serialize_doc(item_doc), "_id": item_id}
    }), 201


# ─── Get Single Item ──────────────────────────────────────────────────────────
@items_bp.route("/<item_id>", methods=["GET"])
@jwt_required(optional=True)
def get_item(item_id):
    """Get full item details including AI matches"""
    db      = get_db()
    user_id = get_jwt_identity()

    try:
        oid = ObjectId(item_id)
    except InvalidId:
        return jsonify({"error": "Invalid item ID"}), 400

    item = db.items.find_one({"_id": oid})
    if not item:
        return jsonify({"error": "Item not found"}), 404

    # Increment view count
    db.items.update_one({"_id": oid}, {"$inc": {"view_count": 1}})

    doc = serialize_doc(item)

    # Poster info
    poster = db.users.find_one({"_id": ObjectId(item["user_id"])}, {"name": 1, "email": 1, "avatar_url": 1, "department": 1})
    doc["poster"] = {
        "id":         item["user_id"],
        "name":       poster["name"] if poster else "Unknown",
        "email":      poster["email"] if poster else None,
        "avatar_url": poster.get("avatar_url") if poster else None,
        "department": poster.get("department") if poster else None,
    }

    doc["is_mine"] = (user_id == item["user_id"])

    # Get AI matches from matches collection
    matches = list(db.matches.find(
        {"$or": [{"lost_item_id": item_id}, {"found_item_id": item_id}]}
    ).sort("score", -1).limit(10))

    serialized_matches = []
    for m in matches:
        other_id = m["found_item_id"] if m["lost_item_id"] == item_id else m["lost_item_id"]
        other_item = db.items.find_one({"_id": ObjectId(other_id)})
        if other_item:
            other_doc = serialize_doc(other_item)
            other_poster = db.users.find_one({"_id": ObjectId(other_item["user_id"])}, {"name": 1})
            other_doc["poster_name"] = other_poster["name"] if other_poster else "Unknown"
            serialized_matches.append({
                "match_id":     str(m["_id"]),
                "score":        m.get("score", 0),
                "score_pct":    round(m.get("score", 0) * 100),
                "highlights":   m.get("highlights", {}),
                "item":         other_doc,
                "created_at":   m["created_at"].isoformat() if m.get("created_at") else None,
            })

    doc["matches"] = serialized_matches

    # Claims on this item
    claims = list(db.claims.find({"item_id": item_id}).sort("created_at", -1))
    doc["claims"] = [serialize_doc(c) for c in claims]
    doc["claims_count"] = len(claims)

    # Location info
    doc["location_detail"] = next(
        (loc for loc in Config.CAMPUS_LOCATIONS if loc["id"] == item.get("location_id")),
        None
    )

    return jsonify(doc), 200


# ─── Update Item ──────────────────────────────────────────────────────────────
@items_bp.route("/<item_id>", methods=["PUT"])
@jwt_required()
def update_item(item_id):
    """Update item details (owner only)"""
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
        return jsonify({"error": "Not authorized to edit this item"}), 403

    data = request.get_json() or {}
    allowed = ["title", "description", "category", "location_id", "location_name",
               "floor", "color", "brand", "tags", "features", "date_occurred"]

    updates = {}
    for field in allowed:
        if field in data:
            updates[field] = data[field]

    if "tags" in updates and isinstance(updates["tags"], str):
        updates["tags"] = [t.strip().lower() for t in updates["tags"].split(",") if t.strip()]

    if "location_id" in updates:
        loc = next((l for l in Config.CAMPUS_LOCATIONS if l["id"] == updates["location_id"]), None)
        if loc:
            updates["location"] = {"lat": loc["lat"], "lng": loc["lng"]}

    updates["updated_at"] = datetime.utcnow()

    db.items.update_one({"_id": oid}, {"$set": updates})
    return jsonify({"message": "Item updated successfully"}), 200


# ─── Delete Item ──────────────────────────────────────────────────────────────
@items_bp.route("/<item_id>", methods=["DELETE"])
@jwt_required()
def delete_item(item_id):
    """Delete item (owner only) — also removes images from Cloudinary"""
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

    # Delete images from Cloudinary
    for img in item.get("images", []):
        if img.get("public_id"):
            try:
                delete_image(img["public_id"])
            except Exception as e:
                logger.warning(f"Cloudinary delete failed: {e}")

    # Delete related data
    db.items.delete_one({"_id": oid})
    db.claims.delete_many({"item_id": item_id})
    db.matches.delete_many({"$or": [{"lost_item_id": item_id}, {"found_item_id": item_id}]})
    db.messages.delete_many({"item_id": item_id})

    logger.info(f"Item deleted: {item_id}")
    return jsonify({"message": "Item deleted successfully"}), 200


# ─── Upload Images to Existing Item ──────────────────────────────────────────
@items_bp.route("/<item_id>/images", methods=["POST"])
@jwt_required()
def upload_item_images(item_id):
    """Add images to an existing item"""
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
        return jsonify({"error": f"Maximum {Config.MAX_IMAGES_PER_ITEM} images already uploaded"}), 400

    files = request.files.getlist("images")
    max_new = Config.MAX_IMAGES_PER_ITEM - current_count

    valid_files = [
        f for f in files[:max_new]
        if f and f.filename and
        f.filename.rsplit(".", 1)[-1].lower() in Config.ALLOWED_EXTENSIONS
    ]

    if not valid_files:
        return jsonify({"error": "No valid images provided"}), 400

    uploaded = upload_images(valid_files, folder=f"items/{user_id}")

    db.items.update_one(
        {"_id": oid},
        {
            "$push": {"images": {"$each": uploaded}},
            "$set":  {"updated_at": datetime.utcnow()}
        }
    )

    return jsonify({
        "message":         "Images uploaded successfully",
        "uploaded_images": uploaded,
    }), 200


# ─── Update Item Status ───────────────────────────────────────────────────────
@items_bp.route("/<item_id>/status", methods=["PUT"])
@jwt_required()
def update_status(item_id):
    """
    Update item status: active → claimed → resolved
    Body: { status: "claimed" | "resolved" | "active" }
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

    new_status = request.get_json().get("status")
    if new_status not in ("active", "claimed", "resolved"):
        return jsonify({"error": "Invalid status"}), 400

    db.items.update_one(
        {"_id": oid},
        {"$set": {"status": new_status, "updated_at": datetime.utcnow()}}
    )

    # Award points for resolving
    if new_status == "resolved":
        db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$inc": {"points": 20}}
        )
        _check_and_award_badges(db, user_id)

    return jsonify({"message": f"Status updated to {new_status}"}), 200


# ─── Get Matches for Item ─────────────────────────────────────────────────────
@items_bp.route("/<item_id>/matches", methods=["GET"])
@jwt_required()
def get_matches(item_id):
    """Trigger fresh match finding and return results"""
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


# ─── Heatmap Data ─────────────────────────────────────────────────────────────
@items_bp.route("/heatmap/data", methods=["GET"])
def get_heatmap():
    """Return aggregated location data for the campus heatmap"""
    db = get_db()

    pipeline = [
        {"$match": {"status": {"$in": ["active", "claimed"]}}},
        {"$group": {
            "_id": "$location_id",
            "count":    {"$sum": 1},
            "lost":     {"$sum": {"$cond": [{"$eq": ["$type", "lost"]},  1, 0]}},
            "found":    {"$sum": {"$cond": [{"$eq": ["$type", "found"]}, 1, 0]}},
            "lat":      {"$first": "$location.lat"},
            "lng":      {"$first": "$location.lng"},
            "location_name": {"$first": "$location_name"},
        }},
        {"$sort": {"count": -1}}
    ]

    results = list(db.items.aggregate(pipeline))
    return jsonify({"heatmap": results}), 200


# ─── Helper ───────────────────────────────────────────────────────────────────
def _check_and_award_badges(db, user_id):
    """Check if user deserves new badges based on points"""
    user = db.users.find_one({"_id": ObjectId(user_id)}, {"points": 1, "badges": 1})
    if not user:
        return

    points        = user.get("points", 0)
    current_badges = [b["id"] for b in user.get("badges", [])]
    new_badges    = []

    for badge_id, badge in Config.BADGES.items():
        if points >= badge["points"] and badge_id not in current_badges:
            new_badges.append({
                "id":         badge_id,
                "label":      badge["label"],
                "icon":       badge["icon"],
                "awarded_at": datetime.utcnow().isoformat(),
            })

    if new_badges:
        db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$push": {"badges": {"$each": new_badges}}}
        )
        logger.info(f"Badges awarded to {user_id}: {[b['id'] for b in new_badges]}")
