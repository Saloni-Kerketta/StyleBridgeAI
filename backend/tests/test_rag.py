import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import config as C
from app.rag import tokenize, TfIdf


@pytest.fixture(scope="module")
def client():
    C.TODAY = "2026-10-28"
    C.LLM_API_KEY = None          # test the deterministic path
    with TestClient(app) as c:
        yield c


def login(client, uid):
    return {"Authorization": f"Bearer {client.post('/api/login', json={'user_id': uid}).json()['token']}"}


def buyer(client):
    from app import main
    a = main.assistant
    return next(u for u in a.svc.ds.user_ids if a.user_purchases(u))


def test_ask_requires_sign_in(client):
    assert client.post("/api/ask", json={"question": "return policy?"}).status_code == 401


def test_policy_question_uses_policy_chunk(client):
    r = client.post("/api/ask", json={"question": "how many days do I have to return footwear"}, headers=login(client, "GUEST-W")).json()
    assert any(s["type"] == "policy" for s in r["sources"]) and "10 days" in r["answer"]


def test_return_by_date_is_computed_from_purchase_date(client):
    from app import main
    uid = buyer(client)
    last = main.assistant.user_purchases(uid)[0]
    r = client.post("/api/ask", json={"question": "until when can I return my last order?"}, headers=login(client, uid)).json()
    assert last["return_by"] in r["answer"] and last["product_id"] in r["answer"]


def test_never_reads_other_shoppers_purchases(client):
    from app import main
    uid = buyer(client)
    mine = {p["product_id"] for p in main.assistant.user_purchases(uid)}
    other = next(u for u in main.svc.ds.user_ids if main.assistant.user_purchases(u) and u != uid)
    theirs = {p["product_id"] for p in main.assistant.user_purchases(other)} - mine
    r = client.post("/api/ask", json={"question": "my recent purchases return date"}, headers=login(client, uid)).json()
    assert not any(s["type"] == "your_purchase" and s["id"] in theirs for s in r["sources"])


def test_tfidf_ranks_matching_doc_first():
    ix = TfIdf(["cotton crop top", "leather black shoes", "refund time"])
    assert ix.scores("leather shoes").argmax() == 1
    assert tokenize("Returns") == ["return"]