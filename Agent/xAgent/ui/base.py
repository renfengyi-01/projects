# -*- coding: utf-8 -*-
"""界面抽象层：定义所有界面（CLI/TUI/Web/Desktop）必须实现的协议。

新增一个界面（例如 Web、Desktop）时，只需继承 :class:`ChatUI` 并实现
:meth:`run`，再在入口处注册即可，core 层无需任何改动。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from core.config import Settings
from core.session import ChatSession


class ChatUI(ABC):
    """界面基类。子类负责启动事件循环并把用户输入交给会话层。"""

    name: str = "base"

    def __init__(self, settings: Settings):
        self.settings = settings

    @abstractmethod
    def run(self, session: ChatSession) -> None:
        """启动界面主循环。"""
        raise NotImplementedError
