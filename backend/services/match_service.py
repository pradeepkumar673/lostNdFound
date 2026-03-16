"""
CampusLostFound - Match Service
CLIP-based image + text embeddings for finding similar items.
Cosine similarity between lost and found items.
"""

import os
import logging
import numpy as np
from io import BytesIO
from datetime import datetime
from PIL import Image

logger = logging.getLogger(__name__)

# ─── Lazy-loaded CLIP model ───────────────────────────────────────────────────
_clip_model     = None
_clip_processor = None


def _load_clip():
    """Load CLIP model lazily"""
    global _clip_model, _clip_processor
    if _clip_model is not None:
        return _clip_model, _clip_processor
    try:
        from transformers import CLIPModel, CLIPProcessor
        model_name      = "openai/clip-vit-base-patch32"
        _clip_processor = CLIPProcessor.from_pretrained(model_name)
        _clip_model     = CLIPModel.from_pretrained(model_name)
        _clip_model.eval()
        logger.info("✅ CLIP model loaded")
    except Exception as e:
        logger.error(f"❌ CLIP load failed: {e}")
        _clip_model     = None
        _clip_processor = None
    return _clip_model, _clip_processor


def get_image_embedding(image_bytes):
    """
    Get CLIP embedding vector for an image.

    Args:
        image_bytes: raw image bytes

    Returns:
        numpy array of shape (512,) or None on failure
    """
    model, processor = _load_clip()
    if model is None:
        return None
    try:
        import torch
        image  = Image.open(BytesIO(image_bytes)).convert("RGB")
        inputs = processor(images=image, return_tensors="pt")
        with torch.no_grad():
            features = model.get_image_features(**inputs)
        embedding = features.numpy()[0]
        # Normalize to unit vector
        norm = np.linalg.norm(embedding)
        return (embedding / norm).tolist() if norm > 0 else embedding.tolist()
    except Exception as e:
        logger.error(f"Image embedding failed: {e}")
        return None


def get_text_embedding(text):
    """
    Get CLIP text embedding for an item description.

    Args:
        text: string description/title

    Returns:
        numpy array of shape (512,) or None
    """
    model, processor = _load_clip()
    if model is None:
        return None
    try:
        import torch
        inputs = processor(text=[text[:77]], return_tensors="pt", truncation=True, padding=True)
        with torch.no_grad():
            features = model.get_text_features(**inputs)
        embedding = features.numpy()[0]
        norm      = np.linalg.norm(embedding)
        return (embedding / norm).tolist() if norm > 0 else embedding.tolist()
    except Exception as e:
        logger.error(f"Text embedding failed: {e}")
        return None


def cosine_similarity(vec_a, vec_b):
    """Compute cosine similarity between two vectors (0.0 to 1.0)"""
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def find_matches_for_item(item_id, threshold=0.45, limit=10):
    """
    Find potential matches for a given item from the opposite type.
    e.g. if item is 'lost', search among 'found' items.

    Args:
        item_id   : MongoDB item ID string
        threshold : minimum similarity score (0–1) to include in results
        limit     : max matches to return

    Returns:
        list of match dicts with score and highlights
    """
    from config.database import get_db
    from bson import ObjectId

    db   = get_db()
    item = db.items.find_one({"_id": ObjectId(item_id)})
    if not item:
        return []

    # Search among opposite type
    opposite_type = "found" if item["type"] == "lost" else "lost"

    # Get all active items of opposite type
    candidates = list(db.items.find({
        "type":    opposite_type,
        "status":  "active",
        "_id":     {"$ne": ObjectId(item_id)},
        "user_id": {"$ne": item["user_id"]},   # Don't match own items
    }).limit(200))

    if not candidates:
        return []

    matches = []

    for candidate in candidates:
        score, highlights = _compute_match_score(item, candidate)

        if score >= threshold:
            # Store/update match in DB
            match_doc = {
                "lost_item_id":  item_id  if item["type"] == "lost"  else str(candidate["_id"]),
                "found_item_id": str(candidate["_id"]) if item["type"] == "lost" else item_id,
                "score":         score,
                "highlights":    highlights,
                "created_at":    datetime.utcnow(),
                "updated_at":    datetime.utcnow(),
            }
            db.matches.update_one(
                {
                    "lost_item_id":  match_doc["lost_item_id"],
                    "found_item_id": match_doc["found_item_id"],
                },
                {"$set": match_doc},
                upsert=True
            )

            matches.append({
                "item_id":   str(candidate["_id"]),
                "score":     round(score, 4),
                "score_pct": round(score * 100),
                "highlights": highlights,
                "item": {
                    "id":          str(candidate["_id"]),
                    "title":       candidate["title"],
                    "type":        candidate["type"],
                    "category":    candidate["category"],
                    "location_name": candidate.get("location_name"),
                    "date_occurred": candidate["date_occurred"].isoformat() if candidate.get("date_occurred") else None,
                    "thumbnail":   candidate["images"][0]["url"] if candidate.get("images") else None,
                    "color":       candidate.get("color"),
                    "brand":       candidate.get("brand"),
                    "tags":        candidate.get("tags", []),
                }
            })

    # Sort by score descending
    matches.sort(key=lambda x: x["score"], reverse=True)

    # Update match count on item
    db.items.update_one(
        {"_id": ObjectId(item_id)},
        {"$set": {"match_count": len(matches)}}
    )

    return matches[:limit]


def _compute_match_score(item_a, item_b):
    """
    Compute similarity score between two items.
    Combines multiple signals:
    - Category match (hard filter)
    - Color similarity
    - Brand match
    - Tag overlap
    - Text embedding similarity
    - Image embedding similarity (if available)

    Returns:
        (score: float 0–1, highlights: dict)
    """
    highlights = {
        "category_match": False,
        "color_match":    False,
        "brand_match":    False,
        "tag_matches":    [],
        "text_score":     0.0,
        "image_score":    0.0,
    }

    score = 0.0
    weight_total = 0.0

    # ── Category match (weight: 0.3) ──────────────────────────────────
    w = 0.3
    weight_total += w
    if item_a.get("category") == item_b.get("category") and item_a.get("category") != "other":
        score += w
        highlights["category_match"] = True
    elif item_a.get("category") and item_b.get("category"):
        # Partial score for same general type
        score += w * 0.2

    # ── Color match (weight: 0.15) ─────────────────────────────────────
    w = 0.15
    weight_total += w
    color_a = (item_a.get("color") or "").lower().strip()
    color_b = (item_b.get("color") or "").lower().strip()
    if color_a and color_b:
        if color_a == color_b:
            score += w
            highlights["color_match"] = True
        elif color_a in color_b or color_b in color_a:
            score += w * 0.6
            highlights["color_match"] = True

    # ── Brand match (weight: 0.2) ──────────────────────────────────────
    w = 0.2
    weight_total += w
    brand_a = (item_a.get("brand") or "").lower().strip()
    brand_b = (item_b.get("brand") or "").lower().strip()
    if brand_a and brand_b and brand_a != "unknown":
        if brand_a == brand_b:
            score += w
            highlights["brand_match"] = True
        elif brand_a in brand_b or brand_b in brand_a:
            score += w * 0.7
            highlights["brand_match"] = True

    # ── Tag overlap (weight: 0.15) ─────────────────────────────────────
    w = 0.15
    weight_total += w
    tags_a = set(t.lower() for t in (item_a.get("tags") or []))
    tags_b = set(t.lower() for t in (item_b.get("tags") or []))
    if tags_a and tags_b:
        common_tags = tags_a & tags_b
        highlights["tag_matches"] = list(common_tags)
        overlap = len(common_tags) / max(len(tags_a), len(tags_b))
        score  += w * overlap

    # ── Text similarity via CLIP (weight: 0.2) ─────────────────────────
    w = 0.2
    weight_total += w
    text_a = f"{item_a.get('title','')} {item_a.get('description','')} {item_a.get('brand','')} {item_a.get('color','')}"
    text_b = f"{item_b.get('title','')} {item_b.get('description','')} {item_b.get('brand','')} {item_b.get('color','')}"

    emb_a = item_a.get("text_embedding")
    emb_b = item_b.get("text_embedding")

    if not emb_a:
        emb_a = get_text_embedding(text_a[:200])
    if not emb_b:
        emb_b = get_text_embedding(text_b[:200])

    if emb_a and emb_b:
        text_sim = cosine_similarity(emb_a, emb_b)
        # Normalize: CLIP text sims range ~0.7–1.0, map to 0–1
        text_sim_normalized = max(0.0, (text_sim - 0.7) / 0.3)
        score += w * text_sim_normalized
        highlights["text_score"] = round(text_sim, 3)

    # Normalize score by total weight
    final_score = score / weight_total if weight_total > 0 else 0.0
    return min(1.0, max(0.0, final_score)), highlights


def search_by_image_embedding(image_bytes, limit=10):
    """
    Search all active items by image similarity using CLIP.

    Args:
        image_bytes: query image bytes
        limit      : max results

    Returns:
        list of items with similarity scores
    """
    from config.database import get_db

    db        = get_db()
    query_emb = get_image_embedding(image_bytes)

    if query_emb is None:
        # Fallback: return recent items
        items = list(db.items.find({"status": "active"}).sort("created_at", -1).limit(limit))
        return [{"item_id": str(i["_id"]), "score": 0, "score_pct": 0} for i in items]

    # Get items that have stored embeddings
    items_with_emb = list(db.items.find(
        {"status": "active", "image_embedding": {"$exists": True}},
    ).limit(500))

    results = []
    for item in items_with_emb:
        item_emb = item.get("image_embedding")
        if item_emb:
            sim = cosine_similarity(query_emb, item_emb)
            if sim > 0.3:
                results.append({
                    "item_id":   str(item["_id"]),
                    "score":     round(sim, 4),
                    "score_pct": round(sim * 100),
                    "title":     item["title"],
                    "type":      item["type"],
                    "category":  item["category"],
                    "thumbnail": item["images"][0]["url"] if item.get("images") else None,
                })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]
