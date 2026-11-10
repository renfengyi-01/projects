# -*- coding: utf-8 -*-
"""MCP 客户端桥接：把外部 MCP server 的工具并入可调用集合。

- 配置：环境变量 XAGENT_MCP_SERVERS 为 JSON 数组，每项形如
  {"name": "pet", "transport": "stdio", "command": "python", "args": ["-m", "pet_hospital_mcp"]}
  或 {"name": "anythingllm", "transport": "http", "url": "http://127.0.0.1:8000/mcp"}
- 启动时逐个连接，连接失败降级（打印提示但不阻塞主流程）。
- 外部工具调用时通过 asyncio 桥接到同步 session。
"""
from __future__ import annotations

import asyncio
import json
import shlex
from typing import Any

from .tools.base import BaseTool, ToolRegistry


def _tool_input_schema(tool: Any) -> dict:
    """读取外部 MCP 工具的入参 schema。

    mcp SDK 2.x 的 Tool 用 snake_case 的 ``input_schema``；1.x 与旧文档用
    ``inputSchema``。两种都兼容，取不到时返回空对象 schema，避免整次连接失败。
    """
    for attr in ("input_schema", "inputSchema"):
        schema = getattr(tool, attr, None)
        if isinstance(schema, dict):
            return schema
    return {"type": "object", "properties": {}}


class _ExternalMcpTool(BaseTool):
    """把一个外部 MCP 工具包装成本地 BaseTool。"""

    def __init__(self, bridge: "McpClientBridge", server_name: str,
                 tool_name: str, description: str, parameters: dict):
        self.bridge = bridge
        self.server_name = server_name
        self.name = f"mcp__{server_name}__{tool_name}"
        self.description = f"[来自 MCP server {server_name}] {description}"
        self.parameters = {
            "type": "object",
            "properties": parameters.get("properties", {}),
            "required": parameters.get("required", []),
        }

    def execute(self, **kwargs) -> dict:
        return self.bridge.call_tool(self.server_name, self.name.split("__", 2)[2], kwargs)


class McpClientBridge:
    def __init__(self, servers_config: list[dict] | None = None):
        self.servers_config = servers_config or []
        self.status: dict[str, str] = {}   # server_name -> "connected" / "failed: ..."
        self._sessions: dict[str, Any] = {}
        self._loops: dict[str, asyncio.AbstractEventLoop] = {}

    @classmethod
    def from_env(cls) -> "McpClientBridge":
        import os
        raw = os.getenv("XAGENT_MCP_SERVERS", "").strip()
        if not raw:
            return cls([])
        try:
            cfg = json.loads(raw)
            if isinstance(cfg, list):
                return cls(cfg)
        except json.JSONDecodeError:
            pass
        return cls([])

    def register_tools(self, registry: ToolRegistry) -> None:
        """连接所有已配置 server，把它们的工具注册进 registry。失败降级。"""
        for cfg in self.servers_config:
            name = cfg.get("name") or "mcp"
            try:
                tools = self._connect_and_list(cfg)
                for t in tools:
                    wrapper = _ExternalMcpTool(
                        self, name,
                        t.get("name", "unknown"),
                        t.get("description", ""),
                        t.get("input_schema") or t.get("inputSchema")
                        or t.get("parameters")
                        or {"type": "object", "properties": {}},
                    )
                    registry.register(wrapper)
                self.status[name] = f"connected ({len(tools)} tools)"
            except Exception as exc:  # noqa: BLE001
                self.status[name] = f"failed: {exc.__class__.__name__}: {exc}"

    def _connect_and_list(self, cfg: dict) -> list[dict]:
        transport = cfg.get("transport", "stdio")
        if transport == "stdio":
            return self._run_stdio(cfg)
        if transport in ("http", "streamable-http", "sse"):
            return self._run_http(cfg)
        raise ValueError(f"未知 transport: {transport}")

    def _run_stdio(self, cfg: dict) -> list[dict]:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        command = cfg.get("command")
        args = cfg.get("args", [])
        env = cfg.get("env")
        params = StdioServerParameters(command=command, args=args, env=env)

        async def _go():
            async with stdio_client(params) as (r, w):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    return [
                        {"name": t.name, "description": t.description or "",
                         "input_schema": _tool_input_schema(t)}
                        for t in listed.tools
                    ]
        return asyncio.run(_go())

    def _run_http(self, cfg: dict) -> list[dict]:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        url = cfg.get("url")

        async def _go():
            async with streamable_http_client(url) as (r, w):
                async with ClientSession(r, w) as session:
                    try:
                        await session.initialize()
                    except Exception:
                        pass  # 无状态 server 可能不需要 initialize
                    listed = await session.list_tools()
                    return [
                        {"name": t.name, "description": t.description or "",
                         "input_schema": _tool_input_schema(t)}
                        for t in listed.tools
                    ]
        return asyncio.run(_go())

    def call_tool(self, server_name: str, tool_name: str, arguments: dict) -> dict:
        """同步调用：根据 server 配置重建连接并 call_tool。教学场景每次新建连接。"""
        cfg = next((c for c in self.servers_config if (c.get("name") or "mcp") == server_name), None)
        if cfg is None:
            return {"ok": False, "error": f"未配置的 MCP server: {server_name}"}

        transport = cfg.get("transport", "stdio")

        async def _go():
            if transport == "stdio":
                from mcp import ClientSession, StdioServerParameters
                from mcp.client.stdio import stdio_client
                params = StdioServerParameters(
                    command=cfg.get("command"), args=cfg.get("args", []), env=cfg.get("env"))
                async with stdio_client(params) as (r, w):
                    async with ClientSession(r, w) as session:
                        await session.initialize()
                        result = await session.call_tool(tool_name, arguments)
                        return self._extract(result)
            else:
                from mcp import ClientSession
                from mcp.client.streamable_http import streamable_http_client
                async with streamable_http_client(cfg.get("url")) as (r, w):
                    async with ClientSession(r, w) as session:
                        try:
                            await session.initialize()
                        except Exception:
                            pass
                        result = await session.call_tool(tool_name, arguments)
                        return self._extract(result)

        try:
            return asyncio.run(_go())
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"MCP 调用失败: {exc.__class__.__name__}: {exc}"}

    @staticmethod
    def _extract(result) -> dict:
        text = ""
        if getattr(result, "content", None):
            text = "\n".join(getattr(c, "text", str(c)) for c in result.content)
        return {"ok": not getattr(result, "is_error", False), "content": text}
