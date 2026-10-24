import React from "react";
import { api, session, useApi } from "../api.js";
import { Chip } from "./ui.jsx";
import { DOMAIN_LABELS, pretty } from "../colors.js";

/** The signed-in shopper's OWN profile. Nothing about any other shopper is ever fetched or shown. */
export default function ProfilePanel({ refreshKey, onSwitched, onSignOut }) {
  const { data: me, error } = useApi(() => api.me(), [refreshKey]);
  const { data: health } = useApi(() => api.health(), []);
  const { data: accounts } = useApi(() => (health?.demo_mode ? api.demoAccounts() : Promise.resolve([])), [health?.demo_mode]);

  async function switchTo(id) {
    if (!id || id === me?.user_id) return;
    const { token, user_id } = await api.login(id);
    session.set({ token, userId: user_id });
    onSwitched(user_id);
  }

  if (error) return <p className="text-sm text-red-700">Couldn't load your profile.</p>;
  if (!me) return <p className="text-sm text-slate2">Loading your profile…</p>;
  const { interest: it } = me;
  return (
    <section aria-labelledby="profile-h" className="space-y-3 rounded-xl border border-line bg-white p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 id="profile-h" className="text-base font-semibold">Your profile</h2>
          <p className="text-sm text-slate2">{me.user_id} · {me.gender}{me.is_guest ? ", new guest" : `, ${me.age_group}, ${me.city}`}</p>
        </div>
        <button type="button" className="btn-ghost shrink-0 whitespace-nowrap" onClick={onSignOut}>Sign out</button>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {Object.entries(me.purchases).map(([d, n]) => (
          <div key={d} className={`rounded-lg p-2.5 ${d === "clothing" ? "bg-saffron-soft" : "bg-thread-soft"}`}>
            <p className={`font-display text-xl font-medium ${d === "clothing" ? "text-saffron-deep" : "text-thread-deep"}`}>{n}</p>
            <p className="text-xs text-slate2">{DOMAIN_LABELS[d].toLowerCase()} bought</p>
          </div>
        ))}
      </div>

      <div>
        <h3 className="text-sm font-semibold">Your interest</h3>
        {it.n_purchases === 0 ? (
          <p className="mt-1 text-xs text-slate2">No purchases yet, so you see the most popular items. Click "Bought it" on a card and your picks will start to follow your taste.</p>
        ) : (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {it.styles.map((s) => <Chip key={s} tone="thread">{s}</Chip>)}
            {it.colour_families.map((s) => <Chip key={s} tone="saffron">{s}</Chip>)}
          </div>
        )}
      </div>

      <dl className="space-y-1 text-sm">
        <div className="flex justify-between gap-2"><dt className="text-slate2">Preferred styles</dt><dd className="text-right">{me.preferred_styles.map(pretty).join(", ")}</dd></div>
        <div className="flex justify-between gap-2"><dt className="text-slate2">Favourite colours</dt><dd className="text-right">{me.favourite_colours.join(", ")}</dd></div>
        <div className="flex justify-between gap-2"><dt className="text-slate2">Sizes</dt><dd>{me.sizes.top} / {me.sizes.bottom} / UK {me.sizes.shoe}</dd></div>
        <div className="flex justify-between gap-2"><dt className="text-slate2">Outfit budget</dt><dd>{"₹" + me.budget_per_outfit_inr.toLocaleString("en-IN")}</dd></div>
      </dl>

      {health?.demo_mode && accounts?.length > 0 && (
        <label className="block border-t border-line pt-3 text-xs text-slate2">
          <span className="mb-1 block">Demo mode: switch to another demo account</span>
          <select className="field text-sm" value={me.user_id} onChange={(e) => switchTo(e.target.value)}>
            {accounts.map((a) => <option key={a.user_id} value={a.user_id}>{a.user_id} · {a.label}</option>)}
            {!accounts.some((a) => a.user_id === me.user_id) && <option value={me.user_id}>{me.user_id} (you)</option>}
          </select>
        </label>
      )}
    </section>
  );
}
