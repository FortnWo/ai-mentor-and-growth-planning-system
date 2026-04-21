# Architecture Overview

## Technology Stack

| Layer | Technology |
| --- | --- |
| Frontend | Vue 3, TypeScript, Vue Router, Axios, Vite |
| Backend | FastAPI, SQLAlchemy 2, Pydantic v2, Passlib, PyJWT |
| Database | MySQL 8 |
| AI Integration | OpenAI SDK with provider-compatible base URL |

## High-Level Design

```text
Vue SPA
    -> API wrappers (src/api)
    -> Axios client with bearer interceptor
    -> FastAPI routers
    -> Service layer (auth/user/chat)
    -> SQLAlchemy models
    -> MySQL
```

The backend follows a layered approach:

- Routers: request parsing, response models, HTTP error mapping.
- Services: business rules, validation, authorization-sensitive logic.
- Models: persistence entities.
- Schemas: request/response contracts.
- Core: config, db wiring, JWT/password utilities, bootstrap initialization.

## Backend Modules

### Core

- `app/core/config.py`: environment-driven settings.
- `app/core/database.py`: engine, session, declarative base.
- `app/core/security.py`: password hashing, JWT create/decode, auth dependencies.
- `app/core/bootstrap.py`: optional startup admin bootstrap.

### Services

- `app/services/auth_service.py`: login flow and token response assembly.
- `app/services/user_service.py`: user CRUD, profile update, password update, admin delegation logic.
- `app/services/chat_service.py`: session/message persistence and LLM interaction.

### Routers

- `app/routers/health.py`: health endpoint.
- `app/routers/auth.py`: login and current-user endpoint.
- `app/routers/profile.py`: current-user profile endpoints.
- `app/routers/user.py`: admin-only user management and delegation endpoints.
- `app/routers/chat.py`: chat send/list endpoints.

## Authentication and RBAC

- JWT bearer authentication for protected endpoints.
- User roles:
    - `user`: regular student account.
    - `admin`: privileged account.
- Admin permission model:
    - `full`: unrestricted admin actions.
    - `limited`: scoped by permission keys.
- Permission keys used by admin routes:
    - `user.read`
    - `user.create`
    - `user.update`
    - `user.delete`
    - `admin.grant`
- Delegation can be configured with optional expiry timestamp.

## Domain Rules

- Student account usernames must match a 10-digit ID pattern.
- Student accounts cannot be created with admin permissions.
- Limited admins must have at least one permission key.

## API Surface

### Public

- `GET /ping`
- `POST /auth/login`

### Authenticated

- `GET /auth/me`
- `GET /profile/me`
- `PUT /profile/me`
- `PATCH /profile/me/password`
- `POST /chat`
- `GET /chat/sessions`
- `GET /chat/{session_id}/messages`

### Admin-only

- `GET /admin/users`
- `POST /admin/users`
- `GET /admin/users/{user_id}`
- `PUT /admin/users/{user_id}`
- `DELETE /admin/users/{user_id}`
- `PATCH /admin/users/{user_id}/admin-access`
- `DELETE /admin/users/{user_id}/admin-access`

## Frontend Routing and Guards

- `/login`: guest-only.
- `/chat`, `/profile`, `/plan`: requires login.
- `/admin/users`: requires login and admin role.
- Route guard restores auth state from local storage and validates `/auth/me` when needed.

## Startup Lifecycle

FastAPI uses a lifespan hook to:

1. create database tables (if missing),
2. run bootstrap admin creation if bootstrap env vars are configured.

This keeps local/dev startup consistent and avoids deprecated startup event hooks.
