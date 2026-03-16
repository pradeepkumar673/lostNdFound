"""
CampusLostFound - Google Gemini Vision Service
Analyzes item photos and returns structured JSON for form auto-fill.
"""

import os
import json
import logging
import base64
import requests
from io import BytesIO
from flask import current_app

logger = logging.getLogger(__name__)

# ─── Gemini Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an AI assistant for a campus Lost & Found system. 
Your job is to analyze photos of lost/found items and extract structured information 
to help students identify and recover their belongings.

Always respond with ONLY valid JSON — no markdown, no explanation, no extra text.
Be specific and accurate. If unsure, make a reasonable inference based on visible details."""

USER_PROMPT = """Analyze this image of a lost/found item and return ONLY a JSON object with these exact fields:

{
  "item_name": "specific name like 'Samsung Galaxy A54' or 'Nike Air Force backpack'",
  "item_type": "general type: phone/wallet/laptop/bag/id_card/keys/earphones/umbrella/water_bottle/notebook/other",
  "brand": "brand name or null if not visible",
  "model": "model name/number or null",
  "color": "primary color(s) of the item",
  "material": "material like leather/fabric/plastic/metal or null",
  "condition": "new/good/fair/worn",
  "distinctive_features": "any unique marks, stickers, scratches, dents, custom parts",
  "visible_text": "any text, names, numbers, roll numbers, phone numbers visible in image",
  "logos": "any brand logos, college logos, or symbols visible",
  "location_clues": "background clues about where photo was taken e.g. library/canteen/hostel/classroom or null",
  "category": "one of: phone/wallet/laptop/bag/id_card/keys/earphones/umbrella/water_bottle/notebook/other",
  "tags": ["tag1", "tag2", "tag3"],
  "suggested_title": "concise title for the Lost & Found post, max 60 chars",
  "suggested_description": "detailed description for the post, 2-3 sentences mentioning all visible details",
  "confidence": "high/medium/low based on image quality and visibility"
}

Be very specific with brands and models when visible. Extract ALL text visible in the image."""


def analyze_with_gemini(image_bytes=None, image_url=None):
    """
    Analyze an image using Google Gemini Vision.

    Args:
        image_bytes : raw image bytes (from file upload)
        image_url   : public URL of the image (Cloudinary URL)

    Returns:
        dict with structured analysis OR {"error": "..."} on failure
    """
    api_key = _get_api_key()
    if not api_key:
        return {"error": "Gemini API key not configured"}

    try:
        # ── Prepare image data ────────────────────────────────────────────
        if image_bytes:
            b64_image = base64.b64encode(image_bytes).decode("utf-8")
            mime_type = _detect_mime_type(image_bytes)
            image_part = {
                "inline_data": {
                    "mime_type": mime_type,
                    "data":      b64_image,
                }
            }
        elif image_url:
            # Download from URL first
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            img_data  = response.content
            b64_image = base64.b64encode(img_data).decode("utf-8")
            mime_type = response.headers.get("content-type", "image/jpeg").split(";")[0]
            image_part = {
                "inline_data": {
                    "mime_type": mime_type,
                    "data":      b64_image,
                }
            }
        else:
            return {"error": "No image provided"}

        # ── Call Gemini API ───────────────────────────────────────────────
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

        payload = {
            "system_instruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "contents": [{
                "parts": [
                    image_part,
                    {"text": USER_PROMPT}
                ]
            }],
            "generationConfig": {
                "temperature":     0.1,    # Low temp for consistent JSON output
                "topP":            0.8,
                "topK":            40,
                "maxOutputTokens": 1024,
            }
        }

        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # ── Extract and parse response ────────────────────────────────────
        raw_text = (
            data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
        )

        result = _parse_gemini_response(raw_text)
        logger.info(f"Gemini analysis successful — category: {result.get('category')}")
        return result

    except requests.exceptions.Timeout:
        logger.error("Gemini API request timed out")
        return {"error": "Gemini API timeout — please try again"}

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else None
        if status == 429:
            return {"error": "Gemini quota exceeded — try again later"}
        if status == 400:
            return {"error": "Invalid image format for Gemini"}
        logger.error(f"Gemini HTTP error {status}: {e}")
        return {"error": f"Gemini API error ({status})"}

    except Exception as e:
        logger.error(f"Gemini analysis failed: {e}", exc_info=True)
        return {"error": str(e)}


def _parse_gemini_response(raw_text):
    """
    Parse Gemini's raw text response into a clean dict.
    Handles cases where Gemini wraps JSON in markdown code blocks.
    """
    if not raw_text:
        return {"error": "Empty response from Gemini"}

    text = raw_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
        return _sanitize_result(parsed)
    except json.JSONDecodeError:
        # Try to extract JSON object from text
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
                return _sanitize_result(parsed)
            except Exception:
                pass
        logger.warning(f"Could not parse Gemini JSON: {text[:200]}")
        return {"error": "Could not parse Gemini response", "raw": text[:500]}


def _sanitize_result(data):
    """Ensure all expected fields exist and are the right type"""
    valid_categories = [
        "phone", "wallet", "laptop", "bag", "id_card",
        "keys", "earphones", "umbrella", "water_bottle", "notebook", "other"
    ]

    # Ensure category is valid
    if data.get("category") not in valid_categories:
        data["category"] = _map_item_type_to_category(data.get("item_type", ""))

    # Ensure tags is a list
    if not isinstance(data.get("tags"), list):
        tags = data.get("tags", "")
        if isinstance(tags, str):
            data["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
        else:
            data["tags"] = []

    # Ensure string fields aren't None when expected
    str_fields = ["item_name", "color", "suggested_title", "suggested_description"]
    for field in str_fields:
        if data.get(field) is None:
            data[field] = ""

    # Ensure confidence is valid
    if data.get("confidence") not in ("high", "medium", "low"):
        data["confidence"] = "medium"

    return data


def _map_item_type_to_category(item_type):
    """Map free-form item_type to our fixed category list"""
    if not item_type:
        return "other"
    t = item_type.lower()
    mapping = {
        "phone":   ["phone", "mobile", "smartphone", "iphone", "android"],
        "wallet":  ["wallet", "purse", "cardholder"],
        "laptop":  ["laptop", "macbook", "notebook", "tablet", "ipad", "computer"],
        "bag":     ["bag", "backpack", "handbag", "satchel", "tote"],
        "id_card": ["id", "card", "badge", "pass"],
        "keys":    ["key", "keys", "keychain", "keyfob"],
        "earphones": ["earphone", "earbud", "headphone", "airpod", "headset"],
        "umbrella":  ["umbrella", "brolly"],
        "water_bottle": ["bottle", "flask", "thermos", "tumbler"],
        "notebook": ["notebook", "diary", "journal", "book", "planner"],
    }
    for category, keywords in mapping.items():
        if any(kw in t for kw in keywords):
            return category
    return "other"


def _detect_mime_type(image_bytes):
    """Detect MIME type from image bytes magic numbers"""
    if image_bytes[:3] == b'\xff\xd8\xff':
        return "image/jpeg"
    if image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        return "image/png"
    if image_bytes[:6] in (b'GIF87a', b'GIF89a'):
        return "image/gif"
    if image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
        return "image/webp"
    return "image/jpeg"  # default fallback


def _get_api_key():
    """Get Gemini API key from Flask config or env"""
    try:
        key = current_app.config.get("GEMINI_API_KEY")
        if key:
            return key
    except RuntimeError:
        pass
    return os.getenv("GEMINI_API_KEY", "")
