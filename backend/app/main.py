"""FastAPI app.  Run from backend/:  uvicorn app.main:app --reload --port 8000

Privacy model: shopper-specific routes (/api/me, /api/recommendations, /api/feedback) identify the shopper ONLY from a
signed token. There is no route that lists shoppers or accepts another shopper's id."""
from contextlib import asynccontextmanager
import json, threading
from typing import Literal
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from . import accounts, auth, config as C, firebase
from .service import RecommenderService, MODELS
from .rag import Assistant

svc: RecommenderService | None = None
assistant: Assistant | None = None
limiter = accounts.LoginLimiter()
reg_lock = threading.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global svc, assistant
    svc = RecommenderService().train()
    assistant = Assistant(svc)
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


class PasswordLogin(BaseModel):
    email: str
    password: str


class Profile(BaseModel):
    gender: Literal["women", "men"]
    age_group: str
    preferred_styles: list[str]
    favourite_colours: list[str]
    budget_per_outfit_inr: int = Field(2000, ge=300, le=50000)
    top_size: str
    bottom_size: str
    shoe_size: str


class Register(Profile):
    email: str
    password: str


class FirebaseToken(BaseModel):
    id_token: str


class FirebaseRegister(Profile):
    id_token: str


class Feedback(BaseModel):
    product_id: str
    event_type: str  # view | like | save | add_to_cart | purchase | dismiss


# ------------------------------------------------------------ public (no personal data)
@app.get("/api/health")
def health():
    return {"status": "ok", "trained_at": svc.trained_at, "demo_mode": C.DEMO_MODE, "registration_open": C.REGISTRATION_OPEN, "firebase": firebase.enabled(), "local_auth": C.LOCAL_AUTH, "signal": C.SIGNAL, "neighbours": C.NEIGHBOURS}


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
    u = svc.ds.user_idx[body.user_id]
    if not (svc.ds.users.is_guest.iat[u] or svc.ds.users.is_synthetic.iat[u]):      # real accounts always need their password
        raise HTTPException(403, "This account needs its email and password.")
    return {"token": auth.make_token(body.user_id), "user_id": body.user_id}


# ------------------------------------------------------------ real accounts (email + password)
@app.get("/api/auth/options")
def auth_options():
    return {**svc.signup_options(), "registration_open": C.REGISTRATION_OPEN}


def _checked_profile(b: Profile) -> dict:
    o = svc.signup_options()
    if b.age_group not in o["age_groups"]:
        raise HTTPException(422, "Choose an age group.")
    styles, colours = list(dict.fromkeys(b.preferred_styles)), list(dict.fromkeys(b.favourite_colours))
    if not 1 <= len(styles) <= 5 or any(x not in o["styles"] for x in styles):
        raise HTTPException(422, "Pick 1 to 5 styles.")
    if not 1 <= len(colours) <= 6 or any(x not in o["colours"] for x in colours):
        raise HTTPException(422, "Pick 1 to 6 favourite colours.")
    sz = o["sizes"][b.gender]
    if b.top_size not in sz["top"] or b.bottom_size not in sz["bottom"] or b.shoe_size not in sz["shoe"]:
        raise HTTPException(422, "Choose your sizes from the lists.")
    return {"gender": b.gender, "age_group": b.age_group, "preferred_styles": styles, "favourite_colours": colours,
            "budget_per_outfit_inr": b.budget_per_outfit_inr, "top_size": b.top_size, "bottom_size": b.bottom_size, "shoe_size": b.shoe_size}


@app.post("/api/auth/register", status_code=201)
def register(b: Register):
    global svc
    if not C.LOCAL_AUTH:
        raise HTTPException(404, "Not found")
    if not C.REGISTRATION_OPEN:
        raise HTTPException(403, "Registration is closed.")
    try:
        email = accounts.clean_email(b.email)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if not 8 <= len(b.password) <= 128:
        raise HTTPException(422, "Password must be 8 to 128 characters.")
    profile = _checked_profile(b)
    with reg_lock:                                   # one sign-up at a time: each one retrains the models with the new shopper
        try:
            uid = accounts.create_account(email, b.password, profile)
        except accounts.EmailTaken:
            raise HTTPException(409, "An account with this email already exists. Sign in instead.")
        new = svc.with_new_user(accounts.profile_row(uid, profile))
        svc = new
        assistant.svc = new
    return {"token": auth.make_token(uid), "user_id": uid}


@app.post("/api/auth/login")
def password_login(b: PasswordLogin, request: Request):
    if not C.LOCAL_AUTH:
        raise HTTPException(404, "Not found")
    key = f"{request.client.host if request.client else '?'}|{b.email.strip().lower()}"
    if limiter.blocked(key):
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")
    uid = accounts.authenticate(b.email, b.password)
    if not uid or uid not in svc.ds.user_idx:
        limiter.fail(key)
        raise HTTPException(401, "Incorrect email or password.")
    limiter.clear(key)
    return {"token": auth.make_token(uid), "user_id": uid}


# ------------------------------------------------------------ Firebase Authentication
def _firebase_claims(id_token: str) -> dict:
    if not firebase.enabled():
        raise HTTPException(503, "Firebase sign-in isn't configured on the server.")
    try:
        return firebase.verify(id_token)
    except firebase.InvalidToken:
        raise HTTPException(401, "Your sign-in is invalid or has expired. Please sign in again.")


@app.post("/api/auth/firebase")
def firebase_login(b: FirebaseToken):
    """Trade a Firebase ID token for this app's session token. 404 = signed in with Firebase but no shopper profile yet."""
    claims = _firebase_claims(b.id_token)
    uid = accounts.firebase_user_id(claims["uid"])
    if not uid or uid not in svc.ds.user_idx:
        raise HTTPException(404, "No shopper profile for this account yet.")
    return {"token": auth.make_token(uid, ttl=C.FIREBASE_SESSION_SECONDS), "user_id": uid}


@app.post("/api/auth/firebase/register", status_code=201)
def firebase_register(b: FirebaseRegister):
    global svc
    claims = _firebase_claims(b.id_token)
    profile = _checked_profile(b)
    with reg_lock:                                   # one sign-up at a time: each one retrains the models with the new shopper
        uid = accounts.firebase_user_id(claims["uid"])
        if uid is None:                              # already linked (e.g. double click)? then just sign in
            if not C.REGISTRATION_OPEN:
                raise HTTPException(403, "Registration is closed.")
            uid = accounts.create_firebase_account(claims["uid"], claims.get("email"), profile)
            new = svc.with_new_user(accounts.profile_row(uid, profile))
            svc = new
            assistant.svc = new
    return {"token": auth.make_token(uid, ttl=C.FIREBASE_SESSION_SECONDS), "user_id": uid}


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


class Ask(BaseModel):
    question: str = Field(min_length=2, max_length=500)


@app.post("/api/ask")
def ask(body: Ask, uid: str = Depends(current_user)):
    """RAG: answers about products, store policies (e.g. return window) and the signed-in shopper's own purchases."""
    return assistant.answer(uid, body.question)


# ------------------------------------------------------------ admin
@app.post("/api/retrain")
def retrain(x_admin_key: str | None = Header(None)):
    """Refit all models including feedback. Needs the X-Admin-Key header when SB_ADMIN_KEY is set; without it, only in demo mode."""
    if (C.ADMIN_KEY and x_admin_key != C.ADMIN_KEY) or (not C.ADMIN_KEY and not C.DEMO_MODE):
        raise HTTPException(403, "Admin key required")
    svc.train()
    return {"status": "retrained", "trained_at": svc.trained_at, "feedback_events": len(svc.extra_events)}