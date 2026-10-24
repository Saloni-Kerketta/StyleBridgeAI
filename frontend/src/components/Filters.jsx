import React from "react";
import { api, useApi } from "../api.js";
import { CATEGORIES_BY_DOMAIN, DOMAIN_LABELS, FAMILIES, MODEL_LABELS, OCCASIONS, pretty, inr } from "../colors.js";

function Select({ label, value, onChange, options, any = "Any", labels = {} }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium">{label}</span>
      <select className="field" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{any}</option>
        {options.map((o) => <option key={o} value={o}>{labels[o] || pretty(o)}</option>)}
      </select>
    </label>
  );
}

export default function Filters({ domain, onDomain, model, onModel, filters, onFilters, showModel = true }) {
  const { data: models } = useApi(() => api.models(), []);
  const set = (k) => (v) => onFilters({ ...filters, [k]: v });
  const categories = domain === "all" ? [...CATEGORIES_BY_DOMAIN.clothing, ...CATEGORIES_BY_DOMAIN.accessories] : CATEGORIES_BY_DOMAIN[domain];
  function changeDomain(d) {
    onDomain(d);
    const allowed = d === "all" ? true : CATEGORIES_BY_DOMAIN[d].includes(filters.category);
    if (!allowed) onFilters({ ...filters, category: "" });
  }
  return (
    <section aria-labelledby="filters-h" className="space-y-4">
      <h2 id="filters-h" className="text-base font-semibold">Search</h2>
      <label className="block text-sm">
        <span className="mb-1 block font-medium">Show</span>
        <select className="field" value={domain} onChange={(e) => changeDomain(e.target.value)}>
          <option value="all">Clothing and footwear & accessories</option>
          <option value="clothing">{DOMAIN_LABELS.clothing} only</option>
          <option value="accessories">{DOMAIN_LABELS.accessories} only</option>
        </select>
      </label>
      {showModel && (
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Recommender</span>
          <select className="field" value={model} onChange={(e) => onModel(e.target.value)}>
            {(models || Object.keys(MODEL_LABELS).map((name) => ({ name }))).map((m) => (
              <option key={m.name} value={m.name}>{MODEL_LABELS[m.name] || m.name}</option>
            ))}
          </select>
          <span className="mt-1 block text-xs text-slate2">{models?.find((m) => m.name === model)?.description}</span>
        </label>
      )}
      <Select label="Category" value={filters.category} onChange={set("category")} options={categories} any="All categories" />
      <Select label="Occasion" value={filters.occasion} onChange={set("occasion")} options={OCCASIONS} any="Any occasion" />
      <Select label="Colour family" value={filters.colour_family} onChange={set("colour_family")} options={FAMILIES} any="Any colour" />
      <label className="block text-sm">
        <span className="mb-1 flex justify-between font-medium">
          <span>Max price per item</span>
          <span className="text-slate2">{filters.max_price ? inr(filters.max_price) : "No limit"}</span>
        </span>
        <input type="range" min="300" max="3000" step="100" className="w-full accent-thread"
          value={filters.max_price || 3000} onChange={(e) => set("max_price")(+e.target.value >= 3000 ? "" : +e.target.value)} />
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" className="accent-thread" checked={filters.size_filter} onChange={(e) => set("size_filter")(e.target.checked)} />
        Only show items in my sizes
      </label>
    </section>
  );
}
