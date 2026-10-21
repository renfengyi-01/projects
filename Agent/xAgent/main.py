#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xAgent 入口：装配 core 组件，并按参数选择界面后端。

用法示例（在 Agent/xAgent 目录下运行）：
    python main.py --ui tui              # 使用 Textual TUI（默认）
    python main.py --ui cli              # 使用命令行界面
    python main.py --ui web              # 预留：Web 界面（开发中）

界面可插拔：新增界面只需在 ui/ 下实现 ChatUI 子类并在下表中注册。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core.config import Settings
from core.llm_client import LLMClient
from core.session import ChatSession
from core.tools import build_file_ops_registry

# ---------------------------------------------------------------------------
# 界面注册表：新增界面在此登记即可被 --ui 选择
# ---------------------------------------------------------------------------
_UI_REGISTRY: dict[str, str] = {
    "cli": "ui.cli_ui:CliUI",
    "tui": "ui.textual_ui:TextualUI",
    # 预留（未实现）：
    "web": "ui.web_ui:WebUI",
    "desktop": "ui.desktop_ui:DesktopUI",
}


def build_session(settings: Settings) -> ChatSession:
    client = LLMClient(settings)
    registry = build_file_ops_registry(settings.workdir)
    return ChatSession(client=client, registry=registry, settings=settings)


def load_ui(name: str, settings: Settings):
    """动态加载 UI 类。找不到实现时给出清晰提示。"""
    module_path, cls_name = _UI_REGISTRY[name].split(":")
    try:
        module = __import__(module_path, fromlist=[cls_name])
    except ImportError as exc:
        raise RuntimeError(
            f"界面「{name}」尚未实现或依赖缺失：{exc}\n"
            f"当前可用界面: cli, tui"
        ) from exc
    cls = getattr(module, cls_name)
    return cls(settings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="xAgent：多界面流式对话代理")
    parser.add_argument("--ui", choices=list(_UI_REGISTRY), default="tui",
                        help="界面后端（默认 tui，Textual）")
    parser.add_argument("--workdir", type=str, default=str(Path.cwd()),
                        help="文件操作的工作目录")
    parser.add_argument("--model", type=str, default=None, help="模型名")
    parser.add_argument("--base-url", type=str, default=None, help="API 地址")
    parser.add_argument("--api-key", type=str, default=None, help="API Key")
    args = parser.parse_args(argv)

    settings = Settings()
    if args.workdir:
        settings.workdir = Path(args.workdir).resolve()
    if args.model:
        settings.model = args.model
    if args.base_url:
        settings.base_url = args.base_url
    if args.api_key:
        settings.api_key = args.api_key

    if not settings.api_key:
        print("错误：未配置 API Key。请设置环境变量 LLM_API_KEY 或用 --api-key 传入。")
        return 1

    session = build_session(settings)
    try:
        ui = load_ui(args.ui, settings)
    except RuntimeError as exc:
        print(exc)
        return 2

    ui.run(session)
    return 0


if __name__ == "__main__":
    sys.exit(main())
