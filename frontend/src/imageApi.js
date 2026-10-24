// Fetches a fashion photo for a product with axios from the Unsplash API.
// Create an app at https://unsplash.com/developers, copy its Access Key into frontend/.env as
// VITE_UNSPLASH_ACCESS_KEY=... and restart `npm run dev`.
import axios from "axios";

const KEY = import.meta.env.VITE_UNSPLASH_ACCESS_KEY;
export const imagesEnabled = Boolean(KEY);

// Unsplash asks for referral parameters on every link back to Unsplash or a photographer.
const UTM = "utm_source=stylebridge_ai&utm_medium=referral";
export const withUtm = (url) => (url ? `${url}${url.includes("?") ? "&" : "?"}${UTM}` : url);

const client = axios.create({
  baseURL: import.meta.env.VITE_UNSPLASH_URL ?? "https://api.unsplash.com",
  headers: { Authorization: `Client-ID ${KEY}` },
  timeout: 10000,
});

// Demo apps are limited to 50 requests/hour, so: one lookup per colour + item type, cached in memory and
// localStorage, and after any 401/403/429 we stop calling the API for 10 minutes (cards keep their swatch).
const STORE = "sb_unsplash_cache_v1";
const PAUSE_MS = 10 * 60 * 1000;
let pausedUntil = 0;
const inflight = new Map();
const saved = (() => { try { return JSON.parse(localStorage.getItem(STORE)) || {}; } catch { return {}; } })();
const persist = () => { try { localStorage.setItem(STORE, JSON.stringify(saved)); } catch { /* storage full or blocked */ } };

export const imageQuery = (item) => `${item.colour} ${item.subcategory} fashion`.toLowerCase();

/** Resolves to { url, alt, photographer, profile, link } or null if nothing was found / the API is unavailable. */
export function fetchProductImage(item) {
  if (!KEY) return Promise.resolve(null);
  const query = imageQuery(item);
  if (saved[query]) return Promise.resolve(saved[query]);
  if (Date.now() < pausedUntil) return Promise.resolve(null);
  if (!inflight.has(query)) {
    inflight.set(query, client.get("/search/photos", { params: { query, per_page: 1, orientation: "portrait", content_filter: "high" } })
      .then(({ data }) => {
        const p = data.results?.[0];
        if (!p) return null;
        saved[query] = { url: p.urls.small, alt: p.alt_description || query, photographer: p.user.name, profile: p.user.links.html, link: p.links.html };
        persist();
        return saved[query];
      })
      .catch((e) => {
        if ([401, 403, 429].includes(e.response?.status)) pausedUntil = Date.now() + PAUSE_MS;
        return null;                                  // bad key, rate limit, offline: fall back to the swatch
      })
      .finally(() => inflight.delete(query)));
  }
  return inflight.get(query);
}
