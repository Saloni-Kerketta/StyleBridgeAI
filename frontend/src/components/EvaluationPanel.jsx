import React, { useState } from "react";
import { api, useApi } from "../api.js";
import { DOMAIN_LABELS, MODEL_LABELS } from "../colors.js";
import { Segmented, Message } from "./ui.jsx";

const METRICS = [{ value: "ndcg", label: "NDCG" }, { value: "recall", label: "Recall" }, { value: "hit", label: "Hit rate" }];
const DOMAINS = Object.entries(DOMAIN_LABELS).map(([value, label]) => ({ value, label }));
const barTone = (m) => (m === "similar_shoppers" ? "bg-thread" : "bg-slate2/50");

export default function EvaluationPanel() {
  const { data, error } = useApi(() => api.evaluation(), []);
  const [domain, setDomain] = useState("clothing");
  const [scenario, setScenario] = useState("new_to_domain");
  const [metric, setMetric] = useState("ndcg");
  const [k, setK] = useState(10);

  if (error?.status === 404) return <Message title="No evaluation results yet">Run <code className="rounded bg-paper px-1">python -m scripts.evaluate</code> in the backend folder, then reload.</Message>;
  if (error) return <Message tone="error" title="Couldn't load evaluation">{error.message}</Message>;
  if (!data) return <p className="text-sm text-slate2">Loading evaluation…</p>;

  const d = data.domains[domain];
  const sc = d.scenarios[scenario];
  const key = `${metric}@${k}`;
  const rows = Object.entries(sc.results).map(([m, r]) => ({ m, v: r[key], r })).sort((a, b) => b.v - a.v);
  const max = Math.max(...rows.map((r) => r.v), 1e-9);
  const scenarios = {
    warm: { label: "Returning shoppers", text: `Trained on earlier activity, tested on later ${d.label.toLowerCase()} activity of the same shoppers.` },
    new_to_domain: { label: `New to ${d.label.toLowerCase()}`, text: `Shoppers whose ${d.label.toLowerCase()} history was hidden. They are recommended items using only what they bought in ${d.other_label.toLowerCase()}.` },
  };

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">How well do the recommenders rank held-out items?</h2>
        <p className="max-w-2xl text-sm text-slate2">{scenarios[scenario].text} {sc.n_users} shoppers, {sc.avg_relevant} relevant items each on average.</p>
      </div>
      <div className="flex flex-wrap gap-3">
        <Segmented label="Domain" value={domain} onChange={setDomain} options={DOMAINS} />
        <Segmented label="Scenario" value={scenario} onChange={setScenario} options={Object.entries(scenarios).map(([value, s]) => ({ value, label: s.label }))} />
        <Segmented label="Metric" value={metric} onChange={setMetric} options={METRICS} />
        <Segmented label="Top K" value={k} onChange={setK} options={data.k_values.map((v) => ({ value: v, label: `Top ${v}` }))} />
      </div>

      <ol className="space-y-2" aria-label="Models ranked by selected metric">
        {rows.map(({ m, v }) => (
          <li key={m} className="grid grid-cols-[170px_1fr_56px] items-center gap-3 text-sm">
            <span className="font-medium">{MODEL_LABELS[m] || m}</span>
            <div className="h-5 rounded bg-white ring-1 ring-line"><div className={`h-full rounded ${barTone(m)}`} style={{ width: `${(v / max) * 100}%` }} /></div>
            <span className="text-right tabular-nums">{v.toFixed(3)}</span>
          </li>
        ))}
      </ol>
      <p className="text-xs text-slate2">Teal is "Shoppers like you" (learns from purchases only); grey are the baselines.</p>

      <div className="overflow-x-auto rounded-lg border border-line bg-white">
        <table className="w-full min-w-[520px] text-sm">
          <caption className="sr-only">All metrics at top {k}</caption>
          <thead><tr className="border-b border-line text-left text-slate2">
            <th className="px-3 py-2 font-medium">Model</th><th className="px-3 py-2 font-medium">NDCG</th>
            <th className="px-3 py-2 font-medium">Recall</th><th className="px-3 py-2 font-medium">Hit rate</th><th className="px-3 py-2 font-medium">Catalogue coverage</th>
          </tr></thead>
          <tbody>{rows.map(({ m, r }) => (
            <tr key={m} className="border-b border-line last:border-0">
              <td className="px-3 py-2 font-medium">{MODEL_LABELS[m] || m}</td>
              <td className="px-3 py-2 tabular-nums">{r[`ndcg@${k}`].toFixed(3)}</td><td className="px-3 py-2 tabular-nums">{r[`recall@${k}`].toFixed(3)}</td>
              <td className="px-3 py-2 tabular-nums">{r[`hit@${k}`].toFixed(3)}</td><td className="px-3 py-2 tabular-nums">{(r["coverage@10"] * 100).toFixed(0)}%</td>
            </tr>))}</tbody>
        </table>
      </div>
      <ul className="list-disc space-y-1 pl-5 text-sm text-slate2">{data.notes.map((n) => <li key={n}>{n}</li>)}</ul>
      <p className="text-xs text-slate2">Generated {data.generated_at}. Signal: {data.signal}; neighbours: {data.neighbours}.</p>
    </div>
  );
}
