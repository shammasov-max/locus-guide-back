import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

# Use PostgreSQL for testing (same as production)
# Default to docker-compose database, override with TEST_DATABASE_URL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5433/locus_guide_test"
)

engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create test database schema once per test session."""
    # Import models to register them
    from app.auth import models  # noqa: F401
    from app.cities import models as cities_models  # noqa: F401
    from app.routes import models as routes_models  # noqa: F401

    # Create extensions and enum types that SQLAlchemy create_all doesn't handle
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS hstore"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        # Create route enums
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE route_status AS ENUM ('draft', 'published', 'coming_soon', 'archived');
            EXCEPTION WHEN duplicate_object THEN null;
            END $$
        """))
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE route_version_status AS ENUM ('draft', 'review', 'published', 'superseded');
            EXCEPTION WHEN duplicate_object THEN null;
            END $$
        """))
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE audio_listen_status AS ENUM ('none', 'started', 'completed');
            EXCEPTION WHEN duplicate_object THEN null;
            END $$
        """))
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE completion_type AS ENUM ('manual', 'automatic');
            EXCEPTION WHEN duplicate_object THEN null;
            END $$
        """))
        conn.commit()

    # Create all tables
    Base.metadata.create_all(bind=engine)
    yield
    # Drop all tables after tests
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(setup_test_database):
    """Create a fresh database session for each test with transaction rollback."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with database session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user_data():
    """Sample user registration data."""
    return {
        "email": "test@example.com",
        "password": "securepassword123",
        "display_name": "Test User",
        "units": "metric",
    }


@pytest.fixture
def registered_user(client, test_user_data):
    """Register a user and return the response data."""
    response = client.post("/api/v1/auth/register", json=test_user_data)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def auth_headers(registered_user):
    """Get authorization headers for a registered user."""
    return {"Authorization": f"Bearer {registered_user['tokens']['access_token']}"}
