import React, { useEffect, useState } from "react";
import { api, session, useApi } from "../api.js";
import { COLOUR_HEX, pretty } from "../colors.js";
import { fb, fbMessage, fbSignOut, firebaseEnabled } from "../firebase.js";
import { Message, Segmented } from "./ui.jsx";

function Toggle({ on, onClick, children, swatch }) {
  return (
    <button type="button" aria-pressed={on} onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${on ? "border-thread bg-thread text-white" : "border-line bg-white text-slate2 hover:text-ink"}`}>
      {swatch && <span className="h-3 w-3 rounded-full border border-black/10" style={{ background: swatch }} />}
      {children}
    </button>
  );
}

const middle = (list) => list[Math.floor(list.length / 2)] ?? "";

/** mode: "signin" | "signup" | "complete" (signed in with Firebase / Google, but no taste profile yet). */
export default function SignIn({ onSignedIn }) {
  const { data: health, error: healthError } = useApi(() => api.health(), []);
  const { data: opts } = useApi(() => api.authOptions(), []);
  const { data: accounts } = useApi(() => (health?.demo_mode ? api.demoAccounts() : Promise.resolve([])), [health?.demo_mode]);
  const useFb = firebaseEnabled && Boolean(health?.firebase);          // Firebase when both sides are configured, else the built-in accounts
  const noSignIn = health && !useFb && !health.local_auth;
  const [mode, setMode] = useState("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [demoId, setDemoId] = useState("");
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const [f, setF] = useState({ gender: "women", age_group: "25-34", styles: [], colours: [], budget: 2000, top: "", bottom: "", shoe: "" });

  const done = ({ token, user_id }) => { session.set({ token, userId: user_id }); onSignedIn(user_id); };
  const sizes = opts?.sizes[f.gender];
  const size = (k) => f[k] || middle(sizes?.[k] ?? []);
  const toggle = (key, v, max) => setF((x) => ({ ...x, [key]: x[key].includes(v) ? x[key].filter((y) => y !== v) : x[key].length < max ? [...x[key], v] : x[key] }));
  const profile = () => ({ gender: f.gender, age_group: f.age_group, preferred_styles: f.styles, favourite_colours: f.colours,
    budget_per_outfit_inr: Number(f.budget), top_size: size("top"), bottom_size: size("bottom"), shoe_size: size("shoe") });

  /** fn resolves to { token, user_id }, or to null when it moved the form to another step. */
  async function run(fn) {
    setBusy(true); setError(null); setNotice(null);
    try { const r = await fn(); if (r) done(r); } catch (e) { setError(fbMessage(e)); } finally { setBusy(false); }
  }

  /** Trade a Firebase ID token for an app session. 404 = no shopper profile yet, so ask for one. */
  async function enter(idToken) {
    try { return await api.firebaseLogin(idToken); } catch (e) {
      if (e.status !== 404) throw e;
      setMode("complete");
      setNotice("Almost done: tell us your taste so we can personalise your picks.");
      return null;
    }
  }

  // Firebase remembers who is signed in on this browser: if the app session expired, sign back in silently.
  useEffect(() => {
    if (!useFb) return;
    let live = true;
    fb.restore().then(async (tok) => {
      if (!tok || !live) return;
      setBusy(true);
      try { const r = await enter(tok); if (r && live) done(r); } catch (e) { if (live) setError(fbMessage(e)); } finally { if (live) setBusy(false); }
    });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [useFb]);

  function submit(e) {
    e.preventDefault();
    if (mode !== "signin" && (f.styles.length < 1 || f.colours.length < 1)) return setError("Pick at least one style and one favourite colour.");
    if (useFb) {
      return run(async () => {
        if (mode === "signin") return enter(await fb.signIn(email, password));
        if (mode === "signup") return api.firebaseRegister({ id_token: await fb.signUp(email, password), ...profile() });
        return api.firebaseRegister({ id_token: await fb.idToken(), ...profile() });
      });
    }
    if (mode === "signin") return run(() => api.signIn(email, password));
    run(() => api.register({ email, password, ...profile() }));
  }

  const forgot = () => run(async () => {
    if (!email.trim()) throw new Error("Enter your email first.");
    await fb.reset(email.trim());
    setNotice("If that email has an account, a reset link is on its way.");
    return null;
  });
  const differentAccount = async () => { await fbSignOut(); setMode("signin"); setNotice(null); setError(null); };

  const profileFields = opts && (
    <>
      <div className="grid grid-cols-2 gap-3">
        <div className="text-sm"><span className="mb-1 block font-medium">Shop for</span>
          <Segmented label="Gender" value={f.gender} onChange={(g) => setF({ ...f, gender: g, top: "", bottom: "", shoe: "" })} options={[{ value: "women", label: "Women" }, { value: "men", label: "Men" }]} /></div>
        <label className="block text-sm"><span className="mb-1 block font-medium">Age group</span>
          <select className="field" value={f.age_group} onChange={(e) => setF({ ...f, age_group: e.target.value })}>{opts.age_groups.map((a) => <option key={a}>{a}</option>)}</select></label>
      </div>
      <div><p className="mb-1 text-sm font-medium">Styles you like <span className="font-normal text-slate2">(1 to 5)</span></p>
        <div className="flex flex-wrap gap-1.5">{opts.styles.map((s) => <Toggle key={s} on={f.styles.includes(s)} onClick={() => toggle("styles", s, 5)}>{pretty(s)}</Toggle>)}</div></div>
      <div><p className="mb-1 text-sm font-medium">Favourite colours <span className="font-normal text-slate2">(1 to 6)</span></p>
        <div className="flex flex-wrap gap-1.5">{opts.colours.map((c) => <Toggle key={c} on={f.colours.includes(c)} swatch={COLOUR_HEX[c]} onClick={() => toggle("colours", c, 6)}>{c}</Toggle>)}</div></div>
      <div className="grid grid-cols-3 gap-3">
        {[["top", "Top size"], ["bottom", "Bottom size"], ["shoe", "Shoe size (UK)"]].map(([k, label]) => (
          <label key={k} className="block text-sm"><span className="mb-1 block font-medium">{label}</span>
            <select className="field" value={size(k)} onChange={(e) => setF({ ...f, [k]: e.target.value })}>{sizes[k].map((v) => <option key={v}>{v}</option>)}</select></label>
        ))}
      </div>
      <label className="block text-sm"><span className="mb-1 block font-medium">Budget per outfit (₹)</span>
        <input className="field" type="number" min="300" max="50000" step="100" value={f.budget} onChange={(e) => setF({ ...f, budget: e.target.value })} /></label>
    </>
  );

  const canRegister = health?.registration_open !== false;
  const label = busy ? (mode === "signup" ? "Creating your account…" : mode === "complete" ? "Saving…" : "Signing in…")
    : mode === "signup" ? "Create account" : mode === "complete" ? "Finish" : "Sign in";
  return (
    <div className="mx-auto grid min-h-screen max-w-xl content-center gap-5 px-4 py-10">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">StyleBridge AI</h1>
        <p className="text-slate2">Clothing and accessories picked from what shoppers like you bought. You only ever see your own profile.</p>
      </div>
      {healthError && <Message tone="error" title="Can't reach the server">Start the backend on port 8000, then reload.</Message>}
      {noSignIn && <Message title="Sign-in isn't configured">Set the Firebase keys in frontend/.env and SB_FIREBASE_PROJECT_ID on the backend.</Message>}
      {firebaseEnabled && health && !health.firebase && <Message title="Firebase is only half set up">The frontend has Firebase keys, but the backend has no SB_FIREBASE_PROJECT_ID.</Message>}

      {!noSignIn && mode !== "complete" && (
        <Segmented label="Account" value={mode} onChange={(m) => { setMode(m); setError(null); setNotice(null); }}
          options={[{ value: "signin", label: "Sign in" }, ...(canRegister ? [{ value: "signup", label: "Create account" }] : [])]} />
      )}

      {!noSignIn && (
        <form onSubmit={submit} className="space-y-4 rounded-xl border border-line bg-white p-4">
          {mode !== "complete" && (
            <>
              <label className="block text-sm"><span className="mb-1 block font-medium">Email</span>
                <input className="field" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
              <label className="block text-sm"><span className="mb-1 block font-medium">Password</span>
                <input className="field" type={showPw ? "text" : "password"} required minLength={mode === "signup" ? opts?.min_password_length ?? 8 : undefined}
                  autoComplete={mode === "signup" ? "new-password" : "current-password"} value={password} onChange={(e) => setPassword(e.target.value)} />
                <span className="mt-1 flex items-center justify-between text-xs text-slate2">
                  <span>{mode === "signup" ? `At least ${opts?.min_password_length ?? 8} characters.` : useFb ? <button type="button" className="underline" onClick={forgot} disabled={busy}>Forgot password?</button> : ""}</span>
                  <label className="flex items-center gap-1"><input type="checkbox" checked={showPw} onChange={(e) => setShowPw(e.target.checked)} /> Show</label>
                </span></label>
            </>
          )}
          {mode !== "signin" && profileFields}

          {notice && <p role="status" className="rounded-md bg-thread-soft px-3 py-2 text-sm text-thread-deep">{notice}</p>}
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
          <button type="submit" disabled={busy || (mode !== "signin" && !opts)} className="w-full rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{label}</button>

          {useFb && mode !== "complete" && (
            <>
              <p className="text-center text-xs text-slate2">or</p>
              <button type="button" disabled={busy} onClick={() => run(async () => enter(await fb.google()))}
                className="w-full rounded-md border border-line bg-white px-4 py-2 text-sm font-medium text-ink hover:bg-paper disabled:opacity-50">Continue with Google</button>
            </>
          )}
          {mode === "complete" && <button type="button" className="w-full text-center text-sm text-slate2 underline" onClick={differentAccount}>Use a different account</button>}
        </form>
      )}

      {health?.demo_mode && mode !== "complete" && (
        <section aria-labelledby="demo-h" className="rounded-xl border border-line bg-white p-4">
          <h2 id="demo-h" className="text-base font-semibold">Try a demo shopper</h2>
          <p className="text-xs text-slate2">Demo mode only: synthetic shoppers, no password. Turn it off with SB_DEMO_MODE=0.</p>
          <ul className="mt-3 space-y-1.5">
            {(accounts || []).map((a) => (
              <li key={a.user_id}>
                <button type="button" disabled={busy} onClick={() => run(() => api.login(a.user_id))}
                  className="flex w-full items-center justify-between rounded-md border border-line px-3 py-2 text-left text-sm hover:bg-paper">
                  <span className="font-medium">{a.user_id}</span><span className="text-slate2">{a.label}</span>
                </button>
              </li>
            ))}
          </ul>
          <form onSubmit={(e) => { e.preventDefault(); if (demoId.trim()) run(() => api.login(demoId.trim())); }} className="mt-3 flex gap-2">
            <input className="field" aria-label="Demo shopper ID" placeholder="Shopper ID, e.g. U0002" value={demoId} onChange={(e) => setDemoId(e.target.value)} autoComplete="off" />
            <button type="submit" disabled={busy || !demoId.trim()} className="btn-ghost shrink-0">Go</button>
          </form>
        </section>
      )}
    </div>
  );
}