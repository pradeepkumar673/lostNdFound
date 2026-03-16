"""
CampusLostFound - Notification Service
"""

from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def create_notification(db, user_id, notif_type, title, message, data=None):
    """
    Create a notification for a user.

    Args:
        db        : MongoDB database instance
        user_id   : recipient user ID (string)
        notif_type: string type identifier
        title     : short notification title
        message   : full notification message
        data      : optional dict with extra payload (item_id, claim_id, etc.)
    """
    notif_doc = {
        "user_id":    user_id,
        "type":       notif_type,
        "title":      title,
        "message":    message,
        "data":       data or {},
        "read":       False,
        "read_at":    None,
        "created_at": datetime.utcnow(),
    }
    result = db.notifications.insert_one(notif_doc)

    # Try to emit via SocketIO if available
    try:
        from services.socket_service import emit_notification
        emit_notification(user_id, {
            "id":      str(result.inserted_id),
            "type":    notif_type,
            "title":   title,
            "message": message,
            "data":    data or {},
        })
    except Exception as e:
        logger.debug(f"Socket emit failed (non-critical): {e}")

    logger.info(f"Notification created for {user_id}: {notif_type}")
    return str(result.inserted_id)
