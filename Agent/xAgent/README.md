# xAgent

对 `Agent/Practice02/chat-stream-tool-fileOps.py` 的**软件工程化重构**：将原本「单文件、业务与界面耦合」的聊天程序，改造为 **core/UI 分层、模块化、可插拔多界面** 的 Agent 工程。

## 设计目标

- **core 与 UI 完全分离**：core 不依赖任何界面，界面只依赖 core 的公开接口
- **界面可插拔**：通过统一抽象 `ChatUI`，同一套 core 可对接 CLI / TUI / Web / Desktop
- **工具可扩展**：基于 `BaseTool` + `ToolRegistry`，新增工具只需继承注册，无需改动会话层
- **遵循软件工程规范**：单一职责、依赖倒置、面向接口、路径穿越防护、配置外置

## 目录结构

```
xAgent/
├── main.py                 # 入口：装配 core + 按 --ui 选择界面后端
├── requirements.txt        # 依赖：requests、textual
├── core/                   # ── 业务核心层（与界面无关）──
│   ├── config.py           #   统一配置（环境变量）
│   ├── llm_client.py       #   大模型客户端（OpenAI 兼容 + SSE 流式）
│   ├── session.py          #   会话层：消息历史 + 模型↔工具循环
│   └── tools/
│       ├── base.py         #   工具基类 BaseTool + 注册表 ToolRegistry
│       └── file_ops.py     #   文件操作工具集（list/read/write/append/delete/info）
└── ui/                     # ── 界面层（可插拔）──
    ├── base.py             #   界面抽象基类 ChatUI（协议）
    ├── cli_ui.py           #   CLI 界面
    └── textual_ui.py       #   Textual TUI 界面
    # web_ui.py / desktop_ui.py 为预留，按 ChatUI 协议实现后即可接入
```

## 快速开始

```bash
cd Agent/xAgent
pip install -r requirements.txt

export LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export LLM_API_KEY="sk-你的Key"
export LLM_MODEL="qwen-plus"

# Textual TUI（默认）
python main.py --ui tui
# 命令行界面
python main.py --ui cli
# 工作目录限定
python main.py --ui cli --workdir ./docs
```

## 界面切换

| `--ui`    | 界面              | 状态     |
| --------- | ----------------- | -------- |
| `tui`     | Textual 终端图形 | ✅ 已实现 |
| `cli`     | 命令行            | ✅ 已实现 |
| `web`     | Web 页面          | 🚧 预留   |
| `desktop` | 桌面应用          | 🚧 预留   |

> **扩展新界面**：在 `ui/` 下新建类继承 `ui.base.ChatUI` 并实现 `run()`，
> 再在 `main.py` 的 `_UI_REGISTRY` 中登记一行即可，core 层零改动。

## core / UI 解耦约定

- core 层**禁止 import** `ui.*`
- 会话输出通过同步生成器 `ChatSession.send()` 逐段产出，由界面层决定展示方式
- 工具通过 `ToolRegistry` 注册，会话层只面向 `schemas()` / `call()` 接口编程

## 安全

- 文件工具含**路径穿越防护**：拒绝访问工作目录之外的路径
- API Key 一律通过环境变量传入，不写入代码或仓库
