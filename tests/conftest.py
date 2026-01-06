import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.common.database import Base, get_db
from app.main import app

# Use SQLite for tests (simpler, no PostGIS needed for basic tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    async_session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(test_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        try:
            yield test_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict:
    """Create a test user and return auth headers."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "testpassword123",
            "display_name": "Test User",
        },
    )
    if response.status_code == 201:
        tokens = response.json()["tokens"]
        return {"Authorization": f"Bearer {tokens['access_token']}"}
    return {}


@pytest_asyncio.fixture
async def editor_headers(client: AsyncClient, test_session: AsyncSession) -> dict:
    """Create an editor user and return auth headers."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "editor@example.com",
            "password": "editorpass123",
            "display_name": "Editor User",
        },
    )
    if response.status_code == 201:
        tokens = response.json()["tokens"]
        # Manually set role to editor
        from app.auth.models import Account
        from sqlalchemy import select

        result = await test_session.execute(
            select(Account).where(Account.email == "editor@example.com")
        )
        account = result.scalar_one()
        account.role = "editor"
        await test_session.commit()
        return {"Authorization": f"Bearer {tokens['access_token']}"}
    return {}


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient, test_session: AsyncSession) -> dict:
    """Create an admin user and return auth headers."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@example.com",
            "password": "adminpass123",
            "display_name": "Admin User",
        },
    )
    if response.status_code == 201:
        tokens = response.json()["tokens"]
        # Manually set role to admin
        from app.auth.models import Account
        from sqlalchemy import select

        result = await test_session.execute(
            select(Account).where(Account.email == "admin@example.com")
        )
        account = result.scalar_one()
        account.role = "admin"
        await test_session.commit()
        return {"Authorization": f"Bearer {tokens['access_token']}"}
    return {}
