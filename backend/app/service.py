"""RecommenderService: trains models, applies business filters, builds explanations, records feedback."""
from __future__ import annotations
import json, time
from collections import Counter
import numpy as np
import pandas as pd
from . import config as C
from .data import Dataset, build_bundle, load_dataset
from .models import build_models

MODELS = ["similar_shoppers", "popularity", "content", "als"]
TOP_SIZE_CATS = {"top", "dress", "outerwear", "ethnic_set"}
DOMAIN_OF_CATEGORY = {c: d for d, cfg in C.DOMAINS.items() for c in cfg["categories"]}


class RecommenderService:
    def __init__(self, ds: Dataset | None = None):
        self.ds = ds or load_dataset()
        self.extra_events: list[dict] = []
        self.family_of = dict(zip(self.ds.products.colour, self.ds.products.colour_family))
        self.trained_at = None

    # ------------------------------------------------------------ training
    def train(self):
        df = self.ds.interactions
        if self.extra_events:
            df = pd.concat([df, pd.DataFrame(self.extra_events)], ignore_index=True)
        self.b = build_bundle(self.ds, df)
        self.models = build_models(self.b)
        self.sim = self.models["similar_shoppers"]
        self.trained_at = time.strftime("%Y-%m-%d %H:%M:%S")
        return self

    # ------------------------------------------------------------ users
    def user_row(self, user_id):
        return self.ds.user_idx[user_id]  # KeyError -> 404 in the API

    def purchases(self, u):
        return {d: int(self.b.pur[u][m].sum()) for d, m in self.ds.dom_mask.items()}

    def state(self, u):
        p = self.purchases(u)
        n = sum(p.values())
        if n < C.MIN_PURCHASES:
            return "no_purchases"
        return "both_domains" if all(v > 0 for v in p.values()) else "one_domain"

    def user_summary(self, u):
        user = self.ds.users.iloc[u]
        return {
            "user_id": user.user_id, "gender": user.gender, "age_group": user.age_group, "city": user.city,
            "is_guest": bool(user.is_guest), "budget_per_outfit_inr": int(user.budget_per_outfit_inr),
            "preferred_styles": user.preferred_styles.split("|"), "favourite_colours": user.favourite_colours.split("|"),
            "sizes": {"top": user.top_size, "bottom": str(user.bottom_size), "shoe": str(user.shoe_size)},
            "purchases": self.purchases(u), "state": self.state(u),
        }

    def interest(self, u):
        """What the shopper's purchases say about their taste (the basis for finding similar shoppers)."""
        ds = self.ds
        idx = np.nonzero(self.b.pur[u])[0]
        if not len(idx):
            return {"n_purchases": 0, "styles": [], "colour_families": [], "colours": []}
        w = self.b.pur[u][idx]
        count = lambda vals: [k for k, _ in Counter(dict(pd.Series(w, index=vals).groupby(level=0).sum())).most_common(3)]
        p = ds.products.iloc[idx]
        return {"n_purchases": int(w.sum()), "styles": count(p["style"].tolist()),
                "colour_families": count(p.colour_family.tolist()), "colours": count(p.colour.tolist())}

    def demo_accounts(self):
        """A handful of curated synthetic accounts for demos (id + short label only; no purchase details)."""
        ds, picks = self.ds, []
        wanted = [("one_domain", "clothing", "Has bought only clothing"), ("one_domain", "accessories", "Has bought only footwear/accessories"),
                  ("both_domains", None, "Has bought in both domains"), ("no_purchases", None, "Existing shopper with no purchases")]
        for state, dom, label in wanted:
            for u, uid in enumerate(ds.user_ids):
                if ds.users.is_guest.iat[u] or self.state(u) != state:
                    continue
                if dom and (self.purchases(u)[dom] == 0 or any(v for d, v in self.purchases(u).items() if d != dom)):
                    continue
                picks.append({"user_id": uid, "label": label})
                break
        picks.append({"user_id": "GUEST-W", "label": "Brand-new guest (women's catalogue)"})
        picks.append({"user_id": "GUEST-M", "label": "Brand-new guest (men's catalogue)"})
        return picks

    # ------------------------------------------------------------ candidate filtering (deterministic business rules)
    def _needed_size(self, user, category, sizes):
        if category in TOP_SIZE_CATS:
            return user.top_size
        if category == "bottom":
            return user.bottom_size if any(s.isdigit() for s in sizes) else user.top_size
        if category == "footwear":
            return str(user.shoe_size)
        return None

    def _size_ok(self, u):
        user = self.ds.users.iloc[u]
        ok = np.ones(len(self.ds.item_ids), bool)
        for i, (cat, sizes) in enumerate(zip(self.ds.category_arr, self.ds.size_sets)):
            need = self._needed_size(user, cat, sizes)
            ok[i] = need is None or "FREE" in sizes or str(need) in sizes
        return ok

    def eligible(self, u, domain, category=None, occasion=None, colour_family=None, max_price=None, size_filter=True):
        ds = self.ds
        mask = ds.dom_mask[domain] & (ds.gender_arr == ds.user_gender[u]) & ds.active & (ds.stock > 0) & ~self.b.seen[u]
        if category:
            mask &= ds.category_arr == category
        if occasion:
            mask &= np.array([occasion in s for s in ds.occ_sets])
        if colour_family:
            mask &= ds.family_arr == colour_family
        if max_price:
            mask &= ds.price <= max_price
        if size_filter:
            mask &= self._size_ok(u)
        return mask

    # ------------------------------------------------------------ output
    def _item(self, i):
        p = self.ds.products.iloc[i]
        return {"product_id": p.product_id, "name": p["name"], "brand": p.brand, "category": p.category,
                "subcategory": p.subcategory, "colour": p.colour, "colour_family": p.colour_family, "style": p["style"],
                "pattern": p.pattern, "fabric": p.fabric, "price_inr": int(p.price_inr), "mrp_inr": int(p.mrp_inr),
                "discount_pct": int(p.discount_pct), "rating": float(p.rating), "comfort_score": int(p.comfort_score),
                "sizes_available": p.sizes_available.split("|") if isinstance(p.sizes_available, str) else [],
                "occasions": p.occasion_tags.split("|"), "image_url": p.image_url}

    def _basis(self, model, detail, s_is_fallback, u, domain):
        label = C.DOMAINS[domain]["label"]
        bought = self.purchases(u)
        if model == "similar_shoppers":
            if detail is None:
                return "no_history", f"No purchase history yet, so these are the most popular items in {label}."
            if len(detail["neighbours"]) == 0:
                return "no_neighbours", f"No shoppers with a similar interest have bought in {label} yet, so these are the most popular."
            other = [d for d in C.DOMAINS if d != domain][0]
            n = len(detail["neighbours"])
            if bought[domain] == 0:
                return "neighbours", (f"You haven't bought in {label} yet. These are what the {n} shoppers whose interest is closest "
                                      f"to your {C.DOMAINS[other]['label'].lower()} purchases bought.")
            return "neighbours", f"Based on what the {n} shoppers closest to your interest bought."
        if s_is_fallback:
            return "popular_fallback", f"This model has no signal for you in {label}, so these are the most popular."
        return model, {"popularity": f"Most popular in {label}.", "content": "Matched to your preferences and activity.",
                       "als": "Learned from shoppers with similar activity in this domain."}[model]

    def _section(self, u, domain, model, k, filters):
        cfg = C.DOMAINS[domain]
        mask = self.eligible(u, domain, **filters)
        sec = {"domain": domain, "label": cfg["label"], "candidates": int(mask.sum()), "items": []}
        if not mask.any():
            return {**sec, "basis": "none", "basis_text": "", "message": "No in-stock items match these filters. Try widening them."}
        m = self.models[model]
        detail = m.detail(u, domain) if model == "similar_shoppers" else None
        s = m.score(self.b, u, domain, mask)
        fallback = s is None
        if fallback:
            s = self.models["popularity"].score(self.b, u, domain, mask)
        basis, text = self._basis(model, detail, fallback, u, domain)
        s = np.where(mask, s, -np.inf)
        top = [int(i) for i in np.argsort(-s)[:k] if mask[i]]
        cand = s[mask]
        user = self.user_summary(u)
        items = []
        for i in top:
            support = int(detail["support"][i]) if detail is not None else 0
            sold = int(self.b.pur[:, i].sum())
            reasons = []
            if support:
                reasons.append(f"Bought by {support} similar {'shopper' if support == 1 else 'shoppers'}")
            elif basis != "content" and basis != "als":
                reasons.append(f"Popular in {cfg['label']}" + (f" ({sold} bought)" if sold else ""))
            colour, style = self.ds.products.colour.iat[i], self.ds.products["style"].iat[i]
            if colour in user["favourite_colours"]:
                reasons.append(f"Your favourite colour: {colour}")
            if style in user["preferred_styles"]:
                reasons.append(f"Matches your {style} style")
            item = self._item(i)
            item.update(score=round(float(s[i]), 4), match_pct=int(round(100 * (cand <= s[i]).mean())),
                        bought_by_similar=support, purchases=sold, reasons=reasons[:3])
            items.append(item)
        return {**sec, "basis": basis, "basis_text": text, "n_neighbours": 0 if detail is None else int(len(detail["neighbours"])),
                "items": items}

    def recommend(self, user_id, domain="all", model="similar_shoppers", k=8, **filters):
        u = self.user_row(user_id)
        if model not in self.models:
            raise ValueError(f"unknown model '{model}'")
        if domain != "all" and domain not in C.DOMAINS:
            raise ValueError(f"domain must be 'all' or one of {list(C.DOMAINS)}")
        domains = list(C.DOMAINS) if domain == "all" else [domain]
        cat = filters.get("category")
        if cat:
            if cat not in DOMAIN_OF_CATEGORY:
                raise ValueError(f"unknown category '{cat}'")
            if domain not in ("all", DOMAIN_OF_CATEGORY[cat]):
                raise ValueError(f"category '{cat}' belongs to the {DOMAIN_OF_CATEGORY[cat]} domain")
            domains = [DOMAIN_OF_CATEGORY[cat]]
        return {"user": self.user_summary(u), "interest": self.interest(u), "model": model,
                "sections": [self._section(u, d, model, k, filters) for d in domains]}

    # ------------------------------------------------------------ feedback
    def record_feedback(self, user_id, product_id, event_type):
        if event_type not in C.EVENT_WEIGHTS:
            raise ValueError(f"event_type must be one of {list(C.EVENT_WEIGHTS)}")
        u, i = self.user_row(user_id), self.ds.item_idx[product_id]
        w = C.EVENT_WEIGHTS[event_type]
        ev = {"user_id": user_id, "product_id": product_id, "event_type": event_type, "event_weight": w,
              "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "split": "train", "is_synthetic": False}
        self.extra_events.append(ev)
        C.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        with open(C.FEEDBACK_FILE, "a") as f:
            f.write(json.dumps(ev) + "\n")
        b = self.b
        b.seen[u, i] = True                                  # never show the same item again
        if w > 0:
            b.R[u, i] += w
        if w >= C.POSITIVE_MIN_WEIGHT:
            b.P[u, i] = True
        if event_type == "purchase":
            b.pur[u, i] += 1
        self.sim.refresh(u)                                  # the shopper's interest and neighbours update at once
        return {"ok": True, "state": self.state(u), "purchases": self.purchases(u)}
