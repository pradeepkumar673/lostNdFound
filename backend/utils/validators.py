"""
backend/utils/validators.py
Input validation helpers.

Changes v2:
  • Type hints throughout
  • validate_item_data checks description length from Config
  • validate_email rejects disposable / obviously fake domains (basic list)
  • validate_phone helper added
"""

from __future__ import annotations

import re

from config.settings import Config

# Basic set of obviously fake / disposable domains
_BLOCKED_DOMAINS = frozenset({
    "mailinator.com", "guerrillamail.com", "throwaway.email",
    "tempmail.com", "sharklasers.com", "yopmail.com",
})


def validate_email(email: str) -> bool:
    """
    Return True if ``email`` is structurally valid and not from a blocked domain.

    Args:
        email: Lowercased email string.
    """
    pattern = r"^[\w.+\-]+@[\w\-]+\.[a-z]{2,}$"
    if not re.match(pattern, email, re.IGNORECASE):
        return False
    domain = email.split("@")[-1].lower()
    return domain not in _BLOCKED_DOMAINS


def validate_password(password: str) -> tuple[bool, str]:
    """
    Validate password strength.

    Rules:
        - At least 8 characters
        - At least one letter
        - At least one digit

    Returns:
        (ok: bool, message: str)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r"[A-Za-z]", password):
        return False, "Password must contain at least one letter"
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number"
    return True, "OK"


def validate_item_data(data: dict) -> list[str]:
    """
    Validate item creation / update payload.

    Args:
        data: Parsed request body dict.

    Returns:
        List of error strings (empty → no errors).
    """
    errors: list[str] = []

    if data.get("type") not in ("lost", "found"):
        errors.append("type must be 'lost' or 'found'")

    title = data.get("title", "").strip()
    if not title:
        errors.append("title is required")
    elif len(title) > Config.ITEM_TITLE_MAX_LEN:
        errors.append(f"title must be under {Config.ITEM_TITLE_MAX_LEN} characters")

    description = data.get("description", "").strip()
    if not description:
        errors.append("description is required")
    elif len(description) < Config.ITEM_DESC_MIN_LEN:
        errors.append(f"description too short — add at least {Config.ITEM_DESC_MIN_LEN} characters")
    elif len(description) > Config.ITEM_DESC_MAX_LEN:
        errors.append(f"description too long — max {Config.ITEM_DESC_MAX_LEN} characters")

    return errors


def validate_phone(phone: str) -> bool:
    """
    Return True if ``phone`` looks like a valid 10-digit Indian mobile number.
    Accepts optional +91 prefix.
    """
    cleaned = re.sub(r"[\s\-()]", "", phone)
    cleaned = re.sub(r"^\+91", "", cleaned)
    return bool(re.match(r"^[6-9]\d{9}$", cleaned))
