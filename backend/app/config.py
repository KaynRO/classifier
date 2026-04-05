from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://classifier:changeme@postgres:5432/classifier"
    DATABASE_URL_SYNC: str = "postgresql://classifier:changeme@postgres:5432/classifier"
    REDIS_URL: str = "redis://redis:6379/0"

    JWT_SECRET_KEY: str = "changeme_jwt_secret_key_at_least_32_chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    ADMIN_USERNAME: str = "admin"
    ADMIN_EMAIL: str = "admin@classifier.local"
    ADMIN_PASSWORD: str = "changeme"

    class Config:
        env_file = ".env"


settings = Settings()
