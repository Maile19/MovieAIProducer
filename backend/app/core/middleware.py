import re
from uuid import uuid4

import structlog

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

class RequestIDMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        incoming = headers.get(b"x-request-id", b"").decode(
            "ascii", errors="ignore"
        )

        request_id = (
            incoming
            if REQUEST_ID_PATTERN.fullmatch(incoming)
            else str(uuid4())
        )

        if "state" not in scope or not isinstance(scope.get("state"), dict):
            scope["state"] = {}
        scope["state"]["request_id"] = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            correlation_id=request_id,
        )

        async def send_with_request_id(message):
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                has_request_id = any(
                    k.lower() == b"x-request-id" for k, _ in response_headers
                )
                if not has_request_id:
                    response_headers.append(
                        (b"x-request-id", request_id.encode("ascii"))
                    )
                message["headers"] = response_headers

            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            structlog.contextvars.clear_contextvars()
