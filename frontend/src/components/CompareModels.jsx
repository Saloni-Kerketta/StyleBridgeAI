import React, { useState } from "react";
import { api, useApi } from "../api.js";
import { DOMAIN_LABELS, MODEL_LABELS } from "../colors.js";
import ProductCard from "./ProductCard.jsx";
import { Message, Segmented } from "./ui.jsx";

const SHOWN = ["similar_shoppers", "content", "als", "popularity"];
const DOMAINS = Object.entries(DOMAIN_LABELS).map(([value, label]) => ({ value, label }));
const RANKS = 5;

/** Rows are ranks, columns are recommenders: the top pick of every model sits in the first row, scroll down for the rest. */
export default function CompareModels({ filters }) {
  const [domain, setDomain] = useState("accessories");
  const { data, error } = useApi(() => Promise.all(SHOWN.map((m) => api.recs({ domain, model: m, k: RANKS, ...filters }))), [domain, filters]);
  if (error) return <Message tone="error" title="Couldn't compare models">{error.message}</Message>;
  if (!data) return <p className="text-sm text-slate2">Loading comparison…</p>;

  const cols = data.map((d) => d.sections[0]);
  const top = new Set(cols[0].items.map((i) => i.product_id));
  return (
    <div className="min-w-[860px] space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-sm text-slate2">
          Your own picks under each recommender. The first row is each model's top pick; scroll down for the rest. "Shoppers like you" learns from similar shoppers' purchases; "Most popular" ignores you; collaborative filtering needs history in the domain.
        </p>
        <Segmented label="Domain" value={domain} onChange={setDomain} options={DOMAINS} />
      </div>

      <div className="sticky top-0 z-20 grid grid-cols-4 gap-4 bg-paper pb-2 pt-1">
        {cols.map((sec, idx) => {
          const overlap = sec.items.filter((i) => top.has(i.product_id)).length;
          return (
            <header key={SHOWN[idx]} className="border-b border-line pb-2">
              <h3 className="text-base font-semibold">{MODEL_LABELS[SHOWN[idx]]}</h3>
              <p className="text-xs text-slate2">
                {sec.basis === "popular_fallback" ? "No signal, showing popular" : idx === 0 ? "Reference column" : `${overlap} of ${RANKS} also in "Shoppers like you"`}
              </p>
            </header>
          );
        })}
      </div>

      {Array.from({ length: RANKS }, (_, r) => (
        <div key={r} className="grid grid-cols-4 gap-4">
          {cols.map((sec, c) => sec.items[r]
            ? <ProductCard key={SHOWN[c]} item={sec.items[r]} compact badge={r === 0 ? "Top pick" : `#${r + 1}`} />
            : <div key={SHOWN[c]} />)}
        </div>
      ))}
    </div>
  );
}
