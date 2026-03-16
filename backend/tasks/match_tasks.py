"""
CampusLostFound - Celery Background Tasks
Async match-finding and notification tasks.
"""

from celery import Celery
import os
import logging

logger = logging.getLogger(__name__)

# ─── Celery App ───────────────────────────────────────────────────────────────
celery_app = Celery(
    "campuslostfound",
    broker  = os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend = os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)
celery_app.conf.update(
    task_serializer       = "json",
    result_serializer     = "json",
    accept_content        = ["json"],
    timezone              = "UTC",
    enable_utc            = True,
    task_track_started    = True,
    task_acks_late        = True,
    worker_prefetch_multiplier = 1,
    # Retry settings
    task_max_retries      = 3,
    task_default_retry_delay = 60,
)


# ─── Task: Find and Notify Matches ───────────────────────────────────────────
@celery_app.task(bind=True, name="tasks.find_and_notify_matches", max_retries=3)
def find_and_notify_matches(self, item_id):
    """
    Background task: find matches for a newly posted item
    and notify the user if strong matches (>75%) are found.

    Args:
        item_id: MongoDB item ID string
    """
    try:
        from pymongo import MongoClient
        from bson import ObjectId
        from config.settings import Config
        from services.match_service import find_matches_for_item
        from services.notification_service import create_notification
        from services.socket_service import emit_match_found

        # Connect to DB
        client = MongoClient(Config.MONGO_URI)
        db     = client.get_database()

        item = db.items.find_one({"_id": ObjectId(item_id)})
        if not item:
            logger.warning(f"Task: item {item_id} not found")
            return

        logger.info(f"Finding matches for item: {item_id}")
        matches = find_matches_for_item(item_id, threshold=0.45, limit=10)

        strong_matches = [m for m in matches if m["score"] >= Config.MATCH_THRESHOLD]

        if strong_matches:
            # Notify the item owner
            top_match = strong_matches[0]
            score_pct = top_match["score_pct"]

            create_notification(
                db         = db,
                user_id    = item["user_id"],
                notif_type = "match_found",
                title      = f"🎯 {score_pct}% Match Found!",
                message    = (
                    f"We found a potential match for your {item['type']} item "
                    f"'{item['title']}' with {score_pct}% similarity. Check it out!"
                ),
                data = {
                    "item_id":        item_id,
                    "matched_item_id": top_match["item_id"],
                    "score":          top_match["score"],
                    "score_pct":      score_pct,
                    "total_matches":  len(strong_matches),
                }
            )

            logger.info(
                f"Notified user {item['user_id']} about {len(strong_matches)} "
                f"strong matches for item {item_id}"
            )

        client.close()
        return {"matches_found": len(matches), "strong_matches": len(strong_matches)}

    except Exception as exc:
        logger.error(f"Match task failed for {item_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


# ─── Task: Generate and Store Embeddings ─────────────────────────────────────
@celery_app.task(name="tasks.generate_embeddings")
def generate_embeddings(item_id):
    """
    Generate and store CLIP embeddings for an item's images and text.
    Run after item creation for future matching.
    """
    try:
        from pymongo import MongoClient
        from bson import ObjectId
        from config.settings import Config
        from services.match_service import get_image_embedding, get_text_embedding
        import requests

        client = MongoClient(Config.MONGO_URI)
        db     = client.get_database()

        item = db.items.find_one({"_id": ObjectId(item_id)})
        if not item:
            return

        updates = {}

        # Text embedding
        text = f"{item.get('title', '')} {item.get('description', '')} {item.get('brand', '')} {item.get('color', '')}"
        text_emb = get_text_embedding(text[:200])
        if text_emb:
            updates["text_embedding"] = text_emb

        # Image embedding (use first image)
        if item.get("images"):
            first_image_url = item["images"][0].get("url")
            if first_image_url:
                try:
                    resp = requests.get(first_image_url, timeout=10)
                    if resp.ok:
                        img_emb = get_image_embedding(resp.content)
                        if img_emb:
                            updates["image_embedding"] = img_emb
                except Exception as e:
                    logger.warning(f"Image embedding failed for {item_id}: {e}")

        if updates:
            db.items.update_one({"_id": ObjectId(item_id)}, {"$set": updates})
            logger.info(f"Embeddings stored for item {item_id}")

        client.close()

    except Exception as e:
        logger.error(f"Embedding task failed for {item_id}: {e}", exc_info=True)


# ─── Task: Daily Cleanup ─────────────────────────────────────────────────────
@celery_app.task(name="tasks.daily_cleanup")
def daily_cleanup():
    """
    Daily cleanup task:
    - Archive items older than 90 days
    - Remove old notifications (>30 days read)
    - Update match scores for stale matches
    """
    from pymongo import MongoClient
    from config.settings import Config
    from datetime import datetime, timedelta

    client = MongoClient(Config.MONGO_URI)
    db     = client.get_database()

    ninety_days_ago  = datetime.utcnow() - timedelta(days=90)
    thirty_days_ago  = datetime.utcnow() - timedelta(days=30)

    # Archive old items
    archived = db.items.update_many(
        {"created_at": {"$lt": ninety_days_ago}, "status": "active"},
        {"$set": {"status": "archived"}}
    )

    # Delete old read notifications
    deleted_notifs = db.notifications.delete_many(
        {"created_at": {"$lt": thirty_days_ago}, "read": True}
    )

    logger.info(
        f"Daily cleanup: archived {archived.modified_count} items, "
        f"deleted {deleted_notifs.deleted_count} notifications"
    )
    client.close()


# ─── Celery Beat Schedule ─────────────────────────────────────────────────────
celery_app.conf.beat_schedule = {
    "daily-cleanup": {
        "task":     "tasks.daily_cleanup",
        "schedule": 86400.0,   # Every 24 hours
    },
}
