"""
用户自定义标签服务
"""
from __future__ import annotations
import importlib
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId

from app.core.config import settings
from app.core.database import get_mongo_db
from app.db.dual import dual_write_hot_document


class TagsService:
    def __init__(self) -> None:
        self.db = None
        self._indexes_ensured = False

    async def _get_db(self):
        if self.db is None:
            self.db = get_mongo_db()
        return self.db

    async def _dual_write_tag(self, document: Dict[str, Any]) -> None:
        result = await dual_write_hot_document("user_tags", document)
        if result.status == "failed":
            logging = importlib.import_module('logging')
            logging.getLogger(__name__).warning("⚠️ 标签 PostgreSQL 双写失败: %s", result.reason)

    async def ensure_indexes(self) -> None:
        if self._indexes_ensured:
            return
        db = await self._get_db()
        # 每个用户的标签名唯一
        await db.user_tags.create_index([("user_id", 1), ("name", 1)], unique=True, name="uniq_user_tag_name")
        await db.user_tags.create_index([("user_id", 1), ("sort_order", 1)], name="idx_user_tag_sort")
        self._indexes_ensured = True

    def _normalize_user_id(self, user_id: str) -> str:
        # 统一为字符串存储，便于兼容开源版(admin)与未来ObjectId
        return str(user_id)

    def _format_doc(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": str(doc.get("_id")),
            "name": doc.get("name"),
            "color": doc.get("color") or "#409EFF",
            "sort_order": doc.get("sort_order", 0),
            "created_at": (doc.get("created_at") or datetime.utcnow()).isoformat(),
            "updated_at": (doc.get("updated_at") or datetime.utcnow()).isoformat(),
        }

    async def list_tags(self, user_id: str) -> List[Dict[str, Any]]:
        if settings.POSTGRES_READ_ENABLED:
            postgres_tags = await self._list_tags_from_postgres(user_id)
            if postgres_tags:
                return postgres_tags

        db = await self._get_db()
        await self.ensure_indexes()
        cursor = db.user_tags.find({"user_id": self._normalize_user_id(user_id)}).sort([
            ("sort_order", 1), ("name", 1)
        ])
        docs = await cursor.to_list(length=None)
        return [self._format_doc(d) for d in docs]

    async def _list_tags_from_postgres(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            get_session_factory = getattr(importlib.import_module('app.db.session'), 'get_session_factory')
            list_user_tags = getattr(importlib.import_module('app.db.preference'), 'list_user_tags')

            async with get_session_factory()() as session:
                return await list_user_tags(session, self._normalize_user_id(user_id))
        except Exception:
            return []

    async def create_tag(self, user_id: str, name: str, color: Optional[str] = None, sort_order: int = 0) -> Dict[str, Any]:
        db = await self._get_db()
        await self.ensure_indexes()
        now = datetime.utcnow()
        doc = {
            "user_id": self._normalize_user_id(user_id),
            "name": name.strip(),
            "color": color or "#409EFF",
            "sort_order": int(sort_order or 0),
            "created_at": now,
            "updated_at": now,
        }
        result = await db.user_tags.insert_one(doc)
        doc["_id"] = result.inserted_id
        await self._dual_write_tag(doc)
        return self._format_doc(doc)

    async def update_tag(self, user_id: str, tag_id: str, *, name: Optional[str] = None, color: Optional[str] = None, sort_order: Optional[int] = None) -> bool:
        db = await self._get_db()
        await self.ensure_indexes()
        update: Dict[str, Any] = {"updated_at": datetime.utcnow()}
        if name is not None:
            update["name"] = name.strip()
        if color is not None:
            update["color"] = color
        if sort_order is not None:
            update["sort_order"] = int(sort_order)
        if len(update) == 1:  # 只有updated_at
            return True
        existing = await db.user_tags.find_one(
            {"_id": ObjectId(tag_id), "user_id": self._normalize_user_id(user_id)}
        )
        result = await db.user_tags.update_one(
            {"_id": ObjectId(tag_id), "user_id": self._normalize_user_id(user_id)},
            {"$set": update}
        )
        if result.matched_count > 0:
            await self._dual_write_tag({**(existing or {}), **update, "_id": ObjectId(tag_id), "user_id": self._normalize_user_id(user_id)})
        return result.matched_count > 0

    async def delete_tag(self, user_id: str, tag_id: str) -> bool:
        db = await self._get_db()
        await self.ensure_indexes()
        existing = await db.user_tags.find_one(
            {"_id": ObjectId(tag_id), "user_id": self._normalize_user_id(user_id)}
        )
        result = await db.user_tags.delete_one({"_id": ObjectId(tag_id), "user_id": self._normalize_user_id(user_id)})
        if result.deleted_count > 0:
            await self._dual_write_tag(
                {
                    **(existing or {}),
                    "_id": ObjectId(tag_id),
                    "user_id": self._normalize_user_id(user_id),
                    "deleted": True,
                    "updated_at": datetime.utcnow(),
                }
            )
        return result.deleted_count > 0


# 全局实例
tags_service = TagsService()
