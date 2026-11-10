# -*- coding: utf-8 -*-
"""网页读取与网络搜索工具。

- fetch_url：用 requests 抓取静态网页，去掉 HTML 标签后返回纯文本（带长度截断）。
- web_search：调用 DuckDuckGo HTML 搜索端点，返回标题+链接+摘要列表。
"""
from __future__ import annotations

import re
from html import unescape

from .base import BaseTool


def _requests():
    """延迟导入 requests，便于无网络环境下模块仍能被导入。"""
    import requests
    return requests

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}
_MAX_TEXT = 8000
_TIMEOUT = 20


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript|head)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<br\s*/?>", "\n", html)
    html = re.sub(r"(?is)<p[^>]*>", "\n", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    text = unescape(html)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class FetchUrlTool(BaseTool):
    name = "fetch_url"
    description = "读取一个静态网页 URL 的正文内容（自动去掉 HTML 标签），返回纯文本。用于获取网页信息。"
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "http/https 开头的完整 URL"},
            "max_chars": {
                "type": "integer",
                "description": "返回文本最大字符数，默认 8000，避免过长撑爆上下文",
            },
        },
        "required": ["url"],
    }

    def execute(self, url: str, max_chars: int = _MAX_TEXT) -> dict:
        if not url.startswith(("http://", "https://")):
            return {"ok": False, "error": "url 必须以 http:// 或 https:// 开头"}
        try:
            resp = _requests().get(url, headers=_HEADERS, timeout=_TIMEOUT)
            resp.raise_for_status()
        except _requests().RequestException as exc:
            return {"ok": False, "error": f"请求失败: {exc.__class__.__name__}: {exc}"}
        ctype = resp.headers.get("Content-Type", "")
        if "html" not in ctype and "text" not in ctype and "json" not in ctype:
            return {"ok": False, "error": f"非文本内容: {ctype}"}
        text = _html_to_text(resp.text)
        truncated = len(text) > int(max_chars)
        return {
            "ok": True,
            "url": resp.url,
            "status_code": resp.status_code,
            "content_type": ctype,
            "char_count": len(text),
            "truncated": truncated,
            "text": text[: int(max_chars)],
        }


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "调用搜索引擎 API 检索关键词，返回前若干条结果的标题、链接和摘要。需要查最新信息时使用。"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
            "limit": {"type": "integer", "description": "返回条数，默认 5，最大 10"},
        },
        "required": ["query"],
    }

    def execute(self, query: str, limit: int = 5) -> dict:
        limit = max(1, min(int(limit), 10))
        try:
            resp = _requests().post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
                headers=_HEADERS,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
        except _requests().RequestException as exc:
            return {"ok": False, "error": f"搜索请求失败: {exc.__class__.__name__}: {exc}"}

        # 解析 DuckDuckGo HTML 结果块
        results = []
        blocks = re.findall(
            r'(?is)<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
            resp.text,
        )
        for href, title, snippet in blocks[:limit]:
            title = _html_to_text(title)
            snippet = _html_to_text(snippet)
            results.append({"title": title, "url": href, "snippet": snippet})
        if not results:
            return {"ok": True, "query": query, "results": [], "note": "未解析到结果，可能被限流"}
        return {"ok": True, "query": query, "count": len(results), "results": results}
