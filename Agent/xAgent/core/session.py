# -*- coding: utf-8 -*-
"""会话层：维护消息历史，驱动“模型 <-> 工具”循环。

本模块与界面完全解耦：:meth:`ChatSession.send` 是一个同步生成器，
逐段产出回复增量，由界面层决定如何展示（CLI 打印 / TUI 刷新 / Web 推送）。
"""
from __future__ import annotations

from typing import Generator

from .config import Settings
from .llm_client import LLMClient
from .tools import ToolRegistry

DEFAULT_SYSTEM_PROMPT = (
    "你是一个乐于助人的助手。当需要操作文件时，请调用对应的工具函数。"
)


class ChatSession:
    def __init__(
        self,
        client: LLMClient,
        registry: ToolRegistry,
        settings: Settings | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ):
        self.client = client
        self.registry = registry
        self.settings = settings or Settings()
        self.system_prompt = system_prompt
        self.messages: list[dict] = [
            {"role": "system", "content": system_prompt}
        ]

    def send(self, user_text: str) -> Generator[str, None, None]:
        """处理一条用户输入，逐段产出回复增量文本（含工具调用过程提示）。"""
        self.messages.append({"role": "user", "content": user_text})

        for _round in range(self.settings.max_tool_rounds):
            assistant_text: list[str] = []
            tool_calls: list[dict] = []

            for kind, payload in self.client.chat_stream(
                self.messages, self.registry.schemas()
            ):
                if kind == "delta":
                    assistant_text.append(payload)
                    yield payload
                elif kind == "tool_call":
                    call_id, name, args = payload
                    tool_calls.append({"id": call_id, "name": name, "arguments": args})
                elif kind == "done":
                    break

            assistant_msg: dict = {"role": "assistant", "content": "".join(assistant_text)}
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {"id": c["id"], "type": "function",
                     "function": {"name": c["name"], "arguments": c["arguments"]}}
                    for c in tool_calls
                ]
            self.messages.append(assistant_msg)

            if not tool_calls:
                break

            # 依次执行工具并把结果回传给模型
            for c in tool_calls:
                yield f"\n[调用工具: {c['name']}]\n"
                result = self.registry.call(c["name"], c["arguments"])
                self.messages.append(
                    {"role": "tool", "tool_call_id": c["id"], "content": result}
                )
        else:
            yield "\n[已达工具调用上限，提前结束本轮。]"
