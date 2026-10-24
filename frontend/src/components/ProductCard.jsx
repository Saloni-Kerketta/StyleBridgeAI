import React from "react";
import { pretty, inr } from "../colors.js";
import ProductImage from "./ProductImage.jsx";
import { Chip } from "./ui.jsx";

const Icon = {
  like: <path d="M12 21s-7-4.6-9.3-9A5.3 5.3 0 0 1 12 6.4 5.3 5.3 0 0 1 21.3 12c-2.3 4.4-9.3 9-9.3 9Z" />,
  save: <path d="M6 3h12v18l-6-4-6 4V3Z" />,
  buy: <path d="M6 7h12l-1 13H7L6 7Zm3 0a3 3 0 0 1 6 0" />,
  dismiss: <path d="M6 6l12 12M18 6 6 18" />,
};

function Action({ kind, label, active, onClick }) {
  return (
    <button type="button" onClick={onClick} aria-label={label} title={label} aria-pressed={active}
      className={`grid h-9 w-9 place-items-center rounded-md border transition-colors ${active ? "border-thread bg-thread text-white" : "border-line bg-white text-slate2 hover:text-ink"}`}>
      <svg viewBox="0 0 24 24" className="h-4 w-4" fill={active && kind !== "dismiss" ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{Icon[kind]}</svg>
    </button>
  );
}

export default function ProductCard({ item, status, onAction, compact = false, featured = false, badge }) {
  return (
    <article className={`relative flex overflow-hidden rounded-xl border bg-white ${featured ? "flex-col border-thread/40 md:flex-row" : "flex-col border-line"}`}>
      {badge && <span className="absolute left-2 top-2 z-10 rounded-full bg-ink px-2.5 py-0.5 text-xs font-semibold text-white">{badge}</span>}
      <div className={featured ? "md:w-72 md:shrink-0" : ""}>
        <ProductImage item={item} size={featured ? "featured" : compact ? "compact" : "default"} />
      </div>
      <div className={`flex flex-1 flex-col gap-2 p-3 ${featured ? "md:p-5" : ""}`}>
        <div>
          <h3 className={`font-semibold leading-snug ${featured ? "text-base md:text-lg" : "text-sm"}`}>{item.name}</h3>
          <p className="text-xs text-slate2">{pretty(item.category)} · {item.style} · rating {item.rating}</p>
        </div>
        <p className="flex items-baseline gap-2">
          <span className="font-display text-lg font-medium">{inr(item.price_inr)}</span>
          {item.discount_pct > 0 && <><span className="text-xs text-slate2 line-through">{inr(item.mrp_inr)}</span><span className="text-xs font-semibold text-thread-deep">{item.discount_pct}% off</span></>}
        </p>
        {!compact && <p className="text-xs text-slate2">Sizes: {item.sizes_available.join(", ")}</p>}

        <div>
          <div className="flex justify-between text-xs text-slate2"><span>Match</span><span>{item.match_pct}%</span></div>
          <div className="mt-1 h-1.5 rounded-full bg-paper" role="img" aria-label={`Match ${item.match_pct} percent`}>
            <div className="h-full rounded-full bg-thread" style={{ width: `${item.match_pct}%` }} />
          </div>
        </div>

        <ul className="flex flex-wrap gap-1">
          {item.reasons.map((r) => (
            <li key={r}><Chip tone={r.startsWith("Bought by") ? "thread" : "plain"}>{r}</Chip></li>
          ))}
        </ul>

        {onAction && (
          <div className="mt-auto flex gap-2 pt-1">
            <Action kind="like" label="Like" active={status === "like"} onClick={() => onAction(item, "like")} />
            <Action kind="save" label="Save" active={status === "save"} onClick={() => onAction(item, "save")} />
            <Action kind="buy" label="Bought it" active={status === "purchase"} onClick={() => onAction(item, "purchase")} />
            <Action kind="dismiss" label="Not for me" onClick={() => onAction(item, "dismiss")} />
          </div>
        )}
      </div>
    </article>
  );
}
