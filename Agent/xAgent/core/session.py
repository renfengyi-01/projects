# -*- coding: utf-8 -*-
"""会话层：维护消息历史，驱动"模型 <-> 工具"循环。

新增能力：
- AGENT.md 长期规则注入（只一次、缺失不报错）
- 技能摘要渐进注入系统提示
- 会话持久化：每次回合结束落盘到 sessions/ 目录（JSON）
- 上下文裁剪：消息条数超过阈值时，把旧消息压缩为一条摘要，保留 system + 最近 N 条
- MCP 连接状态可见（注入系统提示，不阻塞主流程）
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Generator

from .config import Settings
from .llm_client import LLMClient
from .tools import ToolRegistry

_BASE_SYSTEM = (
    "你是一个乐于助人的助手。当需要操作文件、联网查信息、使用技能或调用外部 MCP 工具时，"
    "请通过 function calling 调用对应工具。"
)


class ChatSession:
    def __init__(
        self,
        client: LLMClient,
        registry: ToolRegistry,
        settings: Settings | None = None,
        agent_md_text: str = "",
        skills_summary: list[dict] | None = None,
        mcp_status: dict[str, str] | None = None,
    ):
        self.client = client
        self.registry = registry
        self.settings = settings or Settings()
        self.settings.resolve_paths()

        # 组装系统提示
        system_parts = [_BASE_SYSTEM]
        if agent_md_text:
            system_parts.append("\n## 长期规则（来自 AGENT.md）\n" + agent_md_text)
        if skills_summary:
            skill_lines = "\n".join(
                f"- {s['name']}: {s['description']}" for s in skills_summary
            )
            system_parts.append(
                "\n## 可用技能（用 read_skill 读取正文）\n" + skill_lines
            )
        if mcp_status:
            mcp_lines = "\n".join(f"- {k}: {v}" for k, v in mcp_status.items())
            system_parts.append("\n## MCP 外部工具状态\n" + mcp_lines)
        self.system_prompt = "\n".join(system_parts)

        self.messages: list[dict] = [
            {"role": "system", "content": self.system_prompt}
        ]
        self._session_file: Path | None = None
        self._init_session_file()

    # ------------------------------------------------------------------ 持久化
    def _init_session_file(self) -> None:
        try:
            self.settings.session_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._session_file = self.settings.session_dir / f"session_{ts}.json"
            self._save()
        except OSError:
            self._session_file = None

    def _save(self) -> None:
        if self._session_file is None:
            return
        try:
            payload = {
                "saved_at": datetime.now().isoformat(timespec="seconds"),
                "model": self.settings.model,
                "messages": self.messages,
            }
            self._session_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            pass

    # ------------------------------------------------------------------ 上下文裁剪
    def _trim_context(self) -> None:
        """保留 system + 最近 N 条；把被裁掉的对话压成一条 summary 消息。"""
        limit = self.settings.max_context_messages
        # 不算 system 消息
        history = [m for m in self.messages if m.get("role") != "system"]
        if len(history) <= limit:
            return
        keep = history[-limit:]
        dropped = history[:-limit]
        # 把 dropped 压成简短摘要
        summaries = []
        for m in dropped:
            role = m.get("role")
            content = str(m.get("content", ""))[:200]
            if role in ("user", "assistant") and content:
                summaries.append(f"{role}: {content}")
        compact = {
            "role": "system",
            "content": "以下是更早对话的压缩摘要：\n" + "\n".join(summaries[-20:]),
        }
        system_msg = self.messages[0]
        self.messages = [system_msg, compact] + keep

    # ------------------------------------------------------------------ 主循环
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

            for c in tool_calls:
                yield f"\n[调用工具: {c['name']}]\n"
                result = self.registry.call(c["name"], c["arguments"])
                self.messages.append(
                    {"role": "tool", "tool_call_id": c["id"], "content": result}
                )
            self._trim_context()
        else:
            yield "\n[已达工具调用上限，提前结束本轮。]"

        self._save()
