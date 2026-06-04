"""
Backup, import, and export routines extracted from DatabaseService.
"""

from __future__ import annotations

import asyncio
import gzip
import importlib
import json
import logging
import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.database import get_postgres_db
from app.db.dual import (
    dual_write_hot_document,
    dual_write_hot_documents,
    log_postgres_only_write,
)
from app.db.ids import DocumentId
from app.core.migrate import HOT_COLLECTIONS

from .serialization import serialize_document

logger = logging.getLogger(__name__)


async def _dual_write_backup(document: Dict[str, Any]) -> None:
    result = await dual_write_hot_document("database_backups", document)
    if result.status == "failed":
        logger.warning("⚠️ 数据库备份 PostgreSQL 双写失败: %s", result.reason)


async def _dual_write_imported_documents(
    collection: str, documents: List[Dict[str, Any]]
) -> None:
    if not documents:
        return
    if collection not in HOT_COLLECTIONS:
        log_postgres_only_write(collection, "database_import_unsupported_collection")
        return

    result = await dual_write_hot_documents(collection, documents)
    if result.status == "failed":
        logger.warning(
            "⚠️ 导入集合 %s PostgreSQL 双写失败: %s", collection, result.reason
        )


async def _dual_write_import_overwrite_tombstones(
    collection: str, collection_obj
) -> None:
    if collection not in HOT_COLLECTIONS:
        return

    existing = await collection_obj.find({}).to_list(length=None)
    if not existing:
        return

    now = datetime.utcnow()
    tombstones = [{**doc, "deleted": True, "updated_at": now} for doc in existing]
    await _dual_write_imported_documents(collection, tombstones)


def _native_backup_available() -> bool:
    """Native PostgreSQL backup is no longer supported after the PostgreSQL cutover."""
    return False


async def create_backup_native(
    name: str,
    backup_dir: str,
    collections: Optional[List[str]] = None,
    user_id: str | None = None,
) -> Dict[str, Any]:
    """Create a PostgreSQL document-store backup using the portable JSON path."""
    return await create_backup(
        name, backup_dir, collections=collections, user_id=user_id
    )


async def create_backup(
    name: str,
    backup_dir: str,
    collections: Optional[List[str]] = None,
    user_id: str | None = None,
) -> Dict[str, Any]:
    """
    创建数据库备份（Python 实现，兼容性好但速度较慢）

    对于大数据量（>100MB），建议使用 create_backup_native() 方法
    """
    db = get_postgres_db()

    backup_id = str(DocumentId())
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"backup_{name}_{timestamp}.json.gz"
    backup_path = os.path.join(backup_dir, backup_filename)

    if not collections:
        collections = await db.list_collection_names()

    backup_data: Dict[str, Any] = {
        "backup_id": backup_id,
        "name": name,
        "created_at": datetime.utcnow().isoformat(),
        "created_by": user_id,
        "collections": collections,
        "data": {},
    }

    for collection_name in collections:
        collection = db[collection_name]
        documents: List[dict] = []
        async for doc in collection.find():
            documents.append(serialize_document(doc))
        backup_data["data"][collection_name] = documents

    os.makedirs(backup_dir, exist_ok=True)

    # 🔥 使用 asyncio.to_thread 将阻塞的文件 I/O 操作放到线程池执行
    def _write_backup():
        with gzip.open(backup_path, "wt", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        return os.path.getsize(backup_path)

    file_size = await asyncio.to_thread(_write_backup)

    backup_meta = {
        "_id": DocumentId(backup_id),
        "name": name,
        "filename": backup_filename,
        "file_path": backup_path,
        "size": file_size,
        "collections": collections,
        "created_at": datetime.utcnow(),
        "created_by": user_id,
    }

    await db.database_backups.insert_one(backup_meta)
    await _dual_write_backup(backup_meta)

    return {
        "id": backup_id,
        "name": name,
        "filename": backup_filename,
        "file_path": backup_path,
        "size": file_size,
        "collections": collections,
        "created_at": backup_meta["created_at"].isoformat(),
    }


async def list_backups() -> List[Dict[str, Any]]:
    db = get_postgres_db()
    backups: List[Dict[str, Any]] = []
    async for backup in db.database_backups.find().sort("created_at", -1):
        backups.append(
            {
                "id": str(backup["_id"]),
                "name": backup["name"],
                "filename": backup["filename"],
                "size": backup["size"],
                "collections": backup["collections"],
                "created_at": backup["created_at"].isoformat(),
                "created_by": backup.get("created_by"),
            }
        )
    return backups


async def delete_backup(backup_id: str) -> None:
    db = get_postgres_db()
    backup = await db.database_backups.find_one({"_id": DocumentId(backup_id)})
    if not backup:
        raise Exception("备份不存在")
    if os.path.exists(backup["file_path"]):
        # 🔥 使用 asyncio.to_thread 将阻塞的文件删除操作放到线程池执行
        backup_type = backup.get("backup_type", "python")
        if backup_type == "legacy_native_backup":
            # legacy_native_backup 备份是目录，需要递归删除
            await asyncio.to_thread(shutil.rmtree, backup["file_path"])
        else:
            # Python 备份是单个文件
            await asyncio.to_thread(os.remove, backup["file_path"])
    await db.database_backups.delete_one({"_id": DocumentId(backup_id)})
    await _dual_write_backup(
        {**backup, "deleted": True, "updated_at": datetime.utcnow()}
    )


def _convert_date_fields(doc: dict) -> dict:
    """
    转换文档中的日期字段（字符串 -> datetime）

    常见的日期字段：
    - created_at, updated_at, completed_at
    - started_at, finished_at
    - analysis_date (保持字符串格式，因为是日期而非时间戳)
    """
    parser = getattr(importlib.import_module("dateutil"), "parser")

    date_fields = [
        "created_at",
        "updated_at",
        "completed_at",
        "started_at",
        "finished_at",
        "deleted_at",
        "last_login",
        "last_modified",
        "timestamp",
    ]

    for field in date_fields:
        if field in doc and isinstance(doc[field], str):
            try:
                # 尝试解析日期字符串
                doc[field] = parser.parse(doc[field])
                logger.debug(f"✅ 转换日期字段 {field}: {doc[field]}")
            except Exception as e:
                logger.warning(f"⚠️ 无法解析日期字段 {field}: {doc[field]}, 错误: {e}")

    return doc


async def import_data(
    content: bytes,
    collection: str,
    *,
    format: str = "json",
    overwrite: bool = False,
    filename: str | None = None,
) -> Dict[str, Any]:
    """
    导入数据到数据库

    支持两种导入模式：
    1. 单集合模式：导入数据到指定集合
    2. 多集合模式：导入包含多个集合的导出文件（自动检测）
    """
    db = get_postgres_db()

    if format.lower() == "json":
        # 🔥 使用 asyncio.to_thread 将阻塞的 JSON 解析放到线程池执行
        def _parse_json():
            return json.loads(content.decode("utf-8"))

        data = await asyncio.to_thread(_parse_json)
    else:
        raise Exception(f"不支持的格式: {format}")

    # 检测是否为多集合导出格式
    logger.info(f"🔍 [导入检测] 数据类型: {type(data)}")

    # 🔥 新格式：包含 export_info 和 data 的字典
    if isinstance(data, dict) and "export_info" in data and "data" in data:
        logger.info("📦 检测到新版多集合导出文件（包含 export_info）")
        export_info = data.get("export_info", {})
        logger.info(
            f"📋 导出信息: 创建时间={export_info.get('created_at')}, 集合数={len(export_info.get('collections', []))}"
        )

        # 提取实际数据
        data = data["data"]
        logger.info(f"📦 包含 {len(data)} 个集合: {list(data.keys())}")

    # 🔥 旧格式：直接是集合名到文档列表的映射
    if isinstance(data, dict):
        logger.info(f"🔍 [导入检测] 字典包含 {len(data)} 个键")
        logger.info(f"🔍 [导入检测] 键列表: {list(data.keys())[:10]}")  # 只显示前10个

        # 检查每个键值对的类型
        for k, v in list(data.items())[:5]:  # 只检查前5个
            logger.info(
                f"🔍 [导入检测] 键 '{k}': 值类型={type(v)}, 是否为列表={isinstance(v, list)}"
            )
            if isinstance(v, list):
                logger.info(f"🔍 [导入检测] 键 '{k}': 列表长度={len(v)}")

    if isinstance(data, dict) and all(
        isinstance(k, str) and isinstance(v, list) for k, v in data.items()
    ):
        # 多集合模式
        logger.info(f"📦 确认为多集合导入模式，包含 {len(data)} 个集合")

        total_inserted = 0
        imported_collections = []

        for coll_name, documents in data.items():
            if not documents:  # 跳过空集合
                logger.info(f"⏭️ 跳过空集合: {coll_name}")
                continue

            collection_obj = db[coll_name]

            if overwrite:
                await _dual_write_import_overwrite_tombstones(coll_name, collection_obj)
                deleted_count = await collection_obj.delete_many({})
                logger.info(
                    f"🗑️ 清空集合 {coll_name}：删除 {deleted_count.deleted_count} 条文档"
                )

            # 处理 _id 字段和日期字段
            for doc in documents:
                # 转换 _id
                if "_id" in doc and isinstance(doc["_id"], str):
                    try:
                        doc["_id"] = DocumentId(doc["_id"])
                    except Exception:
                        del doc["_id"]

                # 🔥 转换日期字段（字符串 -> datetime）
                _convert_date_fields(doc)

            # 插入数据
            if documents:
                res = await collection_obj.insert_many(documents)
                inserted_count = len(res.inserted_ids)
                total_inserted += inserted_count
                imported_collections.append(coll_name)
                await _dual_write_imported_documents(coll_name, documents)
                logger.info(f"✅ 导入集合 {coll_name}：{inserted_count} 条文档")

        return {
            "mode": "multi_collection",
            "collections": imported_collections,
            "total_collections": len(imported_collections),
            "total_inserted": total_inserted,
            "filename": filename,
            "format": format,
            "overwrite": overwrite,
        }
    else:
        # 单集合模式（兼容旧版本）
        logger.info(f"📄 单集合导入模式，目标集合: {collection}")
        logger.info(f"🔍 [单集合模式] 数据类型: {type(data)}")

        if isinstance(data, dict):
            logger.info(f"🔍 [单集合模式] 字典包含 {len(data)} 个键")
            logger.info(f"🔍 [单集合模式] 键列表: {list(data.keys())[:10]}")

        collection_obj = db[collection]

        if not isinstance(data, list):
            logger.info("🔍 [单集合模式] 数据不是列表，转换为列表")
            data = [data]

        logger.info(f"🔍 [单集合模式] 准备插入 {len(data)} 条文档")

        if overwrite:
            await _dual_write_import_overwrite_tombstones(collection, collection_obj)
            deleted_count = await collection_obj.delete_many({})
            logger.info(
                f"🗑️ 清空集合 {collection}：删除 {deleted_count.deleted_count} 条文档"
            )

        for doc in data:
            # 转换 _id
            if "_id" in doc and isinstance(doc["_id"], str):
                try:
                    doc["_id"] = DocumentId(doc["_id"])
                except Exception:
                    del doc["_id"]

            # 🔥 转换日期字段（字符串 -> datetime）
            _convert_date_fields(doc)

        inserted_count = 0
        if data:
            res = await collection_obj.insert_many(data)
            inserted_count = len(res.inserted_ids)
            await _dual_write_imported_documents(collection, data)

        return {
            "mode": "single_collection",
            "collection": collection,
            "inserted_count": inserted_count,
            "filename": filename,
            "format": format,
            "overwrite": overwrite,
        }


def _sanitize_document(doc: Any) -> Any:
    """
    递归清空文档中的敏感字段

    敏感字段关键词：api_key, api_secret, secret, token, password,
                    client_secret, webhook_secret, private_key

    排除字段：max_tokens, timeout, retry_times 等配置字段（不是敏感信息）
    """
    SENSITIVE_KEYWORDS = [
        "api_key",
        "api_secret",
        "secret",
        "token",
        "password",
        "client_secret",
        "webhook_secret",
        "private_key",
    ]

    # 排除的字段（虽然包含敏感关键词，但不是敏感信息）
    EXCLUDED_FIELDS = [
        "max_tokens",  # LLM 配置：最大 token 数
        "timeout",  # 超时时间
        "retry_times",  # 重试次数
        "context_length",  # 上下文长度
    ]

    if isinstance(doc, dict):
        sanitized = {}
        for k, v in doc.items():
            # 检查是否在排除列表中
            if k.lower() in [f.lower() for f in EXCLUDED_FIELDS]:
                # 保留该字段
                if isinstance(v, (dict, list)):
                    sanitized[k] = _sanitize_document(v)
                else:
                    sanitized[k] = v
            # 检查字段名是否包含敏感关键词（忽略大小写）
            elif any(keyword in k.lower() for keyword in SENSITIVE_KEYWORDS):
                sanitized[k] = ""  # 清空敏感字段
            elif isinstance(v, (dict, list)):
                sanitized[k] = _sanitize_document(v)  # 递归处理
            else:
                sanitized[k] = v
        return sanitized
    elif isinstance(doc, list):
        return [_sanitize_document(item) for item in doc]
    else:
        return doc


async def export_data(
    collections: Optional[List[str]] = None,
    *,
    export_dir: str,
    format: str = "json",
    sanitize: bool = False,
) -> str:
    pd = importlib.import_module("pandas")

    # 🔥 使用异步数据库连接
    db = get_postgres_db()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    if not collections:
        # 🔥 异步调用 list_collection_names()
        collections = await db.list_collection_names()
        collections = [c for c in collections if not c.startswith("system.")]

    os.makedirs(export_dir, exist_ok=True)

    all_data: Dict[str, List[dict]] = {}
    for collection_name in collections:
        collection = db[collection_name]
        docs: List[dict] = []

        # users 集合在脱敏模式下只导出空数组（保留结构，不导出实际用户数据）
        if sanitize and collection_name == "users":
            all_data[collection_name] = []
            continue

        # 🔥 异步迭代查询结果
        async for doc in collection.find():
            docs.append(serialize_document(doc))
        all_data[collection_name] = docs

    # 如果启用脱敏，递归清空所有敏感字段
    if sanitize:
        all_data = _sanitize_document(all_data)

    if format.lower() == "json":
        filename = f"export_{timestamp}.json"
        file_path = os.path.join(export_dir, filename)
        export_data_dict = {
            "export_info": {
                "created_at": datetime.utcnow().isoformat(),
                "collections": collections,
                "format": format,
            },
            "data": all_data,
        }

        # 🔥 使用 asyncio.to_thread 将阻塞的文件 I/O 操作放到线程池执行
        def _write_json():
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data_dict, f, ensure_ascii=False, indent=2)

        await asyncio.to_thread(_write_json)
        return file_path

    if format.lower() == "csv":
        filename = f"export_{timestamp}.csv"
        file_path = os.path.join(export_dir, filename)
        rows: List[dict] = []
        for collection_name, documents in all_data.items():
            for doc in documents:
                row = {**doc}
                row["_collection"] = collection_name
                rows.append(row)

        # 🔥 使用 asyncio.to_thread 将阻塞的文件 I/O 操作放到线程池执行
        def _write_csv():
            if rows:
                pd.DataFrame(rows).to_csv(file_path, index=False, encoding="utf-8-sig")
            else:
                pd.DataFrame().to_csv(file_path, index=False, encoding="utf-8-sig")

        await asyncio.to_thread(_write_csv)
        return file_path

    if format.lower() in ["xlsx", "excel"]:
        filename = f"export_{timestamp}.xlsx"
        file_path = os.path.join(export_dir, filename)

        # 🔥 使用 asyncio.to_thread 将阻塞的文件 I/O 操作放到线程池执行
        def _write_excel():
            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                for collection_name, documents in all_data.items():
                    df = pd.DataFrame(documents) if documents else pd.DataFrame()
                    sheet = collection_name[:31]
                    df.to_excel(writer, sheet_name=sheet, index=False)

        await asyncio.to_thread(_write_excel)
        return file_path

    raise Exception(f"不支持的导出格式: {format}")
