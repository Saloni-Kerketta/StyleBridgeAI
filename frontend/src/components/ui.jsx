import React from "react";

export function Chip({ children, tone = "plain" }) {
  const tones = {
    plain: "bg-paper text-slate2 border-line",
    thread: "bg-thread-soft text-thread-deep border-thread/20",
    saffron: "bg-saffron-soft text-saffron-deep border-saffron/30",
  };
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>;
}

export function Segmented({ value, onChange, options, label }) {
  return (
    <div role="group" aria-label={label} className="inline-flex rounded-md border border-line bg-white p-0.5">
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={value === o.value} onClick={() => onChange(o.value)}
          className={`rounded px-3 py-1 text-sm font-medium transition-colors ${value === o.value ? "bg-ink text-white" : "text-slate2 hover:text-ink"}`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Message({ title, children, tone = "plain" }) {
  const tones = { plain: "border-line bg-white", error: "border-red-200 bg-red-50 text-red-900" };
  return (
    <div role={tone === "error" ? "alert" : undefined} className={`rounded-lg border p-6 ${tones[tone]}`}>
      <p className="font-display text-lg font-medium">{title}</p>
      {children && <div className="mt-1 text-sm text-slate2">{children}</div>}
    </div>
  );
}
