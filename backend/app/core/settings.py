import os
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import field_validator
from pydantic_settings import BaseSettings


def normalize_database_url(url: str) -> tuple[str, bool]:
    """Return async SQLAlchemy URL and whether SSL is required (Neon, etc.)."""
    ssl_required = 'sslmode=require' in url.lower() or 'neon.tech' in url.lower()

    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql+asyncpg://', 1)
    elif url.startswith('postgresql://') and '+asyncpg' not in url:
        url = url.replace('postgresql://', 'postgresql+asyncpg://', 1)

    parsed = urlparse(url)
    if parsed.query:
        query = [(key, value) for key, value in parse_qsl(parsed.query) if key.lower() != 'sslmode']
        url = urlunparse(parsed._replace(query=urlencode(query)))

    return url, ssl_required


class Settings(BaseSettings):
    app_name: str = 'Lesly AI Trading Backend'
    environment: str = 'development'
    database_url: str = 'sqlite+aiosqlite:///./lesly.db'
    database_ssl: bool = False
    paper_trading: bool = True
    secret_key: str = 'change-me'
    api_prefix: str = '/api'
    cors_origins: str = 'http://localhost:3000,http://127.0.0.1:3000'
    frontend_url: str = ''
    cors_allow_vercel_previews: bool = True

    model_config = {
        'env_file': Path('.') / '.env',
        'env_file_encoding': 'utf-8',
    }

    @field_validator('database_url', mode='before')
    @classmethod
    def _normalize_db_url(cls, value: object) -> object:
        if isinstance(value, str):
            normalized, _ssl = normalize_database_url(value)
            return normalized
        return value

    def model_post_init(self, __context: object) -> None:
        raw_url = os.getenv('DATABASE_URL', self.database_url)
        if (
            'sslmode=require' in raw_url.lower()
            or 'neon.tech' in raw_url.lower()
            or 'neon.tech' in self.database_url
        ):
            object.__setattr__(self, 'database_ssl', True)

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(',') if origin.strip()]
        if self.frontend_url and self.frontend_url not in origins:
            origins.append(self.frontend_url.rstrip('/'))
        return origins

    @property
    def cors_origin_regex(self) -> str | None:
        if self.cors_allow_vercel_previews and self.is_production:
            return r'https://.*\.vercel\.app'
        return None

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == 'production'

    @property
    def use_alembic_only(self) -> bool:
        return self.is_production or self.database_url.startswith('postgresql')


settings = Settings()
