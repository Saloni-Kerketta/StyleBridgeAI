"""Accounts: email + password sign-up and sign-in. Stdlib only (sqlite3 + scrypt).

Passwords are never stored: only a salted scrypt hash. Each account owns exactly one shopper id (random, e.g. R3F9A12C),
and the shopper's profile is kept next to it so the recommender can load it at startup.
"""
from __future__ import annotations
import hashlib, hmac, json, re, secrets, sqlite3, time
from contextlib import closing
import pandas as pd
from . import config as C

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_N, _R, _P = 2 ** 14, 8, 1


class EmailTaken(Exception):
    pass


def clean_email(email: str) -> str:
    e = (email or "").strip().lower()
    if len(e) > 254 or not EMAIL_RE.match(e):
        raise ValueError("Enter a valid email address.")
    return e


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, maxmem=64 * 1024 * 1024)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${h.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, h = stored.split("$")
        calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), maxmem=64 * 1024 * 1024)
        return hmac.compare_digest(calc, bytes.fromhex(h))
    except Exception:
        return False


_DUMMY = None


def _db() -> sqlite3.Connection:
    C.ACCOUNTS_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(C.ACCOUNTS_DB)
    con.execute("""CREATE TABLE IF NOT EXISTS firebase_accounts (
        firebase_uid TEXT PRIMARY KEY, email TEXT, user_id TEXT UNIQUE NOT NULL, profile TEXT NOT NULL, created_at TEXT NOT NULL)""")
    return con


def create_account(email: str, password: str, profile: dict) -> str:
    """Returns the new shopper id. Raises EmailTaken if the email is already registered."""
    email = clean_email(email)
    uid = "R" + secrets.token_hex(4).upper()
    try:
        with closing(_db()) as con, con:
            con.execute("INSERT INTO accounts (email, password_hash, user_id, profile, created_at) VALUES (?,?,?,?,?)",
                        (email, hash_password(password), uid, json.dumps(profile), time.strftime("%Y-%m-%d %H:%M:%S")))
    except sqlite3.IntegrityError:
        raise EmailTaken(email)
    return uid


def firebase_user_id(firebase_uid: str) -> str | None:
    """The shopper id linked to a Firebase user, or None if that Firebase user has no shopper profile yet."""
    if not C.ACCOUNTS_DB.exists():
        return None
    with closing(_db()) as con:
        row = con.execute("SELECT user_id FROM firebase_accounts WHERE firebase_uid = ?", (firebase_uid,)).fetchone()
    return row[0] if row else None


def create_firebase_account(firebase_uid: str, email: str | None, profile: dict) -> str:
    """Links a Firebase user to a new shopper profile. No password is stored here: Firebase owns the credentials."""
    uid = "R" + secrets.token_hex(4).upper()
    with closing(_db()) as con, con:
        con.execute("INSERT INTO firebase_accounts (firebase_uid, email, user_id, profile, created_at) VALUES (?,?,?,?,?)",
                    (firebase_uid, email, uid, json.dumps(profile), time.strftime("%Y-%m-%d %H:%M:%S")))
    return uid

def authenticate(email: str, password: str) -> str | None:
    """Shopper id if the email and password match, else None. Takes the same time for unknown emails."""
    global _DUMMY
    _DUMMY = _DUMMY or hash_password("not-a-real-password")
    try:
        email = clean_email(email)
    except ValueError:
        verify_password(password, _DUMMY)
        return None
    with closing(_db()) as con:
        row = con.execute("SELECT password_hash, user_id FROM accounts WHERE email = ?", (email,)).fetchone()
    ok = verify_password(password, row[0] if row else _DUMMY)
    return row[1] if row and ok else None


def profile_row(user_id: str, p: dict) -> dict:
    """A users.csv-shaped row for the recommender."""
    return {"user_id": user_id, "gender": p["gender"], "age_group": p["age_group"], "city": p.get("city", "Registered"),
            "preferred_styles": "|".join(p["preferred_styles"]), "favourite_colours": "|".join(p["favourite_colours"]),
            "budget_per_outfit_inr": int(p["budget_per_outfit_inr"]), "top_size": p["top_size"],
            "bottom_size": str(p["bottom_size"]), "shoe_size": str(p["shoe_size"]), "is_cold_start": True,
            "is_synthetic": False, "signup_date": time.strftime("%Y-%m-%d")}


def load_profiles() -> pd.DataFrame:
    """Every registered shopper's profile (loaded once at startup so accounts survive restarts)."""
    if not C.ACCOUNTS_DB.exists():
        return pd.DataFrame()
    with closing(_db()) as con:
        rows = (con.execute("SELECT user_id, profile FROM accounts ORDER BY id").fetchall()
                + con.execute("SELECT user_id, profile FROM firebase_accounts ORDER BY rowid").fetchall())
    return pd.DataFrame([profile_row(uid, json.loads(p)) for uid, p in rows])


class LoginLimiter:
    """In-memory brute-force guard: after `limit` failures within `window` seconds, further attempts are refused."""
    def __init__(self, limit=C.LOGIN_MAX_FAILS, window=C.LOGIN_WINDOW_SECONDS):
        self.limit, self.window, self.fails = limit, window, {}

    def _recent(self, key):
        now = time.time()
        self.fails[key] = [t for t in self.fails.get(key, []) if now - t < self.window]
        return self.fails[key]

    def blocked(self, key) -> bool:
        return len(self._recent(key)) >= self.limit

    def fail(self, key):
        self._recent(key).append(time.time())

    def clear(self, key):
        self.fails.pop(key, None)