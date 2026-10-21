# -*- coding: utf-8 -*-
"""统一配置：从环境变量读取大模型接口参数。"""
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

    @property
    def chat_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"
