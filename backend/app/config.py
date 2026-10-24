"""Central configuration. Override paths with SB_DATA_DIR / SB_ARTIFACT_DIR."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("SB_DATA_DIR", ROOT / "data"))
ARTIFACT_DIR = Path(os.getenv("SB_ARTIFACT_DIR", ROOT / "backend" / "artifacts"))
FEEDBACK_FILE = ARTIFACT_DIR / "feedback_events.jsonl"
EVAL_FILE = ARTIFACT_DIR / "evaluation.json"
SECRET_FILE = ARTIFACT_DIR / ".secret"      # signing key for sign-in tokens (created on first run; keep private)

# Demo mode: enables /api/login (sign in by shopper ID, NO password) and /api/demo-accounts (5 curated synthetic accounts).
# It exists only because the bundled data is synthetic. Before real use set SB_DEMO_MODE=0 and plug your own
# authentication into /api/login. Every shopper-specific route stays token-protected either way.
DEMO_MODE = os.getenv("SB_DEMO_MODE", "1") == "1"
ADMIN_KEY = os.getenv("SB_ADMIN_KEY")        # required in the X-Admin-Key header for /api/retrain when set
TOKEN_TTL_SECONDS = 8 * 3600

SEED = 42
EVENT_WEIGHTS = {"view": 1, "like": 2, "save": 3, "add_to_cart": 4, "purchase": 5, "dismiss": -1}
POSITIVE_MIN_WEIGHT = 2           # like/save/cart/purchase count as "relevant" when evaluating

# The two fashion domains. Recommendations are produced for each one separately.
DOMAINS = {
    "clothing": {"label": "Clothing", "categories": ["top", "bottom", "dress", "ethnic_set", "outerwear"]},
    "accessories": {"label": "Footwear & accessories", "categories": ["footwear", "accessory", "bag"]},
}

# "Shoppers like you" logic
SIGNAL = "purchases"      # what defines interest and what neighbours are "buying": "purchases" (default) or
                          # "engagement" (views/likes/saves/carts/purchases weighted by EVENT_WEIGHTS)
NEIGHBOURS = 30           # how many similar shoppers to learn from
MIN_PURCHASES = 1         # fewer purchases than this = "no purchase history" -> most popular items of the domain

# ALS baseline
LATENT_DIM = 32
ALS_ITERS = 15
ALS_REG = 0.1
ALS_ALPHA = 8.0
