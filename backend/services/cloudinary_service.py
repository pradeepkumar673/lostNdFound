"""
CampusLostFound - Cloudinary Service
Image upload, delete, and URL transformation utilities.
"""

import os
import logging
from io import BytesIO

logger = logging.getLogger(__name__)

def _get_cloudinary():
    """Initialize and return Cloudinary module"""
    import cloudinary
    import cloudinary.uploader

    cloudinary.config(
        cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key    = os.getenv("CLOUDINARY_API_KEY"),
        api_secret = os.getenv("CLOUDINARY_API_SECRET"),
        secure     = True,
    )
    return cloudinary


def upload_images(files, folder="items"):
    """
    Upload a list of FileStorage objects to Cloudinary.

    Args:
        files  : list of werkzeug FileStorage objects
        folder : Cloudinary folder path

    Returns:
        list of { url, public_id, width, height, format }
    """
    cld = _get_cloudinary()
    import cloudinary.uploader
    results = []

    for file in files:
        try:
            file.seek(0)
            response = cloudinary.uploader.upload(
                file,
                folder         = f"campuslostfound/{folder}",
                resource_type  = "image",
                allowed_formats= ["jpg", "jpeg", "png", "webp"],
                transformation = [
                    {"width": 1200, "height": 1200, "crop": "limit", "quality": "auto:good"},
                ],
                eager = [
                    {"width": 400, "height": 400, "crop": "fill", "gravity": "auto",
                     "quality": "auto:eco", "fetch_format": "auto"},  # thumbnail
                ],
            )
            results.append({
                "url":        response["secure_url"],
                "public_id":  response["public_id"],
                "width":      response.get("width"),
                "height":     response.get("height"),
                "format":     response.get("format"),
                "thumbnail":  response["eager"][0]["secure_url"] if response.get("eager") else response["secure_url"],
            })
            logger.info(f"Uploaded: {response['public_id']}")
        except Exception as e:
            logger.error(f"Cloudinary upload failed: {e}")

    return results


def upload_image_bytes(image_bytes, folder="items", public_id=None):
    """Upload raw bytes to Cloudinary"""
    cld = _get_cloudinary()
    import cloudinary.uploader
    try:
        kwargs = {
            "folder":        f"campuslostfound/{folder}",
            "resource_type": "image",
        }
        if public_id:
            kwargs["public_id"] = public_id

        response = cloudinary.uploader.upload(image_bytes, **kwargs)
        return {
            "url":       response["secure_url"],
            "public_id": response["public_id"],
        }
    except Exception as e:
        logger.error(f"Cloudinary bytes upload failed: {e}")
        return None


def delete_image(public_id):
    """Delete an image from Cloudinary by public_id"""
    cld = _get_cloudinary()
    import cloudinary.uploader
    try:
        result = cloudinary.uploader.destroy(public_id)
        logger.info(f"Deleted Cloudinary image: {public_id} → {result.get('result')}")
        return result
    except Exception as e:
        logger.error(f"Cloudinary delete failed: {e}")
        return None


def get_thumbnail_url(url, width=300, height=300):
    """Transform a Cloudinary URL to get a thumbnail version"""
    if not url or "cloudinary.com" not in url:
        return url
    # Insert transformation before the version/public_id
    parts = url.split("/upload/")
    if len(parts) == 2:
        return f"{parts[0]}/upload/w_{width},h_{height},c_fill,g_auto,q_auto,f_auto/{parts[1]}"
    return url
