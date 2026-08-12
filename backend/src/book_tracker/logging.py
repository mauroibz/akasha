import logging
from collections.abc import MutableMapping
from typing import Any

import structlog

# Keys whose values never reach a log line. Technical spec section 9: notes,
# import row contents, API keys and full provider payloads are all off limits,
# and the reason they are off limits is that a log file is the one artefact that
# gets copied around, pasted into an issue and kept forever.
REDACTED_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "body",
        "content",
        "description",
        "google_books_api_key",
        "note",
        "notes",
        "payload",
        "record",
        "records",
        "response",
        "review",
        "row",
        "rows",
        "secret",
        "token",
    }
)
REDACTION = "[redacted]"
_HANDLER_NAME = "book-tracker-json"
# A value long enough to be a payload is treated as one even under an innocent
# key, because the failure this guards against is someone logging a provider
# response under `data` and nobody noticing for a year.
MAX_VALUE_LENGTH = 512

_scrub_values: tuple[str, ...] = ()


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        for secret in _scrub_values:
            value = value.replace(secret, REDACTION)
        if len(value) > MAX_VALUE_LENGTH:
            return f"{value[:MAX_VALUE_LENGTH]}…[truncated {len(value)} chars]"
        return value
    if isinstance(value, dict):
        return {key: _redact_entry(key, inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_value(inner) for inner in value]
    return value


def _redact_entry(key: str, value: Any) -> Any:
    return REDACTION if key.lower() in REDACTED_KEYS else _redact_value(value)


def redact_sensitive(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Drop personal and secret values before anything is rendered.

    Applied as the last processor before rendering so it also covers the `extra`
    fields stdlib callers attach, which is where most of this data would arrive.
    """
    return {key: _redact_entry(key, value) for key, value in event_dict.items()}


def configure_logging(level: str, *, scrub: tuple[str, ...] = ()) -> None:
    """Configure structured logging for the application and the standard library.

    `scrub` holds literal secrets — the Google Books key — that are removed from
    any string in any field. Keys leak through URLs far more often than through
    a field politely named `api_key`.
    """
    global _scrub_values
    _scrub_values = tuple(secret for secret in scrub if secret)

    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.stdlib.add_log_level,
    ]
    # Standard-library records are routed through the same chain rather than
    # past it: `logger.warning(..., extra={...})` was previously rendered by a
    # bare "%(message)s" format, so its structured fields were neither emitted
    # nor redacted. Now they are both.
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=[*shared, structlog.stdlib.ExtraAdder()],
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            redact_sensitive,
            structlog.processors.JSONRenderer(),
        ],
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.set_name(_HANDLER_NAME)
    root = logging.getLogger()
    # Replace only the handler this function installed. Wiping `root.handlers`
    # wholesale also removes handlers the surrounding process owns — pytest's
    # `caplog` among them — and silently breaks anything that captures logs.
    for existing in [h for h in root.handlers if h.name == _HANDLER_NAME]:
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level.upper())

    structlog.configure(
        processors=[
            *shared,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
