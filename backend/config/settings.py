"""
backend/config/settings.py
CampusLostFound – Central configuration.
All thresholds, magic numbers, and feature flags live here.
Environment is validated at startup via pydantic-settings so missing
keys surface as a clear error before any route is called.
"""

from __future__ import annotations

import os
import sys
import logging
from datetime import timedelta
from typing import List

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# ─── Pydantic env validation ──────────────────────────────────────────────────
try:
    from pydantic_settings import BaseSettings
    from pydantic import field_validator, ValidationError

    class _EnvSettings(BaseSettings):
        """All required / optional env vars with types and defaults."""

        # Flask
        SECRET_KEY: str
        JWT_SECRET_KEY: str
        DEBUG: bool = False
        FLASK_ENV: str = "production"

        # MongoDB
        MONGO_URI: str

        # Redis
        REDIS_URL: str = "redis://localhost:6379/0"

        # Cloudinary  (optional – upload falls back to local if missing)
        CLOUDINARY_CLOUD_NAME: str = ""
        CLOUDINARY_API_KEY: str = ""
        CLOUDINARY_API_SECRET: str = ""

        # Gemini
        GEMINI_API_KEY: str = ""

        # ML
        MODEL_PATH: str = "models/categorization_model.h5"
        CLASSES_PATH: str = "models/classes.txt"

        class Config:
            env_file = ".env"
            case_sensitive = True

    def _validate_env() -> _EnvSettings:
        try:
            return _EnvSettings()  # type: ignore[call-arg]
        except ValidationError as exc:
            missing = [e["loc"][0] for e in exc.errors() if e["type"] == "missing"]
            logger.critical(
                "❌ Missing required environment variables: %s — "
                "add them to your .env file and restart.",
                missing,
            )
            sys.exit(1)

    _env = _validate_env()

except ImportError:
    # pydantic-settings not installed yet — graceful degradation
    logger.warning("pydantic-settings not installed; skipping strict env validation.")
    _env = None  # type: ignore[assignment]


# ─────────────────────────────────────────────────────────────────────────────
class Config:
    # ── Flask ─────────────────────────────────────────────────────────────────
    SECRET_KEY: str  = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PROD")
    DEBUG: bool      = os.getenv("DEBUG", "False").lower() == "true"
    FLASK_ENV: str   = os.getenv("FLASK_ENV", "production")

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str               = os.getenv("JWT_SECRET_KEY", "CHANGE_JWT_IN_PROD")
    JWT_ACCESS_TOKEN_EXPIRES          = timedelta(hours=24)
    JWT_REFRESH_TOKEN_EXPIRES         = timedelta(days=30)
    JWT_BLACKLIST_ENABLED: bool       = True
    JWT_BLACKLIST_TOKEN_CHECKS: list  = ["access", "refresh"]

    # ── MongoDB ───────────────────────────────────────────────────────────────
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017/campuslostfound")
    MONGO_SERVER_SELECTION_TIMEOUT_MS: int = 5_000
    MONGO_CONNECT_TIMEOUT_MS: int          = 10_000

    # ── Cloudinary ────────────────────────────────────────────────────────────
    CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY: str    = os.getenv("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET", "")

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # ── Celery ────────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str    = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_TASK_SERIALIZER: str   = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: list   = ["json"]
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_ACKS_LATE: bool     = True
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = 1
    CELERY_TASK_MAX_RETRIES: int    = 3
    CELERY_TASK_DEFAULT_RETRY_DELAY: int = 60   # seconds

    # ── Gemini ────────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str         = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str           = "gemini-1.5-flash"
    GEMINI_TIMEOUT_SECONDS: int = 25          # hard HTTP timeout
    GEMINI_MAX_RETRIES: int     = 2
    GEMINI_TEMPERATURE: float   = 0.1
    GEMINI_MAX_OUTPUT_TOKENS: int = 1024
    GEMINI_CACHE_TTL_SECONDS: int = 7 * 24 * 3600   # 7 days

    # ── ML Models ─────────────────────────────────────────────────────────────
    MODEL_PATH: str   = os.getenv("MODEL_PATH",   "models/categorization_model.h5")
    CLASSES_PATH: str = os.getenv("CLASSES_PATH", "models/classes.txt")
    ML_IMAGE_SIZE: tuple = (224, 224)

    # Minimum confidence to auto-apply ML category/tags
    ML_CATEGORY_MIN_CONFIDENCE: float = 0.60

    # ── CLIP / Matching ───────────────────────────────────────────────────────
    CLIP_MODEL_NAME: str = "openai/clip-vit-base-patch32"
    CLIP_EMBEDDING_DIM: int = 512

    # Cosine similarity thresholds
    MATCH_THRESHOLD: float        = 0.75   # strong match → push notification
    MATCH_DISPLAY_THRESHOLD: float = 0.45  # show in UI
    MATCH_CANDIDATE_LIMIT: int    = 200    # max DB candidates per search
    MATCH_RESULT_LIMIT: int       = 10     # max results returned

    # Weights for multi-signal matching score (must sum ≤ 1.0)
    MATCH_WEIGHT_CATEGORY: float = 0.30
    MATCH_WEIGHT_COLOR: float    = 0.15
    MATCH_WEIGHT_BRAND: float    = 0.20
    MATCH_WEIGHT_TAGS: float     = 0.15
    MATCH_WEIGHT_TEXT: float     = 0.20

    # CLIP text similarity raw-to-normalised range (empirical)
    CLIP_SIM_LOW: float  = 0.70
    CLIP_SIM_HIGH: float = 1.00

    # Embedding cache — LRU size in memory
    EMBEDDING_LRU_MAXSIZE: int = 512

    # ── Upload ────────────────────────────────────────────────────────────────
    MAX_CONTENT_LENGTH: int  = 16 * 1024 * 1024   # 16 MB
    ALLOWED_EXTENSIONS: set  = {"jpg", "jpeg", "png", "webp"}
    MAX_IMAGES_PER_ITEM: int = 5

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    RATELIMIT_STORAGE_URL: str       = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    RATELIMIT_LOGIN: str             = "10 per minute"
    RATELIMIT_REGISTER: str          = "5 per minute"
    RATELIMIT_CLAIM: str             = "20 per minute"
    RATELIMIT_CHAT: str              = "30 per minute"
    RATELIMIT_AI: str                = "15 per minute"
    RATELIMIT_ITEMS_WRITE: str       = "20 per minute"
    RATELIMIT_DEFAULT: str           = "200 per minute"

    # ── Sanitization ─────────────────────────────────────────────────────────
    BLEACH_ALLOWED_TAGS: list        = []        # strip ALL html
    BLEACH_ALLOWED_ATTRIBUTES: dict  = {}
    CHAT_MAX_MESSAGE_LEN: int        = 1_000
    ITEM_TITLE_MAX_LEN: int          = 100
    ITEM_DESC_MIN_LEN: int           = 10
    ITEM_DESC_MAX_LEN: int           = 2_000

    # ── Pagination ────────────────────────────────────────────────────────────
    ITEMS_PER_PAGE: int = 12
    MAX_PAGE_SIZE: int  = 50

    # ── Badges ───────────────────────────────────────────────────────────────
    BADGES: dict = {
        "helper": {"points": 10,  "label": "Helper",      "icon": "🤝"},
        "finder": {"points": 25,  "label": "Finder",      "icon": "🔍"},
        "hero":   {"points": 50,  "label": "Campus Hero", "icon": "🦸"},
        "legend": {"points": 100, "label": "Legend",      "icon": "⭐"},
    }

    # Points awarded per action
    POINTS_POST_ITEM: int    = 5
    POINTS_RESOLVE: int      = 20
    POINTS_CLAIM_ACCEPT: int = 15
    POINTS_CLAIM_MAKE: int   = 10

    # ── Campus Locations ─────────────────────────────────────────────────────
    CAMPUS_LOCATIONS: List[dict] = [
        {"id": "lib",       "name": "Central Library",   "lat": 12.9716, "lng": 77.5946},
        {"id": "csedept",   "name": "CSE Department",    "lat": 12.9720, "lng": 77.5950},
        {"id": "canteen",   "name": "Main Canteen",      "lat": 12.9710, "lng": 77.5940},
        {"id": "hostel_a",  "name": "Hostel Block A",    "lat": 12.9730, "lng": 77.5960},
        {"id": "hostel_b",  "name": "Hostel Block B",    "lat": 12.9732, "lng": 77.5965},
        {"id": "sports",    "name": "Sports Complex",    "lat": 12.9700, "lng": 77.5930},
        {"id": "admin",     "name": "Admin Block",       "lat": 12.9715, "lng": 77.5935},
        {"id": "auditorium","name": "Auditorium",        "lat": 12.9718, "lng": 77.5942},
        {"id": "lab_block", "name": "Lab Block",         "lat": 12.9722, "lng": 77.5948},
        {"id": "medical",   "name": "Medical Center",    "lat": 12.9708, "lng": 77.5938},
        {"id": "parking",   "name": "Parking Area",      "lat": 12.9705, "lng": 77.5925},
        {"id": "other",     "name": "Other / Not Sure",  "lat": 12.9716, "lng": 77.5946},
    ]

    # Archive items older than N days
    ITEM_ARCHIVE_DAYS: int       = 90
    NOTIFICATION_KEEP_DAYS: int  = 30
