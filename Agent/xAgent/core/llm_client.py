# -*- coding: utf-8 -*-
"""大模型客户端：OpenAI 兼容接口的流式（SSE）调用。

只负责“发请求 + 逐段解析”，不涉及任何界面逻辑。
"""
from __future__ import annotations

import json

import requests

from .config import Settings


class LLMClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.settings.api_key}",
        }

    def _payload(self, messages: list[dict], tools: list[dict]) -> dict:
        payload = {
            "model": self.settings.model,
            "messages": messages,
            "stream": True,
            "temperature": 0.7,
        }
        if tools:
            payload["tools"] = tools
        return payload

    def chat_stream(self, messages: list[dict], tools: list[dict]):
        """发起流式请求，逐段产出 ``(kind, payload)``。

        kind:
          - ``"delta"``     普通增量文本
          - ``"tool_call"`` 模型请求的工具调用 ``(id, name, arguments)``
          - ``"done"``      本轮结束
        """
        payload = self._payload(messages, tools)
        with requests.post(
            self.settings.chat_url,
            headers=self._headers(),
            json=payload,
            stream=True,
            timeout=self.settings.timeout,
        ) as resp:
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")

            tool_calls_buf: dict[int, dict] = {}
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta", {})

                if delta.get("content"):
                    yield ("delta", delta["content"])

                for tc in delta.get("tool_calls") or []:
                    idx = tc.get("index", 0)
                    buf = tool_calls_buf.setdefault(
                        idx, {"id": "", "name": "", "arguments": ""})
                    if tc.get("id"):
                        buf["id"] += tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        buf["name"] += fn["name"]
                    if fn.get("arguments"):
                        buf["arguments"] += fn["arguments"]

                finish = choices[0].get("finish_reason")
                if finish == "tool_calls":
                    for _, tc in sorted(tool_calls_buf.items()):
                        yield ("tool_call", (tc["id"], tc["name"], tc["arguments"]))
                elif finish == "stop":
                    yield ("done", None)
