from collections.abc import Generator
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import shutil
import tempfile
import uuid

# HARD-GUARD: Force test database path before settings or FastAPI app initialization.
# Use an isolated OS temp directory so the suite never leaves .db artifacts in the repo.
TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="movieai-pytest-"))
TEST_DB_PATH = TEST_DB_DIR / "test_movieai.db"
os.environ["DATABASE_PATH"] = str(TEST_DB_PATH)

from fastapi.testclient import TestClient
import jwt
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings

# Clear lru_cache so newly set env takes effect
get_settings.cache_clear()

from backend.app.infrastructure.database.models.auth import UserModel
from backend.app.main import create_app


@pytest.fixture(scope="session", autouse=True)
def guard_test_db():
    """Ensure tests run strictly on an isolated test database, never on production."""
    settings = get_settings()
    db_path_str = str(settings.database_path)
    async_url = settings.async_database_url

    # Hard-guard safety assertion
    if "data/movieai.db" in db_path_str and "test" not in db_path_str:
        raise RuntimeError(
            f"CRITICAL SAFETY VIOLATION: Test suite attempted to connect to production database: {db_path_str}"
        )
    if "data/movieai.db" in async_url and "test" not in async_url:
        raise RuntimeError(
            f"CRITICAL SAFETY VIOLATION: Test engine URL points to production: {async_url}"
        )

    # Initialize schema in test database
    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink()
        except Exception:
            pass

    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    from backend.app.infrastructure.database.base import Base
    import backend.app.infrastructure.database.models  # noqa: F401

    engine = create_engine(f"sqlite:///{TEST_DB_PATH}")
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL;"))
        conn.execute(text("PRAGMA busy_timeout=5000;"))
        conn.commit()
    Base.metadata.create_all(engine)

    # Seed system preset for preset/pipeline tests
    try:
        import importlib
        migration_mod = importlib.import_module("migrations.versions.0003_add_production_presets")
        youtube_seed = getattr(migration_mod, "YOUTUBE_KIDS_COMEDY_SEED", None)
        if youtube_seed:
            from backend.app.infrastructure.database.models.preset import ProductionPresetModel
            with Session(engine) as session:
                system_preset = ProductionPresetModel(
                    id=uuid.uuid4(),
                    name=youtube_seed["name"],
                    slug=youtube_seed["slug"],
                    category=youtube_seed["category"],
                    description=youtube_seed["description"],
                    is_system=True,
                    preset_data=youtube_seed["preset_data"],
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(system_preset)
                session.commit()
    except Exception as e:
        print(f"Warning: could not seed system preset in test db: {e}")

    engine.dispose()

    yield

    # Clean up isolated test database directory after session
    if TEST_DB_DIR.exists():
        try:
            shutil.rmtree(TEST_DB_DIR, ignore_errors=True)
        except Exception:
            pass


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    app = create_app()
    with TestClient(app, base_url="http://localhost") as c:
        yield c


@pytest.fixture
def test_user(settings) -> UserModel:
    """Ensure a primary test user exists in the database and return it."""
    sync_url = str(settings.database_path)
    engine = create_engine(f"sqlite:///{sync_url}")
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        user = session.execute(
            select(UserModel).where(UserModel.email == "needgenius19@gmail.com")
        ).scalar_one_or_none()

        if not user:
            user = UserModel(
                id=user_id,
                email="needgenius19@gmail.com",
                full_name="Need Genius",
                avatar_url="https://producer.apologets.com/avatar.png",
                role="SHOWRUNNER",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            session.add(user)
            session.commit()
            session.refresh(user)

        user_obj = UserModel(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
    engine.dispose()
    return user_obj


@pytest.fixture
def auth_headers(test_user, settings) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(test_user.id),
        "email": test_user.email,
        "role": test_user.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=2)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_cookies(test_user, settings) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(test_user.id),
        "email": test_user.email,
        "role": test_user.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=2)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return {settings.cookie_name: token}


@pytest.fixture
def secondary_test_user(settings) -> UserModel:
    """Ensure a secondary user exists for multi-tenant isolation testing."""
    sync_url = str(settings.database_path)
    engine = create_engine(f"sqlite:///{sync_url}")
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        user = session.execute(
            select(UserModel).where(UserModel.email == "otheruser@gmail.com")
        ).scalar_one_or_none()

        if not user:
            user = UserModel(
                id=user_id,
                email="otheruser@gmail.com",
                full_name="Other User",
                avatar_url="https://producer.apologets.com/avatar2.png",
                role="SHOWRUNNER",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            session.add(user)
            session.commit()
            session.refresh(user)

        user_obj = UserModel(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
    engine.dispose()
    return user_obj


@pytest.fixture
def secondary_auth_headers(secondary_test_user, settings) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(secondary_test_user.id),
        "email": secondary_test_user.email,
        "role": secondary_test_user.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=2)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return {"Authorization": f"Bearer {token}"}
