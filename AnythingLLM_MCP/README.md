# AnythingLLM MCP Server

基于 MCP 协议 2026-07-28 的 MCP Server，通过 Streamable HTTP 传输访问本机 AnythingLLM。

## 工具清单（3 类能力）

| 工具 | 类别 | 作用 |
|---|---|---|
| `ask_first_workspace(question)` | 对话问答 | 向第一个工作区提问，返回 AI 回答 |
| `list_workspace_files()` | 工作区管理 | 列出所有工作区及其文档 |
| `upload_document(file_path)` | 文档管理 | 上传本地文件到 AnythingLLM 文档库 |
| `add_document_to_workspace(doc_location, workspace_slug?)` | 文档向量化 | 把已上传文档加入工作区并触发 embedding |

## 配置（不硬编码）

复制 `.env.example` 为 `.env`，或直接设置环境变量：

```powershell
$env:ANYTHINGLLM_BASE_URL = "http://localhost:3001/api"
$env:ANYTHINGLLM_API_KEY  = "你的真实Key"
```

未设置 `ANYTHINGLLM_API_KEY` 时，程序启动即报错退出。

## 启动 / 停止

```powershell
pip install -r requirements.txt
python server.py
```

MCP 端点：`http://127.0.0.1:8000/mcp`（Streamable HTTP）。

## 项目级 MCP 配置

`.trae/mcp.json` 需手动添加：

```json
{
  "mcpServers": {
    "anythingllm": {
      "type": "streamableHttp",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

## 验证

```powershell
python test_client.py
```

预期输出：协议版本 `2026-07-28`、工具列表含上述 4 个工具、以及 AnythingLLM 的回答。
