import React, { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { Chip } from "./ui.jsx";

const SUGGESTIONS = [
  "Until when can I return my last order?",
  "How many days do I have to return footwear?",
  "How long does a refund take?",
  "Can I exchange for a different size?",
];

export default function AskAssistant() {
  const [msgs, setMsgs] = useState([{ role: "bot", text: "Ask about returns, refunds, delivery, a product (e.g. P0001), or your own orders." }]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  async function send(text) {
    const question = (text ?? q).trim();
    if (question.length < 2 || busy) return;
    setQ("");
    setMsgs((m) => [...m, { role: "user", text: question }]);
    setBusy(true);
    try {
      const r = await api.ask(question);
      setMsgs((m) => [...m, { role: "bot", text: r.answer, sources: r.sources }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "bot", text: e.message, error: true }]);
    } finally { setBusy(false); }
  }

  return (
    <section aria-label="Ask a question" className="flex flex-col gap-3">
      <div className="space-y-3 rounded-lg border border-line bg-white p-4">
        {msgs.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : ""}>
            <div className={`inline-block max-w-[85%] whitespace-pre-line rounded-lg px-3 py-2 text-left text-sm ${
              m.role === "user" ? "bg-ink text-white" : m.error ? "bg-red-50 text-red-900" : "bg-paper text-ink"}`}>
              {m.text}
            </div>
            {m.sources?.length > 0 && (
              <div className="mt-1 flex flex-wrap gap-1">
                {m.sources.map((s) => <Chip key={`${s.type}-${s.id}`} tone={s.type === "your_purchase" ? "thread" : "plain"}>{s.type === "policy" ? "Policy" : s.type === "your_purchase" ? "Your order" : "Product"}: {s.title}</Chip>)}
              </div>
            )}
          </div>
        ))}
        {busy && <p className="text-sm text-slate2">Thinking…</p>}
        <div ref={end} />
      </div>
      <div className="flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => <button key={s} type="button" onClick={() => send(s)} className="rounded-full border border-line bg-white px-3 py-1 text-xs text-slate2 hover:text-ink">{s}</button>)}
      </div>
      <div className="flex gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} maxLength={500}
          aria-label="Your question" placeholder="e.g. When is the return date for my last order?"
          className="min-w-0 flex-1 rounded-md border border-line bg-white px-3 py-2 text-sm" />
        <button type="button" onClick={() => send()} disabled={busy} className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50">Ask</button>
      </div>
    </section>
  );
}