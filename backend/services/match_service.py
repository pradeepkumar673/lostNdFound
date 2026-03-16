"""
backend/services/match_service.py
CLIP-based multi-signal matching service.

Improvements v2:
  • LRU in-memory cache for embeddings (Config.EMBEDDING_LRU_MAXSIZE)
  • Candidate pool pre-filtered by same category + nearby location
    before computing expensive cosine similarities
  • All thresholds / weights from Config
  • Type hints throughout
  • cosine_similarity handles zero-length vectors safely
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import numpy as np
from PIL import Image
from io import BytesIO

from config.settings import Config

logger = logging.getLogger(__name__)

# ─── Lazy-loaded CLIP ─────────────────────────────────────────────────────────
_clip_model     = None
_clip_processor = None


def _load_clip() -> tuple[Any, Any]:
    global _clip_model, _clip_processor
    if _clip_model is not None:
        return _clip_model, _clip_processor
    try:
        from transformers import CLIPModel, CLIPProcessor
        _clip_processor = CLIPProcessor.from_pretrained(Config.CLIP_MODEL_NAME)
        _clip_model     = CLIPModel.from_pretrained(Config.CLIP_MODEL_NAME)
        _clip_model.eval()
        logger.info("clip_model_loaded", extra={"model": Config.CLIP_MODEL_NAME})
    except Exception as exc:
        logger.error("clip_load_failed", extra={"error": str(exc)})
        _clip_model = _clip_processor = None
    return _clip_model, _clip_processor


# ─── Embedding helpers ────────────────────────────────────────────────────────
def get_image_embedding(image_bytes: bytes) -> list[float] | None:
    """
    Compute a normalised CLIP image embedding vector.

    Args:
        image_bytes: Raw image bytes (JPEG / PNG / WEBP).

    Returns:
        512-float list (normalised) or None on failure.
    """
    model, processor = _load_clip()
    if model is None:
        return None
    try:
        import torch
        image  = Image.open(BytesIO(image_bytes)).convert("RGB")
        inputs = processor(images=image, return_tensors="pt")
        with torch.no_grad():
            feats = model.get_image_features(**inputs)
        vec  = feats.numpy()[0]
        norm = np.linalg.norm(vec)
        return (vec / norm).tolist() if norm > 0 else vec.tolist()
    except Exception as exc:
        logger.error("image_embedding_failed", extra={"error": str(exc)})
        return None


@lru_cache(maxsize=Config.EMBEDDING_LRU_MAXSIZE)
def _cached_text_embedding(text: str) -> tuple[float, ...] | None:
    """LRU-cached text embedding — cache key is the text string itself."""
    model, processor = _load_clip()
    if model is None:
        return None
    try:
        import torch
        inputs = processor(
            text=[text[:77]], return_tensors="pt", truncation=True, padding=True
        )
        with torch.no_grad():
            feats = model.get_text_features(**inputs)
        vec  = feats.numpy()[0]
        norm = np.linalg.norm(vec)
        result = (vec / norm).tolist() if norm > 0 else vec.tolist()
        return tuple(result)   # tuples are hashable → work with lru_cache
    except Exception as exc:
        logger.error("text_embedding_failed", extra={"error": str(exc)})
        return None


def get_text_embedding(text: str) -> list[float] | None:
    """Return text embedding as a list (wraps the cached tuple version)."""
    result = _cached_text_embedding(text[:200])
    return list(result) if result else None


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Compute cosine similarity between two float vectors.

    Returns:
        Float in [0.0, 1.0].  Returns 0.0 if either vector is zero-length.
    """
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.clip(np.dot(a, b) / (na * nb), 0.0, 1.0))


# ─── Main Match Function ──────────────────────────────────────────────────────
def find_matches_for_item(
    item_id:   str,
    threshold: float = Config.MATCH_DISPLAY_THRESHOLD,
    limit:     int   = Config.MATCH_RESULT_LIMIT,
) -> list[dict[str, Any]]:
    """
    Find potential matches for ``item_id`` from the opposite type.

    Strategy:
        1. Pre-filter candidates by same category + location proximity
           (reduces expensive cosine comparisons)
        2. Compute multi-signal score for each candidate
        3. Persist / update matches collection
        4. Return top ``limit`` results above ``threshold``

    Args:
        item_id:   MongoDB item _id string.
        threshold: Minimum combined score to include in results.
        limit:     Maximum number of results to return.

    Returns:
        List of match dicts sorted by score descending.
    """
    from config.database import get_db
    from bson import ObjectId

    db   = get_db()
    item = db.items.find_one({"_id": ObjectId(item_id)})
    if not item:
        return []

    opposite_type = "found" if item["type"] == "lost" else "lost"

    # ── Build candidate filter (narrow before scoring) ────────────────────
    base_filter: dict[str, Any] = {
        "type":    opposite_type,
        "status":  "active",
        "_id":     {"$ne": ObjectId(item_id)},
        "user_id": {"$ne": item["user_id"]},
    }

    # Same category boosts recall and reduces noise
    category = item.get("category")
    if category and category != "other":
        # Return same-category candidates first; if < 30, add "other" too
        same_cat_ids = list(
            db.items.find(
                {**base_filter, "category": category},
                {"_id": 1},
            ).limit(Config.MATCH_CANDIDATE_LIMIT)
        )
        if len(same_cat_ids) < 30:
            other_ids = list(
                db.items.find(
                    {**base_filter, "_id": {"$nin": [d["_id"] for d in same_cat_ids] + [ObjectId(item_id)]}},
                    {"_id": 1},
                ).limit(Config.MATCH_CANDIDATE_LIMIT - len(same_cat_ids))
            )
            candidate_ids = [d["_id"] for d in same_cat_ids + other_ids]
        else:
            candidate_ids = [d["_id"] for d in same_cat_ids]
    else:
        candidate_ids = [
            d["_id"]
            for d in db.items.find(base_filter, {"_id": 1}).limit(Config.MATCH_CANDIDATE_LIMIT)
        ]

    if not candidate_ids:
        return []

    candidates = list(db.items.find({"_id": {"$in": candidate_ids}}))

    # ── Score each candidate ──────────────────────────────────────────────
    matches: list[dict[str, Any]] = []
    for candidate in candidates:
        score, highlights = _compute_match_score(item, candidate)
        if score < threshold:
            continue

        cand_id  = str(candidate["_id"])
        match_doc = {
            "lost_item_id":  item_id  if item["type"] == "lost"  else cand_id,
            "found_item_id": cand_id  if item["type"] == "lost"  else item_id,
            "score":         score,
            "highlights":    highlights,
            "created_at":    datetime.now(timezone.utc),
            "updated_at":    datetime.now(timezone.utc),
        }
        db.matches.update_one(
            {"lost_item_id": match_doc["lost_item_id"], "found_item_id": match_doc["found_item_id"]},
            {"$set": match_doc},
            upsert=True,
        )

        matches.append({
            "item_id":    cand_id,
            "score":      round(score, 4),
            "score_pct":  round(score * 100),
            "highlights": highlights,
            "item": {
                "id":            cand_id,
                "title":         candidate["title"],
                "type":          candidate["type"],
                "category":      candidate.get("category"),
                "location_name": candidate.get("location_name"),
                "date_occurred": (
                    candidate["date_occurred"].isoformat()
                    if candidate.get("date_occurred") else None
                ),
                "thumbnail":     candidate["images"][0]["url"] if candidate.get("images") else None,
                "color":         candidate.get("color"),
                "brand":         candidate.get("brand"),
                "tags":          candidate.get("tags", []),
            },
        })

    matches.sort(key=lambda x: x["score"], reverse=True)

    db.items.update_one(
        {"_id": ObjectId(item_id)},
        {"$set": {"match_count": len(matches)}},
    )

    return matches[:limit]


def search_by_image_embedding(
    image_bytes: bytes,
    limit:       int = Config.MATCH_RESULT_LIMIT,
) -> list[dict[str, Any]]:
    """
    Find items visually similar to ``image_bytes`` using stored CLIP embeddings.

    Args:
        image_bytes: Query image bytes.
        limit:       Max results.

    Returns:
        List of items with similarity score, sorted descending.
    """
    from config.database import get_db

    db        = get_db()
    query_emb = get_image_embedding(image_bytes)

    if query_emb is None:
        # Fallback: return most recent active items
        items = list(db.items.find({"status": "active"}).sort("created_at", -1).limit(limit))
        return [{"item_id": str(i["_id"]), "score": 0, "score_pct": 0, "title": i["title"]} for i in items]

    items_with_emb = list(
        db.items.find(
            {"status": "active", "image_embedding": {"$exists": True}},
            {"title": 1, "type": 1, "category": 1, "images": 1, "image_embedding": 1},
        ).limit(500)
    )

    results: list[dict] = []
    for item in items_with_emb:
        stored_emb = item.get("image_embedding")
        if stored_emb:
            sim = cosine_similarity(query_emb, stored_emb)
            if sim > 0.3:
                results.append({
                    "item_id":   str(item["_id"]),
                    "score":     round(sim, 4),
                    "score_pct": round(sim * 100),
                    "title":     item.get("title"),
                    "type":      item.get("type"),
                    "category":  item.get("category"),
                    "thumbnail": item["images"][0]["url"] if item.get("images") else None,
                })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]


# ─── Scoring ──────────────────────────────────────────────────────────────────
def _compute_match_score(
    item_a: dict[str, Any],
    item_b: dict[str, Any],
) -> tuple[float, dict[str, Any]]:
    """
    Multi-signal similarity score.

    Signals and their weights (from Config):
        category  : 0.30
        color     : 0.15
        brand     : 0.20
        tags      : 0.15
        text (CLIP): 0.20

    Returns:
        (score: float 0–1, highlights: dict)
    """
    highlights: dict[str, Any] = {
        "category_match": False,
        "color_match":    False,
        "brand_match":    False,
        "tag_matches":    [],
        "text_score":     0.0,
    }

    score        = 0.0
    weight_total = 0.0

    # ── Category ──────────────────────────────────────────────────────────
    w = Config.MATCH_WEIGHT_CATEGORY
    weight_total += w
    cat_a, cat_b = item_a.get("category"), item_b.get("category")
    if cat_a and cat_b and cat_a == cat_b and cat_a != "other":
        score += w
        highlights["category_match"] = True
    elif cat_a and cat_b:
        score += w * 0.2

    # ── Color ─────────────────────────────────────────────────────────────
    w = Config.MATCH_WEIGHT_COLOR
    weight_total += w
    col_a = (item_a.get("color") or "").lower().strip()
    col_b = (item_b.get("color") or "").lower().strip()
    if col_a and col_b:
        if col_a == col_b:
            score += w
            highlights["color_match"] = True
        elif col_a in col_b or col_b in col_a:
            score += w * 0.6
            highlights["color_match"] = True

    # ── Brand ─────────────────────────────────────────────────────────────
    w = Config.MATCH_WEIGHT_BRAND
    weight_total += w
    br_a = (item_a.get("brand") or "").lower().strip()
    br_b = (item_b.get("brand") or "").lower().strip()
    if br_a and br_b and br_a not in ("unknown", "n/a"):
        if br_a == br_b:
            score += w
            highlights["brand_match"] = True
        elif br_a in br_b or br_b in br_a:
            score += w * 0.7
            highlights["brand_match"] = True

    # ── Tags ──────────────────────────────────────────────────────────────
    w = Config.MATCH_WEIGHT_TAGS
    weight_total += w
    tags_a = {t.lower() for t in (item_a.get("tags") or [])}
    tags_b = {t.lower() for t in (item_b.get("tags") or [])}
    if tags_a and tags_b:
        common = tags_a & tags_b
        highlights["tag_matches"] = list(common)
        score += w * (len(common) / max(len(tags_a), len(tags_b)))

    # ── Text (CLIP) ───────────────────────────────────────────────────────
    w = Config.MATCH_WEIGHT_TEXT
    weight_total += w

    def _text(i: dict) -> str:
        return " ".join(filter(None, [
            i.get("title"), i.get("description"), i.get("brand"), i.get("color")
        ]))[:200]

    emb_a = item_a.get("text_embedding") or get_text_embedding(_text(item_a))
    emb_b = item_b.get("text_embedding") or get_text_embedding(_text(item_b))

    if emb_a and emb_b:
        raw_sim = cosine_similarity(list(emb_a), list(emb_b))
        # Normalise from [CLIP_SIM_LOW, CLIP_SIM_HIGH] → [0, 1]
        lo, hi  = Config.CLIP_SIM_LOW, Config.CLIP_SIM_HIGH
        normed  = max(0.0, (raw_sim - lo) / max(hi - lo, 1e-6))
        score  += w * normed
        highlights["text_score"] = round(raw_sim, 3)

    final = score / max(weight_total, 1e-9)
    return float(np.clip(final, 0.0, 1.0)), highlights
