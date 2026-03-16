"""
CampusLostFound - Utility Helpers
Serialization, pagination, and common helpers.
"""

from bson import ObjectId
from datetime import datetime
import re


def serialize_doc(doc):
    """
    Convert a MongoDB document to a JSON-serializable dict.
    Converts ObjectId → string, datetime → ISO string.
    """
    if doc is None:
        return None

    result = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, dict):
            result[key] = serialize_doc(value)
        elif isinstance(value, list):
            result[key] = [
                serialize_doc(v) if isinstance(v, dict)
                else str(v)      if isinstance(v, ObjectId)
                else v.isoformat() if isinstance(v, datetime)
                else v
                for v in value
            ]
        else:
            result[key] = value

    # Always expose _id as both "_id" and "id"
    if "_id" in result:
        result["id"] = result["_id"]

    return result


def paginate_query(collection, query, page=1, limit=12, sort=None):
    """
    Helper to paginate a MongoDB query.

    Returns:
        { items: [...], pagination: { total, page, limit, total_pages, has_next, has_prev } }
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
        }
    }
