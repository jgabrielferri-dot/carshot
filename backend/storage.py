import os
import uuid
from io import BytesIO

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
BUCKET_PHOTOS = "photos"
BUCKET_AVATARS = "avatars"

_client = None


def _get_client():
    global _client
    if _client is None:
        from supabase import create_client
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def upload_photo(file_bytes: bytes, ext: str = ".jpg") -> str:
    """Upload original photo, returns public URL."""
    filename = f"originals/{uuid.uuid4()}{ext}"
    client = _get_client()
    client.storage.from_(BUCKET_PHOTOS).upload(
        filename,
        file_bytes,
        {"content-type": "image/jpeg", "upsert": "true"},
    )
    return client.storage.from_(BUCKET_PHOTOS).get_public_url(filename)


def upload_watermarked(file_bytes: bytes, ext: str = ".jpg") -> str:
    """Upload watermarked photo, returns public URL."""
    filename = f"watermarked/{uuid.uuid4()}{ext}"
    client = _get_client()
    client.storage.from_(BUCKET_PHOTOS).upload(
        filename,
        file_bytes,
        {"content-type": "image/jpeg", "upsert": "true"},
    )
    return client.storage.from_(BUCKET_PHOTOS).get_public_url(filename)


def upload_avatar(file_bytes: bytes, ext: str = ".jpg") -> str:
    """Upload avatar, returns public URL."""
    filename = f"{uuid.uuid4()}{ext}"
    client = _get_client()
    client.storage.from_(BUCKET_AVATARS).upload(
        filename,
        file_bytes,
        {"content-type": "image/jpeg", "upsert": "true"},
    )
    return client.storage.from_(BUCKET_AVATARS).get_public_url(filename)


def delete_file(bucket: str, url: str):
    """Delete a file from Supabase Storage given its public URL."""
    try:
        # Extract path from URL: .../storage/v1/object/public/{bucket}/{path}
        marker = f"/object/public/{bucket}/"
        if marker in url:
            path = url.split(marker, 1)[1]
            _get_client().storage.from_(bucket).remove([path])
    except Exception:
        pass
