from __future__ import annotations

import ipaddress
import html
import os
import re
import socket
from typing import Any
from urllib.parse import quote_plus, urlparse

import httpx

from app.services.research_agent.artifacts import ResearchArtifactService

from ..context import ToolExecutionContext
from ..permissions import DOCUMENT_READ, WEB_READ, WEB_SEARCH
from ..registry import ResearchTool


MAX_WEB_BYTES = 200_000
MAX_SEARCH_RESULTS = 5
LOCAL_WEB_PROXY_CANDIDATES = ("http://127.0.0.1:7897", "http://127.0.0.1:7899")


def _network_error_result(tool: str, error: Exception) -> dict[str, Any]:
    error_name = error.__class__.__name__
    if isinstance(error, httpx.ConnectTimeout):
        message = "外部网络连接超时，未能建立连接"
    elif isinstance(error, httpx.ReadTimeout):
        message = "外部网络读取超时，对方服务响应过慢"
    elif isinstance(error, httpx.TimeoutException):
        message = "外部网络请求超时"
    elif isinstance(error, httpx.HTTPStatusError):
        message = f"外部服务返回 HTTP {error.response.status_code}"
    elif isinstance(error, httpx.RequestError):
        message = f"外部网络请求失败：{error_name}"
    else:
        message = str(error).strip() or error_name
    return {
        "tool": tool,
        "status": "degraded",
        "error_type": error_name,
        "error": message,
    }


def _artifact_content(artifact: dict[str, Any]) -> str:
    payload = artifact.get("payload") if isinstance(artifact.get("payload"), dict) else {}
    for key in ("text", "content", "preview"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _port_open(proxy_url: str) -> bool:
    parsed = urlparse(proxy_url)
    if not parsed.hostname or not parsed.port:
        return False
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=0.2):
            return True
    except OSError:
        return False


def _web_proxy_candidates() -> list[str | None]:
    candidates: list[str | None] = [None]
    for key in ("AGENT_WEB_PROXY", "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "all_proxy"):
        value = os.environ.get(key)
        if value and value not in candidates:
            candidates.append(value)
    for value in LOCAL_WEB_PROXY_CANDIDATES:
        if value not in candidates and _port_open(value):
            candidates.append(value)
    return candidates


async def _web_get(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> httpx.Response:
    last_error: httpx.HTTPError | None = None
    for proxy in _web_proxy_candidates():
        try:
            kwargs: dict[str, Any] = {
                "timeout": timeout,
                "follow_redirects": True,
                "trust_env": bool(proxy is None),
            }
            if proxy:
                kwargs["proxies"] = proxy
            async with httpx.AsyncClient(**kwargs) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response
        except httpx.HTTPError as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    raise httpx.ConnectError("No available web transport")


async def _read_owned_artifact(
    context: ToolExecutionContext, payload: dict[str, Any], *, tool_name: str
) -> dict[str, Any]:
    inline_text = str(payload.get("text") or payload.get("content") or "").strip()
    if inline_text:
        artifact = None
        if context.session_id:
            artifact = await ResearchArtifactService().create_artifact(
                session_id=str(context.session_id),
                user_id=context.principal.user_id,
                artifact_type="document",
                payload={
                    "filename": str(payload.get("filename") or "inline-document.md"),
                    "text": inline_text,
                    "source": "inline",
                },
            )
        return {
            "tool": tool_name,
            "status": "completed",
            "artifact_id": artifact.get("artifact_id") if artifact else None,
            "artifact_type": "document",
            "filename": str(payload.get("filename") or "inline-document.md"),
            "content": inline_text,
            "preview": inline_text[:2000],
        }
    artifact_id = str(payload.get("artifact_id") or payload.get("file_id") or "").strip()
    if not artifact_id:
        return {
            "tool": tool_name,
            "status": "config_required",
            "accepted": False,
            "reason": "artifact_id, file_id, text, or content is required.",
        }
    artifact = await ResearchArtifactService().get_artifact(
        artifact_id, context.principal.user_id
    )
    if not artifact:
        return {"tool": tool_name, "status": "not_found", "artifact_id": artifact_id}
    content = _artifact_content(artifact)
    return {
        "tool": tool_name,
        "status": "completed",
        "artifact_id": artifact_id,
        "artifact_type": artifact.get("artifact_type"),
        "filename": (artifact.get("payload") or {}).get("filename"),
        "content": content,
        "preview": content[:2000],
    }


def _validate_public_url(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Only http/https URLs are allowed")
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        raise ValueError("Local/private URLs are not allowed")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip and (ip.is_private or ip.is_loopback or ip.is_link_local):
        raise ValueError("Local/private URLs are not allowed")
    return raw_url


async def _read_url(context: ToolExecutionContext, payload: dict[str, Any]) -> dict[str, Any]:
    raw_url = str(payload.get("url") or "").strip()
    url = _validate_public_url(raw_url)
    try:
        response = await _web_get(url, timeout=10.0)
        content_type = response.headers.get("content-type", "")
        raw = response.content[:MAX_WEB_BYTES]
    except httpx.HTTPError as exc:
        return {
            **_network_error_result("read_url", exc),
            "url": url,
            "content": "",
            "preview": "",
            "instruction": "该网页读取失败，继续使用已有行情、分析工具或让用户提供可访问链接。",
        }
    text = raw.decode(response.encoding or "utf-8", errors="replace")
    artifact = None
    if context.session_id:
        artifact = await ResearchArtifactService().create_artifact(
            session_id=str(context.session_id),
            user_id=context.principal.user_id,
            artifact_type="web_page",
            payload={
                "url": url,
                "content_type": content_type,
                "text": text,
                "truncated": len(response.content) > MAX_WEB_BYTES,
            },
        )
    return {
        "tool": "read_url",
        "status": "completed",
        "url": url,
        "content_type": content_type,
        "content": text,
        "preview": text[:2000],
        "artifact_id": artifact.get("artifact_id") if artifact else None,
    }


def _extract_search_results(markup: str, limit: int) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    blocks = re.findall(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>(.*?)(?=<a[^>]+class="result__a"|$)',
        markup,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for raw_url, raw_title, raw_tail in blocks:
        title = re.sub(r"<[^>]+>", "", raw_title)
        snippet_match = re.search(
            r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
            raw_tail,
            flags=re.IGNORECASE | re.DOTALL,
        )
        snippet = re.sub(r"<[^>]+>", "", snippet_match.group(1)) if snippet_match else ""
        url = html.unescape(raw_url)
        if url.startswith("//duckduckgo.com/l/?"):
            match = re.search(r"[?&]uddg=([^&]+)", url)
            if match:
                from urllib.parse import unquote

                url = unquote(match.group(1))
        results.append(
            {
                "title": html.unescape(title).strip(),
                "url": url,
                "snippet": html.unescape(snippet).strip(),
            }
        )
        if len(results) >= limit:
            break
    if results:
        return results

    for raw_url, raw_title in re.findall(
        r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>',
        markup,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        title = re.sub(r"<[^>]+>", "", raw_title)
        cleaned_title = html.unescape(title).strip()
        if not cleaned_title:
            continue
        results.append({"title": cleaned_title, "url": html.unescape(raw_url), "snippet": ""})
        if len(results) >= limit:
            break
    return results


async def _web_search(context: ToolExecutionContext, payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")
    query = query[:200]
    limit = min(max(int(payload.get("limit") or MAX_SEARCH_RESULTS), 1), 10)
    url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
    try:
        response = await _web_get(
            url,
            headers={"User-Agent": "Current Project Research Agent"},
            timeout=10.0,
        )
        markup = response.text[:MAX_WEB_BYTES]
        results = _extract_search_results(markup, limit)
    except httpx.HTTPError as exc:
        return {
            **_network_error_result("web_search", exc),
            "query": query,
            "results": [],
            "instruction": "Web 搜索暂时不可用，不要编造搜索结果；改用已有 A 股工具证据继续分析，并在结论中说明外部检索受限。",
        }
    artifact = None
    if context.session_id:
        artifact = await ResearchArtifactService().create_artifact(
            session_id=str(context.session_id),
            user_id=context.principal.user_id,
            artifact_type="web_search",
            payload={"query": query, "results": results},
        )
    return {
        "tool": "web_search",
        "status": "completed",
        "query": query,
        "results": results,
        "artifact_id": artifact.get("artifact_id") if artifact else None,
    }


def file_tools() -> list[ResearchTool]:
    return [
        ResearchTool(
            name="read_document",
            description="Read a user-owned uploaded document artifact or inline text/content for example-driven document analysis.",
            permission=DOCUMENT_READ,
            schema={
                "type": "object",
                "properties": {
                    "artifact_id": {"type": "string"},
                    "file_id": {"type": "string"},
                    "text": {"type": "string"},
                    "content": {"type": "string"},
                    "filename": {"type": "string"},
                },
            },
            handler=lambda context, payload: _read_owned_artifact(
                context, payload, tool_name="read_document"
            ),
        ),
        ResearchTool(
            name="read_file",
            description="Read a user-owned uploaded file artifact or inline text/content.",
            permission=DOCUMENT_READ,
            schema={
                "type": "object",
                "properties": {
                    "artifact_id": {"type": "string"},
                    "file_id": {"type": "string"},
                    "text": {"type": "string"},
                    "content": {"type": "string"},
                    "filename": {"type": "string"},
                },
            },
            handler=lambda context, payload: _read_owned_artifact(
                context, payload, tool_name="read_file"
            ),
        ),
        ResearchTool(
            name="read_url",
            description="Fetch and parse a public http/https URL with local/private URL blocking.",
            permission=WEB_READ,
            schema={
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
            handler=_read_url,
        ),
        ResearchTool(
            name="web_search",
            description="Search public web pages with query limits, timeout, and current-session artifact capture.",
            permission=WEB_SEARCH,
            schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["query"],
            },
            handler=_web_search,
        ),
    ]
