from __future__ import annotations

import json
from typing import Any, Dict, List

from app.db.ids import DocumentId


class ReportLookupService:
    @staticmethod
    def build_query(report_id: str) -> Dict[str, Any]:
        ors: List[Dict[str, Any]] = [
            {"analysis_id": report_id},
            {"task_id": report_id},
        ]
        try:
            ors.append({"_id": DocumentId(report_id)})
        except Exception:
            pass
        return {"$or": ors}

    @staticmethod
    def dedupe_documents(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for document in documents:
            key = (
                document.get("analysis_id")
                or document.get("task_id")
                or str(document.get("_id"))
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(document)
        return deduped


class ReportScopePolicy:
    @staticmethod
    def current_user_id(user: dict) -> str:
        return str(user.get("id") or "")

    @staticmethod
    def is_admin_user(user: dict) -> bool:
        return bool(user.get("is_admin")) or "admin" in set(user.get("roles") or [])

    @classmethod
    def private_report_query(cls, query: Dict[str, Any], user: dict) -> Dict[str, Any]:
        if cls.is_admin_user(user):
            return query
        user_id = cls.current_user_id(user)
        if not query:
            return {"user_id": user_id}
        return {"$and": [query, {"user_id": user_id}]}

    @classmethod
    def private_task_query(cls, query: Dict[str, Any], user: dict) -> Dict[str, Any]:
        if cls.is_admin_user(user):
            return query
        user_id = cls.current_user_id(user)
        owner_query = {"$or": [{"user_id": user_id}, {"user": user_id}]}
        if not query:
            return owner_query
        return {"$and": [query, owner_query]}


class ReportExportService:
    @staticmethod
    def json_content(document: Dict[str, Any]) -> bytes:
        return json.dumps(document, ensure_ascii=False, indent=2, default=str).encode("utf-8")

    @staticmethod
    def markdown_content(document: Dict[str, Any], *, stock_symbol: str, analysis_date: str) -> bytes:
        reports = document.get("reports", {})
        content_parts = [
            f"# {stock_symbol} 分析报告",
            f"**分析日期**: {analysis_date}",
            f"**分析师**: {', '.join(document.get('analysts', []))}",
            f"**研究深度**: {document.get('research_depth', 1)}",
            "",
        ]
        if document.get("summary"):
            content_parts.extend(["## 执行摘要", document["summary"], ""])
        for module_name, module_content in reports.items():
            if isinstance(module_content, str) and module_content.strip():
                content_parts.extend([f"## {module_name}", module_content, ""])
        return "\n".join(content_parts).encode("utf-8")
