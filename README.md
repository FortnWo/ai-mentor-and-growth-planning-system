# AI 导师与成长规划系统

一个面向大学生与管理员的全栈导师平台，提供基于角色的访问控制、临时委托管理员权限，以及通过 OpenAI 兼容提供方实现的 AI 聊天支持。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3、Vue Router、TypeScript、Vite |
| 后端 | FastAPI、SQLAlchemy 2、Pydantic v2 |
| 数据库 | MySQL 8（或兼容实现） |
| AI 提供方 | OpenAI 兼容 API（通过环境变量配置） |

## 核心功能

- JWT 登录与前端会话恢复。
- 管理员管理用户全生命周期（创建 / 列表 / 更新 / 删除）。
- 学生账号约束：用户名必须是 10 位学号。
- 角色模型：`user` 与 `admin`。
- 委托管理员权限支持：
  - 完整管理员权限，或
  - 有限权限键与可选过期时间。
- 当前用户资料自助 API（`/profile/me`）。
- AI 聊天会话与消息历史。
- 非阻塞聊天流程：用户消息立即落库，助手回复在后台生成。
- 通过 WebSocket（`/ws`）推送助手实时更新，并提供轮询兜底。
- 明确的助手消息状态语义：`pending`、`completed`、`failed`。
- 后端 5xx 错误记录到 `backend/logs/error.log`。

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 20+
- MySQL 8+

### 1. 初始化数据库

```bash
mysql -u root -p < database/schema.sql
```

### 2. 启动后端

```bash
cd backend

python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt
cp .env.example .env

uvicorn app.main:app --reload --port 8000
```

Swagger UI：http://localhost:8000/docs

运行后端测试：

```bash
pip install -r requirements-dev.txt
pytest -q
```

### 3. 启动前端

```bash
cd frontend

npm install
cp .env.example .env

npm run dev
```

前端地址：http://localhost:5173

生产构建：

```bash
npm run build
```

## 环境变量

`backend/.env` 中的重要后端变量：

- `DATABASE_URL`：SQLAlchemy 连接串。
- `ALLOWED_ORIGINS`：CORS 的 JSON 数组，例如 `["http://localhost:5173"]`。
- `AUTH_SECRET_KEY`：JWT 签名密钥（生产环境必须更改）。
- `AUTH_ACCESS_TOKEN_EXPIRES_MINUTES`：令牌过期时间（分钟）。
- `LLM_API_KEY`、`LLM_API_BASE_URL`、`LLM_MODEL`、`LLM_SYSTEM_PROMPT`：AI 提供方配置。
- `RUN_LIVE_AI_TESTS`：设为 `1` 后启用真实 AI 集成测试。
- `GOAL_BREAKDOWN_ENABLED`：启用 / 禁用目标拆解生成接口。
- `ACTION_PLAN_ENABLED`：启用 / 禁用行动计划生成接口。
- `BOOTSTRAP_ADMIN_USERNAME`、`BOOTSTRAP_ADMIN_EMAIL`、`BOOTSTRAP_ADMIN_PASSWORD`、`BOOTSTRAP_ADMIN_FULL_NAME`：
  可选的启动初始化管理员；配置后，后端会在不存在时创建该管理员。

前端变量：

- `VITE_API_BASE_URL`：后端基础地址，默认 `http://localhost:8000`。
- `VITE_WS_BASE`：可选的 WebSocket 基础地址（用于开发 / 代理自定义）。

## 接口总览

### 公共接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/ping` | 健康检查 |
| POST | `/auth/login` | 登录并获取 JWT |

### 登录后接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/auth/me` | 获取当前用户 |
| GET | `/profile/me` | 获取我的资料 |
| PUT | `/profile/me` | 更新我的资料 |
| PATCH | `/profile/me/password` | 修改我的密码 |
| POST | `/chat` | 发送消息；立即返回会话和用户消息，助手回复异步生成 |
| GET | `/chat/sessions` | 列出当前登录用户的聊天会话 |
| GET | `/chat/{session_id}/messages` | 列出该会话的消息 |

### 成长规划（登录后）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/goals` | 创建目标并触发异步 AI 拆解 |
| GET | `/goals` | 列出当前用户的目标 |
| GET | `/goals/{goal_id}` | 获取带拆解树的目标详情 |
| PUT | `/goals/{goal_id}` | 更新目标元数据 |
| POST | `/goals/{goal_id}/refresh-breakdown` | 异步重新生成 AI 目标拆解 |
| DELETE | `/goals/{goal_id}` | 删除目标及相关拆解节点 |
| POST | `/action-plans` | 为某个目标创建或复用进行中的行动计划 |
| GET | `/action-plans` | 列出当前用户的行动计划 |
| GET | `/action-plans/{plan_id}` | 获取行动计划详情 |
| POST | `/action-plans/{plan_id}/refresh` | 异步刷新行动计划 |
| DELETE | `/action-plans/{plan_id}` | 删除行动计划 |
| GET | `/profile/extended/me` | 获取用户画像（缺失时自动创建） |
| PUT | `/profile/extended/me` | 更新用户画像 |
| POST | `/profile/extended/me/refresh-from-chat` | 根据聊天历史重建用户画像 |

### WebSocket

| 协议 | 路径 | 说明 |
| --- | --- | --- |
| WS | `/ws?token=<jwt>` | 用于推送正在输入 / 新助手消息的实时通道 |

典型推送事件：

- `typing`：`{ "type": "typing", "session_id": number, "message_id": number, "status": "pending" }`
- `new_message`：`{ "type": "new_message", "message": { "id": number, "session_id": number, "role": "assistant", "content": string, "status": "completed|failed", "created_at": string } }`

### 管理员专属

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/users` | 列出用户 |
| POST | `/admin/users` | 创建用户 / 管理员 |
| GET | `/admin/users/{user_id}` | 获取用户 |
| PUT | `/admin/users/{user_id}` | 更新用户 |
| DELETE | `/admin/users/{user_id}` | 删除用户 |
| PATCH | `/admin/users/{user_id}/admin-access` | 授予 / 更新管理员委托 |
| DELETE | `/admin/users/{user_id}/admin-access` | 撤销委托管理员权限 |

## 权限键

有限管理员当前可用的权限键：

- `user.read`
- `user.create`
- `user.update`
- `user.delete`
- `admin.grant`

## 项目结构

```text
ai-mentor-and-growth-planning-system/
├── backend/
│   ├── app/
│   │   ├── core/       # 配置、安全、数据库会话、启动初始化
│   │   ├── models/     # SQLAlchemy ORM 模型
│   │   ├── routers/    # FastAPI 路由处理器
│   │   ├── schemas/    # Pydantic DTO
│   │   ├── services/   # 业务服务（auth、user、chat）
│   │   └── main.py
│   └── tests/
├── frontend/
│   └── src/
│       ├── api/        # 类型化 API 封装
│       ├── stores/     # 认证会话存储
│       ├── router/     # 路由与守卫
│       └── views/      # 登录、聊天、资料、用户管理、计划
├── database/
│   └── schema.sql
└── docs/
    └── architecture.md
```

## 贡献说明

1. 遵循分层模式：routers -> services -> models / schemas。
2. 对行为变更和 RBAC 敏感路径补充测试。
3. 保持文档和环境变量模板与代码变更同步。
