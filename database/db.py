import logging
import psycopg2
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from config import config
from database.models import Base

logger = logging.getLogger(__name__)

# Нормализуем URL для асинхронного движка SQLAlchemy:
# Если передали postgresql:// или postgres://, меняем на postgresql+asyncpg://
db_url = config.database_url
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Fallback на локальный SQLite если DATABASE_URL пустой
if not db_url:
    db_url = "sqlite+aiosqlite:///bot_broadcast.db"
    logger.warning("DATABASE_URL не указан! Переключаемся на SQLite: %s", db_url)

engine = create_async_engine(db_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("База данных успешно инициализирована.")
    except Exception as e:
        logger.error(
            "Не удалось подключиться к базе данных по URL '%s'. Ошибка: %s",
            db_url, e, exc_info=True
        )
        raise
