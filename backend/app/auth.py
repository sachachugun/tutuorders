import base64
import hashlib
import hmac
import json
import time

from fastapi import Header, HTTPException

from app.config import settings


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("utf-8")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def _sign(value: str) -> str:
    digest = hmac.new(settings.auth_secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).digest()
    return _b64url_encode(digest)


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=401, detail="Требуется вход")


def verify_login(username: str, password: str) -> bool:
    return hmac.compare_digest(username, settings.auth_username) and hmac.compare_digest(password, settings.auth_password)


def create_access_token(username: str) -> tuple[str, int]:
    expires_at = int(time.time()) + settings.auth_token_ttl_seconds
    payload = {"sub": username, "exp": expires_at}
    payload_part = _b64url_encode(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    signature = _sign(payload_part)
    return f"{payload_part}.{signature}", expires_at


def decode_access_token(token: str) -> dict:
    try:
        payload_part, signature = token.split(".", 1)
    except ValueError as exc:
        raise _unauthorized() from exc

    expected = _sign(payload_part)
    if not hmac.compare_digest(signature, expected):
        raise _unauthorized()

    try:
        payload = json.loads(_b64url_decode(payload_part))
    except (json.JSONDecodeError, ValueError) as exc:
        raise _unauthorized() from exc

    if int(payload.get("exp", 0)) <= int(time.time()):
        raise _unauthorized()
    return payload


def require_auth(authorization: str | None = Header(default=None)) -> str:
    if not settings.auth_enabled:
        return "local-dev"
    if not authorization or not authorization.startswith("Bearer "):
        raise _unauthorized()
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    subject = str(payload.get("sub", "")).strip()
    if not subject:
        raise _unauthorized()
    return subject
