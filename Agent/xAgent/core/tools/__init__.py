# -*- coding: utf-8 -*-
"""core.tools：工具抽象、注册机制与全部内置工具。"""
from __future__ import annotations

from pathlib import Path

from .base import BaseTool, ToolRegistry
from .file_ops import (
    AppendFileTool, DeleteFileTool, GetFileInfoTool, ListFilesTool,
    ReadFileTool, WriteFileTool,
)
from .time_tool import CurrentTimeTool, LeapYearTool
from .web_tool import FetchUrlTool, WebSearchTool


def build_file_ops_registry(workdir: Path) -> ToolRegistry:
    """仅文件操作（保持向后兼容）。"""
    registry = ToolRegistry()
    for tool_cls in (ListFilesTool, ReadFileTool, WriteFileTool,
                     AppendFileTool, DeleteFileTool, GetFileInfoTool):
        registry.register(tool_cls(workdir))
    return registry


def build_full_registry(workdir: Path, skills_manager=None) -> ToolRegistry:
    """装配全部内置工具：文件操作 + 时间/闰年 + 网页/搜索 + 技能操作。"""
    registry = build_file_ops_registry(workdir)
    # 时间与闰年
    registry.register(CurrentTimeTool())
    registry.register(LeapYearTool())
    # 网页读取与搜索
    registry.register(FetchUrlTool())
    registry.register(WebSearchTool())
    # 技能操作（需要 skills_manager）
    if skills_manager is not None:
        from .skill_tool import CreateSkillTool, ListSkillsTool, ReadSkillTool
        registry.register(ListSkillsTool(skills_manager))
        registry.register(ReadSkillTool(skills_manager))
        registry.register(CreateSkillTool(skills_manager))
    return registry


__all__ = [
    "BaseTool", "ToolRegistry",
    "build_file_ops_registry", "build_full_registry",
]
