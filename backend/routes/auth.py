
"""
CampusLostFound - Authentication Routes
POST /api/auth/register
POST /api/auth/login
POST /api/auth/refresh
GET  /api/auth/me
PUT  /api/auth/me
POST /api/auth/logout
"""

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from bson import ObjectId
import re
import logging

from config.database import get_db
from utils.validators import validate_email, validate_password
from utils.helpers import serialize_doc

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)

# Token blacklist (in production use Redis)
_token_blacklist = set()


# ─── Register ─────────────────────────────────────────────────────────────────
@auth_bp.route("/register", methods=["POST"])
def register():
    """
    Register a new user
    Body: { name, email, password, roll_number?, department?, phone? }
    """
    db = get_db()
    data = request.get_json()

    # Validate required fields
    required = ["name", "email", "password"]
    for field in required:
        if not data.get(field, "").strip():
            return jsonify({"error": f"{field} is required"}), 400

    name     = data["name"].strip()
    email    = data["email"].strip().lower()
    password = data["password"]

    # Validate email format (university email preferred but not enforced)
    if not validate_email(email):
        return jsonify({"error": "Invalid email format"}), 400

    # Validate password strength
    ok, msg = validate_password(password)
    if not ok:
        return jsonify({"error": msg}), 400

    # Check if email already exists
    if db.users.find_one({"email": email}):
        return jsonify({"error": "Email already registered"}), 409

    # Check roll number uniqueness if provided
    roll_number = data.get("roll_number", "").strip().upper()
    if roll_number and db.users.find_one({"roll_number": roll_number}):
        return jsonify({"error": "Roll number already registered"}), 409

    # Create user document
    user_doc = {
        "name":        name,
        "email":       email,
        "password":    generate_password_hash(password),
        "roll_number": roll_number or None,
        "department":  data.get("department", "").strip() or None,
        "phone":       data.get("phone", "").strip() or None,
        "avatar_url":  None,
        "points":      0,
        "badges":      [],
        "is_active":   True,
        "created_at":  datetime.utcnow(),
        "updated_at":  datetime.utcnow(),
        "last_login":  None,
    }

    result    = db.users.insert_one(user_doc)
    user_id   = str(result.inserted_id)

    access_token  = create_access_token(identity=user_id)
    refresh_token = create_refresh_token(identity=user_id)

    logger.info(f"New user registered: {email}")

    return jsonify({
        "message":       "Registration successful",
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "user": {
            "id":          user_id,
            "name":        name,
            "email":       email,
            "roll_number": roll_number or None,
            "department":  user_doc["department"],
            "points":      0,
            "badges":      [],
        }
    }), 201


# ─── Login ────────────────────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Login with email + password
    Body: { email, password }
    """
    db   = get_db()
    data = request.get_json()

    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    user = db.users.find_one({"email": email})
    if not user or not check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid email or password"}), 401

    if not user.get("is_active", True):
        return jsonify({"error": "Account is deactivated"}), 403

    # Update last login
    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.utcnow()}}
    )

    user_id       = str(user["_id"])
    access_token  = create_access_token(identity=user_id)
    refresh_token = create_refresh_token(identity=user_id)

    logger.info(f"User logged in: {email}")

    return jsonify({
        "message":       "Login successful",
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "user": {
            "id":          user_id,
            "name":        user["name"],
            "email":       user["email"],
            "roll_number": user.get("roll_number"),
            "department":  user.get("department"),
            "avatar_url":  user.get("avatar_url"),
            "points":      user.get("points", 0),
            "badges":      user.get("badges", []),
        }
    }), 200


# ─── Refresh Token ────────────────────────────────────────────────────────────
@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """Get a new access token using the refresh token"""
    user_id      = get_jwt_identity()
    access_token = create_access_token(identity=user_id)
    return jsonify({"access_token": access_token}), 200


# ─── Get Current User ─────────────────────────────────────────────────────────
@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def get_me():
    """Get current authenticated user profile"""
    db      = get_db()
    user_id = get_jwt_identity()

    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Get stats
    total_posts     = db.items.count_documents({"user_id": user_id})
    recovered_count = db.items.count_documents({"user_id": user_id, "status": "resolved"})
    claims_count    = db.claims.count_documents({"claimant_id": user_id, "status": "accepted"})

    return jsonify({
        "id":            user_id,
        "name":          user["name"],
        "email":         user["email"],
        "roll_number":   user.get("roll_number"),
        "department":    user.get("department"),
        "phone":         user.get("phone"),
        "avatar_url":    user.get("avatar_url"),
        "points":        user.get("points", 0),
        "badges":        user.get("badges", []),
        "created_at":    user["created_at"].isoformat(),
        "last_login":    user["last_login"].isoformat() if user.get("last_login") else None,
        "stats": {
            "total_posts":     total_posts,
            "recovered_count": recovered_count,
            "claims_accepted": claims_count,
        }
    }), 200


# ─── Update Profile ───────────────────────────────────────────────────────────
@auth_bp.route("/me", methods=["PUT"])
@jwt_required()
def update_me():
    """
    Update current user profile
    Body: { name?, phone?, department?, avatar_url? }
    """
    db      = get_db()
    user_id = get_jwt_identity()
    data    = request.get_json()

    allowed_fields = ["name", "phone", "department", "avatar_url"]
    updates = {}

    for field in allowed_fields:
        if field in data:
            updates[field] = data[field].strip() if isinstance(data[field], str) else data[field]

    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400

    updates["updated_at"] = datetime.utcnow()

    db.users.update_one({"_id": ObjectId(user_id)}, {"$set": updates})

    logger.info(f"User profile updated: {user_id}")
    return jsonify({"message": "Profile updated successfully"}), 200


# ─── Change Password ──────────────────────────────────────────────────────────
@auth_bp.route("/change-password", methods=["POST"])
@jwt_required()
def change_password():
    """
    Change user password
    Body: { current_password, new_password }
    """
    db      = get_db()
    user_id = get_jwt_identity()
    data    = request.get_json()

    current_password = data.get("current_password", "")
    new_password     = data.get("new_password", "")

    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not check_password_hash(user["password"], current_password):
        return jsonify({"error": "Current password is incorrect"}), 401

    ok, msg = validate_password(new_password)
    if not ok:
        return jsonify({"error": msg}), 400

    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "password":   generate_password_hash(new_password),
            "updated_at": datetime.utcnow()
        }}
    )

    return jsonify({"message": "Password changed successfully"}), 200


# ─── Logout ───────────────────────────────────────────────────────────────────
@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    """Blacklist the current JWT token"""
    jti = get_jwt()["jti"]
    _token_blacklist.add(jti)
    return jsonify({"message": "Logged out successfully"}), 200
