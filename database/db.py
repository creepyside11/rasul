import logging
import os
import ssl
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base

logger = logging.getLogger(__name__)

# Полный приоритет на локальный SQLite:
# Если переменная DATABASE_URL пустая, либо указан sqlite, либо указано явно "USE_SQLITE=1"
USE_SQLITE = os.getenv("USE_SQLITE", "1").strip().lower() in ("1", "true", "yes")

if USE_SQLITE:
    db_url = "sqlite+aiosqlite:///bot_broadcast.db"
    connect_args = {}
    logger.info("Режим базы данных: SQLite (%s)", db_url)
else:
    raw_url = os.getenv("DATABASE_URL", "").strip()
    # Чистим параметры URL от конфликтующих параметров
    base_url = raw_url.split("?")[0]
    if base_url.startswith("postgres://"):
        base_url = base_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif base_url.startswith("postgresql://") and not base_url.startswith("postgresql+asyncpg://"):
        base_url = base_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    db_url = base_url
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    connect_args = {"ssl": ssl_context}
    logger.info("Режим базы данных: PostgreSQL (%s)", db_url.split("@")[-1])

engine = create_async_engine(db_url, connect_args=connect_args, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("База данных успешно инициализирована.")
    except Exception as e:
        logger.error(
            "Не удалось инициализировать базу данных по URL '%s'. Ошибка: %s",
            db_url, e, exc_info=True
        )
        raise
