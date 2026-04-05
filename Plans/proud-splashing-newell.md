# Plan: Docker Compose + Professional Web Dashboard for Classifier

## Context

The classifier is a CLI tool with 16 vendor modules for URL categorization and reputation checking. We need to wrap it in a professional web dashboard with:
- Domain asset management
- Real-time status monitoring across all vendors
- Re-query and re-submission triggers from the UI
- Category configuration per domain
- Multi-user authentication
- Dark/light theme toggle
- Full Docker Compose containerization

---

## Tech Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| Backend | **FastAPI** | Same Python ecosystem, native async, WebSocket, auto-docs |
| Database | **PostgreSQL 16** | Relational data, concurrent writes, JSONB for raw responses |
| Task Queue | **Celery + Redis** | Isolated browser-per-task, fan-out, state tracking |
| Frontend | **React 18 + Vite + TailwindCSS + shadcn/ui** | Interactive matrix view, real-time updates, component composition |
| Real-time | **WebSocket via Redis pub/sub** | Push vendor results as they complete |
| Auth | **JWT + bcrypt** | Multi-user with role support (admin/viewer) |
| Theme | **Dark/Light toggle** via TailwindCSS dark mode |
| Containers | **5 services** via Docker Compose |

---

## Container Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Docker Compose Stack                   │
│                                                         │
│  ┌──────────────┐     ┌──────────────┐                  │
│  │   frontend   │     │  web (API)   │                  │
│  │  nginx :80   │────▶│ FastAPI :8000│                  │
│  │  React build │     │ REST + WS    │                  │
│  └──────────────┘     └──────┬───────┘                  │
│                              │                          │
│                       ┌──────┴───────┐                  │
│                       │  redis :6379 │                  │
│                       │ Broker+PubSub│                  │
│                       └──────┬───────┘                  │
│                              │                          │
│  ┌──────────────┐     ┌──────┴───────┐                  │
│  │   postgres   │     │    worker    │                  │
│  │    :5432     │     │ Celery+Chrome│                  │
│  │  persistent  │     │ Xvfb, conc=2│                  │
│  └──────────────┘     └──────────────┘                  │
└─────────────────────────────────────────────────────────┘
```

---

## Database Schema

**6 tables:**

1. **`users`** — Multi-user auth (id, username, email, password_hash, role, is_active, created_at)
2. **`domains`** — Domain assets (id, domain, display_name, desired_category, notes, email_for_submit, is_active, created_by, created_at, updated_at)
3. **`vendors`** — Vendor registry seeded at startup (id, name, display_name, vendor_type, supports_check, supports_submit, is_active)
4. **`check_results`** — Latest result per domain×vendor (UNIQUE constraint on domain_id+vendor_id+action_type). Fields: status, category, reputation, raw_response JSONB, error_message, attempts, timestamps
5. **`check_history`** — Append-only audit log of all checks ever run
6. **`jobs`** — Batch operation tracking with progress JSONB per vendor, celery_task_id

---

## API Endpoints

```
/api/v1/auth/register     POST    Register new user
/api/v1/auth/login        POST    Login → JWT token
/api/v1/auth/me           GET     Current user profile

/api/v1/domains           GET     List domains (paginated, filterable)
/api/v1/domains           POST    Add domain
/api/v1/domains/{id}      GET     Domain detail + latest results
/api/v1/domains/{id}      PUT     Update config (category, notes, email)
/api/v1/domains/{id}      DELETE  Soft-delete

/api/v1/domains/{id}/results  GET   Latest results (all vendors)
/api/v1/domains/{id}/history  GET   Historical results (paginated)

/api/v1/dashboard/summary     GET   Stats cards data
/api/v1/dashboard/matrix      GET   Full domain×vendor matrix

/api/v1/jobs/check         POST    Trigger check (domain_id, vendor?)
/api/v1/jobs/reputation    POST    Trigger reputation check
/api/v1/jobs/submit        POST    Trigger submission
/api/v1/jobs/bulk-check    POST    Check all active domains
/api/v1/jobs/{id}          GET     Job status + progress
/api/v1/jobs               GET     List recent jobs

/api/v1/vendors            GET     List vendors with capabilities

/ws/jobs                   WS      Real-time job progress updates
```

---

## Celery Task Design

- **One task per vendor** (not per domain) — if TrendMicro fails, other vendors still complete
- **Fan-out via Celery group** — orchestrator dispatches all vendor tasks simultaneously
- **One browser per task** — SeleniumBase `uc=True` state isolation
- **Existing retry logic preserved** — `perform_vendor_operation` 3-attempt logic kept inside tasks
- **Worker concurrency = 2** — each Chrome uses ~300MB RAM, scale with `--scale worker=N`

---

## Frontend Pages

1. **Dashboard** — Stats cards + DomainVendorMatrix (core view: domains as rows, vendors as columns, color-coded cells) + Recent activity
2. **Domains** — CRUD table with bulk actions, add domain modal, filter/search
3. **Domain Detail** — Vendor result cards with match indicators, reputation section, history timeline, action buttons (re-check, submit)
4. **Jobs** — Active jobs with per-vendor progress bars, job history table
5. **Settings** — Vendor toggles, user management (admin), theme toggle
6. **Login/Register** — Auth pages

**Key components:** WebSocketProvider (root context), StatusBadge, CategoryBadge, DomainVendorMatrix, VendorCard, JobProgressCard, ThemeToggle

---

## Directory Structure

```
/opt/classifier/
├── classifier.py              # Existing CLI (unchanged)
├── modules/                   # Existing vendor modules (unchanged)
├── helpers/                   # Existing helpers (unchanged)
├── docker-compose.yml         # Top-level compose file
├── .env.example               # Environment variables template
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/               # DB migrations
│   └── app/
│       ├── main.py            # FastAPI app
│       ├── config.py          # Settings from env
│       ├── database.py        # SQLAlchemy async engine
│       ├── models.py          # ORM models
│       ├── schemas.py         # Pydantic models
│       ├── auth.py            # JWT + bcrypt auth
│       ├── routers/
│       │   ├── auth.py
│       │   ├── domains.py
│       │   ├── jobs.py
│       │   ├── vendors.py
│       │   ├── dashboard.py
│       │   └── ws.py
│       ├── services/
│       │   ├── domain_service.py
│       │   ├── job_service.py
│       │   └── result_service.py
│       └── tasks/
│           ├── celery_app.py
│           ├── vendor_tasks.py
│           └── classifier_bridge.py  # Wraps existing modules
│
├── worker/
│   ├── Dockerfile             # Chrome + Xvfb + Python
│   └── entrypoint.sh
│
└── frontend/
    ├── Dockerfile             # Multi-stage: node build → nginx
    ├── nginx.conf
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.ts
    └── src/
        ├── App.tsx
        ├── main.tsx
        ├── api/               # Axios + React Query client
        ├── components/        # Shared: StatusBadge, CategoryBadge, ThemeToggle
        ├── pages/
        │   ├── Dashboard/
        │   ├── Domains/
        │   ├─�� DomainDetail/
        │   ├── Jobs/
        │   ├── Settings/
        │   └── Auth/
        ├── hooks/             # useWebSocket, useJobProgress, useAuth
        └── context/           # WebSocketContext, AuthContext, ThemeContext
```

---

## Implementation Order

### Phase 1: Infrastructure
1. `docker-compose.yml` with all 5 services
2. Backend Dockerfile + FastAPI skeleton
3. Worker Dockerfile (Chrome + Xvfb + SeleniumBase)
4. Frontend Dockerfile (React + nginx)
5. PostgreSQL schema via Alembic migrations
6. `.env.example` with all config vars
7. Redis + Celery basic setup

### Phase 2: Backend API
1. Auth system (JWT, register, login, user model)
2. Domain CRUD endpoints
3. Vendor registry + seed data
4. Celery tasks wrapping classifier modules (`classifier_bridge.py`)
5. Job creation + progress tracking endpoints
6. Check results + history endpoints
7. Dashboard matrix endpoint
8. WebSocket hub for real-time updates

### Phase 3: Frontend
1. React app with routing, layout, auth context
2. Login/Register pages
3. Dashboard page with DomainVendorMatrix
4. Domains page with CRUD table
5. Domain Detail page with vendor cards
6. Jobs page with progress tracking
7. WebSocket integration for live updates
8. Dark/Light theme toggle
9. Settings page

### Phase 4: Integration & Polish
1. End-to-end test: add domain → check → see results live
2. Bulk operations
3. Error handling, toast notifications
4. Responsive layout
5. Loading states, empty states

---

## Verification

1. `docker compose up --build` — all 5 containers start healthy
2. Register user → login → get JWT token
3. Add domain `wedbush.us` via UI
4. Click "Check All Vendors" → see real-time progress via WebSocket
5. Vendor results populate the matrix as they complete
6. Click individual vendor → re-check works
7. Configure desired category → submit to vendor
8. Theme toggle switches dark/light
9. Job history shows all past operations
10. `docker compose down && docker compose up` — data persists via postgres volume

---

## Critical Files to Create

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Orchestrates all 5 services |
| `backend/Dockerfile` | FastAPI container |
| `worker/Dockerfile` | Celery + Chrome + Xvfb container |
| `frontend/Dockerfile` | React build + nginx container |
| `backend/app/main.py` | FastAPI app with all routers |
| `backend/app/models.py` | SQLAlchemy ORM models (6 tables) |
| `backend/app/tasks/classifier_bridge.py` | Wraps existing vendor modules for Celery |
| `frontend/src/pages/Dashboard/DomainVendorMatrix.tsx` | Core UI component |
| `frontend/src/context/WebSocketContext.tsx` | Real-time updates provider |

## Existing Files — NOT Modified

The existing classifier code (`classifier.py`, `modules/`, `helpers/`) remains completely untouched. The worker container mounts it as a read-only volume and imports the vendor classes directly.
