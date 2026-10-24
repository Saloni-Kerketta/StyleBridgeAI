import React, { useState } from "react";
import { api, session, useApi } from "../api.js";
import { Message } from "./ui.jsx";

export default function SignIn({ onSignedIn }) {
  const { data: health, error: healthError } = useApi(() => api.health(), []);
  const { data: accounts } = useApi(() => (health?.demo_mode ? api.demoAccounts() : Promise.resolve([])), [health?.demo_mode]);
  const [id, setId] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function signIn(userId) {
    setBusy(true); setError(null);
    try {
      const { token, user_id } = await api.login(userId.trim());
      session.set({ token, userId: user_id });
      onSignedIn(user_id);
    } catch (e) {
      setError(e.status === 404 ? "No shopper with that ID." : e.message);
    } finally { setBusy(false); }
  }

  return (
    <div className="mx-auto grid min-h-screen max-w-lg place-content-center gap-5 px-4 py-10">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">StyleBridge AI</h1>
        <p className="text-slate2">Sign in to see recommendations picked for you. You only ever see your own profile.</p>
      </div>
      {healthError && <Message tone="error" title="Can't reach the server">Start the backend on port 8000, then reload.</Message>}
      {health && !health.demo_mode && <Message title="Sign-in isn't configured">Connect your authentication provider to the backend's /api/login route.</Message>}
      {health?.demo_mode && (
        <>
          <form onSubmit={(e) => { e.preventDefault(); if (id.trim()) signIn(id); }} className="space-y-2">
            <label className="block text-sm font-medium" htmlFor="sid">Shopper ID</label>
            <div className="flex gap-2">
              <input id="sid" className="field" placeholder="e.g. U0002" value={id} onChange={(e) => setId(e.target.value)} autoComplete="off" />
              <button type="submit" disabled={busy || !id.trim()} className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50">Sign in</button>
            </div>
            {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
          </form>
          <section aria-labelledby="demo-h" className="rounded-xl border border-line bg-white p-4">
            <h2 id="demo-h" className="text-base font-semibold">Demo accounts</h2>
            <p className="text-xs text-slate2">Demo mode only: the data is synthetic and sign-in has no password. Turn it off with SB_DEMO_MODE=0.</p>
            <ul className="mt-3 space-y-1.5">
              {(accounts || []).map((a) => (
                <li key={a.user_id}>
                  <button type="button" disabled={busy} onClick={() => signIn(a.user_id)}
                    className="flex w-full items-center justify-between rounded-md border border-line px-3 py-2 text-left text-sm hover:bg-paper">
                    <span className="font-medium">{a.user_id}</span><span className="text-slate2">{a.label}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
