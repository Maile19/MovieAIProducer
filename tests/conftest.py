from collections.abc import Generator
from datetime import datetime, timedelta, timezone
import uuid

from fastapi.testclient import TestClient
import jwt
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.infrastructure.database.models.auth import UserModel
from backend.app.main import create_app


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
        # Check if needgenius19@gmail.com exists
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
