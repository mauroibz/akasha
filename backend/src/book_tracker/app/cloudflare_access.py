"""Cloudflare Access as a second gate in front of the application (DEC-180 point 4).

Cloudflare Access signs every request it lets through with a JWT, in the
`Cf-Access-Jwt-Assertion` header (and the `CF_Authorization` cookie). With
`AKASHA_CF_ACCESS_TEAM_DOMAIN` and `AKASHA_CF_ACCESS_AUD` set, this middleware refuses
every request whose token is missing or does not verify: RS256 against the team's
published keys, the configured application audience, the team as issuer, and a current
`exp`/`nbf`. A request that reached the container without passing Access — a
misconfigured tunnel, a bypass rule, a port published by mistake, another container on
the same network — is answered 403 before any other code sees it.

It is a gate, not an identity. The verified email goes on `request.state` for logging and
nothing else; the application's own login stays (DEC-180: Access is a second gate, not the
only one). The trusted identity header (`AKASHA_TRUSTED_PROXY_HEADER`) is the separate,
explicit way to let a proxy sign people in.

The one exception is the container's own healthcheck: `GET /api/health/live` and
`/api/health/ready` from loopback. Only a process inside the container's network
namespace connects from 127.0.0.1 or ::1 — Docker's port publishing and the tunnel
sidecar both arrive from a bridge address — and the path is read from the ASGI scope,
never from the `Host` header (finding F2).
"""

import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx
import jwt
from fastapi import FastAPI
from starlette.requests import cookie_parser
from starlette.types import ASGIApp, Receive, Scope, Send

from book_tracker.config import Settings

logger = logging.getLogger(__name__)

ASSERTION_HEADER = b"cf-access-jwt-assertion"
ASSERTION_COOKIE = "CF_Authorization"
#: Clock skew tolerated on `exp`, `nbf` and `iat`, in seconds.
LEEWAY_SECONDS = 30
_HEALTHCHECK_PATHS = frozenset({"/api/health/live", "/api/health/ready"})
_LOOPBACK = frozenset({"127.0.0.1", "::1"})
_REFUSAL = json.dumps(
    {
        "error": {
            "code": "access_denied",
            "message": "This request did not come through Cloudflare Access",
            "details": {},
        }
    }
).encode()


class AccessKeys:
    """The team's signing keys, fetched from `https://<team>/cdn-cgi/access/certs`.

    Keys are cached by `kid`. A token naming a `kid` not in the cache triggers a refresh,
    at most once per `refresh_interval` (Cloudflare rotates keys and publishes the next
    one ahead of use, so a genuine new `kid` is rare and a flood of invented ones must
    not become a flood of fetches). The whole set is refreshed after `max_age` so a
    retired key stops verifying. While no key could ever be fetched, a retry is allowed
    every `retry_interval`. Unavailable keys verify nothing: the gate fails closed.
    """

    def __init__(
        self,
        team_domain: str,
        *,
        client: httpx.AsyncClient | None = None,
        clock: Callable[[], float] = time.monotonic,
        refresh_interval: float = 60.0,
        retry_interval: float = 5.0,
        max_age: float = 3600.0,
    ) -> None:
        self.url = f"https://{team_domain}/cdn-cgi/access/certs"
        # Its own client, not the providers' one: no redirects, a short timeout, and no
        # share of the provider connection pool.
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(5), follow_redirects=False)
        self._clock = clock
        self._refresh_interval = refresh_interval
        self._retry_interval = retry_interval
        self._max_age = max_age
        self._keys: dict[str, Any] = {}
        self._fetched_at: float | None = None
        self._attempted_at: float | None = None
        self._lock = asyncio.Lock()

    async def key_for(self, kid: str) -> Any | None:
        if kid not in self._keys or self._is_stale(self._clock()):
            async with self._lock:
                now = self._clock()
                if (kid not in self._keys or self._is_stale(now)) and self._may_fetch(now):
                    await self._fetch()
        return self._keys.get(kid)

    def _is_stale(self, now: float) -> bool:
        return self._fetched_at is None or now - self._fetched_at >= self._max_age

    def _may_fetch(self, now: float) -> bool:
        if self._attempted_at is None:
            return True
        interval = self._refresh_interval if self._keys else self._retry_interval
        return now - self._attempted_at >= interval

    async def _fetch(self) -> None:
        self._attempted_at = self._clock()
        try:
            response = await self._client.get(self.url)
            response.raise_for_status()
            published = response.json().get("keys", [])
        except (httpx.HTTPError, ValueError, AttributeError) as error:
            # A failed refresh keeps the keys already held: Cloudflare being briefly
            # unreachable must not sign out a working install. With none held, the
            # gate refuses everything until a fetch succeeds.
            logger.warning(
                "cloudflare_access_keys_unavailable",
                extra={"url": self.url, "error": type(error).__name__},
            )
            return
        keys: dict[str, Any] = {}
        for entry in published if isinstance(published, list) else []:
            if not isinstance(entry, dict) or entry.get("kty") != "RSA" or "kid" not in entry:
                continue
            try:
                keys[str(entry["kid"])] = jwt.PyJWK(entry, algorithm="RS256").key
            except jwt.PyJWTError:
                continue
        if not keys:
            logger.warning("cloudflare_access_keys_empty", extra={"url": self.url})
            return
        self._keys = keys
        self._fetched_at = self._attempted_at


class CloudflareAccessMiddleware:
    """Pure ASGI, registered outermost: nothing runs for a request Access did not sign."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        team_domain: str,
        audience: str,
        keys: AccessKeys | None = None,
    ) -> None:
        self.app = app
        self.audience = audience
        self.issuer = f"https://{team_domain}"
        self.keys = keys or AccessKeys(team_domain)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        if _is_local_healthcheck(scope):
            await self.app(scope, receive, send)
            return
        claims = await self._verify(_assertion(scope), str(scope.get("path", "")))
        if claims is None:
            await _refuse(scope, send)
            return
        identity = claims.get("email") or claims.get("common_name")
        if isinstance(identity, str):
            # Starlette's `request.state` reads `scope["state"]`. For logging only.
            scope.setdefault("state", {})["cf_access_email"] = identity
        await self.app(scope, receive, send)

    async def _verify(self, token: str | None, path: str) -> dict[str, Any] | None:
        if not token:
            logger.warning("cloudflare_access_refused", extra={"reason": "missing", "path": path})
            return None
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            logger.warning("cloudflare_access_refused", extra={"reason": "malformed", "path": path})
            return None
        kid = header.get("kid")
        key = await self.keys.key_for(kid) if isinstance(kid, str) else None
        if key is None:
            logger.warning(
                "cloudflare_access_refused", extra={"reason": "unknown_key", "path": path}
            )
            return None
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                leeway=LEEWAY_SECONDS,
                options={"require": ["exp", "aud", "iss"]},
            )
        except jwt.PyJWTError as error:
            logger.warning(
                "cloudflare_access_refused",
                extra={"reason": type(error).__name__, "path": path},
            )
            return None
        return claims


def _is_local_healthcheck(scope: Scope) -> bool:
    client = scope.get("client")
    return (
        scope["type"] == "http"
        and scope.get("method") == "GET"
        and scope.get("path") in _HEALTHCHECK_PATHS
        and client is not None
        and client[0] in _LOOPBACK
    )


def _assertion(scope: Scope) -> str | None:
    cookies: str | None = None
    for name, value in scope.get("headers", []):
        if name == ASSERTION_HEADER:
            return str(value.decode("latin-1")).strip()
        if name == b"cookie":
            cookies = value.decode("latin-1")
    if cookies:
        return cookie_parser(cookies).get(ASSERTION_COOKIE)
    return None


async def _refuse(scope: Scope, send: Send) -> None:
    if scope["type"] == "websocket":
        await send({"type": "websocket.close", "code": 1008})
        return
    await send(
        {
            "type": "http.response.start",
            "status": 403,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(_REFUSAL)).encode()),
                (b"cache-control", b"no-store"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": _REFUSAL})


def install_cloudflare_access(app: FastAPI, configured: Settings) -> None:
    """Add the gate when configured. Call it after every other middleware is added:
    Starlette runs the last-added middleware first, and this one must run before all."""
    if configured.cf_access_team_domain is None or configured.cf_access_aud is None:
        return
    app.add_middleware(
        CloudflareAccessMiddleware,
        team_domain=configured.cf_access_team_domain,
        audience=configured.cf_access_aud,
    )
