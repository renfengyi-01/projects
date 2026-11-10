"""AnythingLLM MCP Server (MVP) - MCP 协议 2026-07-28, Streamable HTTP 传输

能力覆盖（3 类）：
  1) 工作区管理：list_workspaces / list_workspace_files
  2) 对话问答：ask_first_workspace
  3) 文档上传与向量化：upload_document / add_document_to_workspace

配置（全部走环境变量，不硬编码）：
  ANYTHINGLLM_BASE_URL   默认 http://localhost:3001/api
  ANYTHINGLLM_API_KEY    必填，缺失时启动即报错
"""
from __future__ import annotations

import os
import sys

import httpx
from mcp.server.mcpserver import MCPServer

BASE_URL = os.getenv("ANYTHINGLLM_BASE_URL", "http://localhost:3001/api").rstrip("/")
API_KEY = os.getenv("ANYTHINGLLM_API_KEY", "").strip()

if not API_KEY:
    print("错误：未设置 ANYTHINGLLM_API_KEY 环境变量。", file=sys.stderr)
    sys.exit(1)

HEADERS = {"Authorization": f"Bearer {API_KEY}"}
_TIMEOUT = 120.0

mcp = MCPServer("anythingllm")


def _get(path: str) -> dict:
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.get(f"{BASE_URL}{path}", headers=HEADERS)
        resp.raise_for_status()
        return resp.json()


def _post(path: str, json_body: dict | None = None, files=None, data=None) -> dict:
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(f"{BASE_URL}{path}", headers=HEADERS,
                           json=json_body, files=files, data=data)
        resp.raise_for_status()
        return resp.json()


def _first_workspace_slug() -> str:
    workspaces = _get("/v1/workspaces").get("workspaces", [])
    if not workspaces:
        raise RuntimeError("没有任何工作区")
    return workspaces[0]["slug"]


@mcp.tool()
def ask_first_workspace(question: str) -> str:
    """向 AnythingLLM 第一个工作区提问，返回 AI 回答（对话检索类）。"""
    slug = _first_workspace_slug()
    resp = _post(f"/v1/workspace/{slug}/chat",
                 json_body={"message": question, "mode": "chat"})
    if resp.get("error"):
        return f"错误：{resp['error']}"
    return resp.get("textResponse", "（无回答）")


@mcp.tool()
def list_workspace_files() -> str:
    """列出所有 AnythingLLM 工作区及其包含的文件（工作区管理类）。"""
    workspaces = _get("/v1/workspaces").get("workspaces", [])
    if not workspaces:
        return "错误：没有任何工作区"
    lines, total = [], 0
    for ws in workspaces:
        detail = _get(f"/v1/workspace/{ws['slug']}")
        docs = (detail.get("workspace") or [{}])[0].get("documents", [])
        total += len(docs)
        lines.append(f"工作区「{ws['name']}」：{len(docs)} 个文件")
        for doc in docs:
            path = doc.get("docpath") or doc.get("filename") or str(doc)
            lines.append(f"  - {path}")
    lines.append(f"总计：{total} 个文件")
    return "\n".join(lines)


@mcp.tool()
def upload_document(file_path: str) -> str:
    """上传本地文件到 AnythingLLM 文档库（文档管理类）。返回文档 location，供 add_document_to_workspace 使用。"""
    if not os.path.isfile(file_path):
        return f"错误：文件不存在 {file_path}"
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        resp = _post("/v1/document/upload",
                     files={"file": (filename, f, "application/octet-stream")})
    if not resp.get("success"):
        return f"错误：{resp.get('error', '上传失败')}"
    docs = resp.get("documents", [])
    if not docs:
        return "错误：上传成功但未返回文档路径"
    return f"已上传: {docs[0].get('location')}"


@mcp.tool()
def add_document_to_workspace(doc_location: str, workspace_slug: str = "") -> str:
    """把已上传的文档加入指定工作区并触发向量化嵌入（文档向量化类）。"""
    slug = workspace_slug or _first_workspace_slug()
    resp = _post(f"/v1/workspace/{slug}/update-embeddings",
                 json_body={"adds": [doc_location], "deletes": []})
    if resp.get("error"):
        return f"错误：{resp['error']}"
    return f"已将文档 {doc_location} 加入工作区 {slug} 并向量化。"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
