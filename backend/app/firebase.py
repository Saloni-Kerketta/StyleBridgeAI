"""Firebase Authentication on the server: verifies the ID token (an RS256 JWT signed by Google) that the browser got from Firebase.

Needs only the Firebase PROJECT ID, no service-account key. Firebase owns the passwords, Google sign-in, password-reset
emails and sign-in rate limiting; this app only learns "which Firebase user is this" and maps it to a shopper id.
"""
from __future__ import annotations
import threading, time
import requests
from google.auth import jwt as g_jwt
from . import config as C

CERTS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
_certs: dict = {}
_fetched = 0.0
_lock = threading.Lock()


class InvalidToken(Exception):
    pass


def enabled() -> bool:
    return bool(C.FIREBASE_PROJECT_ID)


def _get_certs(force: bool = False) -> dict:
    """Google's public signing certificates, cached for an hour (they rotate, so an unknown key id forces one refresh)."""
    global _certs, _fetched
    with _lock:
        if force or not _certs or time.time() - _fetched > 3600:
            r = requests.get(CERTS_URL, timeout=5)
            r.raise_for_status()
            _certs, _fetched = r.json(), time.time()
        return _certs


def verify(id_token: str) -> dict:
    """Claims of a valid Firebase ID token (uid, email, ...). Raises InvalidToken if it is forged, expired,
    or was issued for a different Firebase project."""
    project = C.FIREBASE_PROJECT_ID
    try:
        kid = g_jwt.decode_header(id_token).get("kid")
        if not kid:
            raise ValueError("token has no key id")
        certs = _get_certs()
        if kid not in certs:
            certs = _get_certs(force=True)
        claims = dict(g_jwt.decode(id_token, certs=certs, audience=project))     # checks signature, expiry, issued-at, audience
    except Exception as e:
        raise InvalidToken(str(e)) from e
    sub = claims.get("sub")
    if claims.get("iss") != f"https://securetoken.google.com/{project}":
        raise InvalidToken("wrong issuer")
    if not isinstance(sub, str) or not 0 < len(sub) <= 128:
        raise InvalidToken("bad subject")
    if claims.get("auth_time", 0) > time.time() + 300:
        raise InvalidToken("auth_time is in the future")
    claims["uid"] = sub
    return claims