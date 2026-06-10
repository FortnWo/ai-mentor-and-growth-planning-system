# Frontend (Vue 3 + TypeScript)

This frontend is the SPA for the AI Mentor platform. It connects to the FastAPI backend and provides authentication, profile management, AI chat, growth planning, growth records, and admin tooling.

## Tech

- Vue 3 with `<script setup>`
- TypeScript (strict)
- Vue Router
- Axios
- Vite
- ECharts (growth trends and admin usage charts)

## Run Locally

```bash
npm install
cp .env.example .env
npm run dev
```

App URL: http://localhost:5173

## Build

```bash
npm run build
```

## Environment Variables

- `VITE_API_BASE_URL`: backend base URL, default `http://localhost:8000`.
- `VITE_WS_BASE` (optional): WebSocket base URL override for dev/proxy setups.

## Pages

| Route | Description |
| --- | --- |
| `/login` | Login form |
| `/forgot-password` | Password reset via SMS or email verification |
| `/home` | Authenticated landing page (default after login) |
| `/chat` | AI chat sessions and messages |
| `/info` | Current-user identity info and password updates |
| `/profile` | Structured user portrait (interests, skills, goals, etc.) |
| `/plan` | Goals, breakdown tree, and action plans |
| `/growth` | Growth records, stats, trends, and weekly summaries |
| `/admin/users` | Admin user management and privilege delegation |
| `/admin/users/:userId/usage` | Per-user AI usage stats (full admin only) |
| `/admin/system` | System config: AI, LLM presets, notify, rate limits, logs (full admin only) |

## Auth and Route Guards

- JWT token is stored in local storage.
- Axios request interceptor injects `Authorization: Bearer <token>`.
- Route guards enforce:
  - guest-only access for `/login` and `/forgot-password`
  - authenticated access for main pages
  - admin access for `/admin/users` (requires `user.read` permission or full admin)
  - full-admin-only access for `/admin/system` and `/admin/users/:userId/usage`
- Full admins are redirected to `/admin/users` after login; regular users go to `/home`.

## API Module Layout

- `src/api/client.ts`: configured Axios instance + auth header injection.
- `src/api/auth.ts`: login and current-user endpoints.
- `src/api/passwordReset.ts`: forgot-password flow.
- `src/api/info.ts`: identity info and password endpoints.
- `src/api/profile.ts`: user portrait endpoints.
- `src/api/chat.ts`: chat sessions, messages, and stop-generation.
- `src/api/goals.ts`: goals and breakdown.
- `src/api/actionPlans.ts`: action plans and item updates.
- `src/api/growthRecords.ts`: growth records, stats, and summaries.
- `src/api/user.ts`: admin user endpoints (including bulk import).
- `src/api/adminSystem.ts`: admin system config and logs.

## Notes

- The frontend expects backend RBAC, profile, planning, and UKL-related endpoints implemented in this repository.
- If backend base URL changes, update `.env` and restart Vite.
