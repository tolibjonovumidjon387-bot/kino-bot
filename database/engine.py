"""
SQLAlchemy asinxron engine va session
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from config import DATABASE_URL
from .models import Base

logger = logging.getLogger(__name__)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def init_db():
    """Barcha jadvallarni yaratadi (agar mavjud bo'lmasa)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Ma'lumotlar bazasi jadvallari tayyor.")


async def get_session() -> AsyncSession:
    """Dependency injection uchun sessiya generator"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
