"""
backend/tasks/match_tasks.py
Celery background tasks.

Tasks added / improved in v2:
  run_ai_pipeline      – categorize + OCR + Gemini → auto-fill item fields
  find_and_notify_matches – unchanged logic, improved error handling + visibility
  generate_embeddings  – CLIP image + text embeddings stored on item
  daily_cleanup        – archive old items / prune read notifications

All tasks use bind=True for retry support and structured logging.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from celery import Celery
from celery.utils.log import get_task_logger

from config.settings import Config

logger = get_task_logger(__name__)

# ─── Celery App ───────────────────────────────────────────────────────────────
celery_app = Celery(
    "campuslostfound",
    broker  = Config.CELERY_BROKER_URL,
    backend = Config.CELERY_RESULT_BACKEND,
)
celery_app.conf.update(
    task_serializer              = Config.CELERY_TASK_SERIALIZER,
    result_serializer            = Config.CELERY_RESULT_SERIALIZER,
    accept_content               = Config.CELERY_ACCEPT_CONTENT,
    timezone                     = "UTC",
    enable_utc                   = True,
    task_track_started           = True,
    task_acks_late               = True,
    worker_prefetch_multiplier   = Config.CELERY_WORKER_PREFETCH_MULTIPLIER,
    result_expires               = 3600,      # keep results 1 hour
    task_soft_time_limit         = 120,       # 2 min soft kill
    task_time_limit              = 180,       # 3 min hard kill
)


# ─── Task: Full AI Pipeline ───────────────────────────────────────────────────
@celery_app.task(
    bind        = True,
    name        = "tasks.run_ai_pipeline",
    max_retries = Config.CELERY_TASK_MAX_RETRIES,
    default_retry_delay = Config.CELERY_TASK_DEFAULT_RETRY_DELAY,
)
def run_ai_pipeline(self, item_id: str) -> dict[str, Any]:
    """
    Full AI pipeline for a newly created / updated item.

    Steps:
        1. categorize_image()  → save category if confidence ≥ ML_CATEGORY_MIN_CONFIDENCE
        2. extract_ocr_text()  → save ocr_text + extracted_fields
        3. analyze_with_gemini() → save ai_analysis; auto-fill brand/color/title/desc/tags
           (skipped if no images; cached per image public_id in Redis/Mongo TTL 7 days)
        4. generate_embeddings() – chained automatically

    Returns:
        dict with keys: category, ocr, gemini, updated_fields
    """
    try:
        return _run_ai_pipeline_sync(item_id)
    except Exception as exc:
        logger.error(
            "ai_pipeline_failed",
            extra={"item_id": item_id, "error": str(exc)},
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=Config.CELERY_TASK_DEFAULT_RETRY_DELAY)


def _run_ai_pipeline_sync(item_id: str) -> dict[str, Any]:
    """
    Synchronous implementation of the AI pipeline.
    Called by the Celery task AND by items.py inline fallback.
    """
    from pymongo import MongoClient
    from bson import ObjectId
    import requests as req_lib

    client = MongoClient(Config.MONGO_URI)
    db     = client.get_database()

    result: dict[str, Any] = {
        "item_id":       item_id,
        "category":      None,
        "ocr":           None,
        "gemini":        None,
        "updated_fields": [],
    }

    try:
        item = db.items.find_one({"_id": ObjectId(item_id)})
        if not item:
            logger.warning("ai_pipeline_item_not_found", extra={"item_id": item_id})
            return result

        updates:  dict[str, Any] = {}
        images: list[dict] = item.get("images", [])
        first_image_bytes: bytes | None = None

        # ── Fetch first image bytes (needed for ML + Gemini) ──────────────────
        if images:
            url = images[0].get("url")
            if url:
                try:
                    resp = req_lib.get(url, timeout=10)
                    if resp.ok:
                        first_image_bytes = resp.content
                except Exception as e:
                    logger.warning("image_fetch_failed", extra={"url": url, "error": str(e)})

        # ── Step 1: MobileNetV2 categorization ────────────────────────────────
        if first_image_bytes:
            try:
                from services.ml_service import categorize_image
                cat_result = categorize_image(first_image_bytes)
                result["category"] = cat_result

                if (
                    cat_result.get("confidence", 0) >= Config.ML_CATEGORY_MIN_CONFIDENCE
                    and item.get("category", "other") == "other"
                ):
                    updates["category"] = cat_result["category"]
                    result["updated_fields"].append("category")
                    logger.info(
                        "category_auto_set",
                        extra={
                            "item_id":    item_id,
                            "category":   cat_result["category"],
                            "confidence": cat_result["confidence"],
                        },
                    )
            except Exception as e:
                logger.warning("categorize_failed", extra={"item_id": item_id, "error": str(e)})

        # ── Step 2: OCR ───────────────────────────────────────────────────────
        if first_image_bytes:
            try:
                from services.ml_service import extract_ocr_text
                ocr_result = extract_ocr_text(first_image_bytes)
                result["ocr"] = ocr_result

                if ocr_result.get("raw_text"):
                    updates["ocr_text"]   = ocr_result["raw_text"][:2000]
                    updates["ocr_fields"] = ocr_result.get("extracted_fields", {})
                    result["updated_fields"].append("ocr_text")
            except Exception as e:
                logger.warning("ocr_failed", extra={"item_id": item_id, "error": str(e)})

        # ── Step 3: Gemini Vision ─────────────────────────────────────────────
        if first_image_bytes or images:
            gemini_result = _gemini_with_cache(
                db            = db,
                item_id       = item_id,
                image_public_id = images[0].get("public_id", "") if images else "",
                image_bytes   = first_image_bytes,
                image_url     = images[0].get("url") if images else None,
            )
            result["gemini"] = gemini_result

            if gemini_result and not gemini_result.get("error"):
                updates["ai_analysis"] = gemini_result

                # Auto-fill only empty / placeholder fields
                _autofill = {
                    "brand":       gemini_result.get("brand"),
                    "color":       gemini_result.get("color"),
                    "features":    gemini_result.get("distinctive_features"),
                }
                for field, value in _autofill.items():
                    if value and not item.get(field):
                        updates[field] = str(value)[:200]
                        result["updated_fields"].append(field)

                # Title: only auto-fill if still the default / very short
                if (
                    gemini_result.get("suggested_title")
                    and len(item.get("title", "")) < 10
                ):
                    updates["title"] = gemini_result["suggested_title"][:Config.ITEM_TITLE_MAX_LEN]
                    result["updated_fields"].append("title")

                # Description: auto-fill if < 20 chars
                if (
                    gemini_result.get("suggested_description")
                    and len(item.get("description", "")) < 20
                ):
                    updates["description"] = gemini_result["suggested_description"][:Config.ITEM_DESC_MAX_LEN]
                    result["updated_fields"].append("description")

                # Tags: merge, dedupe
                existing_tags = set(item.get("tags", []))
                new_tags      = set(gemini_result.get("tags", []))
                merged_tags   = list(existing_tags | new_tags)[:20]
                if merged_tags != list(existing_tags):
                    updates["tags"] = merged_tags
                    result["updated_fields"].append("tags")

                # Category from Gemini (if ML didn't set one)
                if (
                    "category" not in updates
                    and gemini_result.get("category")
                    and item.get("category", "other") == "other"
                ):
                    updates["category"] = gemini_result["category"]
                    result["updated_fields"].append("category")

        # ── Persist all updates ───────────────────────────────────────────────
        if updates:
            updates["ai_processed"] = True
            updates["updated_at"]   = datetime.now(timezone.utc)
            db.items.update_one({"_id": ObjectId(item_id)}, {"$set": updates})
            logger.info(
                "ai_pipeline_complete",
                extra={"item_id": item_id, "updated_fields": result["updated_fields"]},
            )

    finally:
        client.close()

    # ── Chain: generate embeddings ────────────────────────────────────────────
    try:
        generate_embeddings.delay(item_id)
    except Exception:
        pass

    return result


# ─── Gemini Cache Helper ──────────────────────────────────────────────────────
def _gemini_with_cache(
    db: Any,
    item_id: str,
    image_public_id: str,
    image_bytes: bytes | None,
    image_url: str | None,
) -> dict | None:
    """
    Call Gemini with Redis/Mongo cache keyed by image public_id.
    TTL = Config.GEMINI_CACHE_TTL_SECONDS (7 days default).
    """
    cache_key = f"gemini_cache:{image_public_id}" if image_public_id else None

    # ── Try Redis cache ───────────────────────────────────────────────────────
    if cache_key:
        import redis, json as _json
        try:
            r = redis.from_url(Config.REDIS_URL, decode_responses=True)
            cached = r.get(cache_key)
            if cached:
                logger.info("gemini_cache_hit", extra={"item_id": item_id})
                return _json.loads(cached)
        except Exception:
            pass

    # ── Call Gemini ───────────────────────────────────────────────────────────
    from services.gemini_service import analyze_with_gemini
    result = analyze_with_gemini(image_bytes=image_bytes, image_url=image_url)

    if result and not result.get("error") and cache_key:
        # Store in Redis
        import redis, json as _json
        try:
            r = redis.from_url(Config.REDIS_URL, decode_responses=True)
            r.setex(cache_key, Config.GEMINI_CACHE_TTL_SECONDS, _json.dumps(result))
        except Exception:
            pass

    return result


# ─── Task: Match & Notify ─────────────────────────────────────────────────────
@celery_app.task(
    bind        = True,
    name        = "tasks.find_and_notify_matches",
    max_retries = Config.CELERY_TASK_MAX_RETRIES,
    default_retry_delay = Config.CELERY_TASK_DEFAULT_RETRY_DELAY,
)
def find_and_notify_matches(self, item_id: str) -> dict[str, Any]:
    """
    Find potential matches for a new item and push a notification if
    any exceed the MATCH_THRESHOLD.
    """
    try:
        from pymongo import MongoClient
        from bson import ObjectId
        from services.match_service import find_matches_for_item
        from services.notification_service import create_notification

        client = MongoClient(Config.MONGO_URI)
        db     = client.get_database()

        item = db.items.find_one({"_id": ObjectId(item_id)})
        if not item:
            return {"matches_found": 0, "strong_matches": 0}

        matches        = find_matches_for_item(item_id, threshold=Config.MATCH_DISPLAY_THRESHOLD)
        strong_matches = [m for m in matches if m["score"] >= Config.MATCH_THRESHOLD]

        if strong_matches:
            top       = strong_matches[0]
            score_pct = top["score_pct"]
            create_notification(
                db         = db,
                user_id    = item["user_id"],
                notif_type = "match_found",
                title      = f"🎯 {score_pct}% Match Found!",
                message    = (
                    f"We found a potential match for your {item['type']} item "
                    f"'{item['title']}' with {score_pct}% similarity."
                ),
                data = {
                    "item_id":         item_id,
                    "matched_item_id": top["item_id"],
                    "score":           top["score"],
                    "score_pct":       score_pct,
                    "total_matches":   len(strong_matches),
                },
            )
            logger.info(
                "match_notification_sent",
                extra={"item_id": item_id, "strong": len(strong_matches)},
            )

        client.close()
        return {"matches_found": len(matches), "strong_matches": len(strong_matches)}

    except Exception as exc:
        logger.error("match_task_failed", extra={"item_id": item_id, "error": str(exc)}, exc_info=True)
        raise self.retry(exc=exc, countdown=Config.CELERY_TASK_DEFAULT_RETRY_DELAY)


# ─── Task: Generate Embeddings ────────────────────────────────────────────────
@celery_app.task(
    bind        = True,
    name        = "tasks.generate_embeddings",
    max_retries = 2,
    default_retry_delay = 30,
)
def generate_embeddings(self, item_id: str) -> dict[str, Any]:
    """
    Compute CLIP image + text embeddings for an item and persist them.
    These are used by match_service for fast cosine-similarity search.
    """
    try:
        from pymongo import MongoClient
        from bson import ObjectId
        from services.match_service import get_image_embedding, get_text_embedding
        import requests as req_lib

        client = MongoClient(Config.MONGO_URI)
        db     = client.get_database()

        item = db.items.find_one({"_id": ObjectId(item_id)})
        if not item:
            return {"status": "item_not_found"}

        updates: dict = {}

        # Text embedding
        text = " ".join(filter(None, [
            item.get("title"),
            item.get("description"),
            item.get("brand"),
            item.get("color"),
            " ".join(item.get("tags", [])),
        ]))[:300]

        text_emb = get_text_embedding(text)
        if text_emb:
            updates["text_embedding"] = text_emb

        # Image embedding (first image)
        if item.get("images"):
            url = item["images"][0].get("url")
            if url:
                try:
                    resp = req_lib.get(url, timeout=10)
                    if resp.ok:
                        img_emb = get_image_embedding(resp.content)
                        if img_emb:
                            updates["image_embedding"] = img_emb
                except Exception as e:
                    logger.warning("embedding_image_fetch_failed", extra={"error": str(e)})

        if updates:
            db.items.update_one({"_id": ObjectId(item_id)}, {"$set": updates})
            logger.info("embeddings_stored", extra={"item_id": item_id, "keys": list(updates.keys())})

        client.close()
        return {"status": "ok", "fields": list(updates.keys())}

    except Exception as exc:
        logger.error("embeddings_task_failed", extra={"item_id": item_id, "error": str(exc)})
        raise self.retry(exc=exc, countdown=30)


# ─── Task: Daily Cleanup ─────────────────────────────────────────────────────
@celery_app.task(name="tasks.daily_cleanup")
def daily_cleanup() -> dict[str, Any]:
    """
    Archive stale items and prune old read notifications.
    Runs daily via Celery Beat.
    """
    from pymongo import MongoClient

    client = MongoClient(Config.MONGO_URI)
    db     = client.get_database()

    cutoff_items  = datetime.now(timezone.utc) - timedelta(days=Config.ITEM_ARCHIVE_DAYS)
    cutoff_notifs = datetime.now(timezone.utc) - timedelta(days=Config.NOTIFICATION_KEEP_DAYS)

    archived = db.items.update_many(
        {"created_at": {"$lt": cutoff_items}, "status": "active"},
        {"$set": {"status": "archived"}},
    )
    deleted_notifs = db.notifications.delete_many(
        {"created_at": {"$lt": cutoff_notifs}, "read": True},
    )

    client.close()

    result = {
        "archived_items":      archived.modified_count,
        "deleted_notifications": deleted_notifs.deleted_count,
    }
    logger.info("daily_cleanup_done", extra=result)
    return result


# ─── Celery Beat Schedule ─────────────────────────────────────────────────────
celery_app.conf.beat_schedule = {
    "daily-cleanup": {
        "task":     "tasks.daily_cleanup",
        "schedule": 86400.0,
    },
}
