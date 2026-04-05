# URL Classifier Management Dashboard -- Architecture Plan

## 1. Recommended Tech Stack with Justification

### Backend: FastAPI (Python 3.11+)

**Why FastAPI over Django or Flask:**

- The classifier is already Python. FastAPI runs in the same ecosystem with zero friction -- shared imports, shared models, shared utilities.
- Native async/await support. The fundamental constraint here is that vendor checks take 30-120 seconds per vendor. FastAPI's async architecture handles long-running jobs without blocking the event loop, while Flask requires bolt-on solutions (Celery adds operational complexity) and Django is overengineered for this use case.
- Built-in WebSocket support for real-time job status streaming.
- Automatic OpenAPI/Swagger docs -- the API is self-documenting from day one.
- Pydantic models provide request/response validation that maps cleanly to database schemas.

### Database: PostgreSQL 16

**Why PostgreSQL over SQLite or MongoDB:**

- The data model is inherently relational. Domains have many vendor checks. Vendor checks reference vendors. Jobs reference domains. This is textbook relational.
- SQLite fails under concurrent writes -- and we will have concurrent writes from multiple worker processes updating job results simultaneously. This is a fundamental constraint, not a preference.
- MongoDB adds complexity without benefit. There is no schema flexibility need here. The vendor list is known. The category lists are known. Document databases solve a problem we do not have.
- PostgreSQL JSONB columns give us document-store flexibility where we actually need it (storing vendor-specific raw response data that varies per vendor).
- LISTEN/NOTIFY provides native pub/sub for real-time updates without adding Redis.

### Frontend: React 18 + Vite + TailwindCSS + shadcn/ui

**Why React over Vue or Jinja templates:**

- The dashboard needs real-time updates (job progress), interactive tables (sorting, filtering, bulk actions), and modal workflows (configure category, trigger re-check). This is interactive application territory, not document rendering.
- Jinja templates would require full page reloads or bolting on JavaScript anyway -- leading to two rendering systems.
- Vue would work, but React has a larger ecosystem for dashboard components (TanStack Table, recharts) and hiring pool.
- shadcn/ui provides professional, accessible components without the weight of Material UI.
- Vite provides fast builds and HMR during development.

### Task Queue: Celery + Redis

**Why Celery + Redis over direct subprocess or custom queue:**

- The classifier uses SeleniumBase with a real browser. Each job needs an isolated browser instance. Celery workers naturally isolate this -- one worker, one browser, one job.
- Direct subprocess from the web process creates zombie process risk, has no retry logic, no job state tracking, and couples the web server to browser lifecycle management.
- Redis is lightweight (50MB RAM), battle-tested, and doubles as the Celery broker + result backend + WebSocket pub/sub channel.
- Celery provides job state tracking (PENDING, STARTED, SUCCESS, FAILURE), automatic retries, rate limiting, and priority queues -- all things we need and would otherwise hand-build.

### Real-time Updates: WebSocket via FastAPI + Redis Pub/Sub

**Why WebSocket over polling:**

- Jobs run 30-120 seconds. Polling at 2-second intervals means 15-60 wasted HTTP requests per job. With 10 domains x 9 vendors = 90 jobs, that is 1,350-5,400 wasted requests per full scan.
- WebSocket pushes vendor results as they complete. The UI updates in real-time without overhead.
- Redis pub/sub bridges the gap between Celery workers (which produce results) and WebSocket connections (which consume them).

---

## 2. Container Architecture

```
+-------------------------------------------------------------------+
|                        Docker Compose Stack                        |
+-------------------------------------------------------------------+
|                                                                    |
|  +---------------------+     +---------------------+              |
|  |    web (FastAPI)     |     |   frontend (nginx)  |              |
|  |  Port 8000 internal  |     |  Port 80 -> 3000    |              |
|  |  uvicorn + gunicorn  |     |  Serves React build |              |
|  |  REST API + WS       |     |  Proxies /api -> web|              |
|  +----------+-----------+     +----------+----------+              |
|             |                            |                         |
|             +----------------------------+                         |
|             |                                                      |
|  +----------+-----------+                                          |
|  |      redis:7         |                                          |
|  |  Port 6379 internal  |                                          |
|  |  Broker + PubSub     |                                          |
|  +----------+-----------+                                          |
|             |                                                      |
|  +----------+-----------+     +---------------------+              |
|  |  worker (Celery)     |     |    postgres:16      |              |
|  |  classifier + browser|     |  Port 5432 internal |              |
|  |  Chrome + Xvfb       |     |  Persistent volume  |              |
|  |  concurrency=2       |     +---------------------+              |
|  +----------------------+                                          |
|                                                                    |
+-------------------------------------------------------------------+

Container count: 5
  1. frontend  -- nginx serving React static build, reverse proxy to API
  2. web       -- FastAPI application server (API + WebSocket)
  3. worker    -- Celery worker with Chrome + Xvfb + SeleniumBase
  4. redis     -- Message broker + pub/sub
  5. postgres  -- Persistent data store

Network: Single bridge network (classifier-net)
Volumes:
  - postgres_data (persistent)
  - redis_data (persistent, optional)
```

**Key containerization decisions:**

- The worker container is the heaviest. It needs Chrome, Xvfb, Python, SeleniumBase, and all vendor modules. It gets its own Dockerfile based on `python:3.11-slim` with Chrome installed via apt.
- Worker concurrency is set to 2 (not higher). Each browser instance uses ~300MB RAM. Two concurrent vendor checks is a reasonable default. Scale horizontally by adding worker replicas.
- The web container does NOT need Chrome. It only needs FastAPI + database drivers. This separation is critical -- the web container stays lightweight and fast.
- Frontend is a simple nginx container serving the Vite build output. It also handles reverse proxying `/api/*` to the FastAPI container.

---

## 3. Database Schema

```sql
-- Domains the user manages
CREATE TABLE domains (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain          VARCHAR(255) NOT NULL UNIQUE,
    display_name    VARCHAR(255),
    desired_category VARCHAR(50),     -- from available_categories: Business, Education, etc.
    notes           TEXT,
    email_for_submit VARCHAR(255),    -- email to use when submitting category changes
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_domains_domain ON domains(domain);
CREATE INDEX idx_domains_active ON domains(is_active) WHERE is_active = TRUE;

-- Enumeration of supported vendors
CREATE TABLE vendors (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(50) NOT NULL UNIQUE,   -- e.g. 'trendmicro'
    display_name    VARCHAR(100) NOT NULL,          -- e.g. 'TrendMicro'
    vendor_type     VARCHAR(20) NOT NULL,           -- 'category' or 'reputation'
    supports_check  BOOLEAN DEFAULT TRUE,
    supports_submit BOOLEAN DEFAULT FALSE,
    is_active       BOOLEAN DEFAULT TRUE
);

-- Seed data for vendors:
-- trendmicro (category, check+submit)
-- mcafee (category, check+submit)
-- bluecoat (category, check+submit)
-- brightcloud (category, check+submit)
-- paloalto (category, check+submit)
-- zvelo (category, check+submit)
-- watchguard (category, check+submit)
-- talosintelligence (category, check+submit)
-- lightspeedsystems (category, check only)
-- virustotal (reputation, check only)
-- abusech (reputation, check only)
-- abuseipdb (reputation, check only)

-- Latest check result per domain per vendor
CREATE TABLE check_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_id       UUID NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    vendor_id       INTEGER NOT NULL REFERENCES vendors(id),
    action_type     VARCHAR(20) NOT NULL,          -- 'check', 'reputation', 'submit'
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
                    -- pending, running, success, failed, skipped
    category        VARCHAR(255),                   -- returned category string
    reputation      VARCHAR(255),                   -- returned reputation/safety string
    raw_response    JSONB,                          -- vendor-specific raw data
    error_message   TEXT,
    attempts        INTEGER DEFAULT 0,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(domain_id, vendor_id, action_type)       -- one latest result per combo
);

CREATE INDEX idx_check_results_domain ON check_results(domain_id);
CREATE INDEX idx_check_results_vendor ON check_results(vendor_id);
CREATE INDEX idx_check_results_status ON check_results(status);

-- Full history of all checks (append-only)
CREATE TABLE check_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_id       UUID NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    vendor_id       INTEGER NOT NULL REFERENCES vendors(id),
    action_type     VARCHAR(20) NOT NULL,
    status          VARCHAR(20) NOT NULL,
    category        VARCHAR(255),
    reputation      VARCHAR(255),
    raw_response    JSONB,
    error_message   TEXT,
    attempts        INTEGER DEFAULT 0,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_check_history_domain ON check_history(domain_id);
CREATE INDEX idx_check_history_created ON check_history(created_at);

-- Job tracking for batch operations
CREATE TABLE jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_id       UUID NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    action_type     VARCHAR(20) NOT NULL,          -- 'check', 'reputation', 'submit'
    vendor_filter   VARCHAR(50),                    -- null = all, or specific vendor name
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
                    -- pending, running, completed, failed, cancelled
    celery_task_id  VARCHAR(255),                   -- Celery task ID for tracking
    progress        JSONB DEFAULT '{}',             -- {vendor: status} map
    requested_at    TIMESTAMPTZ DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    requested_by    VARCHAR(255) DEFAULT 'ui'
);

CREATE INDEX idx_jobs_domain ON jobs(domain_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_celery ON jobs(celery_task_id);
```

**Schema design rationale:**

- `check_results` uses a UNIQUE constraint on (domain_id, vendor_id, action_type) so the dashboard always shows the LATEST result with a simple query. No need for complex "get latest" subqueries.
- `check_history` is append-only for auditing. Every check ever run is preserved. This table grows but is only queried for historical views.
- `jobs` tracks batch operations. When a user clicks "Re-check all vendors for example.com", one job row is created. The `progress` JSONB column tracks per-vendor completion within that job.
- `vendors` is a reference table seeded at startup. This avoids hardcoding vendor names in queries and makes it easy to add/disable vendors.
- UUIDs for primary keys because these will appear in URLs and API responses. Sequential integers leak information about system usage.

---

## 4. API Endpoint Design

```
Base URL: /api/v1

--- Domain Management ---

GET    /domains                         List all domains (paginated, filterable)
       ?page=1&per_page=25&search=&is_active=true
POST   /domains                         Add a new domain
       Body: {domain, display_name?, desired_category?, notes?, email_for_submit?}
GET    /domains/{domain_id}             Get domain detail with latest results
PUT    /domains/{domain_id}             Update domain config (category, notes, email)
DELETE /domains/{domain_id}             Soft-delete domain (set is_active=false)

--- Check Results ---

GET    /domains/{domain_id}/results     Latest results for a domain (all vendors)
GET    /domains/{domain_id}/history     Historical results (paginated)
       ?vendor=&action_type=&page=1&per_page=50

--- Dashboard / Aggregate ---

GET    /dashboard/summary               Aggregate stats:
                                        - total domains, last full scan time
                                        - domains with mismatched categories
                                        - domains with reputation issues
GET    /dashboard/matrix                Full domain x vendor matrix for table view
       ?page=1&per_page=25

--- Jobs ---

POST   /jobs/check                      Trigger category check
       Body: {domain_id, vendor?: string}   (vendor=null means all)
POST   /jobs/reputation                 Trigger reputation check
       Body: {domain_id}
POST   /jobs/submit                     Trigger category submission
       Body: {domain_id, vendor?: string}
POST   /jobs/bulk-check                 Check all active domains
       Body: {vendor?: string}
GET    /jobs/{job_id}                   Get job status + progress
GET    /jobs                            List recent jobs
       ?status=&domain_id=&page=1&per_page=25
DELETE /jobs/{job_id}                   Cancel a pending/running job

--- Vendors ---

GET    /vendors                         List all vendors with capabilities
GET    /vendors/{vendor_id}/categories  List valid categories for a vendor

--- WebSocket ---

WS     /ws/jobs                         Real-time job progress updates
                                        Server pushes: {job_id, vendor, status, result}
```

**API design rationale:**

- Versioned (`/api/v1`) from day one. Costs nothing, prevents future breaking changes.
- Separate endpoints for `check`, `reputation`, and `submit` rather than a generic `/jobs` with action_type in the body. This is clearer in the UI and allows different permission models later.
- The `/dashboard/matrix` endpoint returns the full domain-vendor matrix pre-joined. This avoids N+1 queries from the frontend fetching each domain's results separately.
- WebSocket is a single connection per client. The server filters messages by job_id. The client subscribes to specific jobs via a JSON message after connection.

---

## 5. Job/Task Queue Design

### Architecture

```
[FastAPI] --enqueue--> [Redis Broker] --dequeue--> [Celery Worker]
                                                         |
                                                    [Chrome/Xvfb]
                                                         |
                                        +----------------+----------------+
                                        |                                 |
                                  [Update DB]                    [Publish to Redis PubSub]
                                                                          |
                                                                    [FastAPI WS Hub]
                                                                          |
                                                                    [Browser Client]
```

### Celery Task Design

```python
# tasks.py -- conceptual design

@celery_app.task(bind=True, max_retries=0)  # retries handled internally
def run_vendor_check(self, job_id: str, domain: str, vendor_name: str, action: str,
                     email: str = None, category: str = None):
    """
    Single vendor check/submit task.
    One task = one vendor = one browser session.
    """
    # 1. Update job progress: {vendor: "running"}
    update_job_progress(job_id, vendor_name, "running")
    publish_ws_update(job_id, vendor_name, "running")

    # 2. Create browser (within worker process)
    driver = Driver(uc=True, headless=True)

    try:
        # 3. Initialize vendor and run operation
        vendor_instance = get_vendor_instance(vendor_name)
        result = perform_vendor_operation_wrapped(vendor_instance, driver, domain, action, email, category)

        # 4. Save to database (check_results + check_history)
        save_result(job_id, domain, vendor_name, action, result)

        # 5. Publish real-time update
        publish_ws_update(job_id, vendor_name, "success", result)

    except Exception as e:
        save_error(job_id, domain, vendor_name, action, str(e))
        publish_ws_update(job_id, vendor_name, "failed", error=str(e))

    finally:
        driver.quit()


@celery_app.task
def run_domain_check(job_id: str, domain_id: str, action: str, vendor_filter: str = None):
    """
    Orchestrator task: fans out to individual vendor tasks.
    """
    domain = get_domain(domain_id)
    vendors = get_applicable_vendors(action, vendor_filter)

    # Fan out: one subtask per vendor
    chord_tasks = [
        run_vendor_check.s(job_id, domain.domain, v.name, action,
                          domain.email_for_submit, domain.desired_category)
        for v in vendors
    ]

    # Execute with concurrency limited by worker pool
    group(chord_tasks).apply_async()
```

**Key design decisions:**

- **One task per vendor, not one task per domain.** This is critical. If we bundle all 9 vendors into one task, a failure in vendor 5 means vendors 6-9 never run (or we need complex internal retry logic). With one task per vendor, Celery handles isolation naturally.
- **Fan-out via Celery group.** The orchestrator dispatches all vendor tasks simultaneously. The worker pool (concurrency=2) acts as natural backpressure -- tasks queue and execute as workers become available.
- **Browser created per task, not shared.** SeleniumBase state is unpredictable. Cookie jars, page state, alerts -- sharing a browser between vendor operations creates flaky, impossible-to-debug failures. The 2-second startup cost of a new Chrome instance is negligible against 30-120 second vendor operations.
- **No Celery retries. Internal retry logic preserved.** The existing classifier has 3-attempt retry logic per vendor (see `perform_vendor_operation` in `classifier.py` line 107). We wrap this existing logic rather than replacing it with Celery retries, which would restart the entire task (including browser creation).

### Queue Configuration

```python
# celery_config.py
broker_url = "redis://redis:6379/0"
result_backend = "redis://redis:6379/1"

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]

# Worker config
worker_concurrency = 2          # 2 browser instances max
worker_prefetch_multiplier = 1  # Don't prefetch -- tasks are long-running
task_acks_late = True           # Ack after completion, not receipt
task_time_limit = 300           # Hard kill after 5 minutes
task_soft_time_limit = 240      # Soft timeout at 4 minutes

# Rate limiting (be respectful to vendors)
task_default_rate_limit = "6/m"  # Max 6 tasks per minute globally
```

---

## 6. Frontend Component Hierarchy

```
App
|
+-- Layout
|   +-- Sidebar
|   |   +-- NavItem (Dashboard)
|   |   +-- NavItem (Domains)
|   |   +-- NavItem (Jobs)
|   |   +-- NavItem (Settings)
|   +-- Header
|   |   +-- SearchBar
|   |   +-- NotificationBell (active job count)
|   +-- MainContent (router outlet)
|
+-- Pages
|   |
|   +-- DashboardPage
|   |   +-- StatsCards (total domains, pending jobs, issues found)
|   |   +-- DomainVendorMatrix
|   |   |   +-- MatrixHeader (vendor columns)
|   |   |   +-- MatrixRow (per domain)
|   |   |   |   +-- StatusCell (color-coded: green/yellow/red/gray)
|   |   |   |   +-- CategoryBadge
|   |   +-- RecentActivity (last 10 job results)
|   |
|   +-- DomainsPage
|   |   +-- DomainToolbar
|   |   |   +-- AddDomainButton -> AddDomainModal
|   |   |   +-- BulkActions (check all, export)
|   |   |   +-- FilterControls
|   |   +-- DomainTable
|   |   |   +-- DomainRow
|   |   |   |   +-- DomainName + DesiredCategory badge
|   |   |   |   +-- VendorStatusIcons (compact: 9 small indicators)
|   |   |   |   +-- LastChecked timestamp
|   |   |   |   +-- ActionDropdown (check, submit, edit, delete)
|   |   +-- Pagination
|   |
|   +-- DomainDetailPage (/:domainId)
|   |   +-- DomainHeader
|   |   |   +-- DomainName + EditButton
|   |   |   +-- DesiredCategory selector
|   |   |   +-- NotesEditor
|   |   |   +-- EmailConfig
|   |   +-- VendorResultsGrid
|   |   |   +-- VendorCard (one per vendor)
|   |   |   |   +-- VendorLogo + Name
|   |   |   |   +-- CurrentCategory
|   |   |   |   +-- MatchIndicator (matches desired? green/red)
|   |   |   |   +-- LastChecked
|   |   |   |   +-- ActionButtons (re-check, submit)
|   |   +-- ReputationSection
|   |   |   +-- ReputationCard (VirusTotal)
|   |   |   +-- ReputationCard (AbuseCH)
|   |   |   +-- ReputationCard (AbuseIPDB)
|   |   +-- HistoryTimeline
|   |       +-- HistoryEntry (timestamp, vendor, old->new category)
|   |
|   +-- JobsPage
|   |   +-- ActiveJobs
|   |   |   +-- JobProgressCard
|   |   |   |   +-- DomainName
|   |   |   |   +-- VendorProgressBar (per-vendor status indicators)
|   |   |   |   +-- CancelButton
|   |   +-- JobHistory
|   |       +-- JobTable (sortable, filterable)
|   |
|   +-- SettingsPage
|       +-- VendorToggleList (enable/disable vendors)
|       +-- CredentialsForm (API keys -- masked)
|       +-- DefaultsForm (default category, email)
|
+-- Shared Components
    +-- StatusBadge (pending/running/success/failed)
    +-- CategoryBadge (color per category)
    +-- ConfirmDialog
    +-- Toast notifications (job completed, errors)
    +-- WebSocketProvider (context for real-time updates)
```

**Frontend architecture decisions:**

- **React Query (TanStack Query)** for server state management. Handles caching, background refetching, and optimistic updates. No Redux needed -- the server is the source of truth.
- **WebSocketProvider** at the app root. Receives all job updates and dispatches to relevant components via React context. When a vendor check completes, the DomainVendorMatrix and DomainDetailPage update in real-time without re-fetching.
- **The DomainVendorMatrix is the core UI.** This is the view users will live in. Domains as rows, vendors as columns, color-coded status cells. One glance shows which domains have mismatched categories. This component drives the entire UX.

---

## 7. Key Architectural Decisions and Trade-offs

### Decision 1: Wrap the CLI, do not rewrite it

**Approach:** The Celery worker imports and calls the existing vendor modules directly (`TrendMicro().check(driver, url)`) rather than shelling out to `classifier.py` as a subprocess.

**Why:** Direct import gives us structured return values (the `check()` methods already return tuples), exception handling, and no stdout parsing. Subprocess would require parsing colored terminal output or redesigning the CLI's output format.

**Trade-off:** The vendor modules were written assuming global state (logger, captcha key). The worker must set these up per-task. This is manageable -- `set_captcha_api_key()` and `set_active_logger()` already exist in `utils.py`.

**What we preserve:** All vendor logic, all retry logic, all CAPTCHA solving, all browser automation. Zero rewrite of the 13 vendor modules.

### Decision 2: One browser per task, not browser pooling

**Why:** Browser state is the enemy of reliability. SeleniumBase with undetected-chromedriver modifies browser fingerprints, manages cookies, handles CloudFlare challenges. Sharing a browser between vendor checks creates cross-contamination. Vendor A's cookies affect vendor B's challenge detection.

**Trade-off:** ~2 second overhead per task for Chrome startup. With 9 vendors, that is 18 seconds of overhead on a full domain check. Acceptable against 270-1080 seconds of actual vendor operations.

**Alternative considered:** Browser pool with clean profile per use. Rejected because SeleniumBase's `uc=True` mode patches Chrome binaries -- pooling patched browsers is fragile.

### Decision 3: PostgreSQL LISTEN/NOTIFY vs dedicated WebSocket server

**Alternative considered:** Using PostgreSQL's LISTEN/NOTIFY to push check_result inserts directly to the FastAPI WebSocket handler, eliminating Redis pub/sub.

**Rejected because:** PostgreSQL LISTEN/NOTIFY has no persistence. If the FastAPI server restarts or a WebSocket disconnects and reconnects, missed notifications are gone. Redis pub/sub has the same limitation, but Redis is already required for Celery. Adding PG LISTEN/NOTIFY means two pub/sub systems. One is enough.

### Decision 4: Worker concurrency = 2 with horizontal scaling

**Why not higher concurrency?** Each Chrome instance uses 200-400MB RAM. At concurrency=4, the worker container needs 1.6GB just for browsers, plus Python overhead. Memory pressure causes OOM kills, which corrupt browser state and leave zombie Chrome processes.

**Scaling strategy:** For users managing 100+ domains who need faster batch checks, add worker replicas via `docker compose up --scale worker=3`. Each replica runs 2 concurrent tasks. Three replicas = 6 parallel vendor checks.

### Decision 5: Frontend framework vs server-rendered templates

**I've seen this pattern across multiple industries.** Every dashboard that starts as Jinja templates eventually gets rewritten in React/Vue when users demand real-time updates, inline editing, and responsive layouts. The migration cost is higher than starting with a proper frontend framework.

**Trade-off:** More initial complexity (separate build step, Node.js in dev). But the DomainVendorMatrix component alone -- with color-coded cells, hover tooltips, click-to-check actions, and real-time status updates -- justifies a proper component framework from day one.

### Decision 6: Single API gateway via nginx

**Why nginx in front, not direct FastAPI exposure:**

- Serves static React assets without Python involvement
- Handles TLS termination (future)
- Rate limiting at the edge
- Clean URL routing: `/api/*` to FastAPI, everything else to React SPA
- WebSocket upgrade handling

---

## 8. Implementation Phases

### Phase 1: Foundation (Week 1)

- Docker Compose with all 5 containers booting
- PostgreSQL schema migration (Alembic)
- FastAPI skeleton with domain CRUD endpoints
- Celery worker that can execute a single vendor check
- React app with routing and layout shell

**Deliverable:** Add a domain, trigger a single vendor check via API, see result in database.

### Phase 2: Core Dashboard (Week 2)

- All API endpoints implemented
- DomainVendorMatrix component
- DomainDetailPage with vendor cards
- Job creation from UI (check, submit buttons)
- WebSocket integration for real-time updates

**Deliverable:** Full dashboard workflow -- add domain, check all vendors, see results update in real-time.

### Phase 3: Polish and Operations (Week 3)

- Bulk operations (check all domains)
- History timeline
- Settings page (vendor toggles, credentials)
- Error handling and retry UI
- Toast notifications
- Responsive layout

**Deliverable:** Production-ready dashboard.

### Phase 4: Future Enhancements

- Scheduled checks (cron-based via Celery Beat)
- Email notifications when categories change
- Multi-user authentication (if needed)
- Export reports (CSV/PDF)
- Category change tracking and diffing over time

---

## 9. File/Directory Structure

```
classifier-dashboard/
|-- docker-compose.yml
|-- .env.example
|
|-- backend/
|   |-- Dockerfile
|   |-- requirements.txt
|   |-- alembic/              # Database migrations
|   |-- app/
|   |   |-- main.py           # FastAPI app + WebSocket
|   |   |-- config.py         # Settings from env vars
|   |   |-- database.py       # SQLAlchemy engine + session
|   |   |-- models.py         # SQLAlchemy ORM models
|   |   |-- schemas.py        # Pydantic request/response models
|   |   |-- routers/
|   |   |   |-- domains.py
|   |   |   |-- jobs.py
|   |   |   |-- vendors.py
|   |   |   |-- dashboard.py
|   |   |   |-- ws.py         # WebSocket handler
|   |   |-- services/
|   |   |   |-- domain_service.py
|   |   |   |-- job_service.py
|   |   |   |-- result_service.py
|   |   |-- tasks/
|   |       |-- celery_app.py
|   |       |-- vendor_tasks.py
|   |       |-- classifier_bridge.py  # Wraps existing classifier modules
|
|-- worker/
|   |-- Dockerfile            # Chrome + Xvfb + Python + SeleniumBase
|   |-- entrypoint.sh         # xvfb-run celery worker
|
|-- frontend/
|   |-- Dockerfile            # Multi-stage: node build -> nginx serve
|   |-- nginx.conf
|   |-- src/
|   |   |-- App.tsx
|   |   |-- api/              # API client (axios + React Query)
|   |   |-- components/       # Shared components
|   |   |-- pages/
|   |   |   |-- Dashboard/
|   |   |   |-- Domains/
|   |   |   |-- DomainDetail/
|   |   |   |-- Jobs/
|   |   |   |-- Settings/
|   |   |-- hooks/
|   |   |   |-- useWebSocket.ts
|   |   |   |-- useJobProgress.ts
|   |   |-- context/
|   |       |-- WebSocketContext.tsx
|
|-- classifier/               # Existing classifier code (mounted as volume)
|   |-- classifier.py
|   |-- modules/
|   |-- helpers/
```

---

## 10. Docker Compose Configuration (Conceptual)

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: classifier
      POSTGRES_USER: classifier
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U classifier"]
      interval: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 128mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 5

  web:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    environment:
      DATABASE_URL: postgresql+asyncpg://classifier:${DB_PASSWORD}@postgres/classifier
      REDIS_URL: redis://redis:6379/0
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }

  worker:
    build: ./worker
    command: >
      xvfb-run --auto-servernum
      celery -A app.tasks.celery_app worker
      --loglevel=info --concurrency=2
    environment:
      DATABASE_URL: postgresql://classifier:${DB_PASSWORD}@postgres/classifier
      REDIS_URL: redis://redis:6379/0
      TWOCAPTCHA_API_KEY: ${TWOCAPTCHA_API_KEY}
    volumes:
      - ./classifier:/app/classifier:ro    # Mount existing classifier code
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - web

volumes:
  postgres_data:
```

---

## Summary

The fundamental constraints driving this architecture:

1. **Browser automation is slow and memory-heavy.** This dictates the Celery + worker separation, concurrency limits, and one-browser-per-task design.
2. **The classifier already works.** This dictates wrapping via direct import rather than rewriting.
3. **Users need real-time feedback on 30-120 second operations.** This dictates WebSocket over polling.
4. **The data model is relational.** This dictates PostgreSQL over MongoDB.
5. **The dashboard is interactive, not document-based.** This dictates React over Jinja templates.

Every technology choice follows from these constraints. The architecture is not trendy -- it is the simplest design that respects the physics of the problem.
