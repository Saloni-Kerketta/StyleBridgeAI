"""FastAPI app.  Run from backend/:  uvicorn app.main:app --reload --port 8000

Privacy model: shopper-specific routes (/api/me, /api/recommendations, /api/feedback) identify the shopper ONLY from a
signed token. There is no route that lists shoppers or accepts another shopper's id."""
from contextlib import asynccontextmanager
import json
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from . import auth, config as C
from .service import RecommenderService, MODELS

svc: RecommenderService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global svc
    svc = RecommenderService().train()
    yield


app = FastAPI(title="StyleBridge AI - Recommender (clothing + footwear/accessories)", version="3.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


def current_user(authorization: str | None = Header(None)) -> str:
    uid = auth.read_token(authorization[7:]) if authorization and authorization.startswith("Bearer ") else None
    if not uid or uid not in svc.ds.user_idx:
        raise HTTPException(401, "Please sign in.")
    return uid


class Login(BaseModel):
    user_id: str


class Feedback(BaseModel):
    product_id: str
    event_type: str  # view | like | save | add_to_cart | purchase | dismiss


# ------------------------------------------------------------ public (no personal data)
@app.get("/api/health")
def health():
    return {"status": "ok", "trained_at": svc.trained_at, "demo_mode": C.DEMO_MODE, "signal": C.SIGNAL, "neighbours": C.NEIGHBOURS}


@app.get("/api/domains")
def domains():
    return [{"name": n, "label": c["label"], "categories": c["categories"]} for n, c in C.DOMAINS.items()]


@app.get("/api/models")
def models():
    return [{"name": n, "description": svc.models[n].description, "default": n == "similar_shoppers"} for n in MODELS]


@app.get("/api/evaluation")
def evaluation():
    if not C.EVAL_FILE.exists():
        raise HTTPException(404, "No evaluation found. Run: python -m scripts.evaluate")
    return json.loads(C.EVAL_FILE.read_text())


# ------------------------------------------------------------ demo sign-in (synthetic data only)
@app.get("/api/demo-accounts")
def demo_accounts():
    if not C.DEMO_MODE:
        raise HTTPException(404, "Not found")
    return svc.demo_accounts()


@app.post("/api/login")
def login(body: Login):
    """DEMO ONLY: signs in by shopper id with no password. Replace with real authentication before real use."""
    if not C.DEMO_MODE:
        raise HTTPException(404, "Not found")
    if body.user_id not in svc.ds.user_idx:
        raise HTTPException(404, "Unknown shopper id")
    return {"token": auth.make_token(body.user_id), "user_id": body.user_id}


# ------------------------------------------------------------ signed-in shopper only
@app.get("/api/me")
def me(uid: str = Depends(current_user)):
    u = svc.user_row(uid)
    return {**svc.user_summary(u), "interest": svc.interest(u)}


@app.get("/api/recommendations")
def recommendations(uid: str = Depends(current_user), domain: str = "all", model: str = "similar_shoppers",
                    k: int = Query(8, ge=1, le=30), category: str | None = None, occasion: str | None = None,
                    colour_family: str | None = None, max_price: int | None = Query(None, ge=1), size_filter: bool = True):
    try:
        return svc.recommend(uid, domain, model, k, category=category, occasion=occasion,
                             colour_family=colour_family, max_price=max_price, size_filter=size_filter)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/feedback")
def feedback(f: Feedback, uid: str = Depends(current_user)):
    if f.product_id not in svc.ds.item_idx:
        raise HTTPException(404, f"Unknown product '{f.product_id}'")
    try:
        return svc.record_feedback(uid, f.product_id, f.event_type)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ------------------------------------------------------------ admin
@app.post("/api/retrain")
def retrain(x_admin_key: str | None = Header(None)):
    """Refit all models including feedback. Needs the X-Admin-Key header when SB_ADMIN_KEY is set; without it, only in demo mode."""
    if (C.ADMIN_KEY and x_admin_key != C.ADMIN_KEY) or (not C.ADMIN_KEY and not C.DEMO_MODE):
        raise HTTPException(403, "Admin key required")
    svc.train()
    return {"status": "retrained", "trained_at": svc.trained_at, "feedback_events": len(svc.extra_events)}
