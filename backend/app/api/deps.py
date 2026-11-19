from collections.abc import AsyncGenerator
import uuid

from fastapi import Depends, HTTPException, Request, Response, status
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import Settings, get_settings
from backend.app.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from backend.app.infrastructure.database.models.auth import UserModel


def resolve_cookie_domain_and_secure(
    request: Request,
    settings: Settings,
) -> tuple[str | None, bool]:
    """Resolve cookie domain and secure flag based on request context and settings."""
    hostname = request.url.hostname or ""
    domain = None
    if settings.cookie_domain and (
        hostname == settings.cookie_domain
        or hostname.endswith("." + settings.cookie_domain)
    ):
        domain = settings.cookie_domain

    is_https = (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto") == "https"
    )
    secure = settings.cookie_secure if is_https else False
    return domain, secure


def delete_session_cookie(
    response: Response,
    settings: Settings,
    request: Request | None = None,
) -> None:
    """Safely delete session cookie with matching domain and path settings to prevent loops."""
    domain = None
    if request:
        domain, _ = resolve_cookie_domain_and_secure(request, settings)
    elif settings.cookie_domain and settings.cookie_domain not in (
        "localhost",
        "127.0.0.1",
        "",
    ):
        domain = settings.cookie_domain

    response.delete_cookie(
        key=settings.cookie_name,
        path="/",
        domain=domain,
    )


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Dependency yielding an active database session."""
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        settings = get_settings()
        engine = create_database_engine(settings.async_database_url)
        session_factory = create_session_factory(engine)
    async with session_factory() as session:
        yield session


async def get_current_user(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> UserModel:
    """Authenticate request via cookie or Authorization header.

    CRITICAL ANTI-LOOP RULE:
    If token is invalid, expired, or missing, we clear the session cookie on response
    and raise 401 Unauthorized.
    """
    token: str | None = None

    # 1. Check HttpOnly cookie
    if settings.cookie_name in request.cookies:
        token = request.cookies[settings.cookie_name]

    # 2. Check Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer ") :].strip()

    if not token:
        delete_session_cookie(response, settings, request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id_str: str | None = payload.get("sub")
        if not user_id_str:
            delete_session_cookie(response, settings, request)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        user_id = uuid.UUID(user_id_str)
    except (jwt.PyJWTError, ValueError) as exc:
        delete_session_cookie(response, settings, request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        ) from exc

    stmt = select(UserModel).where(UserModel.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        delete_session_cookie(response, settings, request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account disabled",
        )

    return user
