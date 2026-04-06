import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserLogin, UserResponse, TokenResponse
from app.auth import hash_password, verify_password, create_access_token, get_current_user

logger = logging.getLogger("classifier.auth")
limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

PASSWORD_MIN_LENGTH = 8


@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit("5/hour")
async def register(request: Request, data: UserCreate, db: AsyncSession = Depends(get_db)):
    if len(data.password) < PASSWORD_MIN_LENGTH:
        raise HTTPException(status_code=400, detail=f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
    if data.password.isdigit() or data.password.isalpha():
        raise HTTPException(status_code=400, detail="Password must contain both letters and numbers")

    existing = await db.execute(
        select(User).where((User.username == data.username) | (User.email == data.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username or email already exists")

    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        role="viewer",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info(f"New user registered: {user.username} (role={user.role})")
    token = create_access_token(user.id, user.role)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        logger.warning(f"Failed login attempt for username: {data.username}")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    logger.info(f"User logged in: {user.username}")
    token = create_access_token(user.id, user.role)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/logout")
async def logout(user: User = Depends(get_current_user)):
    # Client-side token removal. Server-side blacklist would require Redis TTL store.
    # For now, acknowledge the logout so the client knows to clear the token.
    logger.info(f"User logged out: {user.username}")
    return {"detail": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)
