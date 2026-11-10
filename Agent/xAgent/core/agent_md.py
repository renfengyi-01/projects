# -*- coding: utf-8 -*-
"""AGENT.md 支持：启动时读取工作目录下的 AGENT.md / AGENTS.md 作为长期规则注入。

- 只注入一次，长度截断；文件缺失不报错。
- 文件名可配置（settings.agent_md_file）。
"""
from __future__ import annotations

from pathlib import Path

_MAX_AGENT_MD = 4000
_CANDIDATES = ("AGENT.md", "AGENTS.md")


def load_agent_md(workdir: Path, filename: str | None = None) -> str:
    """读取 AGENT.md 内容。找不到返回空字符串（不报错）。"""
    workdir = Path(workdir)
    candidates = [filename] if filename else list(_CANDIDATES)
    for name in candidates:
        if not name:
            continue
        path = workdir / name
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if len(text) > _MAX_AGENT_MD:
                text = text[:_MAX_AGENT_MD] + "\n...（AGENT.md 已截断）"
            return text.strip()
    return ""
