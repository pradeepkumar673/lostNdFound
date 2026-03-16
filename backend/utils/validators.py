"""
CampusLostFound - Input Validators
"""
import re

def validate_email(email):
    pattern = r'^[\w.+\-]+@[\w\-]+\.[a-z]{2,}$'
    return bool(re.match(pattern, email, re.IGNORECASE))

def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r'[A-Za-z]', password):
        return False, "Password must contain at least one letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    return True, "OK"

def validate_item_data(data):
    errors = []
    if data.get("type") not in ("lost", "found"):
        errors.append("type must be 'lost' or 'found'")
    if not data.get("title", "").strip():
        errors.append("title is required")
    if len(data.get("title", "")) > 100:
        errors.append("title must be under 100 characters")
    if not data.get("description", "").strip():
        errors.append("description is required")
    if len(data.get("description", "")) < 10:
        errors.append("description too short — add more detail")
    return errors
