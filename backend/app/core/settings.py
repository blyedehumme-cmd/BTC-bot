from pathlib import Path
from pydantic import BaseSettings


class Settings(BaseSettings):
    app_name: str = 'Lesly AI Trading Backend'
    environment: str = 'development'
    database_url: str = 'postgresql+asyncpg://user:password@localhost:5432/lesly'
    paper_trading: bool = True
    secret_key: str = 'change-me'
    api_prefix: str = '/api'

    class Config:
        env_file = Path('.') / '.env'
        env_file_encoding = 'utf-8'


settings = Settings()
