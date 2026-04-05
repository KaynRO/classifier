from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, domains, vendors, jobs, dashboard, ws

app = FastAPI(title="Classifier Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(domains.router)
app.include_router(vendors.router)
app.include_router(jobs.router)
app.include_router(dashboard.router)
app.include_router(ws.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
