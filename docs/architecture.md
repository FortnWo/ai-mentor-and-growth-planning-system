# 架构总览

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3、TypeScript、Vue Router、Axios、Vite |
| 后端 | FastAPI、SQLAlchemy 2、Pydantic v2、Passlib、PyJWT |
| 数据库 | MySQL 8 |
| AI 集成 | 使用 OpenAI SDK 和兼容提供方基础地址 |

## 高层设计

```text
Vue SPA
    -> API wrappers (src/api)
    -> Axios client with bearer interceptor
    -> WebSocket channel (/ws) for push events
    -> FastAPI routers
    -> Service layer (auth/user/chat)
    -> SQLAlchemy models
    -> MySQL
```

后端采用分层设计：

- Routers：请求解析、响应模型、HTTP 错误映射。
- Services：业务规则、校验、与权限敏感逻辑。
- Models：持久化实体。
- Schemas：请求 / 响应契约。
- Core：配置、数据库连接、JWT / 密码工具、启动初始化。

## 后端模块

### Core

- `app/core/config.py`：由环境变量驱动的配置。
- `app/core/database.py`：引擎、会话、声明式基类。
- `app/core/security.py`：密码哈希、JWT 创建 / 解析、认证依赖。
- `app/core/bootstrap.py`：可选的启动管理员初始化。
- `app/core/ws_manager.py`：内存型 WebSocket 连接管理器（按用户连接）。

### Services

- `app/services/auth_service.py`：登录流程与令牌响应组装。
- `app/services/user_service.py`：用户增删改查、资料更新、密码更新、管理员委托逻辑。
- `app/services/chat_service.py`：会话 / 消息持久化、后台 LLM 交互、消息状态序列化与 WebSocket 通知。

### Routers

- `app/routers/health.py`：健康检查接口。
- `app/routers/auth.py`：登录与当前用户接口。
- `app/routers/profile.py`：当前用户资料接口。
- `app/routers/user.py`：管理员专属的用户管理与委托接口。
- `app/routers/chat.py`：聊天发送 / 列表接口（绑定 JWT 用户身份）。
- `app/routers/ws.py`：用于实时聊天更新的 WebSocket 接口。

## 聊天交付流程

1. `POST /chat` 同步持久化用户消息并立即返回。
2. 后台任务创建助手占位消息（`pending`）并启动心跳推送。
3. LLM 在后台生成完成后，会更新同一条助手记录为最终内容。
4. 后端通过 WebSocket 推送 `new_message`，前端替换占位内容。

消息状态语义：

- `pending`：尚未完成的助手占位消息。
- `completed`：助手回复生成成功。
- `failed`：助手生成失败，已保存兜底错误文本。

## 认证与 RBAC

- 受保护接口使用 JWT Bearer 认证。
- 用户角色：
  - `user`：普通学生账号。
  - `admin`：管理员账号。
- 管理员权限模型：
  - `full`：不受限制的管理员操作。
  - `limited`：由权限键限定范围。
- 管理员路由使用的权限键：
  - `user.read`
  - `user.create`
  - `user.update`
  - `user.delete`
  - `admin.grant`
- 委托权限可配置可选过期时间。

## 领域规则

- 学生账号用户名必须匹配 10 位数字学号。
- 学生账号不能创建为管理员权限。
- 有限管理员至少需要一个权限键。

## 接口面

### 公共接口

- `GET /ping`
- `POST /auth/login`

### 登录后接口

- `GET /auth/me`
- `GET /profile/me`
- `PUT /profile/me`
- `PATCH /profile/me/password`
- `POST /chat`
- `GET /chat/sessions`
- `GET /chat/{session_id}/messages`

### 实时接口

- `WS /ws?token=<jwt>`

### 管理员专属接口

- `GET /admin/users`
- `POST /admin/users`
- `GET /admin/users/{user_id}`
- `PUT /admin/users/{user_id}`
- `DELETE /admin/users/{user_id}`
- `PATCH /admin/users/{user_id}/admin-access`
- `DELETE /admin/users/{user_id}/admin-access`

## 前端路由与守卫

- `/login`：仅游客可访问。
- `/chat`、`/profile`、`/plan`：需要登录。
- `/admin/users`：需要登录且具备管理员角色。
- 路由守卫会从本地存储恢复认证状态，并在需要时校验 `/auth/me`。

## 启动生命周期

FastAPI 使用 lifespan 钩子来：

1. 创建数据库表（如果缺失），
2. 在配置了初始化环境变量时创建 bootstrap 管理员，
3. 将主 asyncio 事件循环挂到 websocket 管理器上，以便跨线程调度推送。

这能保持本地 / 开发启动一致，并避免使用已弃用的 startup 事件钩子。
