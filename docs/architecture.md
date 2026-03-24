# Architecture Overview

## Stack

| Layer     | Technology                          |
|-----------|-------------------------------------|
| Frontend  | Vue 3 · Vite · TypeScript           |
| Backend   | FastAPI (Python 3.11+)              |
| Database  | MySQL 8 · SQLAlchemy 2 (ORM)        |
| API style | RESTful JSON                        |

## Directory Layout

```
ai-mentor-and-growth-planning-system/
├── backend/            # FastAPI application
│   ├── app/
│   │   ├── core/       # Config, DB session
│   │   ├── models/     # SQLAlchemy ORM models
│   │   ├── routers/    # FastAPI route handlers
│   │   ├── schemas/    # Pydantic request/response schemas
│   │   ├── services/   # Business-logic layer
│   │   └── main.py     # App factory & middleware
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── frontend/           # Vue 3 + Vite SPA
│   ├── src/
│   │   ├── api/        # Axios client + typed endpoint wrappers
│   │   ├── router/     # Vue Router routes
│   │   └── views/      # Page-level components
│   ├── package.json
│   └── .env.example
├── database/
│   └── schema.sql      # Initial MySQL DDL
└── docs/
    └── architecture.md # This file
```

## API Endpoints (boilerplate)

| Method | Path              | Description              |
|--------|-------------------|--------------------------|
| GET    | /ping             | Health check             |
| POST   | /chat             | Send a chat message      |
| GET    | /profile/{id}     | Get a user profile       |
| POST   | /profile          | Create a user profile    |
| PATCH  | /profile/{id}     | Update a user profile    |

## Data Flow

```
Browser (Vue 3)
    │  HTTP/JSON (axios)
    ▼
FastAPI  ──►  Service layer  ──►  SQLAlchemy ORM  ──►  MySQL
```

## Frontend Routes

| Path       | Component    |
|------------|--------------|
| /chat      | ChatView     |
| /profile   | ProfileView  |
| /plan      | PlanView     |
