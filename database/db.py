import logging
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base

logger = logging.getLogger(__name__)

# По умолчанию используем локальный SQLite файл bot_broadcast.db
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if not DATABASE_URL or "postgres" not in DATABASE_URL:
    db_url = "sqlite+aiosqlite:///bot_broadcast.db"
    logger.info("Используется локальная база SQLite: %s", db_url)
else:
    db_url = DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    logger.info("Используется база PostgreSQL: %s", db_url.split("@")[-1])

engine = create_async_engine(db_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("База данных успешно создана и инициализирована.")
    except Exception as e:
        logger.error(
            "Не удалось инициализировать базу данных по URL '%s'. Ошибка: %s",
            db_url, e, exc_info=True
        )
        raise
