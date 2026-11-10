# -*- coding: utf-8 -*-
"""统一配置：从环境变量读取大模型接口与 Agent 行为参数。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    base_url: str = field(
        default_factory=lambda: os.getenv(
            "LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
    )
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "qwen-plus"))
    timeout: float = float(os.getenv("LLM_TIMEOUT", "60"))
    workdir: Path = field(
        default_factory=lambda: Path(os.getenv("XAGENT_WORKDIR", Path.cwd()))
    )
    max_tool_rounds: int = int(os.getenv("XAGENT_MAX_TOOL_ROUNDS", "8"))

    # --- 新增：技能 / AGENT.md / 会话 / 上下文裁剪 ---
    agent_md_file: str = field(
        default_factory=lambda: os.getenv("XAGENT_AGENT_MD", "")
    )
    skills_dir: Path = field(
        default_factory=lambda: Path(os.getenv("XAGENT_SKILLS_DIR", ""))
    )
    session_dir: Path = field(
        default_factory=lambda: Path(os.getenv("XAGENT_SESSION_DIR", ""))
    )
    max_context_messages: int = int(os.getenv("XAGENT_MAX_CONTEXT", "24"))

    def resolve_paths(self) -> None:
        """补全 skills_dir / session_dir 的默认值（相对 workdir）。"""
        if not self.skills_dir:
            self.skills_dir = self.workdir / "skills"
        else:
            self.skills_dir = Path(self.skills_dir)
        if not self.session_dir:
            self.session_dir = self.workdir / "sessions"
        else:
            self.session_dir = Path(self.session_dir)

    @property
    def chat_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"
