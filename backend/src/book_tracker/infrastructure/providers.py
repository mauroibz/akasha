"""The shared provider HTTP boundary.

Bounded, retrying JSON reads and the one client every adapter uses. **No domain lives
here**: an adapter belongs to its domain's package (`domains/<item_type>/providers.py`)
and reaches for these, so two domains' adapters never share a file (technical spec 6.6).
"""

import asyncio
import json
import random
import re
from collections.abc import Mapping
from typing import Any

import httpx


class ProviderPayloadError(ValueError):
    """A provider answered, but not with data we can use.

    `code` is the stable machine-readable reason; the message is written for a person
    reading a failed enrichment job.
    """

    def __init__(self, message: str, *, code: str = "provider_payload_invalid") -> None:
        super().__init__(message)
        self.code = code


MAX_PROVIDER_BYTES = 2 * 1024 * 1024
# Open Library's JSON API answers 503 under load, repeatedly and for minutes at a time,
# while their website stays up. Most individual failures are short, so one retry pair
# recovers them; longer outages are handled a layer up by the job queue backing off,
# not by hammering here. Deliberately small: retrying hard against a service that is
# already struggling is how a slow provider becomes a dead one.
# Patience belongs in the background. A batch import can take as long as it needs, so
# enrichment retries; a person waiting on a search must not pay for a provider's bad
# day, so interactive paths ask for fewer attempts or none.
PROVIDER_ATTEMPTS = 3
INTERACTIVE_ATTEMPTS = 2
NO_RETRY = 1
RETRY_BASE_SECONDS: float = 0.4
# A provider that says how long to wait is worth believing, up to a point — an
# interactive search cannot sit behind a five-minute Retry-After.
MAX_RETRY_SLEEP_SECONDS: float = 5.0
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


def create_provider_client(transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    """Build the shared client every provider uses.

    Tests construct it with a replay transport so they exercise the same redirect and
    timeout behaviour the application runs with.
    """
    return httpx.AsyncClient(
        timeout=httpx.Timeout(5),
        limits=httpx.Limits(max_connections=10),
        # `https://openlibrary.org/isbn/{isbn}.json` answers 302 to the edition record.
        # Without this a redirect passes `raise_for_status` and then fails JSON parsing.
        follow_redirects=True,
        transport=transport,
    )


def _retry_delay(attempt: int, response: httpx.Response | None) -> float:
    """How long to wait before the next attempt, honouring `Retry-After`."""
    if response is not None:
        raw = response.headers.get("retry-after", "").strip()
        if raw.isdigit():
            return min(float(raw), MAX_RETRY_SLEEP_SECONDS)
    # Exponential, with jitter so several queued jobs do not resume in lockstep.
    delay: float = RETRY_BASE_SECONDS * float(2**attempt)
    jittered: float = delay + random.uniform(0, delay / 2)
    return jittered if jittered < MAX_RETRY_SLEEP_SECONDS else MAX_RETRY_SLEEP_SECONDS


async def bounded_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: Mapping[str, str | int],
    headers: Mapping[str, str] | None = None,
    timeout: float | None = None,
    attempts: int = PROVIDER_ATTEMPTS,
    method: str = "GET",
    json_body: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Fetch and decode a bounded JSON body, retrying a provider that is unwell.

    Only transport failures and `RETRYABLE_STATUSES` are retried. A 404 is an answer,
    not an outage, and retrying it wastes everyone's time.

    `attempts` is how the caller says whether anyone is waiting: background enrichment
    can afford to be patient, an interactive search cannot.

    `method` and `json_body` exist because a GraphQL provider asks its question in a
    POST body rather than in a query string. Every provider before AniList read with a
    GET, so this boundary was GET-only; the alternative was an adapter writing its own
    request loop and quietly losing the retry policy, the byte bound and the streaming
    read that are the whole reason this function exists. Nothing here branches on which
    provider is calling — the boundary gained a verb, not a special case.
    """
    for attempt in range(attempts):
        try:
            return await _read_json(
                client,
                url,
                params=params,
                headers=headers,
                timeout=timeout,
                method=method,
                json_body=json_body,
            )
        except httpx.HTTPStatusError as error:
            if error.response.status_code not in RETRYABLE_STATUSES or attempt == attempts - 1:
                raise
            await asyncio.sleep(_retry_delay(attempt, error.response))
        except (httpx.TransportError, httpx.TimeoutException):
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(_retry_delay(attempt, None))
    raise AssertionError("unreachable")  # pragma: no cover


async def _read_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: Mapping[str, str | int],
    headers: Mapping[str, str] | None = None,
    timeout: float | None = None,
    method: str = "GET",
    json_body: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    extra: dict[str, Any] = {} if timeout is None else {"timeout": timeout}
    if json_body is not None:
        extra["json"] = json_body
    async with client.stream(method, url, params=params, headers=headers, **extra) as response:
        response.raise_for_status()
        declared = int(response.headers.get("content-length", "0"))
        if declared > MAX_PROVIDER_BYTES:
            raise ProviderPayloadError("Provider response exceeds byte limit")
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > MAX_PROVIDER_BYTES:
                raise ProviderPayloadError("Provider response exceeds byte limit")
    try:
        decoded = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProviderPayloadError("Provider returned malformed JSON") from error
    if not isinstance(decoded, dict):
        raise ProviderPayloadError("Provider returned a non-object payload")
    return decoded


YEAR_PATTERN = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")


def parse_year(value: object) -> int | None:
    """Read a publication year out of whatever shape a provider used.

    Open Library publishes edition dates as `"1984"`, `"1984-03"`, and `"Mar 09, 2005"`
    alike. Taking the first four characters read the last of those as `"Mar "` and threw
    the year away, which is why most search results arrived without one.
    """
    if isinstance(value, list):
        value = value[0] if value else None
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value if 1000 <= value <= 2999 else None
    match = YEAR_PATTERN.search(str(value))
    return int(match.group(1)) if match else None
