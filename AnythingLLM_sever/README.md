# AnythingLLM 上传网页（upload.html）

一个**零构建、零后端**的单文件网页：选一个本地文件 → 上传到 AnythingLLM 文档库 → 加入第一个工作区并触发向量化嵌入。

- 技术栈：原生 HTML + CSS + JS（`fetch` / `FormData`），不依赖任何构建工具或 npm 包
- 文件：`upload.html`（唯一文件，直接双击用浏览器打开即可）

## 前置条件

1. 本地已运行 AnythingLLM（默认 `http://localhost:3001`），且已创建**至少一个工作区**
2. 在 AnythingLLM 里生成一个 API Key（Settings → API Keys）
3. 浏览器能直接访问该地址（页面由浏览器发起跨域请求，因此 AnythingLLM 需允许该来源）

## 使用步骤

1. 浏览器打开 `upload.html`
2. 「AnythingLLM API 地址」填 `http://localhost:3001/api`（末尾不要带 `/`，页面会自动去掉尾部斜杠）
3. 「API Key」粘贴你的 Key
4. 选择文件 → 点「上传并向量化」
5. 页面按 `1/3 获取工作区 → 2/3 上传文档 → 3/3 向量化嵌入` 输出进度，失败会在同一区域显示原因

## 调用流程与对应接口

| 步骤 | 接口 | 说明 |
| --- | --- | --- |
| 1 | `GET /v1/workspaces` | 取工作区列表，默认使用**第一个**工作区的 `slug` |
| 2 | `POST /v1/document/upload` | `FormData` 上传文件，从响应 `documents[0].location` 取文档路径 |
| 3 | `POST /v1/workspace/{slug}/update-embeddings` | 请求体 `{"adds":[docPath]}` 触发 embedding |

所有请求统一带 `Authorization: Bearer <Key>`。

## 配置项

| 项 | 默认 | 说明 |
| --- | --- | --- |
| API 地址 | `http://localhost:3001/api` | 保存在浏览器 `localStorage`（键 `anythingllm_api`） |
| API Key | 空 | 保存在 `localStorage`（键 `anythingllm_key`），**代码中不含任何 Key** |
| 目标工作区 | 列表第一个 | 如需指定工作区，改 `upload.html` 里取 `workspaces[0]` 的那一行 |

## 安全说明

- Key 只存在本机浏览器 `localStorage`，刷新后保留、不上传、不入库；仓库里没有明文 Key
- 所有输出走 `textContent` 写入，不做 HTML 拼接，避免接口返回内容造成的 XSS
- 页面本身不写任何文件，也不调用本机其他服务

## 常见失败原因

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `请先在上方填入 API Key` | Key 为空 | 粘贴 Key 后重试 |
| `Failed to fetch` | AnythingLLM 未启动，或跨域被拒 | 确认服务在 3001 端口；必要时在 AnythingLLM 侧放开 CORS |
| `没有可用的工作区` | AnythingLLM 里一个工作区都没建 | 先在 AnythingLLM 创建并加载工作区 |
| `HTTP 401` | Key 错误或已被撤销 | 重新生成 Key |
| `上传失败` | 文件类型/大小不被 AnythingLLM 支持 | 换受支持的格式或拆小文件 |
| 向量化步骤报错 | 未配置嵌入模型 | 在 AnythingLLM 里先完成 embedding 模型设置 |
