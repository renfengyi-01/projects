# -*- coding: utf-8 -*-
"""Textual TUI 界面：终端内的图形化聊天窗口。

依赖：``pip install textual``
"""
from __future__ import annotations

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, Input, RichLog, Static

from core.config import Settings
from core.session import ChatSession

from .base import ChatUI


class _ChatApp(App):
    TITLE = "xAgent"
    SUB_TITLE = "流式对话 · 工具调用 · 文件操作"

    BINDINGS = [
        Binding("ctrl+q", "quit", "退出"),
        Binding("/", "focus_input", "输入"),
    ]

    def __init__(self, session: ChatSession, settings: Settings):
        super().__init__()
        self.session = session
        self.settings = settings
        self._current = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield RichLog(id="log", highlight=True, markup=True, wrap=True)
            yield Static(id="current", classes="current-line")
            yield Input(placeholder="输入问题（Ctrl+Q 退出）", id="input")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#log", RichLog).write(
            f"[bold green]模型[/] {self.settings.model} · "
            f"工作目录 {self.settings.workdir}\n开始聊天吧！"
        )

    def action_focus_input(self) -> None:
        self.query_one("#input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        self.query_one("#log", RichLog).write(f"[bold cyan]你>[/] {text}")
        self.run_chat(text)

    @work(thread=True)
    def run_chat(self, text: str) -> None:
        """在后台线程消费会话生成器，流式把增量推送到界面。"""
        try:
            self._current = ""
            for delta in self.session.send(text):
                self._current += delta
                self.call_from_thread(self._refresh_current)
            self.call_from_thread(self._finalize)
        except Exception as exc:  # noqa: BLE001
            self.call_from_thread(self._show_error, str(exc))

    def _refresh_current(self) -> None:
        self.query_one("#current", Static).update(self._current)

    def _finalize(self) -> None:
        if self._current:
            self.query_one("#log", RichLog).write(self._current)
        self._current = ""
        self.query_one("#current", Static).update("")

    def _show_error(self, message: str) -> None:
        self.query_one("#log", RichLog).write(f"[bold red]错误[/] {message}")


class TextualUI(ChatUI):
    """基于 Textual 的 TUI 界面。"""

    name = "tui"

    def run(self, session: ChatSession) -> None:
        _ChatApp(session=session, settings=self.settings).run()
