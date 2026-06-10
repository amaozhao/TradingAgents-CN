from __future__ import annotations

import base64
import hmac
import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.database import get_postgres_db


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _secret_key() -> bytes:
    seed = settings.JWT_SECRET or settings.CSRF_SECRET or "change-me-in-production"
    return hashlib.sha256(seed.encode("utf-8")).digest()


def _keystream(key: bytes, salt: bytes, length: int) -> bytes:
    chunks: list[bytes] = []
    counter = 0
    while sum(len(chunk) for chunk in chunks) < length:
        chunks.append(
            hmac.new(
                key, salt + counter.to_bytes(4, "big"), hashlib.sha256
            ).digest()
        )
        counter += 1
    return b"".join(chunks)[:length]


def _encrypt_secret(secret: str) -> str:
    key = _secret_key()
    salt = os.urandom(16)
    plaintext = secret.encode("utf-8")
    stream = _keystream(key, salt, len(plaintext))
    ciphertext = bytes(left ^ right for left, right in zip(plaintext, stream))
    mac = hmac.new(key, b"v1" + salt + ciphertext, hashlib.sha256).digest()
    payload = base64.urlsafe_b64encode(salt + ciphertext + mac).decode("ascii")
    return f"v1.{payload}"


def _decrypt_secret(encrypted_secret: str) -> str | None:
    try:
        version, encoded = encrypted_secret.split(".", 1)
        if version != "v1":
            return None
        payload = base64.urlsafe_b64decode(encoded.encode("ascii"))
        if len(payload) < 16 + 32:
            return None
        salt = payload[:16]
        mac = payload[-32:]
        ciphertext = payload[16:-32]
        key = _secret_key()
        expected_mac = hmac.new(key, b"v1" + salt + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(mac, expected_mac):
            return None
        stream = _keystream(key, salt, len(ciphertext))
        plaintext = bytes(left ^ right for left, right in zip(ciphertext, stream))
        return plaintext.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def _fingerprint(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:16]


class UserModelKeyService:
    collection_name = "user_model_keys"

    def _collection(self):
        return getattr(get_postgres_db(), self.collection_name)

    def _sanitize(self, document: dict[str, Any] | None) -> dict[str, Any] | None:
        if not document:
            return None
        return {
            "id": str(document.get("_id") or document.get("id")),
            "user_id": str(document.get("user_id")),
            "provider": document.get("provider"),
            "model": document.get("model"),
            "display_name": document.get("display_name"),
            "enabled": bool(document.get("enabled", True)),
            "api_key": "****",
            "key_fingerprint": document.get("key_fingerprint"),
            "created_at": document.get("created_at"),
            "updated_at": document.get("updated_at"),
        }

    async def create_key(
        self,
        *,
        user_id: str,
        provider: str,
        model: str,
        api_key: str,
        display_name: str | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        api_key = str(api_key or "").strip()
        if not api_key:
            raise ValueError("api_key is required")

        now = _now_utc()
        document = {
            "_id": str(uuid.uuid4()),
            "user_id": str(user_id),
            "provider": provider,
            "model": model,
            "display_name": display_name,
            "enabled": bool(enabled),
            "encrypted_api_key": _encrypt_secret(api_key),
            "key_fingerprint": _fingerprint(api_key),
            "created_at": now,
            "updated_at": now,
        }

        await self._collection().insert_one(document)
        sanitized = self._sanitize(document)
        if sanitized is None:
            raise RuntimeError("failed to sanitize created key")
        return sanitized

    async def list_keys(self, *, user_id: str) -> list[dict[str, Any]]:
        cursor = self._collection().find({"user_id": str(user_id)}).sort(
            "created_at", -1
        )
        documents: list[dict[str, Any]] = []
        async for document in cursor:
            sanitized = self._sanitize(document)
            if sanitized:
                documents.append(sanitized)
        return documents

    async def get_key(self, *, user_id: str, key_id: str) -> dict[str, Any] | None:
        document = await self._collection().find_one(
            {"_id": str(key_id), "user_id": str(user_id)}
        )
        return self._sanitize(document)

    async def update_key(
        self,
        *,
        user_id: str,
        key_id: str,
        api_key: str | None = None,
        display_name: str | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any] | None:
        query = {"_id": str(key_id), "user_id": str(user_id)}
        existing = await self._collection().find_one(query)
        if not existing:
            return None

        update: dict[str, Any] = {"updated_at": _now_utc()}
        if display_name is not None:
            update["display_name"] = display_name
        if enabled is not None:
            update["enabled"] = bool(enabled)
        if api_key is not None:
            api_key = str(api_key).strip()
            if not api_key:
                raise ValueError("api_key cannot be blank")
            update["encrypted_api_key"] = _encrypt_secret(api_key)
            update["key_fingerprint"] = _fingerprint(api_key)

        await self._collection().update_one(query, {"$set": update})
        return await self.get_key(user_id=user_id, key_id=key_id)

    async def delete_key(self, *, user_id: str, key_id: str) -> bool:
        result = await self._collection().delete_one(
            {"_id": str(key_id), "user_id": str(user_id)}
        )
        return bool(getattr(result, "deleted_count", 0))

    async def resolve_key_for_agent(
        self, *, user_id: str, provider: str, model: str
    ) -> str | None:
        document = await self._collection().find_one(
            {
                "user_id": str(user_id),
                "provider": provider,
                "model": model,
                "enabled": True,
            }
        )
        if not document:
            return None
        encrypted = document.get("encrypted_api_key")
        if not encrypted:
            return None
        return _decrypt_secret(str(encrypted))


user_model_key_service = UserModelKeyService()
