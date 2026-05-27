from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from cnagentos.config import Settings


class Base(DeclarativeBase):
    pass


def build_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(settings.database_url, pool_pre_ping=True)


def build_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with factory() as session:
        yield session
