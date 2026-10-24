import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import auth, config as C


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def login(client, uid):
    r = client.post("/api/login", json={"user_id": uid})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def demo(client, label_part):
    return next(a["user_id"] for a in client.get("/api/demo-accounts").json() if label_part in a["label"])


def test_health_and_domains(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert [d["name"] for d in client.get("/api/domains").json()] == ["clothing", "accessories"]


# ---------------------------------------------------------------- privacy
def test_shopper_routes_require_sign_in(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/recommendations").status_code == 401
    assert client.post("/api/feedback", json={"product_id": "P0001", "event_type": "like"}).status_code == 401


def test_no_route_lists_shoppers_or_takes_another_shoppers_id(client):
    h = login(client, demo(client, "only clothing"))
    for path in ("/api/users", "/api/users/U0002", "/api/recommendations/U0002"):
        assert client.get(path, headers=h).status_code in (404, 405)


def test_each_token_only_ever_returns_its_own_shopper(client):
    a, b = demo(client, "only clothing"), demo(client, "only footwear")
    assert client.get("/api/me", headers=login(client, a)).json()["user_id"] == a
    assert client.get("/api/me", headers=login(client, b)).json()["user_id"] == b
    assert client.get("/api/recommendations", headers=login(client, a)).json()["user"]["user_id"] == a


def test_tampered_expired_and_garbage_tokens_are_rejected(client):
    uid = demo(client, "only clothing")
    token = auth.make_token(uid)
    other = demo(client, "only footwear")
    forged = token.replace(token[:6], auth.make_token(other)[:6], 1)
    for bad in (forged, token[:-4] + "AAAA", "garbage", auth.make_token(uid, ttl=-10)):
        assert client.get("/api/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401


def test_demo_login_is_off_when_demo_mode_is_off(client, monkeypatch):
    monkeypatch.setattr(C, "DEMO_MODE", False)
    assert client.get("/api/demo-accounts").status_code == 404
    assert client.post("/api/login", json={"user_id": "U0002"}).status_code == 404
    assert client.post("/api/retrain").status_code == 403


def test_login_unknown_shopper(client):
    assert client.post("/api/login", json={"user_id": "NOPE"}).status_code == 404


# ---------------------------------------------------------------- recommendation logic (through the API)
def test_both_domains_are_returned_with_correct_categories(client):
    r = client.get("/api/recommendations", headers=login(client, demo(client, "only clothing"))).json()
    assert [s["domain"] for s in r["sections"]] == ["clothing", "accessories"]
    for s in r["sections"]:
        assert s["items"] and all(i["category"] in C.DOMAINS[s["domain"]]["categories"] for i in s["items"])


def test_clothing_only_shopper_gets_accessories_from_similar_shoppers(client):
    r = client.get("/api/recommendations", headers=login(client, demo(client, "only clothing"))).json()
    sec = next(s for s in r["sections"] if s["domain"] == "accessories")
    assert sec["basis"] == "neighbours" and sec["n_neighbours"] > 0 and any(i["bought_by_similar"] > 0 for i in sec["items"])


def test_no_purchase_history_gets_most_popular_items_of_each_domain(client):
    r = client.get("/api/recommendations", params={"k": 6, "size_filter": False}, headers=login(client, "GUEST-W")).json()
    assert r["user"]["state"] == "no_purchases"
    for s in r["sections"]:
        counts = [i["purchases"] for i in s["items"]]
        assert s["basis"] == "no_history" and counts == sorted(counts, reverse=True) and counts[0] > 0


def test_buying_switches_a_guest_from_popular_to_similar_shoppers(client):
    h = login(client, "GUEST-M")
    before = client.get("/api/recommendations", params={"size_filter": False}, headers=h).json()
    item = before["sections"][0]["items"][0]["product_id"]
    assert client.post("/api/feedback", json={"product_id": item, "event_type": "purchase"}, headers=h).status_code == 200
    after = client.get("/api/recommendations", params={"size_filter": False}, headers=h).json()
    assert after["user"]["state"] != "no_purchases" and all(s["basis"] == "neighbours" for s in after["sections"])
    assert item not in [i["product_id"] for s in after["sections"] for i in s["items"]]


def test_filters_domain_and_category_rules(client):
    h = login(client, demo(client, "only clothing"))
    r = client.get("/api/recommendations", params={"domain": "accessories", "max_price": 800}, headers=h).json()
    assert [s["domain"] for s in r["sections"]] == ["accessories"]
    assert all(i["price_inr"] <= 800 and i["sizes_available"] for i in r["sections"][0]["items"])
    r = client.get("/api/recommendations", params={"category": "footwear"}, headers=h).json()
    shoe = r["user"]["sizes"]["shoe"]
    assert [s["domain"] for s in r["sections"]] == ["accessories"]
    assert all(i["category"] == "footwear" and shoe in i["sizes_available"] for i in r["sections"][0]["items"])
    assert client.get("/api/recommendations", params={"domain": "clothing", "category": "footwear"}, headers=h).status_code == 400


def test_errors_and_dismissals(client):
    h = login(client, demo(client, "only clothing"))
    assert client.get("/api/recommendations", params={"model": "x"}, headers=h).status_code == 400
    assert client.get("/api/recommendations", params={"domain": "shoes"}, headers=h).status_code == 400
    assert client.post("/api/feedback", json={"product_id": "P0001", "event_type": "bogus"}, headers=h).status_code == 400
    assert client.post("/api/feedback", json={"product_id": "NOPE", "event_type": "like"}, headers=h).status_code == 404
    first = client.get("/api/recommendations", headers=h).json()["sections"][0]["items"][0]["product_id"]
    client.post("/api/feedback", json={"product_id": first, "event_type": "dismiss"}, headers=h)
    again = [i["product_id"] for s in client.get("/api/recommendations", params={"k": 30}, headers=h).json()["sections"] for i in s["items"]]
    assert first not in again
