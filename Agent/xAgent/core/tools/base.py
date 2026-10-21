# -*- coding: utf-8 -*-
"""工具抽象基类与注册机制：新工具只需继承 BaseTool 并注册。"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """所有可被大模型调用的工具的基类。

    子类必须实现 :meth:`execute`，并通过类属性声明
    ``name`` / ``description`` / ``parameters``（JSON Schema）。
    """

    #: 工具名称（Function Calling 中使用的函数名）
    name: str = ""
    #: 工具说明（模型据此决定是否调用）
    description: str = ""
    #: 参数 JSON Schema
    parameters: dict = {"type": "object", "properties": {}, "required": []}

    def schema(self) -> dict:
        """返回完整的 function schema。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    @abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        """执行工具逻辑，返回可 JSON 序列化的结果。"""

    def call(self, arguments: str) -> str:
        """解析参数并执行，统一封装为 JSON 字符串返回给模型。"""
        try:
            args = json.loads(arguments or "{}") if isinstance(arguments, str) else dict(arguments)
        except json.JSONDecodeError as exc:
            return json.dumps({"ok": False, "error": f"参数解析失败: {exc}"},
                              ensure_ascii=False)
        try:
            result = self.execute(**args)
            return json.dumps({"ok": True, "result": result}, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)


class ToolRegistry:
    """工具注册表：集中管理全部可用工具，供会话层使用。"""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict]:
        return [t.schema() for t in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def call(self, name: str, arguments: str) -> str:
        tool = self.get(name)
        if tool is None:
            return json.dumps({"ok": False, "error": f"未知工具: {name}"},
                              ensure_ascii=False)
        return tool.call(arguments)
