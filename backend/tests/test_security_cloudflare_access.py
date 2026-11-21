"""The Cloudflare Access gate in the application (DEC-180 point 4, Sprint 128).

Every token here is signed by a key generated in the test, and the team's JWKS is served
by an `httpx.MockTransport`: no network. The claims mirror what Access issues
(`aud` a list, `iss` the team URL, `email`, `exp`, `iat`, `nbf`).
"""

import asyncio
import base64
import hashlib
import hmac
import json
import time
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import FastAPI, Request
from jwt.algorithms import RSAAlgorithm

from book_tracker.app.cloudflare_access import (
    AccessKeys,
    CloudflareAccessMiddleware,
    install_cloudflare_access,
)
from book_tracker.config import Settings

TEAM = "team.cloudflareaccess.com"
AUD = "4714c1358e65fe4b408ad6d432a5f878f08194bdb4752441fd56faefa9b2b6f2"
KID = "key-1"


def _private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


SIGNER = _private_key()
STRANGER = _private_key()


def _jwk(key: rsa.RSAPrivateKey, kid: str) -> dict[str, Any]:
    jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update({"kid": kid, "alg": "RS256", "use": "sig"})
    return jwk


def _token(
    key: rsa.RSAPrivateKey = SIGNER,
    *,
    kid: str = KID,
    algorithm: str = "RS256",
    **overrides: Any,
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "aud": [AUD],
        "email": "owner@example.com",
        "exp": now + 600,
        "iat": now,
        "nbf": now,
        "iss": f"https://{TEAM}",
        "sub": "7335d417-61da-459d-899c-0a01c76a2f94",
        "type": "app",
    }
    claims.update(overrides)
    claims = {name: value for name, value in claims.items() if value is not None}
    return jwt.encode(claims, key, algorithm=algorithm, headers={"kid": kid})


class Certs:
    """The team's `/cdn-cgi/access/certs`, counting how often it is asked."""

    def __init__(self, *keys: tuple[rsa.RSAPrivateKey, str], status: int = 200) -> None:
        self.keys = list(keys)
        self.status = status
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status != 200:
            return httpx.Response(self.status)
        return httpx.Response(
            200, json={"keys": [_jwk(key, kid) for key, kid in self.keys], "public_cert": {}}
        )


def _app(certs: Certs, clock: Any = time.monotonic) -> FastAPI:
    inner = FastAPI()

    @inner.get("/api/items")
    def items(request: Request) -> dict[str, Any]:
        return {"email": getattr(request.state, "cf_access_email", None)}

    @inner.get("/api/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @inner.get("/api/health/ready")
    def ready() -> dict[str, str]:
        return {"status": "ok"}

    keys = AccessKeys(
        TEAM, client=httpx.AsyncClient(transport=httpx.MockTransport(certs)), clock=clock
    )
    inner.add_middleware(CloudflareAccessMiddleware, team_domain=TEAM, audience=AUD, keys=keys)
    return inner


def _get(
    app: FastAPI,
    path: str = "/api/items",
    *,
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
    client: tuple[str, int] = ("203.0.113.9", 4000),
    method: str = "GET",
) -> httpx.Response:
    async def go() -> httpx.Response:
        transport = httpx.ASGITransport(app=app, client=client)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://akasha.example", cookies=cookies
        ) as http:
            return await http.request(method, path, headers=headers)

    return asyncio.run(go())


def _assertion(token: str) -> dict[str, str]:
    return {"Cf-Access-Jwt-Assertion": token}


def test_a_valid_assertion_passes_and_exposes_the_email() -> None:
    certs = Certs((SIGNER, KID))
    response = _get(_app(certs), headers=_assertion(_token()))

    assert response.status_code == 200
    assert response.json() == {"email": "owner@example.com"}
    assert [str(request.url) for request in certs.requests] == [
        f"https://{TEAM}/cdn-cgi/access/certs"
    ]


def test_the_access_cookie_is_accepted_when_the_header_is_absent() -> None:
    response = _get(_app(Certs((SIGNER, KID))), cookies={"CF_Authorization": _token()})

    assert response.status_code == 200


def test_a_request_without_an_assertion_is_refused() -> None:
    certs = Certs((SIGNER, KID))
    response = _get(_app(certs))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "access_denied"
    # Nothing to verify, so nothing fetched.
    assert certs.requests == []


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(_token(STRANGER), id="signed-by-another-key"),
        pytest.param(_token(aud=["another-application"]), id="other-audience"),
        pytest.param(_token(iss="https://evil.cloudflareaccess.com"), id="other-team"),
        pytest.param(_token(exp=int(time.time()) - 3600), id="expired"),
        pytest.param(_token(nbf=int(time.time()) + 3600), id="not-yet-valid"),
        pytest.param(_token(exp=None), id="no-expiry"),
        pytest.param(_token(aud=None), id="no-audience"),
        pytest.param(_token(SIGNER, algorithm="RS512"), id="other-algorithm"),
        pytest.param("not.a.jwt", id="garbage"),
        pytest.param("", id="empty"),
    ],
)
def test_an_invalid_assertion_is_refused(token: str) -> None:
    response = _get(_app(Certs((SIGNER, KID))), headers=_assertion(token))

    assert response.status_code == 403


def test_a_symmetric_token_keyed_by_the_public_key_is_refused() -> None:
    """The classic algorithm confusion: HS256 keyed by the published RSA key."""
    pem = SIGNER.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    now = int(time.time())

    def b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    header = b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": KID}).encode())
    claims = {"aud": [AUD], "iss": f"https://{TEAM}", "exp": now + 600, "email": "x@y"}
    payload = b64(json.dumps(claims).encode())
    # PyJWT itself refuses to HMAC-sign with a PEM key, so the token is built by hand.
    signature = b64(hmac.new(pem, f"{header}.{payload}".encode(), hashlib.sha256).digest())
    forged = f"{header}.{payload}.{signature}"

    response = _get(_app(Certs((SIGNER, KID))), headers=_assertion(forged))

    assert response.status_code == 403


def test_keys_unavailable_fails_closed() -> None:
    response = _get(_app(Certs((SIGNER, KID), status=503)), headers=_assertion(_token()))

    assert response.status_code == 403


def test_an_unreachable_team_fails_closed() -> None:
    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    inner = FastAPI()

    @inner.get("/api/items")
    def items() -> dict[str, str]:
        return {"status": "reached"}

    keys = AccessKeys(TEAM, client=httpx.AsyncClient(transport=httpx.MockTransport(unreachable)))
    inner.add_middleware(CloudflareAccessMiddleware, team_domain=TEAM, audience=AUD, keys=keys)

    assert _get(inner, headers=_assertion(_token())).status_code == 403


def test_keys_are_cached_between_requests() -> None:
    certs = Certs((SIGNER, KID))
    app = _app(certs)

    for _ in range(3):
        assert _get(app, headers=_assertion(_token())).status_code == 200

    assert len(certs.requests) == 1


def test_an_unknown_key_refreshes_at_most_once_a_minute() -> None:
    """Rotation is picked up; a flood of made-up `kid`s is not a flood of fetches."""
    now = [1000.0]
    certs = Certs((SIGNER, KID))
    app = _app(certs, clock=lambda: now[0])
    assert _get(app, headers=_assertion(_token())).status_code == 200

    rotated = _private_key()
    certs.keys.append((rotated, "key-2"))
    now[0] += 5
    # Within a minute of the last fetch: the new kid is not looked up yet.
    assert _get(app, headers=_assertion(_token(rotated, kid="key-2"))).status_code == 403
    assert _get(app, headers=_assertion(_token(kid="made-up"))).status_code == 403
    assert len(certs.requests) == 1

    now[0] += 60
    assert _get(app, headers=_assertion(_token(rotated, kid="key-2"))).status_code == 200
    assert len(certs.requests) == 2


@pytest.mark.parametrize("path", ["/api/health/live", "/api/health/ready"])
def test_the_container_healthcheck_from_loopback_needs_no_assertion(path: str) -> None:
    app = _app(Certs((SIGNER, KID)))

    assert _get(app, path, client=("127.0.0.1", 5000)).status_code == 200
    assert _get(app, path, client=("::1", 5000)).status_code == 200


@pytest.mark.parametrize(
    ("path", "client", "method"),
    [
        ("/api/health/live", ("203.0.113.9", 4000), "GET"),
        ("/api/health/ready", ("172.30.10.2", 4000), "GET"),
        ("/api/items", ("127.0.0.1", 5000), "GET"),
        ("/api/health/live", ("127.0.0.1", 5000), "POST"),
    ],
)
def test_the_healthcheck_exemption_is_narrow(
    path: str, client: tuple[str, int], method: str
) -> None:
    response = _get(_app(Certs((SIGNER, KID))), path, client=client, method=method)

    assert response.status_code == 403


def test_the_exemption_reads_the_raw_path_not_the_host_header() -> None:
    """F2's lesson: a forged Host must not turn into an exempt path."""
    response = _get(
        _app(Certs((SIGNER, KID))),
        "/api/items",
        headers={"Host": "x/api/health/live?"},
        client=("127.0.0.1", 5000),
    )

    assert response.status_code == 403


def test_install_is_a_no_op_without_settings(tmp_path: Any) -> None:
    app = FastAPI()
    install_cloudflare_access(app, Settings(data_dir=tmp_path))

    assert app.user_middleware == []


def test_install_registers_the_gate_outermost(tmp_path: Any) -> None:
    app = FastAPI()

    @app.middleware("http")
    async def inner(request: Request, call_next: Any) -> Any:
        return await call_next(request)

    install_cloudflare_access(
        app, Settings(data_dir=tmp_path, cf_access_team_domain=TEAM, cf_access_aud=AUD)
    )

    assert app.user_middleware[0].cls is CloudflareAccessMiddleware


def test_create_app_refuses_requests_without_an_assertion(tmp_path: Any) -> None:
    """End to end through the real factory: the gate stands before the auth boundary."""
    from book_tracker.main import create_app

    app = create_app(
        Settings(
            data_dir=tmp_path,
            auth="on",
            cf_access_team_domain=TEAM,
            cf_access_aud=AUD,
        )
    )

    assert app.user_middleware[0].cls is CloudflareAccessMiddleware
    response = _get(app, "/api/auth/me")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "access_denied"
