#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chat-stream-tool-fileOps.py
============================================================
一个带“流式对话 + 工具调用(Function Calling) + 文件操作(fileOps)”的
大模型命令行程序（OpenAI 兼容接口）。

功能特性
--------
1. 流式输出：以 SSE 方式逐 token 打印大模型回复；
2. 工具调用：模型可请求调用文件操作工具（列目录 / 读文件 / 写文件 /
   追加写 / 删除 / 获取文件信息），程序执行后把结果回传给模型继续回答；
3. 交互式 REPL：命令行输入问题，/exit 退出，/tools 查看可用工具。

环境变量配置（也可在代码中改为硬编码，但请勿提交真实 Key）：
    LLM_BASE_URL  如 https://dashscope.aliyuncs.com/compatible-mode/v1
    LLM_API_KEY   你的 API Key
    LLM_MODEL     如 qwen-plus / qwen-max
"""

import os
import sys
import json
import time
import glob
import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# 基础配置
# ---------------------------------------------------------------------------
BASE_URL = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
API_KEY = os.getenv("LLM_API_KEY", "")
MODEL = os.getenv("LLM_MODEL", "qwen-plus")

CHAT_URL = f"{BASE_URL.rstrip('/')}/chat/completions"
DEFAULT_WORKDIR = Path.cwd()


# ---------------------------------------------------------------------------
# 文件操作工具（fileOps）
# ---------------------------------------------------------------------------
class FileOps:
    """一组可被大模型调用的文件操作工具。"""

    def __init__(self, workdir: Path = DEFAULT_WORKDIR):
        self.workdir = workdir.resolve()

    # -- 工具 schema（用于 function calling） --
    @staticmethod
    def tool_schemas() -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "列出当前工作目录下的文件（可用通配符过滤）。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "文件通配符，如 *.py 或 **/*.md，默认 *",
                            }
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "读取一个文本文件的内容。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "文件相对路径"},
                            "encoding": {"type": "string", "description": "编码，默认 utf-8"},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "把一个文本写入（覆盖）指定文件，自动创建父目录。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "文件相对路径"},
                            "content": {"type": "string", "description": "要写入的文本内容"},
                            "encoding": {"type": "string", "description": "编码，默认 utf-8"},
                        },
                        "required": ["path", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "append_file",
                    "description": "把一段文本追加到指定文件末尾（不存在则创建）。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "文件相对路径"},
                            "content": {"type": "string", "description": "要追加的文本"},
                            "encoding": {"type": "string", "description": "编码，默认 utf-8"},
                        },
                        "required": ["path", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "delete_file",
                    "description": "删除一个文件。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "文件相对路径"},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_file_info",
                    "description": "获取文件大小与修改时间等信息。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "文件相对路径"},
                        },
                        "required": ["path"],
                    },
                },
            },
        ]

    # -- 工具实现 --
    def _resolve(self, path: str) -> Path:
        p = (self.workdir / path).resolve()
        # 防止越出工作目录（路径穿越防护）
        if not str(p).startswith(str(self.workdir)):
            raise PermissionError(f"拒绝访问工作目录之外的路径: {path}")
        return p

    def call(self, name: str, args: dict) -> str:
        try:
            handler = getattr(self, name)
            result = handler(**args)
            return json.dumps({"ok": True, "result": result}, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

    def list_files(self, pattern: str = "*") -> list[str]:
        base = self.workdir
        matches = []
        for p in base.glob(pattern):
            matches.append({
                "path": str(p.relative_to(base)),
                "type": "dir" if p.is_dir() else "file",
                "size": p.stat().st_size if p.is_file() else None,
            })
        return matches

    def read_file(self, path: str, encoding: str = "utf-8") -> str:
        p = self._resolve(path)
        return p.read_text(encoding=encoding)

    def write_file(self, path: str, content: str, encoding: str = "utf-8") -> dict:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding=encoding)
        return {"path": str(p.relative_to(self.workdir)), "bytes": p.stat().st_size}

    def append_file(self, path: str, content: str, encoding: str = "utf-8") -> dict:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding=encoding) as f:
            f.write(content)
        return {"path": str(p.relative_to(self.workdir)), "bytes": p.stat().st_size}

    def delete_file(self, path: str) -> dict:
        p = self._resolve(path)
        if p.is_dir():
            raise ValueError("请使用文件路径，不支持直接删除目录")
        p.unlink()
        return {"path": str(p.relative_to(self.workdir)), "deleted": True}

    def get_file_info(self, path: str) -> dict:
        p = self._resolve(path)
        st = p.stat()
        return {
            "path": str(p.relative_to(self.workdir)),
            "size": st.st_size,
            "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
        }


# ---------------------------------------------------------------------------
# 大模型客户端（OpenAI 兼容 + 流式）
# ---------------------------------------------------------------------------
class LLMClient:
    def __init__(self, base_url: str = BASE_URL, api_key: str = API_KEY,
                 model: str = MODEL, timeout: float = 60.0):
        self.chat_url = f"{base_url.rstrip('/')}/chat/completions"
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _payload(self, messages: list[dict], tools: list[dict]) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": 0.7,
        }
        if tools:
            payload["tools"] = tools
        return payload

    def chat_stream(self, messages: list[dict], tools: list[dict]):
        """发起流式请求，逐段产出 (type, content)。

        type: "delta"  普通增量文本
              "tool_call"  模型请求的工具调用 (name, arguments)
              "done"   本轮结束
        """
        import requests  # 延迟导入，便于无网络环境时程序仍能启动

        payload = self._payload(messages, tools)
        with requests.post(self.chat_url, headers=self._headers(),
                           json=payload, stream=True, timeout=self.timeout) as resp:
            if resp.status_code != 200:
                raise RuntimeError(
                    f"HTTP {resp.status_code}: {resp.text[:500]}"
                )

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

                # 普通增量文本
                if delta.get("content"):
                    yield ("delta", delta["content"])

                # 工具调用增量
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


# ---------------------------------------------------------------------------
# 对话会话
# ---------------------------------------------------------------------------
class ChatSession:
    """维护消息历史，并驱动“模型 <-> 工具”循环。"""

    def __init__(self, client: LLMClient, tools: list[dict], file_ops: FileOps,
                 max_tool_rounds: int = 8):
        self.client = client
        self.tools = tools
        self.file_ops = file_ops
        self.max_tool_rounds = max_tool_rounds
        self.messages: list[dict] = [
            {"role": "system",
             "content": "你是一个乐于助人的助手。当需要操作文件时，调用对应的工具函数。"},
        ]

    def send(self, user_text: str):
        """处理用户输入，返回本轮完整回复字符串。"""
        self.messages.append({"role": "user", "content": user_text})
        full_reply: list[str] = []

        for _round in range(self.max_tool_rounds):
            assistant_text_parts: list[str] = []
            collected_tool_calls: list[dict] = []

            for kind, payload in self.client.chat_stream(self.messages, self.tools):
                if kind == "delta":
                    full_reply.append(payload)
                    assistant_text_parts.append(payload)
                    yield payload  # 边接收边输出
                elif kind == "tool_call":
                    call_id, name, args = payload
                    collected_tool_calls.append(
                        {"id": call_id, "name": name, "arguments": args})
                elif kind == "done":
                    break

            # 组装助手消息
            assistant_msg: dict = {"role": "assistant", "content": "".join(assistant_text_parts)}
            if collected_tool_calls:
                assistant_msg["tool_calls"] = [
                    {"id": c["id"], "type": "function",
                     "function": {"name": c["name"], "arguments": c["arguments"]}}
                    for c in collected_tool_calls
                ]
            self.messages.append(assistant_msg)

            if not collected_tool_calls:
                break  # 无需调用工具，本轮对话结束

            # 执行工具并回传结果
            for c in collected_tool_calls:
                name, args = c["name"], {}
                try:
                    args = json.loads(c["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = self.file_ops.call(name, args)
                self.messages.append(
                    {"role": "tool", "tool_call_id": c["id"], "content": result})
        else:
            yield "\n[已达工具调用上限，提前结束本轮。]"


# ---------------------------------------------------------------------------
# REPL 界面（CLI）
# ---------------------------------------------------------------------------
def repl(session: ChatSession, file_ops: FileOps) -> None:
    print(f"聊天工具已就绪  模型: {MODEL}")
    print(f"工作目录: {file_ops.workdir}   输入 /exit 退出，/tools 查看工具")
    print("-" * 60)
    while True:
        try:
            user_input = input("\n你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            break
        if not user_input:
            continue
        if user_input in ("/exit", "/quit", "/q"):
            print("再见。")
            break
        if user_input == "/tools":
            for t in file_ops.tool_schemas():
                print("  -", t["function"]["name"], ":", t["function"]["description"])
            continue

        print("助手> ", end="", flush=True)
        for delta in session.send(user_input):
            print(delta, end="", flush=True)
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="流式对话 + 工具调用 + 文件操作")
    parser.add_argument("--workdir", type=str, default=str(DEFAULT_WORKDIR),
                        help="文件操作的工作目录")
    parser.add_argument("--model", type=str, default=MODEL, help="模型名")
    parser.add_argument("--base-url", type=str, default=BASE_URL, help="API 地址")
    parser.add_argument("--api-key", type=str, default=API_KEY, help="API Key")
    args = parser.parse_args()

    if not args.api_key:
        print("错误：未配置 API Key。请设置环境变量 LLM_API_KEY 或用 --api-key 传入。")
        sys.exit(1)

    file_ops = FileOps(Path(args.workdir))
    client = LLMClient(base_url=args.base_url, api_key=args.api_key, model=args.model)
    session = ChatSession(client=client, tools=file_ops.tool_schemas(), file_ops=file_ops)
    repl(session, file_ops)


if __name__ == "__main__":
    main()
