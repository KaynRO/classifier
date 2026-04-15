import os, logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select
from app.routers import auth, domains, vendors, jobs, dashboard, ws, settings
from app.database import async_session
from app.models import Job, CheckResult, CheckHistory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("classifier")


async def restore_check_result(db, cr: CheckResult) -> None:
    prior = await db.execute(
        select(CheckHistory)
        .where(
            CheckHistory.domain_id == cr.domain_id,
            CheckHistory.vendor_id == cr.vendor_id,
            CheckHistory.action_type == cr.action_type,
            CheckHistory.status.not_in(["running", "pending", "cancelled"]),
        )
        .order_by(CheckHistory.completed_at.desc().nullslast(), CheckHistory.created_at.desc())
        .limit(1)
    )
    prev = prior.scalar_one_or_none()
    if prev is None:
        await db.delete(cr)
        return
    cr.status = prev.status
    cr.category = prev.category
    cr.reputation = prev.reputation
    cr.error_message = prev.error_message
    cr.raw_response = prev.raw_response
    cr.started_at = prev.started_at
    cr.completed_at = prev.completed_at


async def cleanup_stale_jobs() -> None:
    # On startup cancel any jobs/check_results stuck in running/pending state
    # from a previous worker crash or docker compose down
    async with async_session() as db:
        now = datetime.now(timezone.utc)

        stale_jobs = await db.execute(select(Job).where(Job.status.in_(["running", "pending"])))
        count = 0
        for job in stale_jobs.scalars().all():
            job.status = "cancelled"
            job.completed_at = now
            count += 1
        if count:
            logger.info("Startup cleanup: cancelled %d stale job(s)", count)

        stale_crs = await db.execute(select(CheckResult).where(CheckResult.status.in_(["running", "pending"])))
        cr_count = 0
        for cr in stale_crs.scalars().all():
            await restore_check_result(db, cr)
            cr_count += 1
        if cr_count:
            logger.info("Startup cleanup: restored %d stale check_result row(s)", cr_count)

        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await cleanup_stale_jobs()
    yield


limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(title="Classifier Dashboard API", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": "Too many requests. Please try again later."})


allowed_origins = os.environ.get("CORS_ORIGINS", "http://localhost,http://localhost:80").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(domains.router)
app.include_router(vendors.router)
app.include_router(jobs.router)
app.include_router(dashboard.router)
app.include_router(ws.router)
app.include_router(settings.router)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
