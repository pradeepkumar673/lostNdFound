"""
backend/routes/auth.py
Authentication endpoints.

Changes v2:
  • Rate limiting on login (10/min) and register (5/min)
  • JWT blacklist via Redis (calls app.blacklist_token)
  • bleach sanitisation on name / department fields
  • Type hints throughout
  • Flasgger docstrings
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import bleach
from bson import ObjectId
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from werkzeug.security import check_password_hash, generate_password_hash

from app import limiter
from config.database import get_db
from config.settings import Config
from utils.helpers import serialize_doc
from utils.validators import validate_email, validate_password

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _sanitize_str(value: str) -> str:
    """Strip HTML from a free-text field."""
    return bleach.clean(value.strip(), tags=[], strip=True)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─── Register ─────────────────────────────────────────────────────────────────
@auth_bp.route("/register", methods=["POST"])
@limiter.limit(Config.RATELIMIT_REGISTER)
def register():
    """
    Register a new campus user.
    ---
    tags: [Auth]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          required: [name, email, password]
          properties:
            name:        {type: string, example: "Pradeep Kumar"}
            email:       {type: string, example: "pradeep@university.edu"}
            password:    {type: string, example: "Pass1234"}
            roll_number: {type: string, example: "21CS001"}
            department:  {type: string, example: "CSE"}
            phone:       {type: string, example: "9876543210"}
    responses:
      201:
        description: Registration successful, returns JWT tokens + user object
      400:
        description: Validation error
      409:
        description: Email or roll number already registered
    """
    db   = get_db()
    data = request.get_json(silent=True) or {}

    # ── Required field validation ─────────────────────────────────────────────
    for field in ("name", "email", "password"):
        if not data.get(field, "").strip():
            return jsonify({"error": f"{field} is required"}), 400

    name     = _sanitize_str(data["name"])[:80]
    email    = data["email"].strip().lower()
    password = data["password"]

    if not validate_email(email):
        return jsonify({"error": "Invalid email format"}), 400

    ok, msg = validate_password(password)
    if not ok:
        return jsonify({"error": msg}), 400

    if db.users.find_one({"email": email}):
        return jsonify({"error": "Email already registered"}), 409

    roll_number = _sanitize_str(data.get("roll_number", "")).upper() or None
    if roll_number and db.users.find_one({"roll_number": roll_number}):
        return jsonify({"error": "Roll number already registered"}), 409

    now = _utcnow()
    user_doc = {
        "name":        name,
        "email":       email,
        "password":    generate_password_hash(password),
        "roll_number": roll_number,
        "department":  _sanitize_str(data.get("department", ""))[:60] or None,
        "phone":       _sanitize_str(data.get("phone", ""))[:15] or None,
        "avatar_url":  None,
        "points":      0,
        "badges":      [],
        "is_active":   True,
        "created_at":  now,
        "updated_at":  now,
        "last_login":  None,
    }

    result  = db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)

    access_token  = create_access_token(identity=user_id)
    refresh_token = create_refresh_token(identity=user_id)

    logger.info("user_registered", extra={"user_id": user_id, "email": email})

    return jsonify({
        "message":       "Registration successful",
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "user": _public_user(user_doc, user_id),
    }), 201


# ─── Login ────────────────────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["POST"])
@limiter.limit(Config.RATELIMIT_LOGIN)
def login():
    """
    Login with email + password.
    ---
    tags: [Auth]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          required: [email, password]
          properties:
            email:    {type: string}
            password: {type: string}
    responses:
      200:
        description: Login successful, returns JWT tokens + user object
      401:
        description: Invalid credentials
    """
    db   = get_db()
    data = request.get_json(silent=True) or {}

    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    user = db.users.find_one({"email": email})
    if not user or not check_password_hash(user["password"], password):
        logger.warning("login_failed", extra={"email": email})
        return jsonify({"error": "Invalid email or password"}), 401

    if not user.get("is_active", True):
        return jsonify({"error": "Account is deactivated — contact admin"}), 403

    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": _utcnow()}},
    )

    user_id       = str(user["_id"])
    access_token  = create_access_token(identity=user_id)
    refresh_token = create_refresh_token(identity=user_id)

    logger.info("login_success", extra={"user_id": user_id})

    return jsonify({
        "message":       "Login successful",
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "user": _public_user(user, user_id),
    }), 200


# ─── Refresh ──────────────────────────────────────────────────────────────────
@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """
    Issue a new access token using a valid refresh token.
    ---
    tags: [Auth]
    security: [{Bearer: []}]
    responses:
      200:
        description: New access token
    """
    user_id      = get_jwt_identity()
    access_token = create_access_token(identity=user_id)
    return jsonify({"access_token": access_token}), 200


# ─── Get Profile ──────────────────────────────────────────────────────────────
@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def get_me():
    """
    Return current user's profile + stats.
    ---
    tags: [Auth]
    security: [{Bearer: []}]
    responses:
      200:
        description: User profile object
    """
    db      = get_db()
    user_id = get_jwt_identity()

    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({"error": "User not found"}), 404

    total_posts     = db.items.count_documents({"user_id": user_id})
    recovered_count = db.items.count_documents({"user_id": user_id, "status": "resolved"})
    claims_accepted = db.claims.count_documents({"claimant_id": user_id, "status": "accepted"})

    profile = _public_user(user, user_id)
    profile["stats"] = {
        "total_posts":     total_posts,
        "recovered_count": recovered_count,
        "claims_accepted": claims_accepted,
    }
    profile["created_at"] = user["created_at"].isoformat()
    profile["last_login"]  = user["last_login"].isoformat() if user.get("last_login") else None

    return jsonify(profile), 200


# ─── Update Profile ───────────────────────────────────────────────────────────
@auth_bp.route("/me", methods=["PUT"])
@jwt_required()
def update_me():
    """
    Update editable profile fields.
    ---
    tags: [Auth]
    security: [{Bearer: []}]
    responses:
      200:
        description: Profile updated
    """
    db      = get_db()
    user_id = get_jwt_identity()
    data    = request.get_json(silent=True) or {}

    allowed = {"name": 80, "phone": 15, "department": 60, "avatar_url": 512}
    updates: dict = {}

    for field, max_len in allowed.items():
        if field in data:
            val = _sanitize_str(str(data[field]))[:max_len]
            updates[field] = val or None

    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400

    updates["updated_at"] = _utcnow()
    db.users.update_one({"_id": ObjectId(user_id)}, {"$set": updates})
    return jsonify({"message": "Profile updated"}), 200


# ─── Change Password ──────────────────────────────────────────────────────────
@auth_bp.route("/change-password", methods=["POST"])
@jwt_required()
@limiter.limit("5 per minute")
def change_password():
    """
    Change the authenticated user's password.
    ---
    tags: [Auth]
    security: [{Bearer: []}]
    """
    db      = get_db()
    user_id = get_jwt_identity()
    data    = request.get_json(silent=True) or {}

    current_password = data.get("current_password", "")
    new_password     = data.get("new_password", "")

    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user or not check_password_hash(user["password"], current_password):
        return jsonify({"error": "Current password is incorrect"}), 401

    ok, msg = validate_password(new_password)
    if not ok:
        return jsonify({"error": msg}), 400

    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"password": generate_password_hash(new_password), "updated_at": _utcnow()}},
    )
    return jsonify({"message": "Password changed successfully"}), 200


# ─── Logout ───────────────────────────────────────────────────────────────────
@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    """
    Revoke the current access token (adds JTI to Redis blacklist).
    ---
    tags: [Auth]
    security: [{Bearer: []}]
    responses:
      200:
        description: Logged out
    """
    from app import blacklist_token

    claims     = get_jwt()
    jti        = claims["jti"]
    expires_in = int(Config.JWT_ACCESS_TOKEN_EXPIRES.total_seconds())
    blacklist_token(current_app._get_current_object(), jti, expires_in)

    logger.info("user_logout", extra={"user_id": get_jwt_identity()})
    return jsonify({"message": "Logged out successfully"}), 200


# ─── Private helpers ──────────────────────────────────────────────────────────
def _public_user(user: dict, user_id: str) -> dict:
    """Return a safe public user dict (no password hash)."""
    return {
        "id":          user_id,
        "name":        user.get("name"),
        "email":       user.get("email"),
        "roll_number": user.get("roll_number"),
        "department":  user.get("department"),
        "avatar_url":  user.get("avatar_url"),
        "points":      user.get("points", 0),
        "badges":      user.get("badges", []),
    }
