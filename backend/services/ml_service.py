"""
CampusLostFound - ML Service
MobileNetV2 image categorization + pytesseract OCR
"""

import os
import re
import logging
import numpy as np
from io import BytesIO
from PIL import Image

logger = logging.getLogger(__name__)

# ─── Lazy-loaded model globals ────────────────────────────────────────────────
_model       = None
_class_names = None


def _load_model():
    """Load MobileNetV2 model and class names (lazy load on first use)"""
    global _model, _class_names

    if _model is not None:
        return _model, _class_names

    model_path   = os.getenv("MODEL_PATH",   "models/categorization_model.h5")
    classes_path = os.getenv("CLASSES_PATH", "models/classes.txt")

    try:
        import tensorflow as tf
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found at {model_path}")

        _model = tf.keras.models.load_model(model_path)
        logger.info(f"✅ Model loaded from {model_path}")

        if os.path.exists(classes_path):
            with open(classes_path, "r") as f:
                _class_names = [line.strip() for line in f if line.strip()]
        else:
            # Default fallback classes
            _class_names = [
                "phone", "wallet", "laptop", "bag", "id_card",
                "keys", "earphones", "umbrella", "water_bottle", "notebook", "other"
            ]
        logger.info(f"✅ Classes loaded: {_class_names}")

    except Exception as e:
        logger.error(f"❌ Model load failed: {e}")
        _model       = None
        _class_names = None

    return _model, _class_names


def categorize_image(image_bytes):
    """
    Classify an image into one of 11 item categories.

    Args:
        image_bytes: raw image bytes

    Returns:
        {
            category:         "phone",
            confidence:       0.92,
            confidence_pct:   92,
            top_predictions:  [{"category": "phone", "confidence": 0.92}, ...]
        }
    """
    model, class_names = _load_model()

    if model is None:
        return {
            "category":       "other",
            "confidence":     0.0,
            "confidence_pct": 0,
            "top_predictions": [],
            "error":          "Model not loaded",
        }

    try:
        # Preprocess image
        img = Image.open(BytesIO(image_bytes)).convert("RGB").resize((224, 224))
        arr = np.array(img, dtype=np.float32) / 255.0
        arr = np.expand_dims(arr, axis=0)

        # Predict
        predictions = model.predict(arr, verbose=0)[0]

        top_idx   = int(np.argmax(predictions))
        top_conf  = float(predictions[top_idx])
        top_class = class_names[top_idx] if top_idx < len(class_names) else "other"

        # Top 3 predictions
        top3_idx = np.argsort(predictions)[::-1][:3]
        top3 = [
            {
                "category":       class_names[i] if i < len(class_names) else "other",
                "confidence":     round(float(predictions[i]), 4),
                "confidence_pct": round(float(predictions[i]) * 100, 1),
            }
            for i in top3_idx
        ]

        return {
            "category":        top_class,
            "confidence":      round(top_conf, 4),
            "confidence_pct":  round(top_conf * 100, 1),
            "top_predictions": top3,
        }

    except Exception as e:
        logger.error(f"Categorization failed: {e}", exc_info=True)
        return {
            "category":       "other",
            "confidence":     0.0,
            "confidence_pct": 0,
            "top_predictions": [],
            "error":          str(e),
        }


def extract_ocr_text(image_bytes):
    """
    Extract text from image using pytesseract.
    Useful for ID cards, name tags, phone numbers.

    Returns:
        {
            raw_text:         "JOHN DOE\n21CS001\n9876543210",
            extracted_fields: {
                name:         "John Doe",
                roll_number:  "21CS001",
                phone:        "9876543210",
                email:        null,
            }
        }
    """
    try:
        import pytesseract
        import cv2

        # Load and preprocess image for better OCR
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        img_array = np.array(img)

        # Convert to grayscale
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

        # Adaptive thresholding for better text extraction
        processed = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        # Denoise
        processed = cv2.fastNlMeansDenoising(processed, None, 10, 7, 21)

        # Run OCR with multiple PSM modes for best results
        configs = [
            "--psm 3",   # Fully automatic page segmentation
            "--psm 6",   # Assume uniform block of text
            "--psm 11",  # Sparse text
        ]

        best_text = ""
        for config in configs:
            text = pytesseract.image_to_string(processed, config=config)
            if len(text.strip()) > len(best_text.strip()):
                best_text = text

        raw_text = best_text.strip()

        # Extract structured fields from raw OCR text
        fields = _extract_fields_from_text(raw_text)

        return {
            "raw_text":         raw_text,
            "extracted_fields": fields,
        }

    except ImportError:
        logger.warning("pytesseract not installed — OCR unavailable")
        return {
            "raw_text":         "",
            "extracted_fields": {},
            "error":            "OCR not available",
        }
    except Exception as e:
        logger.error(f"OCR failed: {e}", exc_info=True)
        return {
            "raw_text":         "",
            "extracted_fields": {},
            "error":            str(e),
        }


def _extract_fields_from_text(text):
    """
    Extract structured fields from raw OCR text.
    Looks for common patterns on student ID cards.
    """
    fields = {
        "name":        None,
        "roll_number": None,
        "phone":       None,
        "email":       None,
        "college":     None,
    }

    if not text:
        return fields

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # ── Phone number (10 digits, optional +91 prefix) ──────────────────
    phone_pattern = re.compile(r'(?:\+91[-\s]?)?[6-9]\d{9}')
    phone_match   = phone_pattern.search(text.replace(" ", "").replace("-", ""))
    if phone_match:
        fields["phone"] = phone_match.group().replace("+91", "").strip()

    # ── Email ───────────────────────────────────────────────────────────
    email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    email_match   = email_pattern.search(text)
    if email_match:
        fields["email"] = email_match.group()

    # ── Roll number (common patterns: 21CS001, 2021CSE001, CS21001) ────
    roll_patterns = [
        re.compile(r'\b\d{2}[A-Z]{2,4}\d{3,6}\b'),    # 21CS001
        re.compile(r'\b[A-Z]{2}\d{2}\d{3,6}\b'),       # CS21001
        re.compile(r'\b\d{4}[A-Z]{2,4}\d{3,6}\b'),     # 2021CSE001
        re.compile(r'\bRoll\s*No[.:\s]+([A-Z0-9]+)\b', re.I),
        re.compile(r'\bReg[.\s]+No[.:\s]+([A-Z0-9]+)\b', re.I),
    ]
    for pattern in roll_patterns:
        match = pattern.search(text)
        if match:
            fields["roll_number"] = match.group(1) if match.lastindex else match.group()
            break

    # ── Name (look for "Name:" prefix or all-caps line) ────────────────
    name_prefix = re.compile(r'Name[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', re.I)
    name_match  = name_prefix.search(text)
    if name_match:
        fields["name"] = name_match.group(1).strip()
    else:
        # Look for a line that looks like a name (2-3 words, Title Case)
        for line in lines:
            words = line.split()
            if (2 <= len(words) <= 4 and
                all(w[0].isupper() and w[1:].islower() for w in words if len(w) > 1) and
                not any(c.isdigit() for c in line)):
                fields["name"] = line
                break

    # ── College/University name ─────────────────────────────────────────
    college_keywords = ["university", "college", "institute", "school", "iit", "nit", "bits"]
    for line in lines:
        if any(kw in line.lower() for kw in college_keywords):
            fields["college"] = line
            break

    return fields
