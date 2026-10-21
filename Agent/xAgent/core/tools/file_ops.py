# -*- coding: utf-8 -*-
"""文件操作工具集（fileOps）：重构自 chat-stream-tool-fileOps.py 的 FileOps。"""
from __future__ import annotations

import time
from pathlib import Path

from .base import BaseTool

# ---------------------------------------------------------------------------
# 工具基类的一个具体实现：文件操作
# ---------------------------------------------------------------------------


class ListFilesTool(BaseTool):
    name = "list_files"
    description = "列出当前工作目录下的文件（可用通配符过滤）。"
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "文件通配符，如 *.py 或 **/*.md，默认 *"}
        },
        "required": [],
    }

    def __init__(self, workdir: Path):
        self.workdir = workdir.resolve()

    def execute(self, pattern: str = "*") -> list[dict]:
        matches = []
        for p in self.workdir.glob(pattern):
            matches.append({
                "path": str(p.relative_to(self.workdir)),
                "type": "dir" if p.is_dir() else "file",
                "size": p.stat().st_size if p.is_file() else None,
            })
        return matches


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "读取一个文本文件的内容。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件相对路径"},
            "encoding": {"type": "string", "description": "编码，默认 utf-8"},
        },
        "required": ["path"],
    }

    def __init__(self, workdir: Path):
        self.workdir = workdir.resolve()

    def _resolve(self, path: str) -> Path:
        p = (self.workdir / path).resolve()
        if not str(p).startswith(str(self.workdir)):
            raise PermissionError(f"拒绝访问工作目录之外的路径: {path}")
        return p

    def execute(self, path: str, encoding: str = "utf-8") -> str:
        return self._resolve(path).read_text(encoding=encoding)


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "把一个文本写入（覆盖）指定文件，自动创建父目录。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件相对路径"},
            "content": {"type": "string", "description": "要写入的文本内容"},
            "encoding": {"type": "string", "description": "编码，默认 utf-8"},
        },
        "required": ["path", "content"],
    }

    def __init__(self, workdir: Path):
        self.workdir = workdir.resolve()

    def _resolve(self, path: str) -> Path:
        p = (self.workdir / path).resolve()
        if not str(p).startswith(str(self.workdir)):
            raise PermissionError(f"拒绝访问工作目录之外的路径: {path}")
        return p

    def execute(self, path: str, content: str, encoding: str = "utf-8") -> dict:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding=encoding)
        return {"path": str(p.relative_to(self.workdir)), "bytes": p.stat().st_size}


class AppendFileTool(WriteFileTool):
    name = "append_file"
    description = "把一段文本追加到指定文件末尾（不存在则创建）。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件相对路径"},
            "content": {"type": "string", "description": "要追加的文本"},
            "encoding": {"type": "string", "description": "编码，默认 utf-8"},
        },
        "required": ["path", "content"],
    }

    def execute(self, path: str, content: str, encoding: str = "utf-8") -> dict:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding=encoding) as f:
            f.write(content)
        return {"path": str(p.relative_to(self.workdir)), "bytes": p.stat().st_size}


class DeleteFileTool(BaseTool):
    name = "delete_file"
    description = "删除一个文件。"
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "文件相对路径"}},
        "required": ["path"],
    }

    def __init__(self, workdir: Path):
        self.workdir = workdir.resolve()

    def _resolve(self, path: str) -> Path:
        p = (self.workdir / path).resolve()
        if not str(p).startswith(str(self.workdir)):
            raise PermissionError(f"拒绝访问工作目录之外的路径: {path}")
        return p

    def execute(self, path: str) -> dict:
        p = self._resolve(path)
        if p.is_dir():
            raise ValueError("请使用文件路径，不支持直接删除目录")
        p.unlink()
        return {"path": str(p.relative_to(self.workdir)), "deleted": True}


class GetFileInfoTool(BaseTool):
    name = "get_file_info"
    description = "获取文件大小与修改时间等信息。"
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "文件相对路径"}},
        "required": ["path"],
    }

    def __init__(self, workdir: Path):
        self.workdir = workdir.resolve()

    def _resolve(self, path: str) -> Path:
        p = (self.workdir / path).resolve()
        if not str(p).startswith(str(self.workdir)):
            raise PermissionError(f"拒绝访问工作目录之外的路径: {path}")
        return p

    def execute(self, path: str) -> dict:
        p = self._resolve(path)
        st = p.stat()
        return {
            "path": str(p.relative_to(self.workdir)),
            "size": st.st_size,
            "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
        }


def build_file_ops_registry(workdir: Path) -> "ToolRegistry":
    """构建并返回已注册全部文件操作工具的工具注册表。"""
    from .base import ToolRegistry

    registry = ToolRegistry()
    for tool_cls in (ListFilesTool, ReadFileTool, WriteFileTool,
                     AppendFileTool, DeleteFileTool, GetFileInfoTool):
        registry.register(tool_cls(workdir))
    return registry
