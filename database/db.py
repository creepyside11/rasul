import logging
import os
import urllib.parse
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base

logger = logging.getLogger(__name__)

raw_url = os.getenv("DATABASE_URL", "").strip()

# Если передан DATABASE_URL от Postgres, очищаем параметры для asyncpg
if raw_url and "postgres" in raw_url:
    # Удаляем неподдерживаемые asyncpg параметры из query string (channel_binding и sslmode=require -> ssl=True)
    parsed = urllib.parse.urlparse(raw_url)
    query_params = urllib.parse.parse_qs(parsed.query)
    
    # asyncpg не поддерживает channel_binding
    query_params.pop("channel_binding", None)
    
    # asyncpg использует ?ssl=true вместо ?sslmode=require
    if "sslmode" in query_params:
        query_params.pop("sslmode", None)
        query_params["ssl"] = ["true"]

    new_query = urllib.parse.urlencode(query_params, doseq=True)
    scheme = "postgresql+asyncpg"
    db_url = urllib.parse.urlunparse((scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    logger.info("Подготовлен URL PostgreSQL (asyncpg): %s", parsed.netloc)
else:
    # Иначе чистый SQLite файл в папке бота
    db_url = "sqlite+aiosqlite:///bot_broadcast.db"
    logger.info("Используется локальная база SQLite: %s", db_url)

engine = create_async_engine(db_url, echo=False)
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
