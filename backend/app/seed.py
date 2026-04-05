import asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings
from app.models import Vendor, User, Base
from app.auth import hash_password

VENDORS = [
    {"name": "trendmicro", "display_name": "TrendMicro", "vendor_type": "category", "supports_check": True, "supports_submit": True},
    {"name": "mcafee", "display_name": "McAfee", "vendor_type": "category", "supports_check": True, "supports_submit": True},
    {"name": "bluecoat", "display_name": "BlueCoat", "vendor_type": "category", "supports_check": True, "supports_submit": True},
    {"name": "brightcloud", "display_name": "Brightcloud", "vendor_type": "category", "supports_check": True, "supports_submit": True},
    {"name": "paloalto", "display_name": "Palo Alto", "vendor_type": "category", "supports_check": True, "supports_submit": True},
    {"name": "zvelo", "display_name": "Zvelo", "vendor_type": "category", "supports_check": True, "supports_submit": True},
    {"name": "watchguard", "display_name": "WatchGuard", "vendor_type": "category", "supports_check": True, "supports_submit": True},
    {"name": "talosintelligence", "display_name": "Talos Intelligence", "vendor_type": "category", "supports_check": True, "supports_submit": True},
    {"name": "lightspeedsystems", "display_name": "LightSpeed Systems", "vendor_type": "category", "supports_check": True, "supports_submit": False},
    {"name": "intelixsophos", "display_name": "Sophos Intelix", "vendor_type": "category", "supports_check": True, "supports_submit": False},
    {"name": "fortiguard", "display_name": "FortiGuard", "vendor_type": "category", "supports_check": True, "supports_submit": False},
    {"name": "checkpoint", "display_name": "Check Point", "vendor_type": "category", "supports_check": True, "supports_submit": False},
    {"name": "virustotal", "display_name": "VirusTotal", "vendor_type": "reputation", "supports_check": True, "supports_submit": False},
    {"name": "abusech", "display_name": "URLhaus (abuse.ch)", "vendor_type": "reputation", "supports_check": True, "supports_submit": False},
    {"name": "abuseipdb", "display_name": "AbuseIPDB", "vendor_type": "reputation", "supports_check": True, "supports_submit": False},
    {"name": "googlesafebrowsing", "display_name": "Google Safe Browsing", "vendor_type": "reputation", "supports_check": True, "supports_submit": False},
]


async def seed_vendors_and_admin():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # Seed vendors
        for v in VENDORS:
            existing = await session.execute(select(Vendor).where(Vendor.name == v["name"]))
            if not existing.scalar_one_or_none():
                session.add(Vendor(**v))

        # Seed admin user
        existing_admin = await session.execute(
            select(User).where(User.username == settings.ADMIN_USERNAME)
        )
        if not existing_admin.scalar_one_or_none():
            admin = User(
                username=settings.ADMIN_USERNAME,
                email=settings.ADMIN_EMAIL,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                role="admin",
            )
            session.add(admin)

        await session.commit()

    await engine.dispose()
    print("Seed complete: vendors and admin user created.")
