# -*- coding: utf-8 -*-
"""命令行（CLI）界面：最简交互实现。"""
from __future__ import annotations

from core.config import Settings
from core.session import ChatSession

from .base import ChatUI


class CliUI(ChatUI):
    name = "cli"

    def run(self, session: ChatSession) -> None:
        print(f"xAgent [CLI]  模型: {self.settings.model}")
        print(f"工作目录: {self.settings.workdir}   输入 /exit 退出，/tools 查看工具")
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
                for s in session.registry.schemas():
                    fn = s["function"]
                    print(f"  - {fn['name']}: {fn['description']}")
                continue

            print("助手> ", end="", flush=True)
            for delta in session.send(user_input):
                print(delta, end="", flush=True)
            print()
