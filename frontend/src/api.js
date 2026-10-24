import { useEffect, useState } from "react";

const BASE = import.meta.env.VITE_API_URL ?? "";

// The sign-in token lives only in this browser tab (sessionStorage) and is sent on every request.
// The server derives WHICH shopper is calling from the token, so the app never sends or lists other shoppers' ids.
const KEY = "sb_session";
export const session = {
  get: () => { try { return JSON.parse(sessionStorage.getItem(KEY)); } catch { return null; } },
  set: (s) => sessionStorage.setItem(KEY, JSON.stringify(s)),
  clear: () => sessionStorage.removeItem(KEY),
};

async function request(path, { params, method = "GET", body } = {}) {
  const qs = params
    ? "?" + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "").map(([k, v]) => [k, String(v)]))
    : "";
  const token = session.get()?.token;
  const headers = { ...(body ? { "Content-Type": "application/json" } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) };
  const res = await fetch(`${BASE}/api${path}${qs}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    const err = new Error(detail.detail || `Request failed (${res.status})`);
    err.status = res.status;
    if (res.status === 401 && token) { session.clear(); window.dispatchEvent(new Event("sb-signed-out")); }
    throw err;
  }
  return res.json();
}

export const api = {
  health: () => request("/health"),
  models: () => request("/models"),
  evaluation: () => request("/evaluation"),
  demoAccounts: () => request("/demo-accounts"),
  login: (user_id) => request("/login", { method: "POST", body: { user_id } }),
  me: () => request("/me"),
  recs: (params) => request("/recommendations", { params }),
  feedback: (body) => request("/feedback", { method: "POST", body }),
};

/** Runs `fn` whenever `deps` change; ignores stale responses. */
export function useApi(fn, deps) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  useEffect(() => {
    let live = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    fn()
      .then((data) => live && setState({ data, error: null, loading: false }))
      .catch((error) => live && setState({ data: null, error, loading: false }));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}
