import logging
import re
import sys
from typing import Any

import structlog

SENSITIVE_KEYS = re.compile(
    r"password|passwd|secret|token|api.?key|authorization|credential",
    re.IGNORECASE,
)

BEARER_PATTERN = re.compile(
    r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"
)

SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|password)"
    r"(\s*[:=]\s*)[^\s,;]+"
)

def redact_sensitive_data(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    def redact(value: Any, key: str = "") -> Any:
        if SENSITIVE_KEYS.search(key):
            return "[REDACTED]"

        if isinstance(value, dict):
            return {
                str(k): redact(v, str(k))
                for k, v in value.items()
            }

        if isinstance(value, list):
            return [redact(item) for item in value]

        if isinstance(value, str):
            value = BEARER_PATTERN.sub(r"\1[REDACTED]", value)
            value = SECRET_PATTERN.sub(r"\1\2[REDACTED]", value)

        return value

    return {
        key: redact(value, key)
        for key, value in event_dict.items()
    }

def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        stream=sys.stdout,
        format="%(message)s",
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            structlog.stdlib.add_logger_name,
            redact_sensitive_data,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
