"""Private object storage for evidence (design §31, §44): generated keys, no public bucket, short-lived signed URLs.

``LocalStorage`` keeps files under ``MEDIA_DIR`` and signs URLs that this API itself serves (``/api/v1/evidence/blob/<token>``): zero extra infrastructure for the
hackathon. ``S3Storage`` talks to any S3-compatible store (MinIO / Supabase Storage / Cloudflare R2 free tiers) through boto3 pre-signed URLs; it is optional and was
not exercised against a live server from the cloud session.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from backend.core.config import settings


class Storage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def size(self, key: str) -> int | None: ...
    def delete(self, key: str) -> None: ...
    def upload_url(self, key: str, mime_type: str, ttl: int) -> str: ...
    def download_url(self, key: str, ttl: int) -> str: ...


# ------------------------------------------------------------------------------------------------ signed tokens for LocalStorage
def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign_blob_token(key: str, method: str, ttl: int, mime: str | None = None, now: float | None = None) -> str:
    body = _b64(json.dumps({"k": key, "m": method, "e": int((now or time.time()) + ttl), "t": mime}, separators=(",", ":")).encode())
    sig = _b64(hmac.new(settings.SECRET_KEY.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_blob_token(token: str, method: str, now: float | None = None) -> dict | None:
    try:
        body, sig = token.split(".", 1)
        good = _b64(hmac.new(settings.SECRET_KEY.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return None
        data = json.loads(_unb64(body))
        if data["m"] != method or data["e"] < (now or time.time()):
            return None
        return data
    except Exception:
        return None


class LocalStorage:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or settings.MEDIA_DIR).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:                      # generated keys never contain "..", but never trust a key
            raise ValueError("invalid object key")
        return p

    def put(self, key: str, data: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, p)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def size(self, key: str) -> int | None:
        p = self._path(key)
        return p.stat().st_size if p.is_file() else None

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def upload_url(self, key: str, mime_type: str, ttl: int) -> str:
        return f"{settings.PUBLIC_BASE_URL.rstrip('/')}{settings.API_V1_STR}/evidence/blob/{sign_blob_token(key, 'PUT', ttl, mime_type)}"

    def download_url(self, key: str, ttl: int) -> str:
        return f"{settings.PUBLIC_BASE_URL.rstrip('/')}{settings.API_V1_STR}/evidence/blob/{sign_blob_token(key, 'GET', ttl)}"


class S3Storage:
    def __init__(self, client=None):
        if client is None:
            import boto3          # optional dependency: only needed for STORAGE_BACKEND=s3
            client = boto3.client("s3", endpoint_url=settings.S3_ENDPOINT_URL, aws_access_key_id=settings.S3_ACCESS_KEY, aws_secret_access_key=settings.S3_SECRET_KEY,
                                  region_name=settings.S3_REGION)
        self.client, self.bucket = client, settings.S3_BUCKET

    def put(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def size(self, key: str) -> int | None:
        try:
            return int(self.client.head_object(Bucket=self.bucket, Key=key)["ContentLength"])
        except Exception:
            return None

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def upload_url(self, key: str, mime_type: str, ttl: int) -> str:
        return self.client.generate_presigned_url("put_object", Params={"Bucket": self.bucket, "Key": key, "ContentType": mime_type}, ExpiresIn=ttl)

    def download_url(self, key: str, ttl: int) -> str:
        return self.client.generate_presigned_url("get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=ttl)


@lru_cache(maxsize=1)
def _default() -> Storage:
    return S3Storage() if settings.STORAGE_BACKEND == "s3" else LocalStorage()


_override: Storage | None = None


def get_storage() -> Storage:
    return _override or _default()


def set_storage(storage: Storage | None) -> None:
    """Tests / scripts: install another store (``None`` restores the configured one)."""
    global _override
    _override = storage
