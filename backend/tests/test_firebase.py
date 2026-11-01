"""Firebase sign-in. Tokens are REAL RS256 JWTs signed with a throwaway key, and the verifier runs unmodified:
only the download of Google's public certificates is replaced by our own test certificate."""
import datetime, time
import jwt as pyjwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient
from app import config as C, firebase
from app.main import app

PROJECT = "stylebridge-test"
KID = "test-key-1"


def _make_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(1).not_valid_before(now - datetime.timedelta(days=1)).not_valid_after(now + datetime.timedelta(days=30))
            .sign(key, hashes.SHA256()))
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return pem, cert.public_bytes(serialization.Encoding.PEM).decode()


PRIVATE_PEM, CERT_PEM = _make_key()


def token(uid="fb-ana", email="ana@example.com", aud=PROJECT, iss=None, exp_in=3600, key=None, kid=KID):
    now = int(time.time())
    claims = {"iss": iss or f"https://securetoken.google.com/{aud}", "aud": aud, "sub": uid, "user_id": uid, "email": email,
              "auth_time": now - 5, "iat": now - 5, "exp": now + exp_in}
    return pyjwt.encode(claims, key or PRIVATE_PEM, algorithm="RS256", headers={"kid": kid})


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    C.ACCOUNTS_DB = tmp_path_factory.mktemp("fb") / "accounts.db"
    mp = pytest.MonkeyPatch()
    mp.setattr(C, "FIREBASE_PROJECT_ID", PROJECT)
    mp.setattr(firebase, "_get_certs", lambda force=False: {KID: CERT_PEM})
    with TestClient(app) as c:
        yield c
    mp.undo()


PROFILE = {"gender": "women", "age_group": "25-34", "preferred_styles": ["casual"], "favourite_colours": ["Navy"],
           "budget_per_outfit_inr": 2000, "top_size": "M", "bottom_size": "30", "shoe_size": "6"}


def bearer(t):
    return {"Authorization": f"Bearer {t}"}


# ---- the verifier itself
def test_valid_token_is_accepted(client):
    c = firebase.verify(token())
    assert c["uid"] == "fb-ana" and c["email"] == "ana@example.com"


@pytest.mark.parametrize("bad", [
    lambda: token(aud="some-other-project"),                       # issued for another Firebase project
    lambda: token(iss="https://evil.example.com/" + PROJECT),      # wrong issuer
    lambda: token(exp_in=-120),                                    # expired
    lambda: token(key=_make_key()[0]),                             # signed with a key Google never published
    lambda: token(kid="unknown-kid"),                              # unknown key id
    lambda: "garbage",
    lambda: token()[:-4] + "AAAA",                                 # tampered signature
])
def test_forged_wrong_project_expired_and_garbage_tokens_are_rejected(client, bad):
    with pytest.raises(firebase.InvalidToken):
        firebase.verify(bad())


# ---- the API
def test_signed_in_but_no_profile_yet_is_404(client):
    assert client.post("/api/auth/firebase", json={"id_token": token()}).status_code == 404


def test_register_login_and_own_profile_only(client):
    r = client.post("/api/auth/firebase/register", json={"id_token": token(), **PROFILE})
    assert r.status_code == 201
    uid = r.json()["user_id"]
    me = client.get("/api/me", headers=bearer(r.json()["token"])).json()
    assert me["user_id"] == uid and me["state"] == "no_purchases" and me["is_guest"] is False
    login = client.post("/api/auth/firebase", json={"id_token": token()})
    assert login.status_code == 200 and login.json()["user_id"] == uid
    other = client.post("/api/auth/firebase/register", json={"id_token": token(uid="fb-bob", email="bob@example.com"), **PROFILE}).json()
    assert other["user_id"] != uid                                  # a different Firebase user is a different shopper


def test_registering_twice_does_not_create_a_second_shopper(client):
    a = client.post("/api/auth/firebase/register", json={"id_token": token(), **PROFILE}).json()["user_id"]
    b = client.post("/api/auth/firebase/register", json={"id_token": token(), **PROFILE}).json()["user_id"]
    assert a == b


def test_bad_token_and_bad_profile(client):
    assert client.post("/api/auth/firebase", json={"id_token": "garbage"}).status_code == 401
    assert client.post("/api/auth/firebase/register", json={"id_token": token(aud="other"), **PROFILE}).status_code == 401
    assert client.post("/api/auth/firebase/register", json={"id_token": token(uid="fb-x"), **{**PROFILE, "top_size": "XXL"}}).status_code == 422
    assert client.post("/api/auth/firebase/register", json={"id_token": token(uid="fb-x"), **{**PROFILE, "preferred_styles": []}}).status_code == 422


def test_firebase_shopper_cannot_use_demo_login_and_survives_restart(client):
    uid = client.post("/api/auth/firebase", json={"id_token": token()}).json()["user_id"]
    assert client.post("/api/login", json={"user_id": uid}).status_code == 403
    with TestClient(app) as again:                                  # lifespan reloads accounts.db
        assert again.post("/api/auth/firebase", json={"id_token": token()}).json()["user_id"] == uid


def test_session_token_is_short_lived(client):
    t = client.post("/api/auth/firebase", json={"id_token": token()}).json()["token"]
    import base64
    exp = int(base64.urlsafe_b64decode(t.encode()).decode().split("|")[1])
    assert exp - time.time() <= C.FIREBASE_SESSION_SECONDS


def test_not_configured_and_firebase_only_mode(client, monkeypatch):
    monkeypatch.setattr(C, "LOCAL_AUTH", False)
    assert client.post("/api/auth/login", json={"email": "a@b.co", "password": "x"}).status_code == 404
    assert client.post("/api/auth/register", json={**PROFILE, "email": "a@b.co", "password": "longenough"}).status_code == 404
    monkeypatch.setattr(C, "FIREBASE_PROJECT_ID", None)
    assert client.post("/api/auth/firebase", json={"id_token": token()}).status_code == 503
    assert client.get("/api/health").json()["firebase"] is False