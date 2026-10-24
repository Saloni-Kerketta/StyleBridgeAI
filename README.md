
# StyleBridge AI: Recommender for clothing and footwear/accessories

FastAPI backend + React/Tailwind frontend. All bundled data is **synthetic**.

## The logic
Recommendations are produced **separately for each domain**: *Clothing* (tops, bottoms, dresses, ethnic sets, outerwear) and *Footwear & accessories* (footwear, accessories, bags). For each domain:

1. **Interest** = the style, colour and occasion attributes of what the shopper **bought** (in either domain).
2. **Shoppers like you** = the 30 same-gender shoppers with the closest interest.
3. **Recommend what those shoppers bought in this domain**, ranked by similarity x number of purchases. Items the shopper has already seen are excluded.
4. **No purchase history -> the most popular items of the domain** (by purchases). Popularity also back-fills if the neighbours run out of items.

Because interest is built from attributes shared by both domains, a shopper who has only bought clothes is matched with shoppers who like the same things and gets what *they* bought in footwear/accessories, and the other way round. That is the cross-domain step. Stock, active status, gender and (optionally) sizes are enforced in code before ranking.

## Run it
```bash
# Backend (Python 3.10+)
cd backend
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m scripts.evaluate                               # writes artifacts/evaluation.json (about 20 s)
uvicorn app.main:app --reload --port 8000                # trains on startup (about 5 s)
python -m pytest -q                                      # 18 tests

# Frontend (Node 18+), in a second terminal
cd frontend && npm install && npm run dev                # http://localhost:5173 (proxies /api to :8000)
```
API docs: http://localhost:8000/docs. For a deployed frontend set `VITE_API_URL` and add your origin to CORS in `app/main.py`.

## Using the app
- **Sign in** with a demo account (or type a shopper ID such as `U0002`). The left side then shows only **your own** profile: purchases per domain, learned interest, stated preferences, sizes, budget. Nothing about any other shopper is fetched or shown anywhere.
- The right side shows each domain as a **Top pick** followed by "More picks, in order". The left and right sides **scroll independently** on large screens.
- Click **Bought it** on a card: your interest and neighbours update immediately. A guest with no history switches from "most popular" to "shoppers like you".
- **Compare models** shows your picks under each recommender, with every model's top pick in the first row. **Evaluation** shows the results below.

## Privacy and sign-in
- There is **no route that lists shoppers or accepts another shopper's id**. `/api/me`, `/api/recommendations` and `/api/feedback` identify the shopper only from a signed token (HMAC, 8 hours, stored in `sessionStorage`), so changing an id in a request cannot expose someone else's data.
- **Demo mode** (`SB_DEMO_MODE=1`, the default) exists only because the data is synthetic: `/api/login` signs you in by shopper ID with **no password**, and `/api/demo-accounts` offers six curated synthetic accounts. **Before using real shoppers, set `SB_DEMO_MODE=0` and put your real authentication (passwords/OAuth) behind `/api/login`**; the token check on every shopper route stays as is.
- `/api/retrain` needs the `X-Admin-Key` header when `SB_ADMIN_KEY` is set (and is disabled outside demo mode otherwise).
- Tokens are signed with a key stored in `backend/artifacts/.secret` (created on first run; or set `SB_SECRET`). Keep it private, and use HTTPS when deployed.

## Code map
```
backend/app/
  config.py      domains, neighbours (K), signal, ALS settings, paths
  data.py        CSV loading, interaction matrices (users x all items), item features, virtual guests
  models.py      SimilarShoppersModel (the logic above) + baselines: popularity, content, ALS
  evaluation.py  NDCG/Recall/Hit@K per domain: returning shoppers + "new to this domain"
  auth.py        signed sign-in tokens
  service.py     filters, explanations, feedback, demo accounts
  main.py        REST API
```
| Route | Auth | Purpose |
|---|---|---|
| `GET /api/recommendations?domain=all\|clothing\|accessories&model=&k=&category=&occasion=&colour_family=&max_price=&size_filter=` | token | One section per domain with items, `basis` (neighbours / no_history / ...), readable `basis_text`, per-item `bought_by_similar` |
| `GET /api/me` | token | Your own profile and learned interest |
| `POST /api/feedback` `{product_id, event_type}` | token | `purchase` updates your interest at once |
| `POST /api/login`, `GET /api/demo-accounts` | demo mode only | Demo sign-in |
| `GET /api/health`, `/api/domains`, `/api/models`, `/api/evaluation` | public | Metadata and aggregate results (no personal data) |
| `POST /api/retrain` | admin key | Refit including feedback |

## Evaluation (NDCG@10, seed 42, test split)
"New to this domain": 25% of shoppers who bought in the *other* domain have all events in this domain hidden, so they can only be served from the other domain's interest.

| Domain / scenario | Shoppers like you | Most popular | Content-based | ALS |
|---|---|---|---|---|
| Clothing, returning | 0.119 | 0.057 | 0.184 | 0.086 |
| Clothing, new to clothing | 0.217 | 0.112 | 0.317 | 0.112 |
| Accessories, returning | 0.160 | 0.075 | 0.228 | 0.082 |
| Accessories, new to accessories | 0.262 | 0.141 | 0.379 | 0.141 |

- "Shoppers like you" roughly **doubles popularity in all four settings**, including the cross-domain one. ALS equals popularity for new-to-domain shoppers because it has no signal for them.
- **It does not beat the content-based baseline here.** That model also uses stated preferences and likes/saves/views, which are much richer than the few purchases per shopper (median 4), and in this synthetic data stated preferences and behaviour come from the same hidden taste. With real, noisier profiles the gap may differ. Test on real data.
- `SIGNAL = "engagement"` in `config.py` also uses views, likes, saves and carts. It lifts "Shoppers like you" by about 20-35% (e.g. accessories new-to-domain 0.262 -> 0.330) but is still below content-based, and "no purchase history" then means "no activity at all".
- Absolute numbers are optimistic. Compare models against each other only.

## Product photos (optional)
Cards show a colour swatch by default. To show photos, `frontend/src/imageApi.js` fetches them with axios from the Unsplash API:
1. Create an app at https://unsplash.com/developers, copy its **Access Key**, copy `frontend/.env.example` to `frontend/.env`, set `VITE_UNSPLASH_ACCESS_KEY=your_key`, restart `npm run dev`.
2. Photos are searched by colour + item type, so they are **illustrative stock images, not the exact catalogue item**.
3. Demo apps get **50 requests/hour**. Results are cached (memory + `localStorage`), and after a 401/403/429 the app stops calling the API for 10 minutes and keeps the swatches.
4. Unsplash requires crediting the photographer and Unsplash with `utm` links and hotlinking their URLs (done in `ProductImage.jsx` and the footer). The key is visible in the browser bundle; move the call into the backend if you deploy.

## Using your own data
Replace the CSVs in `data/` (same columns as the dataset pack), rerun `python -m scripts.evaluate`, restart. The domain split is `DOMAINS` in `config.py`. The similarity step is a dense users x users matrix, fine up to a few tens of thousands of shoppers; beyond that use approximate nearest neighbours.

## Connecting to the outfit builder
The outfit builder asks for ranked candidates per category (`category=footwear`, `accessory`, `bag`, `top`, ... with `max_price` from the remaining budget), then validates total price, stock and sizes deterministically.
=======
# StyleBridgeAI
>>>>>>> 8415bd1ed55d00557ebce809a3c78aa065cf67e1
