"""Signed sign-in tokens (stdlib only). A token proves WHICH shopper is calling, so shopper-specific routes never
take a user id from the request: nobody can read another shopper's profile or recommendations by changing an ID."""
import base64, hashlib, hmac, os, secrets, time
from . import config as C


def _secret() -> bytes:
    env = os.getenv("SB_SECRET")
    if env:
        return env.encode()
    if not C.SECRET_FILE.exists():
        C.SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
        C.SECRET_FILE.write_text(secrets.token_hex(32))
    return C.SECRET_FILE.read_text().strip().encode()


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()


def make_token(user_id: str, ttl: int = C.TOKEN_TTL_SECONDS) -> str:
    payload = f"{user_id}|{int(time.time()) + ttl}"
    return base64.urlsafe_b64encode(f"{payload}|{_sign(payload)}".encode()).decode()


def read_token(token: str) -> str | None:
    """Returns the shopper id, or None if the token is malformed, tampered with or expired."""
    try:
        payload, sig = base64.urlsafe_b64decode(token.encode()).decode().rsplit("|", 1)
        user_id, exp = payload.rsplit("|", 1)
        if not hmac.compare_digest(sig, _sign(payload)) or int(exp) < time.time():
            return None
        return user_id
    except Exception:
        return None
