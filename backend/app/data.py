"""Dataset loading, interaction matrices and item features (users x ALL items, split into domains by mask)."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from . import config as C


def load_raw(data_dir=C.DATA_DIR):
    r = lambda n: pd.read_csv(data_dir / n)
    return r("products.csv"), r("users.csv"), r("interactions.csv")


def make_guests() -> pd.DataFrame:
    """Two virtual shoppers with no history, to demonstrate the 'no purchase history -> most popular' rule."""
    base = dict(age_group="25-34", city="Guest", budget_per_outfit_inr=2000, is_cold_start=True, is_synthetic=False,
                signup_date="2026-10-20", is_guest=True)
    return pd.DataFrame([
        dict(user_id="GUEST-W", gender="women", preferred_styles="casual|classic", favourite_colours="Navy|White|Beige",
             top_size="M", bottom_size="30", shoe_size="6", **base),
        dict(user_id="GUEST-M", gender="men", preferred_styles="casual|classic", favourite_colours="Navy|White|Grey",
             top_size="L", bottom_size="34", shoe_size="9", **base),
    ])


class Dataset:
    def __init__(self, products, users, interactions):
        self.products, self.users = products.reset_index(drop=True), users.reset_index(drop=True)
        self.interactions = interactions
        self.item_ids = self.products.product_id.tolist()
        self.item_idx = {p: i for i, p in enumerate(self.item_ids)}
        self.user_ids = self.users.user_id.tolist()
        self.user_idx = {u: i for i, u in enumerate(self.user_ids)}
        p = self.products
        self.gender_arr = np.array(p.gender.tolist(), dtype=object)
        self.user_gender = np.array(self.users.gender.tolist(), dtype=object)
        self.active = np.array(p.is_active.tolist(), dtype=bool)
        self.stock = np.array(p.total_stock.tolist())
        self.price = np.array(p.price_inr.tolist())
        self.category_arr = np.array(p.category.tolist(), dtype=object)
        self.family_arr = np.array(p.colour_family.tolist(), dtype=object)
        self.dom_mask = {d: np.isin(self.category_arr, cfg["categories"]) for d, cfg in C.DOMAINS.items()}
        self.domain_by_pid = {pid: d for d, m in self.dom_mask.items() for pid in np.array(self.item_ids)[m]}
        self.occ_sets = [set(s.split("|")) for s in p.occasion_tags]
        self.size_sets = [set(str(s).split("|")) if isinstance(s, str) else set() for s in p.sizes_available]
        self.F, self.feature_names = item_feature_matrix(p)
        # attributes that mean the same thing in every category: this is what lets interest carry across domains
        self.shared_cols = np.array([n.startswith(("style_", "colour_", "family_", "occ_")) for n in self.feature_names])


def load_dataset(data_dir=C.DATA_DIR, guests=True) -> Dataset:
    products, users, inter = load_raw(data_dir)
    users = users.assign(is_guest=False)
    if guests:
        users = pd.concat([users, make_guests()], ignore_index=True)
    return Dataset(products, users, inter)


def _index_pairs(df, rmap, cmap, rcol, ccol):
    r = df[rcol].map(rmap).to_numpy(dtype=float)
    c = df[ccol].map(cmap).to_numpy(dtype=float)
    ok = ~(np.isnan(r) | np.isnan(c))
    return r[ok].astype(int), c[ok].astype(int), ok


def strength_matrix(df, rmap, cmap, rcol, ccol) -> np.ndarray:
    """Sum of event weights per (user, item), clipped at 0 (a dismiss cancels a view)."""
    M = np.zeros((len(rmap), len(cmap)))
    r, c, ok = _index_pairs(df, rmap, cmap, rcol, ccol)
    np.add.at(M, (r, c), df.event_weight.to_numpy()[ok])
    return np.clip(M, 0, None)


def event_matrix(df, rmap, cmap, rcol, ccol) -> np.ndarray:
    M = np.zeros((len(rmap), len(cmap)), dtype=bool)
    r, c, _ = _index_pairs(df, rmap, cmap, rcol, ccol)
    M[r, c] = True
    return M


BLOCK_WEIGHTS = {"style": 1.0, "colour": 0.8, "family": 0.6, "sub": 0.5, "cat": 0.3, "occ": 0.4, "price": 0.3}


def item_feature_matrix(products: pd.DataFrame):
    """Weighted one-hot item features, L2-normalised. Returns (F, column_names)."""
    price_bucket = pd.cut(products.price_inr, [0, 500, 1000, 2000, 3500, 1e6],
                          labels=["<500", "500-999", "1000-1999", "2000-3499", "3500+"]).astype(str)
    blocks = {
        "style": pd.get_dummies(products["style"], prefix="style"),
        "colour": pd.get_dummies(products["colour"], prefix="colour"),
        "family": pd.get_dummies(products.colour_family, prefix="family"),
        "sub": pd.get_dummies(products.subcategory, prefix="sub"),
        "cat": pd.get_dummies(products.category, prefix="cat"),
        "occ": products.occasion_tags.str.get_dummies("|").add_prefix("occ_"),
        "price": pd.get_dummies(price_bucket, prefix="price"),
    }
    X = pd.concat([b.astype(float) * BLOCK_WEIGHTS[k] for k, b in blocks.items()], axis=1)
    F = X.to_numpy()
    F = F / np.maximum(np.linalg.norm(F, axis=1, keepdims=True), 1e-9)
    return F, list(X.columns)


def stated_profiles(users: pd.DataFrame, products: pd.DataFrame, feature_names) -> np.ndarray:
    """User vectors built only from profile preferences (works with zero history)."""
    col = {n: i for i, n in enumerate(feature_names)}
    fam_of = dict(zip(products.colour, products.colour_family))
    S = np.zeros((len(users), len(feature_names)))
    for r, u in enumerate(users.itertuples()):
        for s in str(u.preferred_styles).split("|"):
            if f"style_{s}" in col:
                S[r, col[f"style_{s}"]] += 1.0
        for c in str(u.favourite_colours).split("|"):
            if f"colour_{c}" in col:
                S[r, col[f"colour_{c}"]] += 1.0
            if f"family_{fam_of.get(c)}" in col:
                S[r, col[f"family_{fam_of[c]}"]] += 0.5
    return S


@dataclass
class Bundle:
    """users x ALL items matrices built from a chosen slice of interactions."""
    ds: Dataset
    R: np.ndarray      # strength: sum of event weights (clipped at 0)
    P: np.ndarray      # bool: positive engagement (weight >= 2)
    pur: np.ndarray    # purchase counts
    seen: np.ndarray   # bool: any event
    S: np.ndarray      # stated-preference profiles


def build_bundle(ds: Dataset, df: pd.DataFrame, hide=None) -> Bundle:
    """hide=(users, domain): drop those users' events in that domain, simulating 'new to this domain'."""
    if hide:
        users, domain = hide
        in_dom = df.product_id.map(ds.domain_by_pid).eq(domain)
        df = df[~(df.user_id.isin(set(users)) & in_dom)]
    args = (ds.user_idx, ds.item_idx, "user_id", "product_id")
    R = strength_matrix(df, *args)
    P = event_matrix(df[df.event_weight >= C.POSITIVE_MIN_WEIGHT], *args)
    seen = event_matrix(df, *args)
    pur = strength_matrix(df[df.event_type == "purchase"].assign(event_weight=1), *args)
    return Bundle(ds, R, P, pur, seen, stated_profiles(ds.users, ds.products, ds.feature_names))
