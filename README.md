# DeepDive R&D — Backend API

FastAPI + MySQL backend for the DeepDive creator poll intelligence platform.

---

## Table of Contents
1. [Project Structure](#project-structure)
2. [Software Engineering Concepts Applied](#software-engineering-concepts-applied)
3. [Quick Start](#quick-start)
4. [API Reference](#api-reference)
5. [Frontend ↔ Backend Connection](#frontend--backend-connection)
6. [Frontend File Cleanup](#frontend-file-cleanup)
7. [Database Schema](#database-schema)

---

## Project Structure

```
deepdive-backend/
├── app/
│   ├── api/
│   │   ├── deps.py                  # Shared FastAPI dependencies (auth guard)
│   │   └── v1/
│   │       ├── router.py            # Aggregates all sub-routers under /api
│   │       └── endpoints/
│   │           ├── auth.py          # POST /api/auth/login, GET /api/auth/me
│   │           ├── polls.py         # Full Poll + Question CRUD
│   │           ├── votes.py         # Public fan-vote endpoints
│   │           └── analytics.py     # Insights summary + CSV export
│   ├── core/
│   │   ├── config.py                # Pydantic-settings, loaded from .env
│   │   └── security.py             # JWT mint/verify + bcrypt hashing
│   ├── db/
│   │   ├── base_class.py           # SQLAlchemy DeclarativeBase
│   │   ├── base.py                 # Imports all models for Alembic
│   │   ├── session.py              # Engine + SessionLocal + get_db()
│   │   └── init_db.py              # Table creation + first-user seed
│   ├── models/                      # SQLAlchemy ORM models (one per table)
│   │   ├── user.py
│   │   ├── poll.py
│   │   ├── question.py
│   │   ├── option.py
│   │   ├── vote.py
│   │   └── answer.py
│   ├── schemas/                     # Pydantic request/response schemas
│   │   ├── auth.py
│   │   ├── poll.py
│   │   └── analytics.py
│   ├── services/                    # Business logic layer (no HTTP concerns)
│   │   ├── auth_service.py
│   │   ├── poll_service.py
│   │   ├── vote_service.py
│   │   └── analytics_service.py
│   └── main.py                      # App factory + CORS + lifespan
├── alembic/                         # Database migration scripts
├── tests/
│   └── test_auth.py
├── requirements.txt
├── alembic.ini
└── .env.example
```

---

## Software Engineering Concepts Applied

### 1. Design Patterns

| Pattern | Where Used | Why |
|---|---|---|
| **Factory Method** | `app/main.py` — `create_app()` | Builds and configures the FastAPI app in a testable, isolated function rather than at module level |
| **Singleton** | `app/core/config.py` — `@lru_cache` on `get_settings()` | The `.env` file is read exactly once per process; all modules share the same `Settings` object |
| **Service Layer** | `app/services/*.py` | Separates business logic from HTTP transport; services can be unit-tested without FastAPI |
| **Repository (light)** | `poll_service.py`, `vote_service.py` | All DB queries are funnelled through the service, not scattered across endpoint handlers |
| **Facade** | `app/core/security.py` | Wraps `python-jose` (JWT) and `passlib` (bcrypt) behind a clean three-function API so the rest of the app is decoupled from those libraries |
| **Dependency Injection** | `app/api/deps.py` + `Depends()` everywhere | FastAPI resolves `get_db` and `get_current_user` automatically; endpoints declare *what* they need, not *how* to get it |
| **Unit of Work** | `app/db/session.py` — `get_db()` generator | Each HTTP request gets one Session; all writes commit or roll back as a single atomic unit |
| **Strategy** | `analytics_service.py` — filter switching | Cross-tab results switch strategy (all / long-format / Patreon) without changing the calling code |
| **Template Method** | `_compute_question_analytics` | The analytics computation skeleton is fixed; per-type result calculation varies by question type via branching |

---

### 2. SOLID Principles

| Principle | How It Is Applied |
|---|---|
| **S** — Single Responsibility | Every module has exactly one reason to change: `security.py` handles crypto, `config.py` handles env vars, each service handles one domain |
| **O** — Open/Closed | Adding a new question type only requires a new branch in `_compute_question_analytics`; callers are unchanged |
| **L** — Liskov Substitution | Pydantic `*Update` schemas are strict subsets of `*Create`; PATCH endpoints accept partial payloads without breaking contracts |
| **I** — Interface Segregation | Schemas are split: `LoginRequest`, `TokenResponse`, `UserOut` — each carries only what its endpoint needs |
| **D** — Dependency Inversion | Endpoint handlers depend on `get_db` and service singletons (abstractions), not on concrete `SessionLocal` or `AnalyticsService()` calls |

---

### 3. Other Engineering Practices

- **Docstrings on every function** — Google-style Args/Returns/Raises documentation on all public methods
- **Layered architecture** — HTTP → Router → Service → DB (one-way dependency flow)
- **Environment-based config** — No hardcoded credentials; everything in `.env`
- **Cascade deletes** — MySQL FK `ON DELETE CASCADE` ensures child rows are cleaned up automatically
- **Pool pre-ping** — Stale MySQL connections recycled automatically with `pool_pre_ping=True`
- **Migration-ready** — Alembic wired to the same metadata; run `alembic revision --autogenerate` for any model change
- **Test isolation** — Tests override `get_db` with an in-memory SQLite session; no MySQL needed for CI

---

## Quick Start

### Prerequisites
- Python 3.11+
- MySQL 8.0+ running locally
- Node 18+ (for the frontend)

### 1. Clone / place the backend

```bash
# Place the deepdive-backend/ folder at the same level as your frontend:
my-project/
├── deepdive-frontend/   ← your existing React project
└── deepdive-backend/    ← this folder
```

### 2. Create MySQL database

```sql
-- Run in MySQL Workbench or mysql CLI
CREATE DATABASE deepdive_rnd CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'deepdive'@'localhost' IDENTIFIED BY 'yourpassword';
GRANT ALL PRIVILEGES ON deepdive_rnd.* TO 'deepdive'@'localhost';
FLUSH PRIVILEGES;
```

### 3. Configure environment

```bash
cd deepdive-backend
cp .env.example .env
# Edit .env — set DATABASE_URL, SECRET_KEY, and FIRST_SUPERUSER_PASSWORD
```

**Minimum changes in `.env`:**
```
DATABASE_URL=mysql+pymysql://deepdive:yourpassword@localhost:3306/deepdive_rnd
SECRET_KEY=some-random-64-char-string-change-this
FIRST_SUPERUSER_EMAIL=you@yourdomain.com
FIRST_SUPERUSER_PASSWORD=strongpassword
```

### 4. Install dependencies and start

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Tables are auto-created on first start via init_db()
uvicorn app.main:app --reload --port 8000
```

API is now live at **http://localhost:8000**
Interactive docs at **http://localhost:8000/docs**

### 5. (Optional) Alembic migrations

```bash
# Generate a migration after changing a model:
alembic revision --autogenerate -m "describe your change"
alembic upgrade head
```

### 6. Run tests

```bash
pip install pytest httpx
pytest tests/ -v
```

---

## API Reference

All creator endpoints require `Authorization: Bearer <token>`.
Fan-vote endpoints (`/api/vote/*`) are public.

```
POST   /api/auth/login                    Login → JWT
GET    /api/auth/me                       Current creator profile
POST   /api/auth/refresh                  Refresh JWT

GET    /api/polls                         List all polls (creator)
POST   /api/polls                         Create poll + questions
GET    /api/polls/{id}                    Get poll detail
PATCH  /api/polls/{id}                    Update poll
DELETE /api/polls/{id}                    Delete poll
POST   /api/polls/{id}/publish            Draft → Active
POST   /api/polls/{id}/close              Active → Closed

GET    /api/polls/{id}/questions          List questions
POST   /api/polls/{id}/questions          Add question
PATCH  /api/polls/{id}/questions/{qid}    Update question
DELETE /api/polls/{id}/questions/{qid}    Delete question
POST   /api/polls/{id}/questions/reorder  Reorder questions

GET    /api/vote/{poll_id}                Public poll (fan page)
POST   /api/vote/{poll_id}                Submit vote (fan page)

GET    /api/analytics/{id}/summary        Full Insights payload
GET    /api/analytics/{id}/export         Download CSV
```

---

## Frontend ↔ Backend Connection

### Step 1 — Vite proxy (already correct, no changes needed)

Your `vite.config.js` needs this proxy so `/api/*` calls go to the FastAPI server:

```js
// vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': '/src' },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

### Step 2 — Disable mock mode

In **three frontend files**, change `USE_MOCK = true` → `false`:

#### `src/context/PollContext.jsx`  (line 9)
```js
// BEFORE
const USE_MOCK = true

// AFTER
const USE_MOCK = false
```

#### `src/pages/FanVote.jsx`  (line 6)
```js
// BEFORE
const USE_MOCK = true

// AFTER
const USE_MOCK = false
```

### Step 3 — Login flow

The `client.js` already stores the token under `dd_token` and attaches it as
`Authorization: Bearer <token>` on every request.  You need a login page (or
a temporary call) to obtain the token first:

```js
// Quick test in browser console after starting both servers:
const resp = await fetch('/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: 'you@yourdomain.com', password: 'strongpassword' })
})
const { access_token } = await resp.json()
localStorage.setItem('dd_token', access_token)
// Now reload the app — the dashboard should load real data
```

### Step 4 — Fan vote URL format

Fan vote URLs use the numeric poll ID, e.g.:
```
http://localhost:5173/vote/1
```

The backend's `share_url` is set automatically on poll creation.

---

## Frontend File Cleanup

The following lines/sections in your frontend are **mock-only** and should be
removed or disabled once the backend is live:

### `src/api/mockData.js`
**Action: Delete the entire file** once `USE_MOCK = false` everywhere.
It is only referenced by the three `USE_MOCK` branches.

### `src/context/PollContext.jsx`
Remove these lines after going live:
```js
// DELETE these imports:
import { MOCK_POLLS, MOCK_POLL_DETAIL, MOCK_ANALYTICS } from '@/api/mockData'

// DELETE this constant:
const MOCK_DELAY = 400

// DELETE this helper:
const delay = (ms) => new Promise((r) => setTimeout(r, ms))
```
Also remove all `if (USE_MOCK) { ... await delay(MOCK_DELAY) ... }` branches,
keeping only the `else { ... }` body in each function.

### `src/pages/FanVote.jsx`
```js
// DELETE:
import { MOCK_POLL_DETAIL } from '@/api/mockData'
const delay = (ms) => new Promise(r => setTimeout(r, ms))
```
Remove the `if (USE_MOCK)` block in `useEffect` (load) and `handleSubmit`, keeping only the `else` body.

### `src/pages/Dashboard.jsx`
```js
// REPLACE:
import { MOCK_CREATOR } from '@/api/mockData'
const creator = MOCK_CREATOR

// WITH a real fetch from /api/auth/me, e.g. via a useEffect + authApi.me()
// Or keep it static if you don't need live creator stats on the dashboard
```

### `src/api/client.js`
The `client.js` file is **production-ready as-is**. No changes needed.

### `src/pages/Insights.jsx`
The hardcoded `"Q3 Deep Dive Topics"` title in the `PageHeader` should use
`analytics?.poll_title` once the backend adds that field, or fetch the poll
title separately. This is cosmetic — the charts all work from live data.

---

## Database Schema

```
users
  id PK | email UNIQUE | hashed_password | name | channel | plan
  avatar_initials | is_active | created_at

polls
  id PK | owner_id FK→users | title | description | status
  share_url | created_at | closes_at

questions
  id PK | poll_id FK→polls | order | type | text | required

options
  id PK | question_id FK→questions | order | text

votes
  id PK | poll_id FK→polls | platform | submitted_at

answers
  id PK | vote_id FK→votes | question_id FK→questions | value TEXT
```

All FK relationships use `ON DELETE CASCADE`.
