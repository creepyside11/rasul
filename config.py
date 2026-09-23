import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Config(BaseSettings):
    bot_token: str = Field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    admin_id: int = Field(default_factory=lambda: int(os.getenv("ADMIN_ID", "0")))
    api_id: int = Field(default_factory=lambda: int(os.getenv("API_ID", "0")))
    api_hash: str = Field(default_factory=lambda: os.getenv("API_HASH", ""))
    database_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", ""))

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

config = Config()
