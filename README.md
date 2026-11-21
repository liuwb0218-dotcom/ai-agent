# AI 智能客服 Agent

基于 FastAPI + LangChain 的智能客服 Agent，支持意图识别、Function Calling 工具调用、多轮对话与会话记忆。

## 功能特性
- **用户体系**：注册/登录（JWT）、个人资料与头像、多角色（管理员/普通用户）、管理后台
- **会话隔离**：聊天会话按用户隔离（Redis key 绑定 user_id）
- **意图识别**：规则关键词快路径 + LLM 兜底，三分类 `tool / knowledge / chat`
- **工具调用**：查天气（和风天气/内置演示）、查库存、查订单、四则运算（`ast` 安全求值）
- **多轮对话**：会话上下文窗口（条数 + token 预算双重限制），Redis 会话记忆（含内存降级）
- **知识库路由**：内置本地 RAG（bge-small-zh-v1.5 向量化 + FAISS 检索），`knowledge` 意图直接基于知识库回答
- **可观测**：JSON 行日志（耗时 / token / 工具链指标）
- **前端**：原生 HTML/CSS/JS 聊天界面，深色/浅色主题

## 技术栈
- 后端：Python 3.10+ / FastAPI / Uvicorn
- AI：LangChain 1.x / ChatOpenAI（OpenAI 或 Ollama 本地模型）
- 存储：Redis 5.x（RESP2），会话记忆
- 外部服务：和风天气 QWeather（可选）；知识库为内置本地 RAG，无需外部服务

## 项目结构
```
app/
  main.py             # FastAPI 入口
  api/                # 路由层（chat / conversations / health / tools）
  core/               # 配置与日志
  models/schemas.py   # Pydantic 模型
  services/           # 业务层（intent / llm / chat_service / rag / weather）
  storage/            # Redis 客户端与会话存储
  tools/              # 工具实现与注册表
  static/             # 前端页面
scripts/              # 分阶段验证与演示脚本
tests/                # pytest 单元测试
docs/                 # 接口 / 数据库 / 配置部署文档
```

## 快速开始
1. 安装依赖：`pip install -r requirements.txt`（建议虚拟环境）
2. 配置：复制 `.env.example` 为 `.env` 并修改（含 MySQL 连接与 JWT 密钥）
3. 初始化数据库：`python -m alembic upgrade head`，然后 `python scripts/seed_admin.py`（默认 admin / admin123456）
4. 启动依赖：Redis（127.0.0.1:6379）、Ollama（11434，先 `ollama pull qwen2.5:3b`）
5. 启动服务：`.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8082`
6. 验证：浏览器访问 `http://127.0.0.1:8082`，注册/登录后使用；管理后台 `http://127.0.0.1:8082/admin.html`

## API 一览
| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/register` `/api/auth/login` | 注册 / 登录 |
| GET/PUT | `/api/auth/me` | 当前用户 / 修改资料 |
| PUT/POST | `/api/auth/password` `/api/auth/avatar` | 改密码 / 上传头像 |
| GET/PATCH/DELETE | `/api/admin/users...` | 用户管理（admin） |
| POST | `/api/chat` | 多轮对话（需登录，knowledge 意图自动检索本地知识库） |
| GET/POST/DELETE | `/api/admin/knowledge/documents...` | 知识库管理（admin，列表/上传/删除） |
| GET/DELETE | `/api/conversations/{session_id}` | 会话历史 / 清除（本人） |
| GET | `/health` | 健康检查（Redis/Ollama） |
| GET | `/api/tools` | 工具注册表 |

详细参数见 `docs/接口文档.docx`。

## 测试
```powershell
.venv\Scripts\python.exe -m pytest tests -v
```
覆盖：意图识别、工具实现（计算器安全/库存/订单）、上下文窗口、工具注册表、会话存储、用户模块（密码哈希/JWT/权限）。

## 文档
- `docs/接口文档.docx` — 接口规范与变更日志
- `docs/数据库设计.docx` — 存储结构与变更日志
- `docs/配置与部署.docx` — 环境变量 / 部署 / 依赖
