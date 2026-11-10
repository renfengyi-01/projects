#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xAgent 入口：装配 core 组件，并按参数选择界面后端。

用法示例（在 Agent/xAgent 目录下运行）：
    python main.py --ui tui              # 使用 Textual TUI（默认）
    python main.py --ui cli              # 使用命令行界面
    python main.py --workdir ./docs      # 限定文件操作工作目录

环境变量：
    LLM_API_KEY / LLM_BASE_URL / LLM_MODEL / LLM_TIMEOUT
    XAGENT_AGENT_MD    AGENT.md 文件名（默认自动找 AGENT.md / AGENTS.md）
    XAGENT_SKILLS_DIR   技能目录（默认 <workdir>/skills）
    XAGENT_SESSION_DIR  会话持久化目录（默认 <workdir>/sessions）
    XAGENT_MAX_CONTEXT  上下文保留消息条数（默认 24）
    XAGENT_MCP_SERVERS  JSON 数组，外部 MCP server 配置（见 core/mcp_client.py）
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core.agent_md import load_agent_md
from core.config import Settings
from core.llm_client import LLMClient
from core.mcp_client import McpClientBridge
from core.session import ChatSession
from core.skills_manager import SkillsManager
from core.tools import build_full_registry

_UI_REGISTRY: dict[str, str] = {
    "cli": "ui.cli_ui:CliUI",
    "tui": "ui.textual_ui:TextualUI",
    "web": "ui.web_ui:WebUI",        # 预留
    "desktop": "ui.desktop_ui:DesktopUI",
}


def build_session(settings: Settings) -> ChatSession:
    settings.resolve_paths()

    # 1) 技能系统：扫描技能目录，只把 name+description 注入系统提示
    skills_manager = SkillsManager(settings.skills_dir)
    skills_manager.scan()

    # 2) AGENT.md 长期规则
    agent_md_text = load_agent_md(settings.workdir, settings.agent_md_file or None)

    # 3) 装配内置工具
    registry = build_full_registry(settings.workdir, skills_manager)

    # 4) MCP 客户端：连接外部 server，失败降级不阻塞
    mcp_bridge = McpClientBridge.from_env()
    mcp_bridge.register_tools(registry)

    client = LLMClient(settings)
    return ChatSession(
        client=client,
        registry=registry,
        settings=settings,
        agent_md_text=agent_md_text,
        skills_summary=skills_manager.list_summary(),
        mcp_status=mcp_bridge.status,
    )


def load_ui(name: str, settings: Settings):
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
    parser.add_argument("--workdir", type=str, default=None, help="文件操作的工作目录")
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

    settings.resolve_paths()
    if not settings.api_key:
        print("错误：未配置 API Key。请设置环境变量 LLM_API_KEY 或用 --api-key 传入。")
        return 1

    session = build_session(settings)
    try:
        ui = load_ui(args.ui, settings)
    except RuntimeError as exc:
        print(exc)
        return 2

    # 打印装配状态
    print(f"[xAgent] 工作目录: {settings.workdir}")
    print(f"[xAgent] 技能数: {len(session.registry.names())} 个工具已注册")
    ui.run(session)
    return 0


if __name__ == "__main__":
    sys.exit(main())
