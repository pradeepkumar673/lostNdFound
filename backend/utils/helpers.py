"""
backend/utils/helpers.py
Serialization, pagination, and shared utilities.

Changes v2:
  • Full type hints
  • serialize_doc handles nested lists of dicts correctly
  • paginate_query returns typed dict
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId


def serialize_doc(doc: dict | None) -> dict | None:
    """
    Recursively convert a MongoDB document to a JSON-serializable dict.

    Conversions:
        ObjectId  → str
        datetime  → ISO-8601 str
        dict      → recursively serialized
        list      → elements serialized individually

    Returns None if doc is None.
    """
    if doc is None:
        return None

    result: dict[str, Any] = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, dict):
            result[key] = serialize_doc(value)
        elif isinstance(value, list):
            result[key] = [
                serialize_doc(v)   if isinstance(v, dict)
                else str(v)        if isinstance(v, ObjectId)
                else v.isoformat() if isinstance(v, datetime)
                else v
                for v in value
            ]
        else:
            result[key] = value

    # Expose _id as both "_id" and "id" for frontend convenience
    if "_id" in result:
        result["id"] = result["_id"]

    return result


def paginate_query(
    collection,
    query: dict,
    page:  int = 1,
    limit: int = 12,
    sort:  list | None = None,
) -> dict[str, Any]:
    """
    Paginate a MongoDB collection query.

    Args:
        collection: PyMongo collection object.
        query:      Filter dict.
        page:       1-based page number.
        limit:      Items per page.
        sort:       List of (field, direction) tuples. Defaults to newest-first.

    Returns:
        Dict with ``items`` and ``pagination`` keys.
    """
    sort  = sort or [("created_at", -1)]
    skip  = (page - 1) * limit
    total = collection.count_documents(query)
    items = list(collection.find(query).sort(sort).skip(skip).limit(limit))

    return {
        "items": [serialize_doc(i) for i in items],
        "pagination": {
            "total":       total,
            "page":        page,
            "limit":       limit,
            "total_pages": max(1, (total + limit - 1) // limit),
            "has_next":    (page * limit) < total,
            "has_prev":    page > 1,
        },
    }
