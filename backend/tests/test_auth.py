import sqlite3
import pytest
from fastapi.testclient import TestClient
from app import accounts, config as C
from app.main import app


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    C.ACCOUNTS_DB = tmp_path_factory.mktemp("auth") / "accounts.db"      # never touch the real accounts file
    with TestClient(app) as c:
        yield c


def form(email="Ana@Example.com", password="correct horse", **kw):
    return {"email": email, "password": password, "gender": "women", "age_group": "25-34", "preferred_styles": ["casual", "minimalist"],
            "favourite_colours": ["Navy", "White"], "budget_per_outfit_inr": 2500, "top_size": "M", "bottom_size": "30", "shoe_size": "6", **kw}


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_then_sign_in_and_see_only_own_profile(client):
    r = client.post("/api/auth/register", json=form())
    assert r.status_code == 201
    uid = r.json()["user_id"]
    me = client.get("/api/me", headers=bearer(r.json()["token"])).json()
    assert me["user_id"] == uid and me["state"] == "no_purchases" and me["is_guest"] is False
    login = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "correct horse"})   # email is case-insensitive
    assert login.status_code == 200 and login.json()["user_id"] == uid


def test_new_account_gets_recommendations_and_can_buy(client):
    t = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "correct horse"}).json()["token"]
    recs = client.get("/api/recommendations", headers=bearer(t)).json()
    assert [s["basis"] for s in recs["sections"]] == ["no_history", "no_history"] and all(s["items"] for s in recs["sections"])
    pid = recs["sections"][0]["items"][0]["product_id"]
    assert client.post("/api/feedback", json={"product_id": pid, "event_type": "purchase"}, headers=bearer(t)).status_code == 200


def test_wrong_password_unknown_email_and_duplicate(client):
    assert client.post("/api/auth/login", json={"email": "ana@example.com", "password": "nope nope nope"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "whatever123"}).status_code == 401
    assert client.post("/api/auth/register", json=form(email="ANA@example.com")).status_code == 409


def test_validation(client):
    assert client.post("/api/auth/register", json=form(email="bad", password="longenough")).status_code == 422
    assert client.post("/api/auth/register", json=form(email="b@example.com", password="short")).status_code == 422
    assert client.post("/api/auth/register", json=form(email="b@example.com", preferred_styles=[])).status_code == 422
    assert client.post("/api/auth/register", json=form(email="b@example.com", top_size="XXL")).status_code == 422   # not a women's size


def test_password_is_stored_only_as_a_salted_hash(client):
    con = sqlite3.connect(C.ACCOUNTS_DB)
    (h,) = con.execute("SELECT password_hash FROM accounts WHERE email='ana@example.com'").fetchone()
    assert h.startswith("scrypt$") and "correct horse" not in h
    assert accounts.hash_password("x") != accounts.hash_password("x")


def test_registered_shopper_cannot_be_reached_through_demo_login_or_demo_list(client):
    uid = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "correct horse"}).json()["user_id"]
    assert client.post("/api/login", json={"user_id": uid}).status_code == 403
    assert uid not in [a["user_id"] for a in client.get("/api/demo-accounts").json()]


def test_account_survives_a_restart(client):
    with TestClient(app) as again:                      # lifespan runs again and reloads accounts.db
        assert again.post("/api/auth/login", json={"email": "ana@example.com", "password": "correct horse"}).status_code == 200


def test_login_is_rate_limited(client):
    for _ in range(C.LOGIN_MAX_FAILS):
        client.post("/api/auth/login", json={"email": "victim@example.com", "password": "guess guess"})
    assert client.post("/api/auth/login", json={"email": "victim@example.com", "password": "guess guess"}).status_code == 429


def test_registration_can_be_closed(client, monkeypatch):
    monkeypatch.setattr(C, "REGISTRATION_OPEN", False)
    assert client.post("/api/auth/register", json=form(email="c@example.com")).status_code == 403