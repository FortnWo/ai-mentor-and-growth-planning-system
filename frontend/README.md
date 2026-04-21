# Frontend (Vue 3 + TypeScript)

This frontend is the SPA for the AI Mentor platform. It connects to the FastAPI backend and provides authentication, profile management, chat interactions, and admin user management.

## Tech

- Vue 3 with `<script setup>`
- TypeScript (strict)
- Vue Router
- Axios
- Vite

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

## Environment Variable

- `VITE_API_BASE_URL`: backend base URL, default `http://localhost:8000`.

## Pages

- `/login`: login form.
- `/chat`: AI chat sessions and messages.
- `/profile`: current-user profile and password updates.
- `/plan`: growth planning placeholder page.
- `/admin/users`: admin-only user management and privilege delegation.

## Auth and Route Guards

- JWT token is stored in local storage.
- Axios request interceptor injects `Authorization: Bearer <token>`.
- Route guards enforce:
	- guest-only access for `/login`
	- authenticated access for main pages
	- admin-only access for `/admin/users`

## API Module Layout

- `src/api/client.ts`: configured Axios instance + auth header injection.
- `src/api/auth.ts`: login and current-user endpoints.
- `src/api/profile.ts`: profile and password endpoints.
- `src/api/user.ts`: admin user endpoints.
- `src/api/chat.ts`: chat sessions and messages.

## Notes

- The frontend expects backend RBAC and profile endpoints implemented in this repository.
- If backend base URL changes, update `.env` and restart Vite.
