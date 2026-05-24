# 前端（Vue 3 + TypeScript）

这是 AI Mentor 平台的单页应用前端。它连接 FastAPI 后端，提供登录认证、资料管理、聊天交互以及管理员用户管理功能。

## 技术栈

- Vue 3，使用 `<script setup>`
- TypeScript（严格模式）
- Vue Router
- Axios
- Vite

## 本地运行

```bash
npm install
cp .env.example .env
npm run dev
```

应用地址：http://localhost:5173

## 构建

```bash
npm run build
```

## 环境变量

- `VITE_API_BASE_URL`：后端基础地址，默认 `http://localhost:8000`。

## 页面

- `/login`：登录表单。
- `/chat`：AI 聊天会话和消息。
- `/profile`：当前用户资料和密码更新。
- `/plan`：成长规划占位页面。
- `/admin/users`：仅管理员可用的用户管理和权限委托页面。

## 认证与路由守卫

- JWT 令牌存储在 localStorage 中。
- Axios 请求拦截器会自动注入 `Authorization: Bearer <token>`。
- 路由守卫会限制：
	- `/login` 仅游客可访问
	- 主要页面仅登录用户可访问
	- `/admin/users` 仅管理员可访问

## API 模块结构

- `src/api/client.ts`：已配置的 Axios 实例和认证头注入。
- `src/api/auth.ts`：登录和当前用户接口。
- `src/api/profile.ts`：资料和密码接口。
- `src/api/user.ts`：管理员用户接口。
- `src/api/chat.ts`：聊天会话和消息接口。

## 说明

- 前端依赖本仓库中已实现的后端 RBAC 和资料接口。
- 如果后端基础地址变化，请更新 `.env` 并重启 Vite。

## 图表（echarts）

- 本项目在 `GrowthRecordsView.vue` 等视图中使用 `echarts` 进行可视化展示。
- 在启动开发服务器前，请先在前端目录安装该依赖：

```bash
cd frontend
npm install echarts
```

- 如果你的环境使用 SSR，或者遇到类似 “Failed to resolve import \"echarts\"” 的导入解析错误，请优先使用动态客户端导入（本代码库已经采用这种模式）。如果需要强制 Vite 在 SSR 中预打包或包含 echarts，请在 `vite.config.ts` 中加入如下配置：

```ts
export default defineConfig({
	// ...
	optimizeDeps: { include: ['echarts'] },
	ssr: { noExternal: ['echarts'] },
})
```

这样可以确保 Vite 在开发环境和 SSR 构建中都能正确处理 `echarts`。
