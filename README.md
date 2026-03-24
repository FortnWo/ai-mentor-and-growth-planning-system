# AI Mentor & Growth Planning System

A full-stack platform that helps university students set goals, receive AI-powered mentoring advice, and track their personal growth.

## Stack

| Layer    | Technology                    |
|----------|-------------------------------|
| Frontend | Vue 3 · Vite · TypeScript     |
| Backend  | FastAPI (Python 3.11+)        |
| Database | MySQL 8 · SQLAlchemy 2        |
| API      | RESTful JSON                  |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- MySQL 8 (or a compatible server)

---

### 1. Database

```bash
mysql -u root -p < database/schema.sql
```

---

### 2. Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — set DATABASE_URL and other values

# Run the development server
uvicorn app.main:app --reload --port 8000
```

API docs are available at http://localhost:8000/docs once the server is running.

#### Run backend tests

```bash
pip install -r requirements-dev.txt
pytest
```

---

### 3. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env — set VITE_API_BASE_URL if your backend is on a different host/port

# Run the development server
npm run dev
```

The app is available at http://localhost:5173.

#### Build for production

```bash
npm run build
```

---

## Project Structure

```
ai-mentor-and-growth-planning-system/
├── backend/
│   ├── app/
│   │   ├── core/        # Config, DB session factory
│   │   ├── models/      # SQLAlchemy ORM models
│   │   ├── routers/     # FastAPI route handlers (/ping, /chat, /profile)
│   │   ├── schemas/     # Pydantic schemas
│   │   ├── services/    # Business-logic layer
│   │   └── main.py      # App factory & CORS middleware
│   ├── tests/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/         # Axios client + typed endpoint helpers
│   │   ├── router/      # Vue Router (chat, profile, plan)
│   │   └── views/       # ChatView, ProfileView, PlanView
│   ├── package.json
│   └── .env.example
├── database/
│   └── schema.sql       # Initial MySQL DDL
├── docs/
│   └── architecture.md  # Architecture overview
├── .gitignore
└── README.md            # This file
```

---

## API Endpoints

| Method | Path           | Description           |
|--------|----------------|-----------------------|
| GET    | /ping          | Health check          |
| POST   | /chat          | Send a chat message   |
| GET    | /profile/{id}  | Get a user profile    |
| POST   | /profile       | Create a user profile |
| PATCH  | /profile/{id}  | Update a user profile |

---

## Contributing

1. Fork the repository and create a feature branch.
2. Follow the existing code structure (routers → services → models).
3. Add or update tests for any new functionality.
4. Open a pull request with a clear description.
