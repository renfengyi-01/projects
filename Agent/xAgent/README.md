# xAgent

对 `Agent/Practice02/chat-stream-tool-fileOps.py` 的**软件工程化重构**：将原本「单文件、业务与界面耦合」的聊天程序，改造为 **core/UI 分层、模块化、可插拔多界面** 的 Agent 工程，并在其上补齐了技能系统、AGENT.md 长期规则、会话持久化、上下文裁剪与 MCP 客户端接入。

## 设计目标

- **core 与 UI 完全分离**：core 不依赖任何界面，界面只依赖 core 的公开接口
- **界面可插拔**：通过统一抽象 `ChatUI`，同一套 core 可对接 CLI / TUI / Web / Desktop
- **工具可扩展**：基于 `BaseTool` + `ToolRegistry`，新增工具只需继承注册，无需改动会话层
- **遵循软件工程规范**：单一职责、依赖倒置、面向接口、路径穿越防护、配置外置

## 目录结构

```
xAgent/
├── main.py                 # 入口：装配 core + 按 --ui 选择界面后端
├── requirements.txt        # 依赖：requests、textual、mcp（可选）
├── AGENT.md                # 长期规则示例（启动时自动读取并注入）
├── skills/
│   └── writing-summary/
│       └── SKILL.md        # 示例技能（YAML frontmatter + 正文）
├── core/                   # ── 业务核心层（与界面无关）──
│   ├── config.py           #   统一配置（环境变量）
│   ├── llm_client.py       #   大模型客户端（OpenAI 兼容 + SSE 流式）
│   ├── session.py          #   会话层：消息历史 + 模型↔工具循环 + 落盘 + 上下文裁剪
│   ├── agent_md.py         #   AGENT.md / AGENTS.md 读取与截断
│   ├── skills_manager.py   #   技能扫描、渐进加载、创建校验
│   ├── mcp_client.py       #   MCP 客户端桥接（stdio / HTTP），失败降级
│   └── tools/
│       ├── base.py         #   工具基类 BaseTool + 注册表 ToolRegistry
│       ├── file_ops.py     #   文件操作工具集（list/read/write/append/delete/info）
│       ├── time_tool.py    #   当前时间 + 闰年判定
│       ├── web_tool.py     #   网页读取 + 网络搜索
│       └── skill_tool.py   #   技能操作（list/read/create）
└── ui/                     # ── 界面层（可插拔）──
    ├── base.py             #   界面抽象基类 ChatUI（协议）
    ├── cli_ui.py           #   CLI 界面
    └── textual_ui.py       #   Textual TUI 界面
    # web_ui.py / desktop_ui.py 为预留，按 ChatUI 协议实现后即可接入
```

## 内置工具（13 个）

| 类别 | 工具 | 说明 |
| --- | --- | --- |
| 文件 | `list_files` | 列出工作目录，支持通配符 |
| 文件 | `read_file` | 读取文本文件 |
| 文件 | `write_file` | 写入（覆盖），自动建父目录 |
| 文件 | `append_file` | 追加（不存在则创建） |
| 文件 | `delete_file` | 删除文件（对目录显式拒绝） |
| 文件 | `get_file_info` | 文件大小与修改时间 |
| 时间 | `get_current_time` | 当前日期时间（跨平台，可选时区偏移） |
| 时间 | `is_leap_year` | 闰年判定（整百年需被 400 整除） |
| 联网 | `fetch_url` | 抓取静态网页正文（去标签 + 截断） |
| 联网 | `web_search` | 搜索引擎检索，返回标题/链接/摘要 |
| 技能 | `list_skills` | 列出技能名称与描述（不含正文） |
| 技能 | `read_skill` | 按需读取技能正文（12000 字上限） |
| 技能 | `create_skill` | 落盘 `skills/<name>/SKILL.md`，拒绝重名与非法命名 |

文件工具统一经 `_resolve` 做工作目录白名单校验，越界请求返回 `{"ok": false, "error": ...}`。

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

## 配置（全部走环境变量）

| 变量 | 默认 | 含义 |
| --- | --- | --- |
| `LLM_BASE_URL` | DashScope 兼容地址 | OpenAI 兼容接口地址 |
| `LLM_API_KEY` | 空（必填） | 接口 Key，缺失时启动即提示并退出 |
| `LLM_MODEL` | `qwen-plus` | 模型名 |
| `LLM_TIMEOUT` | `60` | 单次请求超时（秒） |
| `XAGENT_WORKDIR` | 当前目录 | 文件操作根目录（越界拒绝） |
| `XAGENT_MAX_TOOL_ROUNDS` | `8` | 单轮最大工具调用轮数 |
| `XAGENT_MAX_CONTEXT` | `24` | 上下文保留消息条数（超出后压缩旧消息） |
| `XAGENT_AGENT_MD` | 自动找 `AGENT.md`/`AGENTS.md` | 长期规则文件名 |
| `XAGENT_SKILLS_DIR` | `<workdir>/skills` | 技能目录 |
| `XAGENT_SESSION_DIR` | `<workdir>/sessions` | 会话落盘目录 |
| `XAGENT_MCP_SERVERS` | 空 | 外部 MCP server 的 JSON 数组配置 |

## 接入外部 MCP server

```bash
# stdio：本地子进程
export XAGENT_MCP_SERVERS='[{"name":"pet","transport":"stdio","command":"python","args":["-m","pet_hospital_mcp"]}]'

# HTTP：已在运行的 Streamable HTTP MCP 服务
export XAGENT_MCP_SERVERS='[{"name":"anythingllm","transport":"http","url":"http://127.0.0.1:8000/mcp"}]'
```

启动时逐个连接并 `tools/list`，外部工具以 `mcp__<server>__<tool>` 命名并入可调用集合，描述带 `[来自 MCP server <name>]` 来源标记；连接失败只会把 `failed: ...` 写进状态并注入系统提示，不阻塞主流程。

## 会话与上下文

- 每次回合结束后把 `messages` 落盘到 `sessions/session_<时间戳>.json`（含 `saved_at`/`model`）
- 历史消息超过 `XAGENT_MAX_CONTEXT` 时，把被裁掉的对话压成一条摘要消息，保留 system + 最近 N 条
- 工作目录下的 `AGENT.md` / `AGENTS.md` 在启动时读取一次（4000 字截断）作为长期规则注入系统提示

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
