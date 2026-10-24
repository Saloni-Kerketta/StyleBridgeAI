"""Ranking metrics and the evaluation protocol, run separately for each domain."""
from __future__ import annotations
import json, time
import numpy as np
from . import config as C
from .data import Dataset, build_bundle
from .models import build_models

KS = (5, 10, 20)


def ndcg_at_k(ranked, relevant, k):
    dcg = sum(1.0 / np.log2(i + 2) for i, it in enumerate(ranked[:k]) if it in relevant)
    idcg = sum(1.0 / np.log2(i + 2) for i in range(min(len(relevant), k)))
    return dcg / idcg if idcg else 0.0


def recall_at_k(ranked, relevant, k):
    return len(set(ranked[:k]) & relevant) / len(relevant) if relevant else 0.0


def hit_rate_at_k(ranked, relevant, k):
    return float(bool(set(ranked[:k]) & relevant))


def evaluate_model(model, b, domain, popularity, users, relevant, cand, exclude_seen, ks=KS):
    """cand[gender] -> bool mask of candidate items. A model with no signal for a shopper falls back to popularity,
    exactly as the live app does."""
    acc = {f"{m}@{k}": [] for m in ("ndcg", "recall", "hit") for k in ks}
    recommended = set()
    for u in users:
        mask = cand[b.ds.user_gender[u]].copy()
        if exclude_seen:
            mask &= ~b.seen[u]
        s = model.score(b, u, domain, mask)
        if s is None:
            s = popularity.score(b, u, domain, mask)
        s = np.where(mask, s, -np.inf)
        ranked = [int(i) for i in np.argsort(-s)[:max(ks)] if mask[i]]
        recommended.update(ranked[:10])
        for k in ks:
            acc[f"ndcg@{k}"].append(ndcg_at_k(ranked, relevant[u], k))
            acc[f"recall@{k}"].append(recall_at_k(ranked, relevant[u], k))
            acc[f"hit@{k}"].append(hit_rate_at_k(ranked, relevant[u], k))
    out = {k: round(float(np.mean(v)), 4) for k, v in acc.items()}
    out["coverage@10"] = round(len(recommended) / int((b.ds.active & b.ds.dom_mask[domain]).sum()), 4) if users else 0.0
    return out


def run_protocol(ds: Dataset, cold_frac=0.25, seed=C.SEED, verbose=True):
    """
    For each domain D (candidates = active items of D for the shopper's gender):
      warm           : train on split=train, test on later positive events (like/save/cart/purchase) in D.
      new_to_domain  : 25% of shoppers who HAVE bought in the other domain get ALL their D events removed from
                       training. They must be recommended D items from the interest shown in the other domain.
    """
    rng = np.random.default_rng(seed)
    inter = ds.interactions
    train = inter[inter.split == "train"]
    pos = inter[inter.event_weight >= C.POSITIVE_MIN_WEIGHT]
    real = [u for u, g in zip(ds.user_ids, ds.users.is_guest) if not g]
    b0 = build_bundle(ds, train)
    report = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "k_values": list(KS), "seed": seed,
              "signal": C.SIGNAL, "neighbours": C.NEIGHBOURS, "domains": {},
              "notes": ["All data is synthetic; absolute numbers are optimistic. Compare models against each other only.",
                        "A shopper with no purchase history gets the most popular items, so for them 'Shoppers like you' and 'Most popular' are identical by design.",
                        "New to this domain: the shopper's events in the domain were hidden from training; only their purchases in the other domain are known."]}

    for dom, cfg in C.DOMAINS.items():
        other = [d for d in C.DOMAINS if d != dom][0]
        m_dom, m_oth = ds.dom_mask[dom], ds.dom_mask[other]

        def rel_sets(df, users):
            d = {}
            for uid, pid in zip(df.user_id, df.product_id):
                j = ds.item_idx.get(pid)
                if uid in users and j is not None and m_dom[j]:
                    d.setdefault(ds.user_idx[uid], set()).add(j)
            return d

        has_other = {u for u in real if b0.pur[ds.user_idx[u]][m_oth].sum() > 0}
        has_pos = {ds.user_ids[u] for u in rel_sets(pos, set(real))}
        pool = sorted(has_other & has_pos)
        cold = set(rng.choice(pool, int(len(pool) * cold_frac), replace=False))

        b = build_bundle(ds, train, hide=(cold, dom))
        models = build_models(b)
        cand = {g: ds.active & m_dom & (ds.gender_arr == g) for g in ("women", "men")}

        warm_ids = set(real) - cold
        warm_rel = {u: r - set(np.nonzero(b.seen[u])[0]) for u, r in rel_sets(pos[pos.split == "test"], warm_ids).items()}
        warm_rel = {u: r for u, r in warm_rel.items() if r}
        cold_rel = {u: r for u, r in rel_sets(pos, cold).items() if r}

        scen = {}
        for name, rel, excl in (("warm", warm_rel, True), ("new_to_domain", cold_rel, False)):
            users = sorted(rel)
            res = {mn: evaluate_model(m, b, dom, models["popularity"], users, rel, cand, excl) for mn, m in models.items()}
            scen[name] = {"n_users": len(users), "avg_relevant": round(float(np.mean([len(rel[u]) for u in users])), 2), "results": res}
            if verbose:
                print(f"\n[{cfg['label']} / {name}] shoppers={len(users)}")
                print(f"{'model':18s} NDCG@10  Recall@10  Hit@10  Cov@10")
                for mn, r in res.items():
                    print(f"{mn:18s} {r['ndcg@10']:.4f}   {r['recall@10']:.4f}    {r['hit@10']:.4f}  {r['coverage@10']:.3f}")
        report["domains"][dom] = {"label": cfg["label"], "other_label": C.DOMAINS[other]["label"], "scenarios": scen}
    return report


def save(report, path=C.EVAL_FILE):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
