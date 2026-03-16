"""
CampusLostFound - Database Configuration
MongoDB connection + collection helpers + index setup
"""

from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from pymongo.errors import ConnectionFailure
import logging

logger = logging.getLogger(__name__)

# Global db reference
_db = None

def init_db(app):
    """Initialize MongoDB connection and create indexes"""
    global _db
    try:
        client = MongoClient(app.config["MONGO_URI"], serverSelectionTimeoutMS=5000)
        # Test connection
        client.admin.command("ping")
        _db = client.get_database()
        app.db = _db

        _create_indexes(_db)
        logger.info(f"✅ MongoDB connected: {_db.name}")
    except ConnectionFailure as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        raise

def get_db():
    """Return the active database instance"""
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db(app) first.")
    return _db

def _create_indexes(db):
    """Create all necessary indexes for performance"""

    # ── Users ──────────────────────────────────────────────────────────────
    db.users.create_index("email",     unique=True)
    db.users.create_index("roll_number", unique=True, sparse=True)
    db.users.create_index("created_at", DESCENDING)

    # ── Items ──────────────────────────────────────────────────────────────
    db.items.create_index("type")                        # lost / found
    db.items.create_index("status")                      # active / claimed / resolved
    db.items.create_index("category")
    db.items.create_index("user_id")
    db.items.create_index("created_at", DESCENDING)
    db.items.create_index("location_id")
    db.items.create_index([("title", TEXT), ("description", TEXT), ("tags", TEXT)])
    db.items.create_index([("location.lat", ASCENDING), ("location.lng", ASCENDING)])

    # ── Claims ─────────────────────────────────────────────────────────────
    db.claims.create_index("item_id")
    db.claims.create_index("claimant_id")
    db.claims.create_index("status")
    db.claims.create_index("created_at", DESCENDING)

    # ── Notifications ──────────────────────────────────────────────────────
    db.notifications.create_index("user_id")
    db.notifications.create_index("read")
    db.notifications.create_index("created_at", DESCENDING)

    # ── Messages ───────────────────────────────────────────────────────────
    db.messages.create_index("item_id")
    db.messages.create_index("created_at", ASCENDING)
    db.messages.create_index([("item_id", ASCENDING), ("created_at", ASCENDING)])

    # ── Matches ────────────────────────────────────────────────────────────
    db.matches.create_index("lost_item_id")
    db.matches.create_index("found_item_id")
    db.matches.create_index("score", DESCENDING)
    db.matches.create_index("created_at", DESCENDING)

    logger.info("✅ MongoDB indexes created")
