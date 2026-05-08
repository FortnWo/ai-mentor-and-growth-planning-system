# AI Mentor & Growth Planning System

A full-stack mentoring platform for university students and admins, with role-based access control, temporary delegated admin permissions, and AI chat support through OpenAI-compatible providers.

## Stack

| Layer | Technology |
| --- | --- |
| Frontend | Vue 3, Vue Router, TypeScript, Vite |
| Backend | FastAPI, SQLAlchemy 2, Pydantic v2 |
| Database | MySQL 8 (or compatible) |
| AI Provider | OpenAI-compatible API (configured via environment variables) |

## Core Features

- JWT login and authenticated session restoration on frontend.
- Admin-managed user lifecycle (create/list/update/delete).
- Student account constraint: username must be a 10-digit student ID.
- Role model: `user` and `admin`.
- Delegated admin access with:
	- full admin scope, or
	- limited permission keys and optional expiry.
- Profile self-service APIs for current user (`/profile/me`).
- AI chat sessions and message history.
- Non-blocking chat flow: user message is persisted immediately, assistant reply is generated in background.
- Real-time assistant updates via WebSocket (`/ws`) with polling fallback.
- Explicit assistant message status semantics: `pending`, `completed`, `failed`.
- Backend 5xx error logging to `backend/logs/error.log`.

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- MySQL 8+

### 1. Initialize Database

```bash
mysql -u root -p < database/schema.sql
```

### 2. Start Backend

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

Swagger UI: http://localhost:8000/docs

Run backend tests:

```bash
pip install -r requirements-dev.txt
pytest -q
```

### 3. Start Frontend

```bash
cd frontend

npm install
cp .env.example .env

npm run dev
```

Frontend app: http://localhost:5173

Production build:

```bash
npm run build
```

## Environment Variables

Important backend variables in `backend/.env`:

- `DATABASE_URL`: SQLAlchemy DSN.
- `ALLOWED_ORIGINS`: JSON array for CORS, e.g. `["http://localhost:5173"]`.
- `AUTH_SECRET_KEY`: JWT signing key (must be changed in production).
- `AUTH_ACCESS_TOKEN_EXPIRES_MINUTES`: token expiry in minutes.
- `LLM_API_KEY`, `LLM_API_BASE_URL`, `LLM_MODEL`, `LLM_SYSTEM_PROMPT`: AI provider settings.
- `RUN_LIVE_AI_TESTS`: set to `1` to enable live AI integration tests.
- `GOAL_BREAKDOWN_ENABLED`: enable/disable goal breakdown generation APIs.
- `ACTION_PLAN_ENABLED`: enable/disable action plan generation APIs.
- `BOOTSTRAP_ADMIN_USERNAME`, `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD`, `BOOTSTRAP_ADMIN_FULL_NAME`:
	optional startup bootstrap admin. When set, backend creates this admin if it does not already exist.

Frontend variable:

- `VITE_API_BASE_URL`: backend base URL, default `http://localhost:8000`.
- `VITE_WS_BASE`: optional explicit WebSocket base URL (for dev/proxy customization).

## API Overview

### Public

| Method | Path | Description |
| --- | --- | --- |
| GET | `/ping` | Health check |
| POST | `/auth/login` | Login and receive JWT |

### Authenticated

| Method | Path | Description |
| --- | --- | --- |
| GET | `/auth/me` | Get current user |
| GET | `/profile/me` | Get my profile |
| PUT | `/profile/me` | Update my profile |
| PATCH | `/profile/me/password` | Change my password |
| POST | `/chat` | Send message; returns session + user message immediately, assistant reply is asynchronous |
| GET | `/chat/sessions` | List chat sessions for current authenticated user |
| GET | `/chat/{session_id}/messages` | List messages in session for current authenticated user |

### Growth Planning (Authenticated)

| Method | Path | Description |
| --- | --- | --- |
| POST | `/goals` | Create goal and trigger async AI breakdown |
| GET | `/goals` | List current user's goals |
| GET | `/goals/{goal_id}` | Get goal detail with breakdown tree |
| PUT | `/goals/{goal_id}` | Update goal metadata |
| POST | `/goals/{goal_id}/refresh-breakdown` | Re-run AI goal breakdown asynchronously |
| DELETE | `/goals/{goal_id}` | Delete goal and related breakdown nodes |
| POST | `/action-plans` | Create or reuse in-progress action plan for a goal |
| GET | `/action-plans` | List current user's action plans |
| GET | `/action-plans/{plan_id}` | Get action plan detail |
| POST | `/action-plans/{plan_id}/refresh` | Refresh action plan asynchronously |
| DELETE | `/action-plans/{plan_id}` | Delete action plan |
| GET | `/profile/extended/me` | Get extended profile (auto-create if missing) |
| PUT | `/profile/extended/me` | Update extended profile |
| POST | `/profile/extended/me/refresh-from-chat` | Rebuild extended profile from chat history |

### WebSocket

| Protocol | Path | Description |
| --- | --- | --- |
| WS | `/ws?token=<jwt>` | Real-time push for typing/new assistant messages |

Typical push event payloads:

- `typing`: `{ "type": "typing", "session_id": number, "message_id": number, "status": "pending" }`
- `new_message`: `{ "type": "new_message", "message": { "id": number, "session_id": number, "role": "assistant", "content": string, "status": "completed|failed", "created_at": string } }`

### Admin Only

| Method | Path | Description |
| --- | --- | --- |
| GET | `/admin/users` | List users |
| POST | `/admin/users` | Create user/admin |
| GET | `/admin/users/{user_id}` | Get user |
| PUT | `/admin/users/{user_id}` | Update user |
| DELETE | `/admin/users/{user_id}` | Delete user |
| PATCH | `/admin/users/{user_id}/admin-access` | Grant/update admin delegation |
| DELETE | `/admin/users/{user_id}/admin-access` | Revoke delegated admin |

## Permission Keys

For limited admins, current permission keys are:

- `user.read`
- `user.create`
- `user.update`
- `user.delete`
- `admin.grant`

## Project Structure

```text
ai-mentor-and-growth-planning-system/
├── backend/
│   ├── app/
│   │   ├── core/       # Config, security, DB session, bootstrap
│   │   ├── models/     # SQLAlchemy ORM models
│   │   ├── routers/    # FastAPI route handlers
│   │   ├── schemas/    # Pydantic DTOs
│   │   ├── services/   # Business services (auth, user, chat)
│   │   └── main.py
│   └── tests/
├── frontend/
│   └── src/
│       ├── api/        # Typed API wrappers
│       ├── stores/     # Auth session store
│       ├── router/     # Route + guards
│       └── views/      # Login, Chat, Profile, AdminUsers, Plan
├── database/
│   └── schema.sql
└── docs/
    └── architecture.md
```

## Contributing

1. Follow the layering pattern: routers -> services -> models/schemas.
2. Add tests for behavior changes and RBAC-sensitive paths.
3. Keep docs and env templates synchronized with code changes.
