"""Alembic migration and bootstrap acceptance tests."""

import asyncio
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from cnagentos.config import get_settings
from cnagentos.models.entities import Function, Permission, Role
from cnagentos.services.bootstrap import (
    SYSTEM_FUNCTIONS,
    SYSTEM_ROLE_CODE,
    SYSTEM_ROLE_PERMISSION_CODES,
    create_system_admin,
)


ADMIN_DATABASE_URL = "postgresql+asyncpg://cnagentos:cnagentos_dev@127.0.0.1:54329/postgres"
TEST_DATABASE_PREFIX = "cnagentos_migration_test_"
ADMIN_PASSWORD = "Admin-password-123"


def migration_database_url(database_name: str) -> str:
    return f"postgresql+asyncpg://cnagentos:cnagentos_dev@127.0.0.1:54329/{database_name}"


async def recreate_database(database_name: str) -> None:
    engine = create_async_engine(ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    async with engine.connect() as connection:
        await connection.execute(
            text(
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity "
                "WHERE datname = :database_name AND pid <> pg_backend_pid()"
            ),
            {"database_name": database_name},
        )
        await connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
        await connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    await engine.dispose()


async def drop_database(database_name: str) -> None:
    engine = create_async_engine(ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    async with engine.connect() as connection:
        await connection.execute(
            text(
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity "
                "WHERE datname = :database_name AND pid <> pg_backend_pid()"
            ),
            {"database_name": database_name},
        )
        await connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
    await engine.dispose()


def alembic_config(database_url: str, monkeypatch) -> Config:
    backend_root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("CSRF_SECRET", "migration-test-csrf-secret")
    monkeypatch.setenv("ENCRYPTION_KEY", "migration-test-encryption-key-32b")
    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()

    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


async def assert_bootstrap_reference_data(database_url: str) -> None:
    engine = create_async_engine(database_url)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionmaker() as session:
        user, created = await create_system_admin(
            session,
            "migration-root",
            "迁移测试管理员",
            ADMIN_PASSWORD,
        )
        assert created is True
        assert user.is_system_admin is True

        permissions = set(await session.scalars(select(Permission.code)))
        assert SYSTEM_ROLE_PERMISSION_CODES.issubset(permissions)

        functions = set(await session.scalars(select(Function.code)))
        expected_functions = {item[0] for item in SYSTEM_FUNCTIONS}
        assert expected_functions.issubset(functions)

        system_role = await session.scalar(select(Role).where(Role.code == SYSTEM_ROLE_CODE))
        assert system_role is not None
        assert system_role.status == "active"
    await engine.dispose()


async def assert_platform_tables_removed(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        users_table = await connection.scalar(text("SELECT to_regclass('public.users')"))
        alembic_table = await connection.scalar(text("SELECT to_regclass('public.alembic_version')"))
        version_count = 0
        if alembic_table is not None:
            version_count = await connection.scalar(text("SELECT count(*) FROM alembic_version"))
    await engine.dispose()
    assert users_table is None
    assert version_count == 0


def test_alembic_upgrade_bootstrap_and_downgrade_base(monkeypatch):
    database_name = f"{TEST_DATABASE_PREFIX}{uuid4().hex[:12]}"
    database_url = migration_database_url(database_name)
    config = alembic_config(database_url, monkeypatch)

    asyncio.run(recreate_database(database_name))
    try:
        command.upgrade(config, "head")
        asyncio.run(assert_bootstrap_reference_data(database_url))
        command.downgrade(config, "base")
        asyncio.run(assert_platform_tables_removed(database_url))
    finally:
        asyncio.run(drop_database(database_name))
        get_settings.cache_clear()
