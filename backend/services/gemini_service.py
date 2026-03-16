"""
backend/services/gemini_service.py
Google Gemini Vision analysis service.

Improvements v2:
  • Hard HTTP timeout (Config.GEMINI_TIMEOUT_SECONDS)
  • Retry with exponential back-off (Config.GEMINI_MAX_RETRIES)
  • Circuit-breaker: after 5 consecutive failures, skip Gemini for 5 min
  • Structured logging
  • Type hints throughout
  • Prompt and model name read from Config (not hardcoded)
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from functools import wraps
from typing import Any

import requests

from config.settings import Config

logger = logging.getLogger(__name__)

# ─── Circuit Breaker state (in-process; sufficient for single-worker dev) ────
_cb_failure_count  = 0
_cb_open_until: float = 0.0          # epoch seconds
_CB_FAILURE_THRESHOLD  = 5
_CB_OPEN_DURATION_SECS = 300         # 5 minutes


# ─── Prompts ──────────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = (
    "You are an AI assistant for a campus Lost & Found system. "
    "Analyse photos of lost or found items and extract structured information "
    "to help students identify and recover their belongings. "
    "Always respond with ONLY valid JSON — no markdown fences, no explanation, no extra text."
)

_USER_PROMPT = """Analyse the image and return ONLY a JSON object with exactly these fields:

{
  "item_name": "specific name e.g. 'Samsung Galaxy A54' or 'Nike Air Force backpack'",
  "item_type": "phone|wallet|laptop|bag|id_card|keys|earphones|umbrella|water_bottle|notebook|other",
  "brand": "brand name or null",
  "model": "model name/number or null",
  "color": "primary colour(s)",
  "material": "leather|fabric|plastic|metal|other or null",
  "condition": "new|good|fair|worn",
  "distinctive_features": "unique marks, stickers, scratches, custom parts",
  "visible_text": "all text, names, numbers, roll numbers, phone numbers visible",
  "logos": "brand logos, college logos, symbols visible",
  "location_clues": "background clues about location e.g. library/canteen/hostel/classroom or null",
  "category": "phone|wallet|laptop|bag|id_card|keys|earphones|umbrella|water_bottle|notebook|other",
  "tags": ["tag1", "tag2", "tag3"],
  "suggested_title": "concise post title ≤60 chars",
  "suggested_description": "2–3 sentence description mentioning all visible details",
  "confidence": "high|medium|low"
}

Be specific about brands and models when visible. Extract ALL text in the image."""


# ─── Public API ───────────────────────────────────────────────────────────────
def analyze_with_gemini(
    image_bytes: bytes | None = None,
    image_url:   str   | None = None,
) -> dict[str, Any]:
    """
    Analyse an item image using Google Gemini Vision and return structured JSON.

    Args:
        image_bytes: Raw image bytes (from file upload / Cloudinary download).
        image_url:   Public URL of the image (downloaded internally if bytes not provided).

    Returns:
        Structured analysis dict, or ``{"error": "<reason>"}`` on failure.
    """
    global _cb_failure_count, _cb_open_until

    # ── Circuit breaker check ──────────────────────────────────────────────
    if time.time() < _cb_open_until:
        logger.warning("gemini_circuit_open — skipping")
        return {"error": "Gemini temporarily disabled (circuit open)"}

    api_key = _get_api_key()
    if not api_key:
        return {"error": "GEMINI_API_KEY not configured"}

    # ── Resolve image bytes ────────────────────────────────────────────────
    if not image_bytes and image_url:
        try:
            resp = requests.get(image_url, timeout=10)
            resp.raise_for_status()
            image_bytes = resp.content
        except Exception as exc:
            return {"error": f"Could not download image: {exc}"}

    if not image_bytes:
        return {"error": "No image provided"}

    b64      = base64.b64encode(image_bytes).decode("utf-8")
    mime     = _detect_mime(image_bytes)
    payload  = _build_payload(b64, mime)
    url      = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{Config.GEMINI_MODEL}:generateContent?key={api_key}"
    )

    # ── Retry loop ─────────────────────────────────────────────────────────
    last_error: str = ""
    for attempt in range(1, Config.GEMINI_MAX_RETRIES + 1):
        try:
            resp = requests.post(
                url,
                json    = payload,
                timeout = Config.GEMINI_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            raw_text = (
                resp.json()
                    .get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
            )
            result = _parse_response(raw_text)
            # ── Success → reset circuit breaker ───────────────────────────
            _cb_failure_count = 0
            logger.info("gemini_ok", extra={"category": result.get("category"), "confidence": result.get("confidence")})
            return result

        except requests.exceptions.Timeout:
            last_error = "timeout"
            logger.warning("gemini_timeout", extra={"attempt": attempt})

        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response else 0
            if status == 429:
                wait = 2 ** attempt
                logger.warning("gemini_rate_limited", extra={"wait": wait})
                time.sleep(wait)
                last_error = "rate_limited"
                continue
            if status == 400:
                _record_failure()
                return {"error": "Invalid image for Gemini (400)"}
            last_error = f"http_{status}"
            logger.error("gemini_http_error", extra={"status": status, "attempt": attempt})

        except Exception as exc:
            last_error = str(exc)
            logger.error("gemini_unexpected", extra={"error": str(exc), "attempt": attempt})

        if attempt < Config.GEMINI_MAX_RETRIES:
            time.sleep(2 ** attempt)

    _record_failure()
    return {"error": f"Gemini failed after {Config.GEMINI_MAX_RETRIES} attempts: {last_error}"}


# ─── Private helpers ──────────────────────────────────────────────────────────
def _record_failure() -> None:
    global _cb_failure_count, _cb_open_until
    _cb_failure_count += 1
    if _cb_failure_count >= _CB_FAILURE_THRESHOLD:
        _cb_open_until = time.time() + _CB_OPEN_DURATION_SECS
        logger.error(
            "gemini_circuit_opened",
            extra={"open_until": _cb_open_until, "failures": _cb_failure_count},
        )
        _cb_failure_count = 0


def _build_payload(b64: str, mime: str) -> dict:
    return {
        "system_instruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": mime, "data": b64}},
                {"text": _USER_PROMPT},
            ]
        }],
        "generationConfig": {
            "temperature":     Config.GEMINI_TEMPERATURE,
            "topP":            0.8,
            "topK":            40,
            "maxOutputTokens": Config.GEMINI_MAX_OUTPUT_TOKENS,
        },
    }


def _parse_response(raw: str) -> dict[str, Any]:
    """Parse and sanitise Gemini's text response to a clean dict."""
    if not raw:
        return {"error": "Empty Gemini response"}

    text = raw.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:] if lines[0].startswith("```") else lines
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
        return _sanitise(parsed)
    except json.JSONDecodeError:
        import re
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return _sanitise(json.loads(m.group()))
            except Exception:
                pass
        return {"error": "Could not parse Gemini JSON", "raw": text[:300]}


def _sanitise(data: dict) -> dict[str, Any]:
    """Ensure all expected fields exist with correct types."""
    valid_categories = {
        "phone", "wallet", "laptop", "bag", "id_card",
        "keys", "earphones", "umbrella", "water_bottle", "notebook", "other",
    }
    if data.get("category") not in valid_categories:
        data["category"] = _infer_category(data.get("item_type", ""))

    if not isinstance(data.get("tags"), list):
        raw = data.get("tags", "")
        data["tags"] = [t.strip() for t in raw.split(",") if t.strip()] if isinstance(raw, str) else []

    for field in ("item_name", "color", "suggested_title", "suggested_description"):
        if not isinstance(data.get(field), str):
            data[field] = ""

    if data.get("confidence") not in ("high", "medium", "low"):
        data["confidence"] = "medium"

    return data


def _infer_category(item_type: str) -> str:
    t = (item_type or "").lower()
    MAP = {
        "phone":        ["phone", "mobile", "smartphone", "iphone", "android"],
        "wallet":       ["wallet", "purse", "cardholder"],
        "laptop":       ["laptop", "macbook", "tablet", "ipad"],
        "bag":          ["bag", "backpack", "handbag", "satchel"],
        "id_card":      ["id", "card", "badge", "pass"],
        "keys":         ["key", "keys", "keychain"],
        "earphones":    ["earphone", "earbud", "headphone", "airpod"],
        "umbrella":     ["umbrella", "brolly"],
        "water_bottle": ["bottle", "flask", "thermos", "tumbler"],
        "notebook":     ["notebook", "diary", "journal", "book"],
    }
    for cat, kws in MAP.items():
        if any(k in t for k in kws):
            return cat
    return "other"


def _detect_mime(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _get_api_key() -> str:
    try:
        from flask import current_app
        return current_app.config.get("GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    except RuntimeError:
        return os.getenv("GEMINI_API_KEY", "")
