
"""
CampusLostFound - Configuration Settings
All environment variables and app config live here
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ─── Flask ────────────────────────────────────────────────────────────────
    SECRET_KEY = os.getenv("SECRET_KEY", "campus-lost-found-super-secret-2024")
    DEBUG      = os.getenv("DEBUG", "True") == "True"

    # ─── JWT ──────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY            = os.getenv("JWT_SECRET_KEY", "jwt-campus-secret-2024")
    JWT_ACCESS_TOKEN_EXPIRES  = timedelta(hours=24)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # ─── MongoDB ──────────────────────────────────────────────────────────────
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/campuslostfound")

    # ─── Cloudinary ───────────────────────────────────────────────────────────
    CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY    = os.getenv("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")

    # ─── Google Gemini ────────────────────────────────────────────────────────
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    # ─── Redis / Celery ───────────────────────────────────────────────────────
    REDIS_URL            = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL    = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # ─── ML Models ────────────────────────────────────────────────────────────
    MODEL_PATH   = os.getenv("MODEL_PATH",   "models/categorization_model.h5")
    CLASSES_PATH = os.getenv("CLASSES_PATH", "models/classes.txt")

    # ─── Upload ───────────────────────────────────────────────────────────────
    MAX_CONTENT_LENGTH  = 16 * 1024 * 1024   # 16 MB
    ALLOWED_EXTENSIONS  = {"jpg", "jpeg", "png", "webp"}

    # ─── App Settings ─────────────────────────────────────────────────────────
    MATCH_THRESHOLD      = 0.75   # 75% similarity to trigger notification
    MAX_IMAGES_PER_ITEM  = 5
    ITEMS_PER_PAGE       = 12

    # ─── Campus Locations ─────────────────────────────────────────────────────
    CAMPUS_LOCATIONS = [
        {"id": "lib",      "name": "Central Library",       "lat": 12.9716, "lng": 77.5946},
        {"id": "csedept",  "name": "CSE Department",        "lat": 12.9720, "lng": 77.5950},
        {"id": "canteen",  "name": "Main Canteen",          "lat": 12.9710, "lng": 77.5940},
        {"id": "hostel_a", "name": "Hostel Block A",        "lat": 12.9730, "lng": 77.5960},
        {"id": "hostel_b", "name": "Hostel Block B",        "lat": 12.9732, "lng": 77.5965},
        {"id": "sports",   "name": "Sports Complex",        "lat": 12.9700, "lng": 77.5930},
        {"id": "admin",    "name": "Admin Block",           "lat": 12.9715, "lng": 77.5935},
        {"id": "auditorium","name": "Auditorium",           "lat": 12.9718, "lng": 77.5942},
        {"id": "lab_block","name": "Lab Block",             "lat": 12.9722, "lng": 77.5948},
        {"id": "medical",  "name": "Medical Center",        "lat": 12.9708, "lng": 77.5938},
        {"id": "parking",  "name": "Parking Area",          "lat": 12.9705, "lng": 77.5925},
        {"id": "other",    "name": "Other / Not Sure",      "lat": 12.9716, "lng": 77.5946},
    ]

    # ─── Badge Thresholds ────────────────────────────────────────────────────
    BADGES = {
        "helper":     {"points": 10,  "label": "Helper",      "icon": "🤝"},
        "finder":     {"points": 25,  "label": "Finder",      "icon": "🔍"},
        "hero":       {"points": 50,  "label": "Campus Hero", "icon": "🦸"},
        "legend":     {"points": 100, "label": "Legend",      "icon": "⭐"},
    }
