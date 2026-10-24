import React, { useState } from "react";
import { api, useApi } from "../api.js";
import { MODEL_LABELS } from "../colors.js";
import ProductCard from "./ProductCard.jsx";
import { Message } from "./ui.jsx";

const BANNER = {
  neighbours: "bg-thread-soft text-thread-deep",
  no_history: "bg-saffron-soft text-saffron-deep",
  no_neighbours: "bg-saffron-soft text-saffron-deep",
  popular_fallback: "bg-saffron-soft text-saffron-deep",
};

export default function Recommendations({ domain, model, filters, onPurchase }) {
  const [reload, setReload] = useState(0);
  const [marks, setMarks] = useState({});
  const [hidden, setHidden] = useState(new Set());
  const [note, setNote] = useState("");
  const [error, setError] = useState(null);

  const { data, error: loadError, loading } = useApi(() => api.recs({ domain, model, k: 9, ...filters }), [domain, model, filters, reload]);

  async function act(item, type) {
    setError(null);
    try {
      await api.feedback({ product_id: item.product_id, event_type: type });
      if (type === "dismiss") setHidden((h) => new Set(h).add(item.product_id));
      else setMarks((m) => ({ ...m, [item.product_id]: type }));
      if (type === "purchase") {                       // a purchase changes your interest, so refresh both lists and your profile
        setNote(`Purchase recorded: ${item.name}. Your interest and both lists have been updated.`);
        setHidden(new Set());
        setReload((n) => n + 1);
        onPurchase?.();
      }
    } catch (e) { if (e.status !== 401) setError(e.message); }
  }

  if (loadError) return <Message tone="error" title="Couldn't load recommendations">{loadError.message}</Message>;
  if (!data) return <p className="text-sm text-slate2">Loading recommendations…</p>;

  return (
    <div className="space-y-8">
      {note && <p role="status" className="rounded-md bg-thread-soft px-3 py-2 text-sm text-thread-deep">{note}</p>}
      {error && <Message tone="error" title="Couldn't save that">{error}</Message>}
      <p className="text-sm text-slate2">Recommender: <span className="font-medium text-ink">{MODEL_LABELS[model] || model}</span></p>

      {data.sections.map((sec) => {
        const items = sec.items.filter((it) => !hidden.has(it.product_id));
        const [top, ...rest] = items;
        return (
          <section key={sec.domain} aria-labelledby={`sec-${sec.domain}`} className={loading ? "opacity-60" : ""}>
            <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
              <h2 id={`sec-${sec.domain}`} className="text-xl font-semibold">{sec.label}</h2>
              <span className="text-sm text-slate2">{sec.candidates} in-stock items considered</span>
            </div>
            {sec.basis_text && <p className={`mb-3 rounded-md px-3 py-2 text-sm ${BANNER[sec.basis] || "bg-paper text-slate2"}`}>{sec.basis_text}</p>}
            {sec.message && <Message title="Nothing to show">{sec.message}</Message>}
            {top && <ProductCard featured badge="Top pick" item={top} status={marks[top.product_id]} onAction={act} />}
            {rest.length > 0 && (
              <>
                <h3 className="mb-2 mt-5 text-sm font-semibold text-slate2">More picks, in order</h3>
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                  {rest.map((it) => <ProductCard key={it.product_id} item={it} status={marks[it.product_id]} onAction={act} />)}
                </div>
              </>
            )}
          </section>
        );
      })}
    </div>
  );
}
