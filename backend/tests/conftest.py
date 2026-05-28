import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from cnagentos.app import create_app
from cnagentos.config import Settings
from cnagentos.db import Base
from cnagentos.services.bootstrap import create_system_admin


TEST_DATABASE_URL = "postgresql+asyncpg://cnagentos:cnagentos_dev@127.0.0.1:54329/cnagentos_test"
ADMIN_DATABASE_URL = "postgresql+asyncpg://cnagentos:cnagentos_dev@127.0.0.1:54329/postgres"
ADMIN_PASSWORD = "Admin-password-123"


@pytest_asyncio.fixture(scope="session")
async def app():
    admin_engine = create_async_engine(ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as connection:
        exists = await connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = 'cnagentos_test'")
        )
        if not exists:
            await connection.execute(text("CREATE DATABASE cnagentos_test"))
    await admin_engine.dispose()

    settings = Settings(
        DATABASE_URL=TEST_DATABASE_URL,
        CSRF_SECRET="integration-test-csrf-secret-value",
        APP_ENV="development",
        ENCRYPTION_KEY="integration-test-encryption-key-32b",
    )
    application = create_app(settings)
    async with application.state.engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    async with application.state.sessionmaker() as session:
        await create_system_admin(session, "root", "系统管理员", ADMIN_PASSWORD)
    yield application
    async with application.state.engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await application.state.engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as http_client:
        yield http_client


@pytest_asyncio.fixture(scope="function")
async def admin_session(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "root", "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["data"]["csrf_token"]
