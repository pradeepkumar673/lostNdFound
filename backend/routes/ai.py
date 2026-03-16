"""
CampusLostFound - AI Routes
POST /api/ai/analyze-gemini   - Analyze image with Google Gemini Vision
POST /api/ai/categorize       - Classify image with MobileNetV2
POST /api/ai/ocr              - Extract text from image via pytesseract
POST /api/ai/search-by-image  - CLIP-based image similarity search
GET  /api/ai/categories       - List available categories
"""

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging
import base64
import io

from services.gemini_service import analyze_with_gemini
from services.ml_service import categorize_image, extract_ocr_text
from services.match_service import search_by_image_embedding
from config.database import get_db
from utils.helpers import serialize_doc

logger = logging.getLogger(__name__)
ai_bp = Blueprint("ai", __name__)

CATEGORIES = [
    {"id": "phone",        "label": "Phone / Mobile",     "icon": "📱"},
    {"id": "wallet",       "label": "Wallet / Purse",     "icon": "👛"},
    {"id": "laptop",       "label": "Laptop / Tablet",    "icon": "💻"},
    {"id": "bag",          "label": "Bag / Backpack",     "icon": "🎒"},
    {"id": "id_card",      "label": "ID / Access Card",   "icon": "🪪"},
    {"id": "keys",         "label": "Keys / Keychain",    "icon": "🔑"},
    {"id": "earphones",    "label": "Earphones / AirPods","icon": "🎧"},
    {"id": "umbrella",     "label": "Umbrella",           "icon": "☂️"},
    {"id": "water_bottle", "label": "Water Bottle",       "icon": "🍶"},
    {"id": "notebook",     "label": "Notebook / Diary",   "icon": "📓"},
    {"id": "other",        "label": "Other",              "icon": "📦"},
]


# ─── Get Categories ───────────────────────────────────────────────────────────
@ai_bp.route("/categories", methods=["GET"])
def get_categories():
    return jsonify({"categories": CATEGORIES}), 200


# ─── Gemini Vision Analysis ───────────────────────────────────────────────────
@ai_bp.route("/analyze-gemini", methods=["POST"])
@jwt_required()
def analyze_gemini():
    """
    Main AI analysis endpoint.
    Accepts: multipart image file OR JSON { image_url: "..." }

    Returns structured JSON with:
    - item_name, brand, model, color, material, condition
    - visible_text, location_clues, category, tags
    - suggested_title, suggested_description
    - confidence level
    """
    image_bytes = None
    image_url   = None

    # ── Accept multipart file ─────────────────────────────────────────────
    if request.files.get("image"):
        file = request.files["image"]
        image_bytes = file.read()

    # ── Accept base64 encoded image ───────────────────────────────────────
    elif request.is_json:
        data = request.get_json()
        if data.get("image_base64"):
            try:
                image_bytes = base64.b64decode(data["image_base64"])
            except Exception:
                return jsonify({"error": "Invalid base64 image data"}), 400
        elif data.get("image_url"):
            image_url = data["image_url"]
        else:
            return jsonify({"error": "Provide image file, image_base64, or image_url"}), 400

    else:
        return jsonify({"error": "No image provided"}), 400

    # ── Call Gemini ───────────────────────────────────────────────────────
    result = analyze_with_gemini(image_bytes=image_bytes, image_url=image_url)

    if result.get("error"):
        # Fallback: try MobileNetV2 + OCR
        logger.warning(f"Gemini failed, falling back: {result['error']}")
        fallback = _run_fallback_analysis(image_bytes)
        return jsonify({
            "source":   "fallback",
            "analysis": fallback,
            "warning":  "Gemini unavailable — used local AI fallback",
        }), 200

    return jsonify({
        "source":   "gemini",
        "analysis": result,
    }), 200


# ─── MobileNetV2 Categorization ───────────────────────────────────────────────
@ai_bp.route("/categorize", methods=["POST"])
@jwt_required()
def categorize():
    """
    Classify an image into one of 11 categories.
    Accepts: multipart image file
    Returns: { category, confidence, top_predictions: [...] }
    """
    if not request.files.get("image"):
        return jsonify({"error": "Image file required"}), 400

    file        = request.files["image"]
    image_bytes = file.read()

    result = categorize_image(image_bytes)
    return jsonify(result), 200


# ─── OCR Text Extraction ──────────────────────────────────────────────────────
@ai_bp.route("/ocr", methods=["POST"])
@jwt_required()
def ocr():
    """
    Extract text from an image using pytesseract.
    Useful for extracting name, roll number, phone from ID cards etc.
    Accepts: multipart image file
    Returns: { raw_text, extracted_fields: { name, roll_number, phone } }
    """
    if not request.files.get("image"):
        return jsonify({"error": "Image file required"}), 400

    file        = request.files["image"]
    image_bytes = file.read()

    result = extract_ocr_text(image_bytes)
    return jsonify(result), 200


# ─── Image-Based Search (CLIP) ────────────────────────────────────────────────
@ai_bp.route("/search-by-image", methods=["POST"])
@jwt_required()
def search_by_image():
    """
    Upload an image and find visually similar items in the database.
    Uses CLIP embeddings + cosine similarity.
    Accepts: multipart image file
    Returns: list of matching items with similarity scores
    """
    if not request.files.get("image"):
        return jsonify({"error": "Image file required"}), 400

    file        = request.files["image"]
    image_bytes = file.read()

    matches = search_by_image_embedding(image_bytes)
    return jsonify({
        "matches": matches,
        "count":   len(matches),
    }), 200


# ─── Full Analysis Pipeline ───────────────────────────────────────────────────
@ai_bp.route("/full-analysis", methods=["POST"])
@jwt_required()
def full_analysis():
    """
    Run complete analysis pipeline:
    1. Gemini Vision (primary)
    2. MobileNetV2 categorization
    3. OCR text extraction
    4. Return combined results

    Used for the "Analyze with AI" button after upload.
    """
    if not request.files.get("image"):
        return jsonify({"error": "Image file required"}), 400

    file        = request.files["image"]
    image_bytes = file.read()

    response = {
        "gemini":    None,
        "category":  None,
        "ocr":       None,
        "source":    "pipeline",
        "combined":  {},
    }

    # 1. Gemini Analysis
    gemini_result = analyze_with_gemini(image_bytes=image_bytes)
    if not gemini_result.get("error"):
        response["gemini"] = gemini_result
        response["source"] = "gemini"

    # 2. MobileNetV2 Categorization
    try:
        cat_result = categorize_image(image_bytes)
        response["category"] = cat_result
    except Exception as e:
        logger.warning(f"Categorization failed: {e}")

    # 3. OCR
    try:
        ocr_result = extract_ocr_text(image_bytes)
        response["ocr"] = ocr_result
    except Exception as e:
        logger.warning(f"OCR failed: {e}")

    # 4. Combine results for form auto-fill
    combined = {}

    if response["gemini"]:
        g = response["gemini"]
        combined.update({
            "title":       g.get("suggested_title", ""),
            "description": g.get("suggested_description", ""),
            "category":    g.get("category", "other"),
            "brand":       g.get("brand", ""),
            "color":       g.get("color", ""),
            "features":    g.get("distinctive_features", ""),
            "tags":        g.get("tags", []),
        })
    elif response["category"]:
        combined["category"] = response["category"].get("category", "other")

    if response["ocr"] and response["ocr"].get("extracted_fields"):
        fields = response["ocr"]["extracted_fields"]
        if fields.get("name") and not combined.get("features"):
            combined["features"] = f"Name visible: {fields['name']}"

    response["combined"] = combined

    return jsonify(response), 200


# ─── Helper: Fallback Analysis ────────────────────────────────────────────────
def _run_fallback_analysis(image_bytes):
    """Run local ML models when Gemini is unavailable"""
    result = {
        "category":             "other",
        "confidence":           0,
        "suggested_title":      "Lost/Found Item",
        "suggested_description": "Please add a description.",
        "visible_text":         "",
        "tags":                 [],
    }

    try:
        cat = categorize_image(image_bytes)
        result["category"]   = cat.get("category", "other")
        result["confidence"] = cat.get("confidence", 0)
        result["suggested_title"] = f"Lost {cat.get('category', 'Item').replace('_', ' ').title()}"
    except Exception as e:
        logger.warning(f"Fallback categorization failed: {e}")

    try:
        ocr = extract_ocr_text(image_bytes)
        result["visible_text"] = ocr.get("raw_text", "")
        if ocr.get("extracted_fields", {}).get("name"):
            result["suggested_title"] += f" — {ocr['extracted_fields']['name']}"
    except Exception as e:
        logger.warning(f"Fallback OCR failed: {e}")

    return result
