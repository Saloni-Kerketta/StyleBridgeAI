"""
Recommenders. Every model has  score(bundle, user, domain, mask=None) -> array over ALL items, or None if it has no signal.

SimilarShoppersModel  (the StyleBridge logic)
    1. Interest of a shopper = the style/colour/occasion attributes of what they BOUGHT (any domain).
    2. Similar shoppers = same gender, highest cosine similarity of interest vectors (top K).
    3. Score of an item in the requested domain = sum over similar shoppers of similarity x times they bought it.
       Because interest uses attributes shared by clothing and accessories, a shopper who has only bought clothes
       is matched with shoppers who like the same things and gets what those shoppers bought in accessories (and vice versa).
    4. No purchase history -> None, and the caller shows the most popular items of the domain.
Baselines: popularity, content (stated preferences + history attributes), als (latent CF inside the domain).
"""
from __future__ import annotations
import numpy as np
from . import config as C
from .data import Bundle

# ---------------------------------------------------------------- helpers
def popularity_vector(b: Bundle, domain: str) -> np.ndarray:
    """Purchases per item; engagement strength breaks ties."""
    m = b.ds.dom_mask[domain]
    r = (b.R * m).sum(axis=0)
    return (b.pur * m).sum(axis=0) + 1e-3 * r / max(float(r.max()), 1.0)


def neighbour_scores(sim_row: np.ndarray, signal_dom: np.ndarray, k: int):
    """sim_row: similarity of the target shopper to every shopper (self and other genders already 0).
    signal_dom: (users x items) how much each shopper bought each item of the domain.
    Only shoppers who bought something in the domain can contribute. Returns (scores, support, idx, sims)."""
    has = signal_dom.sum(axis=1) > 0
    s = np.where(has, sim_row, 0.0)
    idx = np.argsort(-s)[:k]
    idx = idx[s[idx] > 0]
    scores = s[idx] @ signal_dom[idx] if len(idx) else np.zeros(signal_dom.shape[1])
    support = (signal_dom[idx] > 0).sum(axis=0) if len(idx) else np.zeros(signal_dom.shape[1], dtype=int)
    return scores, support, idx, s[idx]


def als_implicit(R, k=C.LATENT_DIM, iters=C.ALS_ITERS, reg=C.ALS_REG, alpha=C.ALS_ALPHA, seed=C.SEED):
    """Hu-Koren-Volinsky implicit ALS (dense; fine below ~10k x 10k). Empty rows/cols keep a zero factor."""
    rng = np.random.default_rng(seed)
    P = (R > 0).astype(float)
    Cm = 1.0 + alpha * R
    X = rng.normal(0, 0.1, (R.shape[0], k))
    Y = rng.normal(0, 0.1, (R.shape[1], k))

    def solve(fixed, Cmat, Pmat):
        FtF = fixed.T @ fixed + reg * np.eye(k)
        out = np.zeros((Cmat.shape[0], k))
        for i in range(Cmat.shape[0]):
            nz = np.nonzero(Pmat[i])[0]
            if nz.size == 0:
                continue
            Fn, cn = fixed[nz], Cmat[i, nz]
            out[i] = np.linalg.solve(FtF + (Fn.T * (cn - 1.0)) @ Fn, (Fn.T * cn) @ Pmat[i, nz])
        return out

    for _ in range(iters):
        X = solve(Y, Cm, P)
        Y = solve(X, Cm.T, P.T)
    return X, Y


def _unit(M):
    return M / np.maximum(np.linalg.norm(M, axis=-1, keepdims=True), 1e-9)


# ---------------------------------------------------------------- models
class PopularityModel:
    name = "popularity"
    description = "The most popular items of the domain (by purchases). Same for everyone."

    def fit(self, b):
        self.pop = {d: popularity_vector(b, d) for d in C.DOMAINS}
        return self

    def score(self, b, u, domain, mask=None):
        return self.pop[domain]


class SimilarShoppersModel:
    name = "similar_shoppers"
    description = ("Finds shoppers with the same interest as you (from what they bought) and recommends what they bought "
                   "in this domain. No purchase history: the most popular items of the domain.")

    def fit(self, b):
        self.b = b
        self.Fs = _unit(b.ds.F[:, b.ds.shared_cols])
        self.signal = b.pur if C.SIGNAL == "purchases" else b.R          # live reference: feedback updates it
        self.min_hist = C.MIN_PURCHASES if C.SIGNAL == "purchases" else 1
        g = b.ds.user_gender
        self.same_gender = g[:, None] == g[None, :]
        self.V = _unit(self.signal @ self.Fs)
        self.sim = np.clip(self.V @ self.V.T, 0, None) * self.same_gender
        np.fill_diagonal(self.sim, 0)
        self.pop = {d: popularity_vector(b, d) for d in C.DOMAINS}
        return self

    def has_history(self, u):
        return self.signal[u].sum() >= self.min_hist

    def refresh(self, u):
        """Recompute one shopper's interest after new feedback (cheap; avoids a full retrain)."""
        self.V[u] = _unit(self.signal[u] @ self.Fs)
        row = np.clip(self.V @ self.V[u], 0, None) * self.same_gender[u]
        row[u] = 0
        self.sim[u, :] = row
        self.sim[:, u] = row

    def detail(self, u, domain):
        """None if the shopper has no purchase history, else neighbours and per-item support."""
        if not self.has_history(u):
            return None
        sig = self.signal * self.b.ds.dom_mask[domain][None, :]
        scores, support, idx, sims = neighbour_scores(self.sim[u], sig, C.NEIGHBOURS)
        return {"scores": scores, "support": support, "neighbours": idx, "sims": sims}

    def score(self, b, u, domain, mask=None):
        d = self.detail(u, domain)
        if d is None:
            return None
        return d["scores"] + 1e-6 * self.pop[domain]      # popularity back-fills when neighbours run out of items


class ContentModel:
    name = "content"
    description = "Matches item attributes to your stated preferences and everything you have interacted with."

    def fit(self, b):
        return self

    def score(self, b, u, domain, mask=None):
        ds = b.ds
        m = ds.dom_mask[domain]
        h = (b.R[u] * m) @ ds.F + ((b.R[u] * ~m) @ ds.F) * ds.shared_cols
        n = b.P[u].sum()
        s = _unit(b.S[u])
        h = _unit(h)
        a = n / (n + 5.0)
        return ds.F @ (a * h + (1 - a) * s)


class ALSModel:
    name = "als"
    description = "Collaborative filtering (latent factors) inside the domain. Needs history in that domain."

    def fit(self, b):
        self.f = {d: als_implicit(b.R * b.ds.dom_mask[d][None, :]) for d in C.DOMAINS}
        return self

    def score(self, b, u, domain, mask=None):
        X, Y = self.f[domain]
        return None if not np.any(X[u]) else Y @ X[u]


def build_models(b: Bundle):
    models = [SimilarShoppersModel(), PopularityModel(), ContentModel(), ALSModel()]
    return {m.name: m.fit(b) or m for m in models}
