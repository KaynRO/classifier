from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User, AppConfig
from app.auth import get_current_user

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

CREDENTIAL_KEYS = [
    "virustotal_api_key",
    "abuseipdb_api_key",
    "urlhaus_api_key",
    "google_safebrowsing_api_key",
    "twocaptcha_api_key",
    "capsolver_api_key",
    "brightdata_api_key",
    "brightdata_browser_ws",
    "checkpoint_username",
    "checkpoint_password",
    "checkpoint_totp_secret",
    "talos_username",
    "talos_password",
    "watchguard_username",
    "watchguard_password",
    "paloalto_username",
    "paloalto_password",
    "gmail_email",
    "gmail_app_password",
]

SENSITIVE_KEYS = {
    "checkpoint_password", "checkpoint_totp_secret",
    "talos_password", "watchguard_password", "paloalto_password",
    "gmail_app_password",
}


def mask_credential(key: str, value: str | None) -> str:
    if not value:
        return ""
    if key in SENSITIVE_KEYS:
        return "••••••••"
    if len(value) > 10:
        return f"••••{value[-6:]}"
    return "••••"


@router.get("/credentials")
async def get_credentials(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    result = await db.execute(select(AppConfig))
    rows = {row.key: row.value for row in result.scalars().all()}
    return {key: mask_credential(key, rows.get(key)) for key in CREDENTIAL_KEYS}


@router.put("/credentials")
async def update_credentials(
    data: dict[str, str],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin required")

    for key, value in data.items():
        if key not in CREDENTIAL_KEYS:
            continue
        if value == "":
            existing = await db.get(AppConfig, key)
            if existing:
                await db.delete(existing)
            continue
        if value.startswith("••••"):
            continue
        existing = await db.get(AppConfig, key)
        if existing:
            existing.value = value
        else:
            db.add(AppConfig(key=key, value=value))

    await db.commit()
    return {"detail": "Credentials updated"}
