"""
通知服务：持久化 + 列表 + 已读 + SSE 发布
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId

from app.core.coredatabase import get_mongo_db, get_redis_client
from app.db.dualwrite import dual_write_hot_document, dual_write_hot_documents
from app.models.notification import (
    NotificationCreate, NotificationOut, NotificationList
)
from app.utils.timezone import now_tz

logger = logging.getLogger("webapi.notifications")


class NotificationsService:
    def __init__(self):
        self.collection = "notifications"
        self.channel_prefix = "notifications:"
        self.retain_days = 90
        self.max_per_user = 1000

    async def _ensure_indexes(self):
        try:
            db = get_mongo_db()
            await db[self.collection].create_index([("user_id", 1), ("created_at", -1)])
            await db[self.collection].create_index([("user_id", 1), ("status", 1)])
        except Exception as e:
            logger.warning(f"创建索引失败(忽略): {e}")

    async def create_and_publish(self, payload: NotificationCreate) -> str:
        await self._ensure_indexes()
        db = get_mongo_db()
        doc = {
            "user_id": payload.user_id,
            "type": payload.type,
            "title": payload.title,
            "content": payload.content,
            "link": payload.link,
            "source": payload.source,
            "severity": payload.severity or "info",
            "status": "unread",
            "created_at": now_tz(),
            "metadata": payload.metadata or {},
        }
        res = await db[self.collection].insert_one(doc)
        doc["_id"] = res.inserted_id
        await self._dual_write_notification(doc)
        doc_id = str(res.inserted_id)

        payload_to_publish = {
            "id": doc_id,
            "type": doc["type"],
            "title": doc["title"],
            "content": doc.get("content"),
            "link": doc.get("link"),
            "source": doc.get("source"),
            "status": doc.get("status", "unread"),
            "created_at": doc["created_at"].isoformat(),
        }

        # 🔥 使用 WebSocket 发送通知
        try:
            from app.routers.websocketnotifications import send_notification_via_websocket
            await send_notification_via_websocket(payload.user_id, payload_to_publish)
            logger.debug(f"✅ [WS] 通知已通过 WebSocket 发送: user={payload.user_id}")
        except Exception as e:
            logger.warning(f"⚠️ [WS] WebSocket 发送失败: {e}")

        # 清理策略：保留最近N天/最多M条
        try:
            old_docs = await db[self.collection].find({
                "user_id": payload.user_id,
                "created_at": {"$lt": now_tz() - timedelta(days=self.retain_days)}
            }).to_list(length=None)
            delete_result = await db[self.collection].delete_many({
                "user_id": payload.user_id,
                "created_at": {"$lt": now_tz() - timedelta(days=self.retain_days)}
            })
            if delete_result.deleted_count:
                await self._dual_write_notification_tombstones(old_docs)

            # 超过配额按时间删旧
            count = await db[self.collection].count_documents({"user_id": payload.user_id})
            if count > self.max_per_user:
                skip = count - self.max_per_user
                docs_to_delete = await db[self.collection].find({"user_id": payload.user_id}).sort("created_at", 1).limit(skip).to_list(length=None)
                ids = [d["_id"] for d in docs_to_delete]
                if ids:
                    delete_result = await db[self.collection].delete_many({"_id": {"$in": ids}})
                    if delete_result.deleted_count:
                        await self._dual_write_notification_tombstones(docs_to_delete)
        except Exception as e:
            logger.warning(f"通知清理失败(忽略): {e}")

        return doc_id

    async def unread_count(self, user_id: str) -> int:
        db = get_mongo_db()
        return await db[self.collection].count_documents({"user_id": user_id, "status": "unread"})

    async def list(self, user_id: str, *, status: Optional[str] = None, ntype: Optional[str] = None, page: int = 1, page_size: int = 20) -> NotificationList:
        db = get_mongo_db()
        q: Dict[str, Any] = {"user_id": user_id}
        if status in ("read", "unread"):
            q["status"] = status
        if ntype in ("analysis", "alert", "system"):
            q["type"] = ntype
        total = await db[self.collection].count_documents(q)
        cursor = db[self.collection].find(q).sort("created_at", -1).skip((page-1)*page_size).limit(page_size)
        items: List[NotificationOut] = []
        async for d in cursor:
            items.append(NotificationOut(
                id=str(d.get("_id")),
                type=d.get("type"),
                title=d.get("title"),
                content=d.get("content"),
                link=d.get("link"),
                source=d.get("source"),
                status=d.get("status", "unread"),
                created_at=d.get("created_at") or now_tz(),
            ))
        return NotificationList(items=items, total=total, page=page, page_size=page_size)

    async def mark_read(self, user_id: str, notif_id: str) -> bool:
        db = get_mongo_db()
        try:
            oid = ObjectId(notif_id)
        except Exception:
            return False
        res = await db[self.collection].update_one({"_id": oid, "user_id": user_id}, {"$set": {"status": "read"}})
        if res.modified_count:
            await self._dual_write_notification({"_id": oid, "user_id": user_id, "status": "read"})
        return res.modified_count > 0

    async def mark_all_read(self, user_id: str) -> int:
        db = get_mongo_db()
        unread_docs = await db[self.collection].find({"user_id": user_id, "status": "unread"}).to_list(length=None)
        res = await db[self.collection].update_many({"user_id": user_id, "status": "unread"}, {"$set": {"status": "read"}})
        if res.modified_count:
            await dual_write_hot_documents(
                self.collection,
                [{**doc, "status": "read"} for doc in unread_docs],
            )
        return res.modified_count

    async def _dual_write_notification(self, document: Dict[str, Any]) -> None:
        result = await dual_write_hot_document(self.collection, document)
        if result.status == "failed":
            logger.warning("⚠️ 通知 PostgreSQL 双写失败: %s", result.reason)

    async def _dual_write_notification_tombstones(self, documents: List[Dict[str, Any]]) -> None:
        if not documents:
            return
        result = await dual_write_hot_documents(
            self.collection,
            [{**document, "deleted": True, "updated_at": now_tz()} for document in documents],
        )
        if result.status == "failed":
            logger.warning("⚠️ 通知 PostgreSQL tombstone 双写失败: %s", result.reason)


_notifications_service: Optional[NotificationsService] = None


def get_notifications_service() -> NotificationsService:
    global _notifications_service
    if _notifications_service is None:
        _notifications_service = NotificationsService()
    return _notifications_service
